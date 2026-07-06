export default function Footer() {
  return (
    <footer className="border-t border-border/70 bg-secondary/40 py-10 text-center text-sm text-muted-foreground">
      <div className="mx-auto max-w-5xl px-6">
        <p className="font-heading text-base font-semibold text-foreground">
          Aura<span className="text-primary">Match</span>
        </p>
        <p className="mt-2">
          &copy; {new Date().getFullYear()} AuraMatch AI. Built for JTP Project Round.
        </p>
      </div>
    </footer>
  );
}
