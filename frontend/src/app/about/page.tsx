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

      <h1 className="text-3xl font-bold tracking-tight">About AuraMatch AI</h1>

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
          <li><strong>Database:</strong> PostgreSQL + pgvector (384-d embeddings, HNSW indexing)</li>
          <li><strong>Infrastructure:</strong> Docker Compose (3 containers), Supabase (cloud)</li>
        </ul>

        <h2 className="text-base font-semibold text-foreground">Data Sources</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>DA Fragrance Analysis (37K perfumes)</li>
          <li>Fragrantica Perfume Dataset (70K perfumes)</li>
          <li>Fragrantica Cleaned Dataset (24K perfumes with structured notes)</li>
          <li>Perfume Recommendation Dataset (2.2K niche perfumes with images)</li>
        </ul>

        <h2 className="text-base font-semibold text-foreground">How It Works</h2>
        <ol className="list-decimal space-y-1 pl-5">
          <li>You describe your vibe or budget in plain English</li>
          <li>The query is enriched with scenario-specific olfactory keywords</li>
          <li>A 384-d embedding is generated via SentenceTransformers</li>
          <li>pgvector performs cosine similarity search against 94K+ perfumes</li>
          <li>The Decision Engine applies hybrid scoring (similarity × 0.8 + price × 0.2)</li>
          <li>A deterministic explanation is generated — no LLM API calls needed</li>
        </ol>
      </div>

      <div className="mt-10">
        <Link href="https://github.com/anomalyco/opencode" target="_blank">
          <Button variant="outline">View on GitHub</Button>
        </Link>
      </div>
    </div>
  );
}
