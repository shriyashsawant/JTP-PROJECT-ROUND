import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft size={14} /> Back
      </Link>

      <h1 className="font-heading text-3xl font-semibold tracking-tight">About AuraMatch AI</h1>

      <div className="mt-6 space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>
          AuraMatch AI is an AI-powered perfume recommendation platform built
          for the JTP Project Round. It combines vector similarity search,
          hybrid scoring, and a deterministic explanation engine to help users
          find their perfect scent.
        </p>

        <h2 className="text-base font-semibold text-foreground">Tech Stack</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li><strong>Frontend:</strong> Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Framer Motion</li>
          <li><strong>Backend:</strong> FastAPI, asyncpg, SentenceTransformers (all-MiniLM-L6-v2)</li>
          <li><strong>Database:</strong> PostgreSQL + pgvector (384-d embeddings, GIN-indexed accord/note arrays)</li>
          <li><strong>Infrastructure:</strong> Docker Compose, 3 containers on a custom bridge network - no external cloud services required</li>
        </ul>

        <h2 className="text-base font-semibold text-foreground">Data Sources</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Primary Olfactory Dataset (37K perfumes with accords and ingredients)</li>
          <li>Structured Notes Dataset (70K perfumes with accord breakdowns)</li>
          <li>Curated Notes Dataset (24K perfumes with structured top, heart, and base notes)</li>
          <li>Niche Perfume Collection (2.2K perfumes with images and descriptions)</li>
          <li>Hand-curated Indian brand supplement with complete note pyramids</li>
        </ul>
        <p>Merged and deduplicated by normalized brand+name into ~40,600 unique perfumes.</p>

        <h2 className="text-base font-semibold text-foreground">How It Works</h2>
        <ol className="list-decimal space-y-1 pl-5">
          <li>You describe your vibe, occasion, or budget in plain English (or pick filters)</li>
          <li>The query is enriched with scenario-specific olfactory keywords and parsed for gender/budget/longevity/negation intent</li>
          <li>A 384-d embedding is generated via SentenceTransformers and matched against the catalog with pgvector</li>
          <li>A deterministic Decision Engine scores every candidate across occasion fit, note/accord overlap, gender lean, age bracket, longevity, projection, and price - each signal only counts when the query actually implies it</li>
          <li>An explanation is generated for each result - by an optional LLM re-ranking layer when configured (grounded strictly in that perfume&apos;s real accords/notes/score, wrapped in a circuit breaker), or by the deterministic engine itself otherwise. Either way, results always fall back to the deterministic ranking untouched if anything upstream fails</li>
        </ol>
      </div>

      <div className="mt-10">
        <Link href="https://github.com/shriyashsawant/JTP-PROJECT-ROUND" target="_blank">
          <Button variant="outline">View on GitHub</Button>
        </Link>
      </div>
    </div>
  );
}
