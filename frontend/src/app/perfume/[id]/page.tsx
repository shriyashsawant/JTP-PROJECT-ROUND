"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { getPerfumeById } from "@/lib/api";
import type { PerfumeDetail } from "@/lib/api";

export default function PerfumeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [perfume, setPerfume] = useState<PerfumeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const perfumeId = parseInt(id, 10);

  useEffect(() => {
    if (!id || isNaN(perfumeId)) {
      setLoading(false);
      setError("Invalid perfume ID");
      return;
    }
    setLoading(true);
    setError("");
    getPerfumeById(perfumeId)
      .then(setPerfume)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <Skeleton className="mb-6 h-6 w-32" />
        <div className="space-y-4">
          <Skeleton className="h-8 w-60" />
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
        <div className="mt-8 space-y-3">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-full" />
        </div>
      </div>
    );
  }

  if (error || !perfume) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-24 text-center">
        <h2 className="text-2xl font-bold">Perfume not found</h2>
        <p className="mt-2 text-muted-foreground">
          {error || "This perfume doesn't exist in our collection."}
        </p>
        <div className="mt-6 flex justify-center gap-4">
          <Link href="/">
            <Button variant="outline" className="gap-2">
              <ArrowLeft size={16} /> Go Home
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mx-auto max-w-3xl px-6 py-12"
    >
      <Link
        href="/search"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft size={14} /> Back to results
      </Link>

      <div className="flex flex-col gap-8 sm:flex-row">
        {/* Image placeholder */}
        <div className="flex h-64 w-full items-center justify-center rounded-xl bg-secondary sm:w-48">
          <span className="text-4xl font-bold text-muted-foreground/30">
            {perfume.brand.charAt(0)}
            {perfume.perfume.charAt(0)}
          </span>
        </div>

        <div className="flex-1 space-y-4">
          <div>
            <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              {perfume.brand}
            </p>
            <h1 className="text-2xl font-bold">{perfume.perfume}</h1>
          </div>

          {perfume.price_inr != null && (
            <p className="text-2xl font-bold">
              ₹{perfume.price_inr.toLocaleString("en-IN")}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {perfume.type && (
              <span className="rounded-full border px-3 py-1 text-xs font-medium">
                {perfume.type}
              </span>
            )}
            {perfume.launch_year && perfume.launch_year !== "Unknown" && (
              <span className="rounded-full border px-3 py-1 text-xs font-medium">
                {perfume.launch_year}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Accords */}
      {perfume.main_accords.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Main Accords
          </h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {perfume.main_accords.map((a) => (
              <span
                key={a}
                className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground"
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Notes */}
      {perfume.notes.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Notes
          </h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {perfume.notes.map((n) => (
              <span
                key={n}
                className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground"
              >
                {n}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Longevity / Sillage */}
      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        <div>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Longevity</span>
            <span className="font-semibold">
              {perfume.longevity_score != null
                ? `${perfume.longevity_score}%`
                : "N/A"}
            </span>
          </div>
          <Progress
            value={perfume.longevity_score ?? 0}
            className="h-2"
          />
        </div>
        <div>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Sillage</span>
            <span className="font-semibold">
              {perfume.sillage_score != null
                ? `${perfume.sillage_score}%`
                : "N/A"}
            </span>
          </div>
          <Progress
            value={perfume.sillage_score ?? 0}
            className="h-2"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="mt-10">
        <Link href={`/dupe`}>
          <Button variant="outline" className="gap-2">
            <Search size={16} /> Find Dupes for this
          </Button>
        </Link>
      </div>
    </motion.div>
  );
}
