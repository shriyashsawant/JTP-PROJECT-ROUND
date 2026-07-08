import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Shared by PerfumeCard and the perfume detail page - was previously
// duplicated verbatim in both, which risked the two silently drifting out
// of sync on a future tweak.
const WOODY_ACCORDS = new Set(["woody", "leather", "tobacco", "smoky", "oud", "animalic", "amber", "spicy", "warm spicy"]);
const FRESH_ACCORDS = new Set(["citrus", "fresh", "aquatic", "marine", "green", "ozonic", "aromatic", "fresh spicy", "herbal"]);
const SWEET_ACCORDS = new Set(["floral", "fruity", "sweet", "gourmand", "vanilla", "tropical", "powdery"]);

export function getAccordGradient(accords: string[] | undefined): string {
  if (!accords || accords.length === 0) {
    return "from-slate-900 via-neutral-900 to-stone-950";
  }
  const main = accords.map((a) => a.toLowerCase().trim());

  let woodyCount = 0;
  let freshCount = 0;
  let sweetCount = 0;
  for (const a of main) {
    if (WOODY_ACCORDS.has(a)) woodyCount++;
    if (FRESH_ACCORDS.has(a)) freshCount++;
    if (SWEET_ACCORDS.has(a)) sweetCount++;
  }

  if (woodyCount >= freshCount && woodyCount >= sweetCount) {
    return "from-amber-950/70 via-stone-900 to-stone-950";
  }
  if (freshCount >= woodyCount && freshCount >= sweetCount) {
    return "from-cyan-950/70 via-slate-900 to-zinc-950";
  }
  if (sweetCount >= woodyCount && sweetCount >= freshCount) {
    return "from-rose-950/60 via-zinc-900 to-neutral-950";
  }
  return "from-slate-900 via-neutral-900 to-stone-950";
}

// `noopener,noreferrer` matters here the same way it already does on the
// existing Fragrantica link in the detail page: without it, the opened tab
// can access `window.opener` and redirect the original tab (a real, well-
// known "tabnabbing" risk) - a plain `window.open(url, "_blank")` omits it.
export function openAmazonSearch(brand: string, perfume: string) {
  const query = `${brand} ${perfume} perfume`;
  const url = `https://www.amazon.in/s?k=${encodeURIComponent(query)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}
