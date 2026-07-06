"use client";

import { useEffect, useRef, useState, type SyntheticEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, AlertCircle, Plus, History, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import PerfumeCard from "@/components/PerfumeCard";
import { searchByContext, ClarificationNeededError } from "@/lib/api";
import type { Perfume } from "@/lib/api";

// localStorage (not sessionStorage) - a saved chat should survive a closed
// tab/browser, not just back-navigation within one. Stores every
// conversation as its own entry, not just the most recent one, so starting
// a new chat never discards an old one - it just stops being the active
// thread.
const CONVERSATIONS_KEY = "auramatch_conversations";
const ACTIVE_ID_KEY = "auramatch_active_conversation_id";
const MAX_SAVED_CONVERSATIONS = 30;
// Bumped from an earlier 6 - with ~40k perfumes in the catalog, a handful of
// cards per turn undersold how much is actually available. "Show More"
// below paginates further using the same query.
const RESULTS_LIMIT = 10;
const SHOW_MORE_INCREMENT = 10;
// Mirrors the `le=60` ceiling in backend/app/models/schemas.py - the button
// simply stops being offered once a turn has already reached it.
const BACKEND_MAX_LIMIT = 60;
// Soft quality floor, not a hard 80%+ filter: results are already shown
// best-first, so this only stops "Show More" once the pool has run dry of
// genuinely good matches - measured live, a 30-deep pool for a realistic
// query tailed off to ~15% by the end, not worth surfacing just to pad a count.
const MIN_SHOW_MORE_SCORE = 50;
// Last N user messages are sent as the query, not the whole conversation -
// keeps recent refinements ("cheaper please") in context without letting a
// superseded early preference (e.g. "woody" before the user later corrects
// to "fresh aquatic instead") permanently pollute every later turn's note-
// family signal. Tunable - not a hard architectural commitment.
const CONTEXT_WINDOW = 3;

const QUICK_REPLIES = {
  gender: [
    { label: "Male", value: "Male" },
    { label: "Female", value: "Female" },
    { label: "Unisex", value: "Unisex" },
  ],
  occasion: [
    { label: "Gym", value: "For the gym" },
    { label: "Office", value: "For the office" },
    { label: "Date Night", value: "For date night" },
    { label: "Daily Wear", value: "Daily casual wear" },
    { label: "Party", value: "For party night out" },
  ],
  scent: [
    { label: "Fresh / Citrus", value: "Citrus fresh" },
    { label: "Woody / Earthy", value: "Woody notes" },
    { label: "Sweet / Gourmand", value: "Sweet gourmand" },
    { label: "Floral", value: "Floral notes" },
    { label: "Spicy", value: "Spicy notes" },
  ],
  budget: [
    { label: "Under ₹2,000", value: "Under 2000" },
    { label: "Under ₹3,500", value: "Under 3500" },
    { label: "Under ₹5,000", value: "Under 5000" },
    { label: "No limit", value: "No budget limit" },
  ],
};

const CHEAPER_RE = /\b(cheap(er)?|less expensive|lower budget|reduce.*budget)\b/i;
const HAS_DIGIT_RE = /\d/;

// Deterministic, client-side "does this message have enough to search well"
// check - deliberately not a real NLU system, just enough signal to decide
// whether to ask a follow-up first or go straight to the (already good)
// backend intent detection. Mirrors the actual highest-weight scoring
// dimensions in decision_engine.py (SCENARIO_WEIGHT=0.28 is the single
// largest weight, which is why occasion is asked about first) rather than
// an arbitrary word list.
const OCCASION_RE = /\b(gym|office|work|date|party|wedding|daily|casual|summer|winter|monsoon|spring|autumn|fall|evening|night|formal|festival|commute|travel|college|school)\b/i;
const SCENT_RE = /\b(woody|floral|citrus|fresh|sweet|spicy|oud|musk|vanilla|aquatic|fruity|gourmand|aromatic|earthy|smoky|leather|powdery)\b/i;
const BUDGET_RE = /(\d|budget|cheap|expensive|affordable|under|below|within|₹|rs\.?\s*\d|no limit|unlimited)/i;
const DUPE_RE = /\b(alternative|dupe|cheaper than|similar to|instead of)\b/i;

// The backend only ever reads age from an explicit `age` request field
// (routes_search.py: `age=req.age`) - there's no server-side detection of
// age from free text the way gender/budget/scenario/negation all are. Since
// this chat sends everything as free text, "22, need a gym scent..." would
// otherwise silently lose the age entirely (it'd just sit inertly inside
// the embedding text, never reaching age_fit's actual scoring). Deliberately
// conservative - only "22 years old"/"22yo"/"22 y/o" explicitly, or a bare
// 1-2 digit number at the very start of the message (a common informal
// self-intro pattern, "22, love hiking..." style) - not any bare number
// anywhere, which would be far too easy to confuse with something else.
const AGE_RE = /\b(\d{1,2})\s*(?:years?\s*old|yo\b|y\/o)\b|^(\d{1,2})\b(?=[\s,])/i;

function extractAge(text: string): number | undefined {
  const match = AGE_RE.exec(text.trim());
  if (!match) return undefined;
  const age = Number(match[1] ?? match[2]);
  return age >= 13 && age <= 100 ? age : undefined;
}

interface ExtractedPreferences {
  gender?: string;
  occasion?: string;
  scent?: string;
  budget?: string;
}

function extractPreferences(messages: ChatMessage[]): ExtractedPreferences {
  // Find the index of the last message that was a restart / no-results prompt
  const lastResetIndex = [...messages].reverse().findIndex(
    (m) => m.role === "assistant" && m.isClarification && m.content.includes("couldn't find any")
  );

  // If found, slice the messages to only include ones after the reset
  const activeMessages = lastResetIndex !== -1
    ? messages.slice(messages.length - 1 - lastResetIndex)
    : messages;

  const userTexts = activeMessages
    .filter((m) => m.role === "user")
    .map((m) => m.content)
    .join(" ");

  const prefs: ExtractedPreferences = {};

  // Extract Gender
  if (/\b(men|man|male|masculine|boys?|him)\b/i.test(userTexts)) {
    prefs.gender = "male";
  } else if (/\b(women|woman|female|feminine|girls?|her)\b/i.test(userTexts)) {
    prefs.gender = "female";
  } else if (/\b(unisex|shared|both)\b/i.test(userTexts)) {
    prefs.gender = "unisex";
  }

  // Extract Occasion
  const occasionMatch = OCCASION_RE.exec(userTexts);
  if (occasionMatch) {
    prefs.occasion = occasionMatch[1].toLowerCase();
  }

  // Extract Scent family
  const scentMatch = SCENT_RE.exec(userTexts);
  if (scentMatch) {
    prefs.scent = scentMatch[1].toLowerCase();
  }

  // Extract Budget
  const budgetMatch = BUDGET_RE.exec(userTexts);
  if (budgetMatch) {
    prefs.budget = budgetMatch[0];
  }

  return prefs;
}

function buildClarifyingQuestion(messages: ChatMessage[]): { content: string; type: "gender" | "occasion" | "scent" | "budget" } | null {
  const userTexts = messages.filter((m) => m.role === "user").map((m) => m.content).join(" ");
  if (DUPE_RE.test(userTexts)) return null;

  const prefs = extractPreferences(messages);

  if (!prefs.gender) {
    return {
      content: "First, could you tell me if this scent is for a male, female, or unisex preference?",
      type: "gender",
    };
  }
  if (!prefs.occasion) {
    return {
      content: "Got it. What occasion or season is this fragrance for (e.g. gym, office, date night, summer)?",
      type: "occasion",
    };
  }
  if (!prefs.scent) {
    return {
      content: "Understood. What kind of scent profile do you prefer (e.g. fresh/citrus, woody/earthy, sweet/gourmand, floral, spicy)?",
      type: "scent",
    };
  }
  if (!prefs.budget) {
    return {
      content: "Finally, do you have a target budget in INR (e.g. under ₹2,000, under ₹5,000, or no limit)?",
      type: "budget",
    };
  }

  return null;
}

const SUGGESTIONS = [
  "fresh scent for the gym under ₹2,000",
  "long-lasting date night fragrance",
  "cheaper alternative to Bleu de Chanel",
  "office-friendly, not too strong",
];

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  perfumes?: Perfume[];
  isError?: boolean;
  isClarification?: boolean;
  questionType?: "gender" | "occasion" | "scent" | "budget";
  // Snapshotted at the moment this turn's results were fetched, so "Show
  // More" can re-run the exact same search with a larger limit later -
  // frozen per-message rather than read from the live conversation state,
  // since the conversation (and its sliding CONTEXT_WINDOW) may have moved
  // on by the time the button is clicked.
  searchParams?: { query: string; budget?: number; dealBreaker?: boolean; age?: number };
  currentLimit?: number;
  loadingMore?: boolean;
}

interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
}

function deriveTitle(messages: ChatMessage[]): string {
  const firstUserMsg = messages.find((m) => m.role === "user")?.content.trim();
  if (!firstUserMsg) return "New Chat";
  return firstUserMsg.length > 42 ? `${firstUserMsg.slice(0, 42)}...` : firstUserMsg;
}

function formatRelativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return diffDay === 1 ? "yesterday" : `${diffDay}d ago`;
}

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveConversations(list: Conversation[]) {
  try {
    // Cap the saved list rather than let it grow forever - oldest (by
    // updatedAt) drop off first, matching how every real chat product's
    // history behaves.
    const trimmed = [...list].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_SAVED_CONVERSATIONS);
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(trimmed));
  } catch {
    // Storage full or unavailable - persistence is a nice-to-have, not critical.
  }
}

function buildSummaryLine(results: Perfume[]): string {
  if (results.length === 0) {
    return "No matches found for that - try loosening any budget or rephrasing what you're looking for.";
  }
  const top = results[0];
  const count = results.length;
  const price = top.price_inr != null ? ` (₹${top.price_inr.toLocaleString("en-IN")})` : "";
  return `Found ${count} match${count === 1 ? "" : "es"} - top pick is ${top.brand} ${top.perfume}${price}.`;
}

