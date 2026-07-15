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
  // Below: newer questions covering scoring dimensions that used to only be
  // caught opportunistically (or, for longevity/projection, silently
  // defaulted from occasion - see scenario_map.SCENARIO_PERFORMANCE_DEFAULTS)
  // rather than asked outright. Longevity (0.20 weight) and projection (0.10)
  // both include a "let AuraMatch decide" option that deliberately carries no
  // hour/projection phrase at all, so it falls straight through to that
  // occasion-based default instead of forcing a real preference out of
  // someone who doesn't have one.
  avoidNotes: [
    { label: "No vanilla", value: "No vanilla please" },
    { label: "No oud", value: "No oud please" },
    { label: "No musk", value: "No musk please" },
    { label: "None - no restrictions", value: "No specific notes to avoid" },
  ],
  longevity: [
    { label: "A few hours (4-6)", value: "4-6 hours" },
    { label: "Most of the day (6-8)", value: "6-8 hours" },
    { label: "All day (8+)", value: "8+ hours" },
    { label: "Let AuraMatch decide", value: "No specific longevity preference, use your best judgement for the occasion" },
  ],
  projection: [
    { label: "Subtle, close to skin", value: "close to skin" },
    { label: "Moderate", value: "moderate projection" },
    { label: "Strong, room-filling", value: "room-filling" },
    { label: "Let AuraMatch decide", value: "No specific projection preference, use your best judgement for the occasion" },
  ],
  age: [
    { label: "Under 25", value: "22 years old" },
    { label: "25-40", value: "30 years old" },
    { label: "Over 40", value: "45 years old" },
    { label: "Prefer not to say", value: "Prefer not to say my age" },
  ],
  skinType: [
    { label: "Dry", value: "I have dry skin" },
    { label: "Oily", value: "I have oily skin" },
    { label: "Normal", value: "I have normal skin" },
    { label: "Not sure / skip", value: "No specific skin type" },
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
// Regression: "party" is not a substring of "parties" (party -> parties
// drops the "y" and adds "ies", it isn't a plain "+s" plural like most of
// the other words here), so a message that only ever said "parties" (e.g.
// "I sweat a lot during parties...") matched nothing and the occasion
// question got asked anyway despite already being answered. `part(?:y|ies)`
// covers both forms; a trailing `s?` on the whole group covers the ordinary
// plurals (dates, weddings, festivals, ...) for the rest of the list.
const OCCASION_RE = /\b(gym|office|work|date|part(?:y|ies)|wedding|daily|casual|summer|winter|monsoon|spring|autumn|fall|evening|night|formal|festival|commute|travel|college|school)s?\b/i;
const SCENT_RE = /\b(woody|floral|citrus|fresh|sweet|spicy|oud|musk|vanilla|aquatic|fruity|gourmand|aromatic|earthy|smoky|leather|powdery)\b/i;
// Regression: a bare `\d` alternative here used to be "safe enough" when
// budget was always the 4th (and last free-text-numeric) question asked.
// Once longevity ("8+ hours") and age ("22 years old") got their own
// questions ahead of budget in the sequence, their digits alone satisfied
// this regex against the *whole* conversation, silently marking budget as
// already answered and skipping it entirely - caught by simulating the full
// 9-question sequence end to end, not by any single-message test. A bare
// number with no currency/budget wording is no longer enough on its own;
// buildClarifyingQuestion's wasAsked(...,"budget") fallback still correctly
// recognizes a plain "2000" typed in direct response to the budget question.
const BUDGET_RE = /(budget|cheap|expensive|affordable|under|below|within|₹|rs\.?\s*\d|no limit|unlimited)/i;
// Kept in sync with backend's DUPE_INTENT_PHRASES (scenario_map.py) plus its
// own bare "dupe(s)" word check (intent_detector.detect_dupe_intent) - this
// used to be a narrower ad hoc list ("alternative|dupe|cheaper than|similar
// to|instead of") that missed "clone of", "smells like", "cheaper version",
// and "budget version", so those phrasings fell through to the full 9-
// question clarifying flow instead of routing straight to a dupe search the
// way "cheaper alternative to X" already did.
const DUPE_RE = /\b(alternative|dupe(s)?|cheaper than|similar to|instead of|clone of|smells like|cheaper version|budget version)\b/i;

// Single source of truth for gender vocabulary - kept in sync with backend/
// app/services/scenario_map.py's MALE_HINTS/FEMALE_HINTS/UNISEX_HINTS.
// Previously duplicated across three separate regex literals here
// (GENDER_HINT_RE below + two more inline in extractPreferences), which had
// already drifted out of sync with each other and with the backend -
// GENDER_HINT_RE was missing "gentleman"/"gentlemen"/"lady"/"ladies" even
// though this same diff added them to the backend's MALE_HINTS/FEMALE_HINTS,
// so a message like "movie for a lady?" could be bounced as off-topic by
// looksOffTopic() while the backend would have recognized the same gender
// signal.
const MALE_WORDS = "men|man|male|masculine|boys?|him|gentlemen|gentleman";
const FEMALE_WORDS = "women|woman|female|feminine|girls?|her|ladies|lady";
const UNISEX_WORDS = "unisex|shared|both";
const MALE_GENDER_RE = new RegExp(`\\b(${MALE_WORDS})\\b`, "i");
const FEMALE_GENDER_RE = new RegExp(`\\b(${FEMALE_WORDS})\\b`, "i");
const UNISEX_GENDER_RE = new RegExp(`\\b(${UNISEX_WORDS})\\b`, "i");
const GENDER_HINT_RE = new RegExp(`\\b(${MALE_WORDS}|${FEMALE_WORDS}|${UNISEX_WORDS})\\b`, "i");

// Regression: "suggest me a book" matched none of the regexes above (no
// gender/occasion/scent/budget word), so buildClarifyingQuestion fell
// straight through to "ask about gender" as if it were just a vague
// fragrance request - answering a completely different kind of ask with a
// perfume-specific follow-up question. Deliberately narrow (a fixed list of
// common other-domain asks), not a broad "is this fragrance-related"
// classifier - a genuinely vague but real fragrance ask ("something nice
// for my mom") has no fragrance keyword either and must still go through
// the normal clarification flow, not get bounced as off-topic.
const OFF_TOPIC_RE = /\b(book|novel|movie|film|show|series|song|music|playlist|recipe|restaurant|joke|riddle|poem|haircut|hairstyle|car|phone|laptop|game|videogame)\b/i;
const FRAGRANCE_TOPIC_RE = /\b(perfume|fragrance|scent|cologne|eau de|edp|edt|ittar|attar|deodorant|deo|smell|aroma|aftershave)\b/i;

function looksOffTopic(messages: ChatMessage[]): boolean {
  const userTexts = messages.filter((m) => m.role === "user").map((m) => m.content).join(" ");
  if (!OFF_TOPIC_RE.test(userTexts)) return false;
  // Any real fragrance signal anywhere in the conversation - vocabulary,
  // occasion, scent family, gender, budget, or dupe-intent - means this is
  // still a genuine (if oddly worded) fragrance ask, not actually off-topic.
  return !(
    FRAGRANCE_TOPIC_RE.test(userTexts) ||
    OCCASION_RE.test(userTexts) ||
    SCENT_RE.test(userTexts) ||
    BUDGET_RE.test(userTexts) ||
    DUPE_RE.test(userTexts) ||
    GENDER_HINT_RE.test(userTexts)
  );
}

// The backend only ever reads age from an explicit `age` request field
// (routes_search.py: `age=req.age`) - there's no server-side detection of
// age from free text the way gender/budget/scenario/negation all are. Since
// this chat sends everything as free text, "22, need a gym scent..." would
// otherwise silently lose the age entirely (it'd just sit inertly inside
// the embedding text, never reaching age_fit's actual scoring). Deliberately
// conservative - only "22 years old"/"22 years"/"22yo"/"22 y/o" explicitly,
// or a bare 1-2 digit number at the very start of the message (a common
// informal self-intro pattern, "22, love hiking..." style) - not any bare
// number anywhere, which would be far too easy to confuse with something
// else.
// Regression: "22 years" (no trailing "old") - an extremely common way to
// state an age - matched neither branch, so a fully-stated age like "I'm 22
// years and I sweat a lot at parties..." still got the age question asked
// anyway. "old" is now optional after "years?"; extractAge's own 13-100
// bounds check already filters out the rare false-positive this widens
// (e.g. "worn this cologne for 10 years" - 10 falls outside that range and
// is discarded, same as it would be for any other stray number).
const AGE_RE = /\b(\d{1,2})\s*(?:years?(?:\s*old)?|yo\b|y\/o)\b|^(\d{1,2})\b(?=[\s,])/i;

// Regression: "i'm twenty two i do go to parties..." stated age in words,
// not digits - AGE_RE only ever matched digit forms ("22 years old", a bare
// "22" at message start), so this was silently missed and the age question
// got asked anyway despite the user having already answered it. Mirrors
// AGE_RE's own conservatism (a self-intro phrase or an explicit "years old"
// suffix), just for spelled-out numbers instead of digits.
const NUMBER_WORDS: Record<string, number> = {
  ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15,
  sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19,
  twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90,
};
const ONES_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
};
const NUMBER_WORD_ALT = Object.keys(NUMBER_WORDS).join("|");
const WORD_AGE_RE = new RegExp(
  `\\b(?:i'?m|i\\s+am)\\s+((?:${NUMBER_WORD_ALT})(?:[\\s-](?:one|two|three|four|five|six|seven|eight|nine))?)\\b` +
  `|\\b((?:${NUMBER_WORD_ALT})(?:[\\s-](?:one|two|three|four|five|six|seven|eight|nine))?)\\s+years?\\s*old\\b`,
  "i"
);

