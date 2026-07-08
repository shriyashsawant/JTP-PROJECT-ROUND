"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import Image from "next/image";
import { Star, Check, Minus, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import LimitedDataNotice from "@/components/LimitedDataNotice";
import { getAccordGradient, openAmazonSearch } from "@/lib/utils";
import type { Perfume } from "@/lib/api";

function StatusIcon({ status }: { status: "met" | "partial" | "unmet" }) {
  if (status === "met") return <Check size={12} className="text-emerald-600" />;
  if (status === "partial") return <Minus size={12} className="text-amber-500" />;
  return <X size={12} className="text-red-400" />;
}

function BestMatchBadge() {
  return (
    <span className="absolute left-2 top-2 z-10 inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary-foreground shadow-sm">
      <Star size={9} className="fill-current" />
      Best Match
    </span>
  );
}

function PerfumeThumbnail({ perfume, showBadge }: { perfume: Perfume; showBadge: boolean }) {
  const [failed, setFailed] = useState(false);
  const gradientClass = getAccordGradient(perfume.main_accords);

  if (!perfume.image_url || failed) {
    return (
      <div className={`relative flex h-32 w-full items-center justify-center overflow-hidden rounded-lg bg-gradient-to-br ${gradientClass} border border-white/5`}>
        {showBadge && <BestMatchBadge />}
        <div className="absolute inset-0 bg-black/15 backdrop-blur-[1px]" />
        <span className="relative z-10 text-2xl font-bold uppercase tracking-wider text-white/50 transition-transform duration-300 group-hover:scale-110">
          {perfume.brand.charAt(0)}
          {perfume.perfume.charAt(0)}
        </span>
        <div className="absolute bottom-2 right-2 text-[9px] uppercase tracking-widest text-white/30 font-medium">
          {perfume.main_accords?.[0] || "scent"}
        </div>
      </div>
    );
  }
  return (
    <div className="relative h-32 w-full overflow-hidden rounded-lg bg-secondary border border-white/5">
      {showBadge && <BestMatchBadge />}
      <Image
        src={perfume.image_url}
        alt={`${perfume.brand} ${perfume.perfume}`}
        fill
        sizes="(max-width: 640px) 100vw, 33vw"
        className="object-cover transition-transform duration-300 group-hover:scale-105"
        onError={() => setFailed(true)}
      />
    </div>
  );
}

export default function PerfumeCard({
  perfume,
  index = 0,
}: {
  perfume: Perfume;
  index?: number;
}) {
  const stars = perfume.match_score != null ? Math.round(perfume.match_score / 20) : 0;
  const isBestMatch = index === 0 && perfume.match_score != null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
    >
      <Link href={`/perfume/${perfume.id}`}>
        <Card
          className={`group relative h-full transition-all duration-300 hover:-translate-y-1.5 hover:shadow-xl hover:shadow-primary/10 ${
            isBestMatch
              ? "border-primary/50 shadow-md shadow-primary/10 ring-1 ring-primary/20 hover:border-primary/70"
              : "hover:border-primary/40"
          }`}
        >
          <CardContent className="flex flex-col gap-3 p-5">
            <PerfumeThumbnail perfume={perfume} showBadge={isBestMatch} />

            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {perfume.brand}
                </p>
                <h3 className="font-heading truncate text-base font-semibold leading-tight transition-colors group-hover:text-primary">
                  {perfume.perfume}
                </h3>
              </div>
              {perfume.type && (
                <span className="shrink-0 rounded-full border border-primary/30 bg-primary/5 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                  {perfume.type}
                </span>
              )}
            </div>

            {perfume.price_inr != null && (
              <p className="text-lg font-bold">
                ₹{perfume.price_inr.toLocaleString("en-IN")}
              </p>
            )}

            {perfume.match_score != null && (
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-0.5">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        size={11}
                        className={i < stars ? "fill-amber-400 text-amber-400" : "text-muted-foreground/30"}
                      />
                    ))}
                  </span>
                  <span className="font-semibold">{perfume.match_score}%</span>
                </div>
                <Progress value={perfume.match_score} className="h-1.5" />
              </div>
            )}

            {perfume.best_for && perfume.best_for.length > 0 && (
              <p className="text-[11px] font-medium text-muted-foreground">
                Best for: {perfume.best_for.join(", ")}
              </p>
            )}

            {perfume.has_limited_data && (
              <LimitedDataNotice className="text-[11px] font-medium" iconSize={11}>
                Limited fragrance data - notes inferred from accords
              </LimitedDataNotice>
            )}

            <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
              {perfume.estimated_wear_hours && (
                <span>Wear: {perfume.estimated_wear_hours}</span>
              )}
              {perfume.projection_label && (
                <span className="capitalize">Projection: {perfume.projection_label}</span>
              )}
            </div>

            {perfume.notes && perfume.notes.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {perfume.notes.slice(0, 4).map((note) => (
                  <span
                    key={note}
                    className="rounded-full bg-secondary px-2.5 py-0.5 text-[11px] font-medium text-secondary-foreground"
                  >
                    {note}
                  </span>
                ))}
              </div>
            )}

            {perfume.match_breakdown && perfume.match_breakdown.length > 0 && (
              <ul className="space-y-0.5 border-t pt-2 text-[11px]">
                {perfume.match_breakdown.map((c) => (
                  <li key={c.label} className="flex items-center gap-1.5">
                    <StatusIcon status={c.status} />
                    <span className="text-muted-foreground">{c.label}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-2 flex items-center justify-between gap-2 border-t pt-3">
              {perfume.savings != null && perfume.savings > 0 ? (
                <span className="inline-flex items-center rounded-full bg-emerald-600/10 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">
                  Save ₹{perfume.savings.toLocaleString("en-IN")}
                </span>
              ) : (
                <div />
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  openAmazonSearch(perfume.brand, perfume.perfume);
                }}
                className="inline-flex items-center gap-1 rounded bg-secondary px-3 py-1.5 text-[11px] font-semibold text-secondary-foreground hover:bg-primary hover:text-primary-foreground transition-colors cursor-pointer"
              >
                Shop Now ↗
              </button>
            </div>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}