function canShowMore(message: ChatMessage): boolean {
  if (!message.perfumes || message.perfumes.length === 0 || !message.searchParams) return false;
  const currentLimit = message.currentLimit ?? RESULTS_LIMIT;
  if (currentLimit >= BACKEND_MAX_LIMIT) return false;
  // Fewer results came back than were asked for - the pool for this query
  // is already exhausted, asking for more would just repeat the same set.
  if (message.perfumes.length < currentLimit) return false;
  const lastScore = message.perfumes[message.perfumes.length - 1]?.match_score;
  if (lastScore != null && lastScore < MIN_SHOW_MORE_SCORE) return false;
  return true;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm bg-secondary px-4 py-3">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-2 w-2 rounded-full bg-muted-foreground/50"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </div>
  );
}

function MessageBubble({ message, onShowMore }: { message: ChatMessage; onShowMore: (id: string) => void }) {
  if (message.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex justify-end"
      >
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground">
          {message.content}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div
        className={`flex max-w-[85%] items-start gap-2 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm ${
          message.isError
            ? "bg-destructive/10 text-destructive"
            : "bg-secondary text-secondary-foreground"
        }`}
      >
        {message.isError && <AlertCircle size={15} className="mt-0.5 shrink-0" />}
        <span>{message.content}</span>
      </div>

      {message.perfumes && message.perfumes.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {message.perfumes.map((p, i) => (
            <PerfumeCard key={p.id} perfume={p} index={i} />
          ))}
        </div>
      )}

      {canShowMore(message) && (
        <div className="flex justify-center pt-1">
          <button
            type="button"
            onClick={() => onShowMore(message.id)}
            disabled={message.loadingMore}
            className="rounded-full border border-border px-5 py-2 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground disabled:opacity-60"
          >
            {message.loadingMore ? "Loading more..." : "Show More"}
          </button>
        </div>
      )}
    </motion.div>
  );
}