function wordsToAge(phrase: string): number | undefined {
  const parts = phrase.toLowerCase().trim().split(/[\s-]+/);
  const tens = NUMBER_WORDS[parts[0]];
  if (tens === undefined) return undefined;
  if (parts.length === 1) return tens;
  if (tens >= 20 && parts.length === 2 && ONES_WORDS[parts[1]] !== undefined) {
    return tens + ONES_WORDS[parts[1]];
  }
  return undefined;
}

function extractAge(text: string): number | undefined {
  const trimmed = text.trim();
  const match = AGE_RE.exec(trimmed);
  if (match) {
    const age = Number(match[1] ?? match[2]);
    if (age >= 13 && age <= 100) return age;
  }
  const wordMatch = WORD_AGE_RE.exec(trimmed);
  if (wordMatch) {
    const age = wordsToAge(wordMatch[1] ?? wordMatch[2]);
    if (age !== undefined && age >= 13 && age <= 100) return age;
  }
  return undefined;
}

// Mirrors (loosely - just enough to know "has this already been answered",
// the backend's own regexes in intent_detector.py/scenario_map.py do the
// real parsing at request time) LONGEVITY_HOUR_PATTERN/LONGEVITY_PHRASES and
// PROJECTION_HINTS - so a query that already naturally states "8+ hours" or
// "subtle, close to skin" skips the corresponding question instead of asking
// something the user already answered unprompted.
const LONGEVITY_HINT_RE = /\b\d{1,2}\s*\+?\s*(?:(?:-\s*|to\s+|or\s+)\d{1,2}\s*)?(?:hour|hr)s?\b|\b(long.?lasting|lasts?\s+(all|full)\s+day|all.?day)\b/i;
const PROJECTION_HINT_RE = /\b(subtle|close to skin|skin scent|light projection|moderate projection|strong projection|room.?filling|beast mode|sillage)\b/i;

