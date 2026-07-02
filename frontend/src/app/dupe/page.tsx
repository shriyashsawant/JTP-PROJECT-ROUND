"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Loader2, IndianRupee } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import PerfumeCard from "@/components/PerfumeCard";
import { searchByDupe } from "@/lib/api";
import type { Perfume } from "@/lib/api";

export default function DupePage() {
  const [perfumeName, setPerfumeName] = useState("");
  const [budget, setBudget] = useState("");
  const [results, setResults] = useState<Perfume[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const budgetNum = parseInt(budget, 10);
    if (!perfumeName.trim() || !budgetNum || budgetNum < 100) return;
    setLoading(true);
    setError("");
    setResults(null);
    try {
      const data = await searchByDupe({
        query: perfumeName.trim(),
        budget: budgetNum,
        limit: 6,
      });
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-3xl font-bold tracking-tight">Dupe Engine</h1>
        <p className="mt-2 text-muted-foreground">
          Love a luxury scent? Enter the name and your budget — we&apos;ll find the
          best affordable alternatives.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">Perfume name</label>
            <Input
              placeholder="e.g. Bleu de Chanel, Creed Aventus..."
              value={perfumeName}
              onChange={(e) => setPerfumeName(e.target.value)}
              className="min-h-[48px] text-base"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Max budget (₹)
            </label>
            <Input
              type="number"
              placeholder="2500"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              min={100}
              className="min-h-[48px] text-base"
            />
          </div>

          <Button
            type="submit"
            disabled={
              loading ||
              !perfumeName.trim() ||
              !budget ||
              parseInt(budget, 10) < 100
            }
            size="lg"
            className="w-full gap-2"
          >
            {loading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Search size={18} />
            )}
            {loading ? "Searching..." : "Find Dupes"}
          </Button>
        </form>

        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
            <button onClick={handleSubmit} className="ml-2 font-medium underline">
              Retry
            </button>
          </div>
        )}
      </div>

      <AnimatePresence>
        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-12 text-center text-muted-foreground"
          >
            <Loader2 size={24} className="mx-auto animate-spin" />
            <p className="mt-3">Searching for the best dupes...</p>
          </motion.div>
        )}

        {results && results.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-12 text-center"
          >
            <p className="text-muted-foreground">
              No dupes found within ₹{parseInt(budget, 10).toLocaleString("en-IN")}.
              Try increasing your budget or a different perfume.
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
