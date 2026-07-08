import type { ReactNode } from "react";
import { Info } from "lucide-react";

// Shared by PerfumeCard.tsx and perfume/[id]/page.tsx - both render the same
// "no real note data, scored from accords instead" notice independently
// before this was extracted, despite this app already establishing the
// pattern of pulling shared UI logic into one place (see getAccordGradient/
// openAmazonSearch in lib/utils.ts). Callers keep their own copy/sizing via
// props/children since the card (compact grid) and detail page (more room)
// intentionally use different text and icon sizes.
export default function LimitedDataNotice({
  className = "",
  iconSize = 12,
  children,
}: {
  className?: string;
  iconSize?: number;
  children: ReactNode;
}) {
  return (
    <p className={`flex items-center gap-1 text-amber-600 dark:text-amber-400 ${className}`}>
      <Info size={iconSize} />
      {children}
    </p>
  );
}