// skin_type has no free-text detector on the backend at all (unlike gender/
// budget/scenario/longevity/projection) - it's only ever read from the
// explicit `skin_type` request field (app/services/decision_engine.py's
// SKIN_TYPE_PHRASES), so unlike everything else here, this needs to be
// extracted client-side and threaded through explicitly, not just left to
// flow into the free-text query.
const SKIN_TYPE_VALUE_RE = /\b(dry|oily|normal)\b\s*skin|\bskin\b\s*(?:is\s*)?(dry|oily|normal)\b/i;

// Mirrors backend's _NEGATION_TRIGGER_PATTERN (intent_detector.py) just
// closely enough to know "has the user already stated a note/ingredient to
// avoid" - not a real clause parser, the backend does that at request time.
const AVOID_NOTES_HINT_RE = /\b(?:no|not|without|avoid|hate|dislike)\b\s+\S/i;

function extractSkinType(messages: ChatMessage[]): string | undefined {
  const userTexts = messages.filter((m) => m.role === "user").map((m) => m.content).join(" ");
  const match = SKIN_TYPE_VALUE_RE.exec(userTexts);
  if (!match) return undefined;
  return (match[1] ?? match[2])?.toLowerCase();
}

interface ExtractedPreferences {
  gender?: string;
  occasion?: string;
  scent?: string;
  budget?: string;
}

