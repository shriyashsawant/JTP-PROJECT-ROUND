"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { getPerfumeById } from "@/lib/api";
import { getAccordGradient, openAmazonSearch } from "@/lib/utils";
import type { PerfumeDetail } from "@/lib/api";

function PerfumeHero({ perfume }: { perfume: PerfumeDetail }) {
  const [failed, setFailed] = useState(false);
  const gradientClass = getAccordGradient(perfume.main_accords);

  if (!perfume.image_url || failed) {
    return (
      <div className={`relative flex h-64 w-full items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br ${gradientClass} border border-white/5 sm:w-48`}>
        <div className="absolute inset-0 bg-black/15 backdrop-blur-[1px]" />
        <span className="relative z-10 text-4xl font-bold uppercase tracking-wider text-white/50">
          {perfume.brand.charAt(0)}
          {perfume.perfume.charAt(0)}
        </span>
        <div className="absolute bottom-3 right-3 text-[10px] uppercase tracking-widest text-white/30 font-medium">
          {perfume.main_accords?.[0] || "scent"}
        </div>
      </div>
    );
  }
  return (
    <div className="relative h-64 w-full overflow-hidden rounded-xl bg-secondary border border-white/5 sm:w-48">
      <Image
        src={perfume.image_url}
        alt={`${perfume.brand} ${perfume.perfume}`}
        fill
        sizes="(max-width: 640px) 100vw, 192px"
        className="object-cover"
        onError={() => setFailed(true)}
      />
    </div>
  );
}

export default function PerfumeDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [perfume, setPerfume] = useState<PerfumeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const perfumeId = parseInt(id, 10);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
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
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [id, perfumeId]);

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
        <h2 className="font-heading text-2xl font-semibold">Perfume not found</h2>
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
      <button
        type="button"
        onClick={() => router.back()}
        className="mb-6 inline-flex items-center gap-1 border-0 bg-transparent p-0 text-sm text-muted-foreground hover:text-foreground cursor-pointer"
      >
        <ArrowLeft size={14} /> Back to results
      </button>

      <div className="flex flex-col gap-8 sm:flex-row">
        <PerfumeHero perfume={perfume} />

        <div className="flex-1 space-y-4">
          <div>
            <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
              {perfume.brand}
            </p>
            <h1 className="font-heading text-2xl font-semibold">{perfume.perfume}</h1>
          </div>

          {perfume.price_inr != null && (
            <p className="text-2xl font-bold text-primary">
              ₹{perfume.price_inr.toLocaleString("en-IN")}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {perfume.type && (
              <span className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
                {perfume.type}
              </span>
            )}
            {perfume.country && (
              <span className="rounded-full border px-3 py-1 text-xs font-medium">
                {perfume.country}
              </span>
            )}
            {perfume.launch_year && perfume.launch_year !== "Unknown" && (
              <span className="rounded-full border px-3 py-1 text-xs font-medium">
                {perfume.launch_year}
              </span>
            )}
          </div>

          <div className="pt-2 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => openAmazonSearch(perfume.brand, perfume.perfume)}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90 transition-opacity cursor-pointer shadow-md shadow-primary/10"
            >
              Shop Now ↗
            </button>
            <Link
              href={`/search?prefill=${encodeURIComponent("cheaper alternative to " + perfume.brand + " " + perfume.perfume)}`}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-5 py-2 text-xs font-semibold text-primary hover:bg-primary/10 transition-colors cursor-pointer"
            >
              Find Dupes
            </Link>
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

      {/* Scent Pyramid: Top / Heart / Base, in increasing visual weight to
          mirror increasing density/persistence down the pyramid */}
      {perfume.top_notes.length > 0 || perfume.heart_notes.length > 0 || perfume.base_notes.length > 0 ? (
        <div className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Scent Pyramid
          </h2>
          <div className="mt-3 space-y-4">
            {perfume.top_notes.length > 0 && (
              <div>
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary/40" />
                  Top Notes
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {perfume.top_notes.map((n) => (
                    <span
                      key={n}
                      className="rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-foreground"
                    >
                      {n}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {perfume.heart_notes.length > 0 && (
              <div>
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
                  Heart Notes
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {perfume.heart_notes.map((n) => (
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
            {perfume.base_notes.length > 0 && (
              <div>
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                  Base Notes
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {perfume.base_notes.map((n) => (
                    <span
                      key={n}
                      className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground"
                    >
                      {n}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : perfume.notes.length > 0 ? (
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
      ) : null}

      {/* Perfumer */}
      {perfume.perfumer && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Perfumer
          </h2>
          <p className="mt-1 text-sm">{perfume.perfumer}</p>
        </div>
      )}

      {/* Fragrantica Link */}
      {perfume.url && (
        <div className="mt-4">
          <a
            href={perfume.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground underline hover:text-foreground"
          >
            View on Fragrantica ↗
          </a>
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
    </motion.div>
  );
}
