import Link from "next/link";
import { ArrowRight, Sparkles, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <section className="relative flex w-full max-w-3xl flex-col items-center px-6 py-24 text-center sm:py-32">
        <div className="hero-glow" />

        <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-xs font-medium tracking-wide text-primary">
          <Sparkles size={13} />
          AI-Powered Fragrance Discovery
        </span>

        <h1 className="font-heading mt-6 text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
          Find your signature.
          <br />
          <span className="text-gradient-gold">Or steal theirs.</span>
        </h1>
        <p className="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
          Tell us your vibe, your budget, and your occasion. We&apos;ll find the
          perfect scent — without the guesswork.
        </p>
        <div className="mt-9 flex flex-col gap-4 sm:flex-row">
          <Link href="/search">
            <Button size="lg" className="gap-2 shadow-lg shadow-primary/25">
              <Sparkles size={18} />
              Start Chatting
            </Button>
          </Link>
        </div>
      </section>

      {/* Feature cards */}
      <section className="w-full max-w-5xl px-6 pb-24">
        <div className="grid gap-6 sm:grid-cols-2">
          <Link
            href="/search"
            className="group rounded-2xl border border-border bg-card p-8 shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-xl hover:shadow-primary/10"
          >
            <div className="mb-5 flex size-11 items-center justify-center rounded-full bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
              <Sparkles size={20} />
            </div>
            <h2 className="font-heading text-lg font-semibold">Vibe Check</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Describe your mood, occasion, or preferences in plain English. Our
              AI matches you with scents that fit - and keeps refining as you chat.
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
              Try it{" "}
              <ArrowRight
                size={14}
                className="transition-transform group-hover:translate-x-1"
              />
            </span>
          </Link>

          <Link
            href="/search"
            className="group rounded-2xl border border-border bg-card p-8 shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-xl hover:shadow-primary/10"
          >
            <div className="mb-5 flex size-11 items-center justify-center rounded-full bg-accent/10 text-accent transition-colors group-hover:bg-accent group-hover:text-accent-foreground">
              <Search size={20} />
            </div>
            <h2 className="font-heading text-lg font-semibold">Dupe Engine</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Love a luxury perfume but not the price? Just name it in the same
              chat - we&apos;ll find the best affordable alternatives within budget.
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
              Find dupes{" "}
              <ArrowRight
                size={14}
                className="transition-transform group-hover:translate-x-1"
              />
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
