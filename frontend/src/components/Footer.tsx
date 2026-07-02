export default function Footer() {
  return (
    <footer className="border-t border-border py-8 text-center text-sm text-muted-foreground">
      <div className="mx-auto max-w-5xl px-6">
        <p>&copy; {new Date().getFullYear()} AuraMatch AI. Built for JTP Project Round.</p>
      </div>
    </footer>
  );
}
