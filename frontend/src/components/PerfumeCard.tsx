"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import Image from "next/image";
import { Star, Check, Minus, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Perfume } from "@/lib/api";

function StatusIcon({ status }: { status: "met" | "partial" | "unmet" }) {
  if (status === "met") return <Check size={12} className="text-emerald-600" />;
  if (status === "partial") return <Minus size={12} className="text-amber-500" />;
  return <X size={12} className="text-red-400" />;
}

function PerfumeThumbnail({ perfume }: { perfume: Perfume }) {
  const [failed, setFailed] = useState(false);
  if (!perfume.image_url || failed) {
    return (
      <div className="flex h-32 w-full items-center justify-center rounded-lg bg-secondary">
        <span className="text-2xl font-bold text-muted-foreground/30">
          {perfume.brand.charAt(0)}
          {perfume.perfume.charAt(0)}
        </span>
      </div>
    );
  }
  return (
    <div className="relative h-32 w-full overflow-hidden rounded-lg bg-secondary">
      <Image
        src={perfume.image_url}
        alt={`${perfume.brand} ${perfume.perfume}`}
        fill
        sizes="(max-width: 640px) 100vw, 33vw"
        className="object-cover"
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
    >
      <Link href={`/perfume/${perfume.id}`}>
        <Card className="group h-full transition-all hover:-translate-y-1 hover:shadow-lg">
          <CardContent className="flex flex-col gap-3 p-5">
            <PerfumeThumbnail perfume={perfume} />

            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {perfume.brand}
                </p>
                <h3 className="truncate text-base font-semibold leading-tight">
                  {perfume.perfume}
                </h3>
              </div>
              {perfume.type && (
                <span className="shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
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

            {perfume.savings != null && perfume.savings > 0 && (
              <p className="text-xs font-medium text-emerald-600">
                Save ₹{perfume.savings.toLocaleString("en-IN")}
              </p>
            )}
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}
