import Link from "next/link";
import { ArrowRight, Sparkles, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <section className="flex w-full max-w-3xl flex-col items-center px-6 py-24 text-center sm:py-32">
        <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
          Find your signature.
          <br />
          <span className="text-muted-foreground">Or steal theirs.</span>
        </h1>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
          Tell us your vibe, your budget, and your occasion. We&apos;ll find the
          perfect scent — without the guesswork.
        </p>
        <div className="mt-8 flex flex-col gap-4 sm:flex-row">
          <Link href="/search">
            <Button size="lg" className="gap-2">
              <Sparkles size={18} />
              Match by Lifestyle
            </Button>
          </Link>
          <Link href="/dupe">
            <Button size="lg" variant="outline" className="gap-2">
              <Search size={18} />
              Find a Dupe
            </Button>
          </Link>
        </div>
      </section>

      {/* Feature cards */}
      <section className="w-full max-w-5xl px-6 pb-24">
        <div className="grid gap-6 sm:grid-cols-2">
          <Link
            href="/search"
            className="group rounded-xl border border-border p-8 transition-all hover:-translate-y-1 hover:shadow-md"
          >
            <Sparkles size={24} className="mb-4 text-foreground" />
            <h2 className="text-lg font-semibold">Vibe Check</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Describe your mood, occasion, or preferences in plain English. Our
              AI matches you with scents that fit.
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium">
              Try it <ArrowRight size={14} />
            </span>
          </Link>

          <Link
            href="/dupe"
            className="group rounded-xl border border-border p-8 transition-all hover:-translate-y-1 hover:shadow-md"
          >
            <Search size={24} className="mb-4 text-foreground" />
            <h2 className="text-lg font-semibold">Dupe Engine</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Love a luxury perfume but not the price? Find the best affordable
              alternatives within your budget.
            </p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium">
              Find dupes <ArrowRight size={14} />
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
