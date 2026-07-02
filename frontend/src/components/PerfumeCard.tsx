"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Perfume } from "@/lib/api";

export default function PerfumeCard({
  perfume,
  index = 0,
}: {
  perfume: Perfume;
  index?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
    >
      <Link href={`/perfume/${perfume.id}`}>
        <Card className="group h-full transition-all hover:-translate-y-1 hover:shadow-lg">
          <CardContent className="flex flex-col gap-3 p-5">
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
                  <span className="text-muted-foreground">Match</span>
                  <span className="font-semibold">{perfume.match_score}%</span>
                </div>
                <Progress value={perfume.match_score} className="h-1.5" />
              </div>
            )}

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