function EmptyState({ onSuggestion }: { onSuggestion: (text: string) => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-1 flex-col items-center justify-center py-16 text-center"
    >
      <div className="hero-glow" />
      <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-xs font-medium tracking-wide text-primary">
        <Sparkles size={13} />
        Ask AuraMatch
      </span>
      <h1 className="font-heading mt-6 text-3xl font-semibold tracking-tight sm:text-4xl">
        What are you <span className="text-gradient-gold">looking for?</span>
      </h1>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
        Describe a vibe, an occasion, or name a perfume you want a cheaper alternative to -
        in plain English. One conversation handles both.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSuggestion(s)}
            className="rounded-full border border-border px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
          >
            {s}
          </button>
        ))}
      </div>
    </motion.div>
  );
}

export default function SearchPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string>("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [restored, setRestored] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  // A saved chat persists (localStorage, not sessionStorage - survives a
  // closed tab/browser) as one entry in a list of conversations, not a
  // single blob - so "New Chat" can start fresh without ever discarding an
  // older conversation. A `?prefill=` link (the "Find Dupes for this" flow)
  // always starts a brand-new conversation rather than continuing whatever
  // was last active - a distinct new intent shouldn't get mixed into an
  // unrelated earlier thread.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    const list = loadConversations();
    setConversations(list);

    const prefill = typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("prefill")
      : null;

    if (prefill) {
      const freshId = crypto.randomUUID();
      setConversationId(freshId);
      setMessages([]);
      setRestored(true);
      void sendMessage(prefill);
      return;
    }

    const activeId = typeof window !== "undefined" ? localStorage.getItem(ACTIVE_ID_KEY) : null;
    const active = list.find((c) => c.id === activeId) ?? list[0];
    if (active) {
      setConversationId(active.id);
      setMessages(active.messages);
    } else {
      setConversationId(crypto.randomUUID());
    }
    setRestored(true);
    /* eslint-enable react-hooks/set-state-in-effect */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Upsert the active conversation into the saved list on every change,
  // instead of persisting one flat blob - this is what makes "New Chat"
  // safe (switching conversationId just starts writing to a different
  // entry). Reads/writes localStorage directly rather than deriving from
  // the `conversations` React state (and never calls setConversations here) -
  // that state is only ever refreshed from event handlers (opening the
  // history panel, starting/switching/deleting a chat), not synchronously
  // inside this effect, to avoid the cascading-render risk of setState
  // calls in a bare effect body.
  useEffect(() => {
    if (!restored || messages.length === 0 || !conversationId) return;
    const list = loadConversations();
    const idx = list.findIndex((c) => c.id === conversationId);
    const entry: Conversation = { id: conversationId, title: deriveTitle(messages), messages, updatedAt: Date.now() };
    if (idx >= 0) list[idx] = entry;
    else list.push(entry);
    saveConversations(list);
    try {
      localStorage.setItem(ACTIVE_ID_KEY, conversationId);
    } catch {
      // Storage full or unavailable - persistence is a nice-to-have, not critical.
    }
  }, [restored, messages, conversationId]);

  function startNewChat() {
    setConversationId(crypto.randomUUID());
    setMessages([]);
    setInput("");
    setHistoryOpen(false);
  }

  function openConversation(id: string) {
    const target = conversations.find((c) => c.id === id);
    if (!target) return;
    setConversationId(id);
    setMessages(target.messages);
    setHistoryOpen(false);
  }

  function deleteConversation(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    const next = conversations.filter((c) => c.id !== id);
    setConversations(next);
    saveConversations(next);
    if (id === conversationId) {
      startNewChat();
    }
  }

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: trimmed };
    const priorMessages = messages;
    const nextMessages = [...priorMessages, userMsg];
    setMessages(nextMessages);
    setInput("");

    const clarification = buildClarifyingQuestion(nextMessages);
    if (clarification) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: clarification.content,
          isClarification: true,
          questionType: clarification.type,
        },
      ]);
      return;
    }

    setLoading(true);

    const allUserTexts = nextMessages.filter((m) => m.role === "user").map((m) => m.content);
    const combinedQuery = allUserTexts.slice(-CONTEXT_WINDOW).join(". ");

    // Age is a stable fact, not a shifting preference like scent/occasion -
    // it doesn't need to "age out" of the sliding window the way an earlier,
    // superseded scent preference should. Checked across the whole
    // conversation so far, not just the last few messages, so mentioning it
    // once near the start of a long conversation still applies later.
    const age = allUserTexts.map(extractAge).find((a) => a !== undefined);

    // Bare "cheaper"/"less expensive" with no number can't be picked up by
    // the backend's own detect_budget_from_text (it needs an actual figure) -
    // this is the one piece of real cross-turn logic: derive an explicit
    // ceiling from whatever was last shown, strictly below the cheapest of
    // those results, so "cheaper please" genuinely narrows instead of
    // silently re-running the same search.
    let explicitBudget: number | undefined;
    let dealBreaker: boolean | undefined;
    if (CHEAPER_RE.test(trimmed) && !HAS_DIGIT_RE.test(trimmed)) {
      // `m.perfumes` being an empty array is truthy in JS - checking `.length`
      // explicitly so a zero-result turn ("no matches found") doesn't get
      // treated as "the last results to compare against" and silently skip
      // over an earlier turn that actually had prices to derive a ceiling from.
      const lastResults = [...priorMessages].reverse().find((m) => m.perfumes && m.perfumes.length > 0)?.perfumes ?? [];
      const prices = lastResults.map((p) => p.price_inr).filter((p): p is number => p != null);
      if (prices.length > 0) {
        explicitBudget = Math.max(100, Math.min(...prices) - 1);
        dealBreaker = true;
      }
    }

    try {
      const results = await searchByContext({
        query: combinedQuery,
        limit: RESULTS_LIMIT,
        budget: explicitBudget,
        deal_breaker: dealBreaker,
        age,
      });
      if (results.length === 0) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "I couldn't find any fragrances matching that description. Let's restart with your basic preferences. What gender preference should we filter by?",
            isClarification: true,
            questionType: "gender",
          },
        ]);
        return;
      }
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: buildSummaryLine(results),
          perfumes: results,
          searchParams: { query: combinedQuery, budget: explicitBudget, dealBreaker, age },
          currentLimit: RESULTS_LIMIT,
        },
      ]);
    } catch (err) {
      // A raw `fetch()` network failure (server unreachable, connection
      // reset mid-request) surfaces as the literal browser string "Failed
      // to fetch"/"NetworkError..." - technically accurate but not a
      // helpful chat message, so it gets a clearer one instead.
      const isNetworkFailure = err instanceof TypeError && /fetch|network/i.test(err.message);
      const content = isNetworkFailure
        ? "Couldn't reach the server just now - check your connection and try again."
        : err instanceof ClarificationNeededError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.";
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", content, isError: true }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleShowMore(messageId: string) {
    const target = messages.find((m) => m.id === messageId);
    if (!target || !target.searchParams || target.loadingMore) return;

    const newLimit = Math.min(BACKEND_MAX_LIMIT, (target.currentLimit ?? RESULTS_LIMIT) + SHOW_MORE_INCREMENT);
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, loadingMore: true } : m)));

    try {
      const results = await searchByContext({
        query: target.searchParams.query,
        limit: newLimit,
        budget: target.searchParams.budget,
        deal_breaker: target.searchParams.dealBreaker,
        age: target.searchParams.age,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, perfumes: results, currentLimit: newLimit, loadingMore: false } : m
        )
      );
    } catch {
      // "Show More" failing shouldn't disrupt the already-shown results -
      // just stop the loading state and leave the existing cards as-is,
      // the button stays there to retry.
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, loadingMore: false } : m)));
    }
  }

  function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    void sendMessage(input);
  }

  // Gate on `restored`, not just `messages.length === 0` - otherwise a
  // `?prefill=` link (the "Find Dupes for this" flow) flashes the full
  // empty-state hero + suggestion chips for one frame before the restore
  // effect fires and auto-sends, snapping straight to the chat view. Nothing
  // renders in the message area during that brief pre-restore window instead -
  // a blank beat is a much less jarring default than showing the wrong state.
  const isEmpty = restored && messages.length === 0 && !loading;

  const lastMsg = messages[messages.length - 1];
  const activeQuestionType = lastMsg && lastMsg.role === "assistant" && lastMsg.isClarification && lastMsg.questionType;
  const replies = activeQuestionType ? QUICK_REPLIES[activeQuestionType] : [];

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-3xl flex-col px-6 py-8">
      <div className="relative mb-2 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            // Refresh from localStorage right as the panel opens, since the
            // persist effect writes storage directly rather than keeping
            // `conversations` state continuously synced (see that effect's
            // comment) - this is the one point that needs an up-to-date list.
            if (!historyOpen) setConversations(loadConversations());
            setHistoryOpen((v) => !v);
          }}
          className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
        >
          <History size={13} />
          Chats{conversations.length > 0 ? ` (${conversations.length})` : ""}
        </button>
        <button
          type="button"
          onClick={startNewChat}
          className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
        >
          <Plus size={13} />
          New Chat
        </button>

        <AnimatePresence>
          {historyOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="absolute right-0 top-10 z-20 max-h-96 w-80 overflow-y-auto rounded-xl border border-border bg-card p-2 shadow-xl"
            >
              <div className="mb-1 flex items-center justify-between px-2 py-1">
                <span className="text-xs font-semibold text-muted-foreground">Saved chats</span>
                <button type="button" onClick={() => setHistoryOpen(false)} className="text-muted-foreground hover:text-foreground">
                  <X size={14} />
                </button>
              </div>
              {conversations.length === 0 ? (
                <p className="px-2 py-3 text-xs text-muted-foreground">No saved chats yet.</p>
              ) : (
                [...conversations]
                  .sort((a, b) => b.updatedAt - a.updatedAt)
                  .map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => openConversation(c.id)}
                      className={`group flex w-full items-center justify-between gap-2 rounded-lg px-2 py-2 text-left text-xs transition-colors hover:bg-secondary ${
                        c.id === conversationId ? "bg-secondary" : ""
                      }`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-foreground">{c.title}</span>
                        <span className="text-[10px] text-muted-foreground">{formatRelativeTime(c.updatedAt)}</span>
                      </span>
                      <span
                        role="button"
                        tabIndex={0}
                        onClick={(e) => deleteConversation(c.id, e)}
                        className="shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                      >
                        <Trash2 size={13} />
                      </span>
                    </button>
                  ))
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {isEmpty ? (
        <EmptyState onSuggestion={(text) => void sendMessage(text)} />
      ) : (
        <div className="flex-1 space-y-6 pb-4">
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} onShowMore={handleShowMore} />
            ))}
          </AnimatePresence>
          {loading && <TypingIndicator />}
          <div ref={scrollAnchorRef} />
        </div>
      )}

      {replies.length > 0 && !loading && (
        <div className="mt-4 flex flex-wrap gap-2 justify-center">
          {replies.map((opt) => (
            <button
              key={opt.label}
              type="button"
              onClick={() => void sendMessage(opt.value)}
              className="rounded-full border border-primary/20 bg-primary/5 px-4 py-2 text-xs font-semibold text-primary hover:bg-primary hover:text-primary-foreground transition-colors cursor-pointer"
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="sticky bottom-4 z-10 mt-4 flex items-center gap-2 rounded-2xl border border-border bg-card/95 p-2 shadow-lg shadow-black/5 backdrop-blur"
      >
        <Input
          autoFocus
          placeholder="Describe a vibe, or name a perfume for a cheaper alternative..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="min-h-[44px] border-0 bg-transparent shadow-none focus-visible:ring-0"
        />
        <Button type="submit" size="icon" disabled={loading || !input.trim()} className="shrink-0">
          <Send size={16} />
        </Button>
      </form>
    </div>
  );
}