// Shared "since the last restart" boundary - every consumer of message
// history that needs to reason about "the current attempt" (not stale
// pre-restart context) must go through this same slice. Previously
// duplicated inline in three places (extractPreferences, sendMessage, and -
// the actual bug this fixes - never applied at all in wasAsked/
// buildClarifyingQuestion's own userTexts/DUPE_RE check), which let those
// two silently see pre-restart messages: after a "couldn't find any" reset,
// wasAsked(messages, "gender") still found the OLD pre-reset clarification
// question anywhere in full history and returned true, permanently
// skipping re-collection of every one of the 9 answers on the next attempt.
function getActiveMessages(messages: ChatMessage[]): ChatMessage[] {
  const lastResetIndex = [...messages].reverse().findIndex(
    (m) => m.role === "assistant" && m.isClarification && m.content.includes("couldn't find any")
  );
  return lastResetIndex !== -1
    ? messages.slice(messages.length - 1 - lastResetIndex)
    : messages;
}

function extractPreferences(messages: ChatMessage[]): ExtractedPreferences {
  const activeMessages = getActiveMessages(messages);

  const userTexts = activeMessages
    .filter((m) => m.role === "user")
    .map((m) => m.content)
    .join(" ");

  const prefs: ExtractedPreferences = {};

  // Extract Gender
  if (MALE_GENDER_RE.test(userTexts)) {
    prefs.gender = "male";
  } else if (FEMALE_GENDER_RE.test(userTexts)) {
    prefs.gender = "female";
  } else if (UNISEX_GENDER_RE.test(userTexts)) {
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

type QuestionType = "gender" | "occasion" | "scent" | "avoidNotes" | "longevity" | "projection" | "budget" | "age" | "skinType";

// The 5 newer question types don't have the same reliable positive-content
// pattern gender/occasion/scent/budget do (a "let AuraMatch decide" or
// "prefer not to say" answer has no clean signal to regex-match), so
// "already asked once in this active segment" is the completion check for
// those instead of re-deriving it from message content every time - once
// asked, whatever the user replies (including a skip) counts as answered.
// Scoped via getActiveMessages, not the raw `messages` passed in - without
// this, a question asked before a "couldn't find any" restart still counted
// as "asked" on the next attempt and was silently never re-asked.
function wasAsked(messages: ChatMessage[], type: QuestionType): boolean {
  return getActiveMessages(messages).some((m) => m.role === "assistant" && m.isClarification && m.questionType === type);
}

function buildClarifyingQuestion(messages: ChatMessage[]): { content: string; type: QuestionType } | null {
  const activeMessages = getActiveMessages(messages);
  const userTexts = activeMessages.filter((m) => m.role === "user").map((m) => m.content).join(" ");
  if (DUPE_RE.test(userTexts)) return null;

  const prefs = extractPreferences(messages);

  // Ordered by scoring weight (see decision_engine.py / DECISION_ENGINE.md
  // §2.2), not just the original 4 - occasion (0.28) and note match still
  // come first, but longevity (0.20) and projection (0.10) now get their own
  // question too, ahead of budget/age/skin-type (0.05 or a soft nudge only).
  if (!prefs.gender && !wasAsked(messages, "gender")) {
    return {
      content: "First, could you tell me if this scent is for a male, female, or unisex preference?",
      type: "gender",
    };
  }
  if (!prefs.occasion && !wasAsked(messages, "occasion")) {
    return {
      content: "Got it. What occasion or season is this fragrance for (e.g. gym, office, date night, summer)?",
      type: "occasion",
    };
  }
  if (!prefs.scent && !wasAsked(messages, "scent")) {
    return {
      content: "Understood. What kind of scent profile do you prefer (e.g. fresh/citrus, woody/earthy, sweet/gourmand, floral, spicy)?",
      type: "scent",
    };
  }
  if (!AVOID_NOTES_HINT_RE.test(userTexts) && !wasAsked(messages, "avoidNotes")) {
    return {
      content: "Any notes or ingredients you'd like to avoid?",
      type: "avoidNotes",
    };
  }
  if (!LONGEVITY_HINT_RE.test(userTexts) && !wasAsked(messages, "longevity")) {
    return {
      content: "How long should it last on skin?",
      type: "longevity",
    };
  }
  if (!PROJECTION_HINT_RE.test(userTexts) && !wasAsked(messages, "projection")) {
    return {
      content: "How noticeable should it be to people around you?",
      type: "projection",
    };
  }
  if (!prefs.budget && !wasAsked(messages, "budget")) {
    return {
      content: "Do you have a target budget in INR (e.g. under ₹2,000, under ₹5,000, or no limit)?",
      type: "budget",
    };
  }
  const hasStatedAge = messages
    .filter((m) => m.role === "user")
    .some((m) => extractAge(m.content) !== undefined);
  if (!hasStatedAge && !wasAsked(messages, "age")) {
    return {
      content: "What's your age group? This helps fine-tune recommendations, but it's entirely optional.",
      type: "age",
    };
  }
  if (!extractSkinType(messages) && !wasAsked(messages, "skinType")) {
    return {
      content: "Last one - do you know your skin type? Scents wear differently on dry vs. oily skin.",
      type: "skinType",
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
  questionType?: QuestionType;
  // Snapshotted at the moment this turn's results were fetched, so "Show
  // More" can re-run the exact same search with a larger limit later -
  // frozen per-message rather than read from the live conversation state,
  // since the conversation (and its sliding CONTEXT_WINDOW) may have moved
  // on by the time the button is clicked.
  searchParams?: { query: string; budget?: number; dealBreaker?: boolean; age?: number; skinType?: string };
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

    if (looksOffTopic(nextMessages)) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "I'm AuraMatch, a fragrance recommendation assistant - I can help you find a perfume or a cheaper alternative to one, but I can't help with that. What kind of scent are you looking for?",
        },
      ]);
      return;
    }

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

    // Same "since the last restart" boundary extractPreferences/wasAsked use,
    // so the Q&A intake and the actual search agree on where the current
    // attempt begins.
    const activeMessages = getActiveMessages(nextMessages);
    const hasSearchedBeforeInSegment = activeMessages.some((m) => m.role === "assistant" && m.perfumes && m.perfumes.length > 0);

    // Regression: expanding the clarification flow from 4 to 9 questions
    // exposed a real bug here - a fixed CONTEXT_WINDOW=3 was fine when the
    // last 3 messages were occasion+scent+budget, but with 9 answers, the
    // first real search only ever saw the *last 3* (typically budget/age/
    // skin-type), silently dropping gender/occasion/scent/notes/longevity/
    // projection from the actual query even though the user had just
    // answered every one of them - directly observed live: a fully-answered
    // 9-question flow still scored every result in the 25-31% range, because
    // almost none of what was answered ever reached the backend. The 9
    // answers all belong to *one* still-being-built initial request, not a
    // sequence of independent turns, so the first search after intake uses
    // every answer given so far; only once real results have already been
    // shown does the smaller sliding window make sense again - that's
    // genuine turn-by-turn refinement ("cheaper please", "actually more
    // woody"), where letting an old superseded preference age out is exactly
    // the point (see CONTEXT_WINDOW's own comment).
    const combinedQuery = hasSearchedBeforeInSegment
      ? allUserTexts.slice(-CONTEXT_WINDOW).join(". ")
      : activeMessages.filter((m) => m.role === "user").map((m) => m.content).join(". ");

    // Age is a stable fact, not a shifting preference like scent/occasion -
    // it doesn't need to "age out" of the sliding window the way an earlier,
    // superseded scent preference should. Checked across the whole
    // conversation so far, not just the last few messages, so mentioning it
    // once near the start of a long conversation still applies later.
    const age = allUserTexts.map(extractAge).find((a) => a !== undefined);

    // skin_type has no free-text detector on the backend at all (see
    // extractSkinType's comment) - unlike everything else here, it has to be
    // pulled out and sent as its own explicit field or it's silently lost.
    const skinType = extractSkinType(nextMessages);

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
        skin_type: skinType,
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
          searchParams: { query: combinedQuery, budget: explicitBudget, dealBreaker, age, skinType },
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
        skin_type: target.searchParams.skinType,
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

      {!isEmpty && (
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          Tip: mention occasion, scent, and budget in one message for the best matches - e.g.{" "}
          <span className="italic">&quot;fresh citrus scent for the office, under ₹3,000&quot;</span>
        </p>
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
