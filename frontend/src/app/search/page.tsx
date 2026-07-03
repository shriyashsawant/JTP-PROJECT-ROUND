"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import PerfumeCard from "@/components/PerfumeCard";
import { searchByContext, ClarificationNeededError } from "@/lib/api";
import type { Perfume } from "@/lib/api";

const scenarios = [
  { value: "daily", label: "Daily Wear" },
  { value: "gym", label: "Gym / Sports" },
  { value: "party", label: "Party / Night Out" },
  { value: "date", label: "Date Night" },
  { value: "office", label: "Office / Work" },
  { value: "wedding", label: "Wedding / Festival" },
  { value: "summer", label: "Summer" },
  { value: "winter", label: "Winter" },
  { value: "monsoon", label: "Monsoon / Rainy" },
  { value: "spring", label: "Spring" },
  { value: "autumn", label: "Autumn / Fall" },
  { value: "evening", label: "Evening" },
];

const scentFamilies = [
  { value: "citrus", label: "Fresh / Citrus" },
  { value: "woody", label: "Woody / Earthy" },
  { value: "gourmand", label: "Sweet / Gourmand" },
  { value: "fresh_aquatic", label: "Aquatic / Ocean" },
  { value: "spicy", label: "Spicy / Warm" },
  { value: "floral", label: "Floral" },
];

const skinTypes = [
  { value: "", label: "Normal" },
  { value: "dry", label: "Dry" },
  { value: "oily", label: "Oily" },
];

const genders = [
  { value: "", label: "Prefer not to say" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "unisex", label: "Unisex" },
];

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [budget, setBudget] = useState([5000]);
  const [scenario, setScenario] = useState<string[]>([]);
  const [noteFamilies, setNoteFamilies] = useState<string[]>([]);
  const [skinType, setSkinType] = useState("");
  const [gender, setGender] = useState("");
  const [age, setAge] = useState("");
  const [results, setResults] = useState<Perfume[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [needsBudget, setNeedsBudget] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setNeedsBudget(false);
    setResults(null);
    try {
      const data = await searchByContext({
        query: query.trim(),
        budget: budget[0],
        scenario: scenario.length ? scenario : undefined,
        skin_type: skinType || undefined,
        gender: gender || undefined,
        age: age ? Number(age) : undefined,
        note_families: noteFamilies.length ? noteFamilies : undefined,
      });
      setResults(data);
    } catch (err) {
      if (err instanceof ClarificationNeededError) {
        setError(err.message);
        if (err.field === "budget") setNeedsBudget(true);
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-3xl font-bold tracking-tight">Vibe Check</h1>
        <p className="mt-2 text-muted-foreground">
          Describe your perfect scent in plain English. We&apos;ll handle the rest.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div className="space-y-4">
            <label className="text-sm font-medium">What are you looking for?</label>
            <Input
              placeholder="e.g. 22 male, office commute, gym in the evening, long lasting"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-[56px] text-base"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-3">
              <label className="text-sm font-medium">Gender (optional)</label>
              <div className="flex flex-wrap gap-2">
                {genders.map((g) => (
                  <button
                    key={g.value}
                    type="button"
                    onClick={() => setGender(g.value)}
                    className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
                      gender === g.value
                        ? "border-foreground bg-foreground text-background"
                        : "border-border hover:border-foreground/50"
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <label className="text-sm font-medium">Age (optional)</label>
              <Input
                type="number"
                min={13}
                max={100}
                placeholder="e.g. 22"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-medium">Occasion (optional, select any)</label>
            <div className="flex flex-wrap gap-2">
              {scenarios.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setScenario((prev) => toggle(prev, s.value))}
                  className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
                    scenario.includes(s.value)
                      ? "border-foreground bg-foreground text-background"
                      : "border-border hover:border-foreground/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-medium">Scent Preference (optional, select any)</label>
            <div className="flex flex-wrap gap-2">
              {scentFamilies.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => setNoteFamilies((prev) => toggle(prev, f.value))}
                  className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
                    noteFamilies.includes(f.value)
                      ? "border-foreground bg-foreground text-background"
                      : "border-border hover:border-foreground/50"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-medium">Skin Type (optional)</label>
            <div className="flex gap-2">
              {skinTypes.map((st) => (
                <button
                  key={st.value}
                  type="button"
                  onClick={() => setSkinType(st.value)}
                  className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
                    skinType === st.value
                      ? "border-foreground bg-foreground text-background"
                      : "border-border hover:border-foreground/50"
                  }`}
                >
                  {st.label}
                </button>
              ))}
            </div>
          </div>

          <div
            className={`space-y-3 rounded-lg p-3 transition-colors ${
              needsBudget ? "ring-2 ring-amber-400 bg-amber-50" : ""
            }`}
          >
            <label className="text-sm font-medium">
              Budget: ₹{budget[0].toLocaleString("en-IN")}
            </label>
            <Slider
              value={budget}
              onValueChange={(v) => {
                setBudget(v as number[]);
                setNeedsBudget(false);
              }}
              max={15000}
              step={500}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>₹0</span>
              <span>₹15,000+</span>
            </div>
          </div>

          <Button type="submit" disabled={loading || !query.trim()} size="lg" className="w-full gap-2">
            {loading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Sparkles size={18} />
            )}
            {loading ? "Analyzing..." : "Find My Scent"}
          </Button>
        </form>

        {error && needsBudget && (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {error} Adjust the budget slider above and try again.
          </div>
        )}
        {error && !needsBudget && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
            <button onClick={handleSubmit} className="ml-2 font-medium underline">
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      <AnimatePresence>
        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="space-y-3 rounded-xl border p-5">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-2 w-full" />
                <div className="flex gap-2">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
              </div>
            ))}
          </motion.div>
        )}

        {results && results.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-12 text-center"
          >
            <p className="text-muted-foreground">
              No perfumes found within your budget. Try increasing your budget or
              broadening your preferences.
            </p>
          </motion.div>
        )}

        {results && results.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-12 space-y-8"
          >
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {results.map((p, i) => (
                <div key={p.id}>
                  <PerfumeCard perfume={p} index={i} />
                  {p.explanation && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.3 + i * 0.08 }}
                      className="mt-2 px-1 text-xs leading-relaxed text-muted-foreground"
                    >
                      {p.explanation}
                    </motion.p>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
