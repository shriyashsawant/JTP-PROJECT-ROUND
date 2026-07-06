"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// The Dupe Engine is now part of the unified chat at /search - the backend's
// own detect_dupe_intent/find_reference_perfume already handle "cheaper
// alternative to X" style queries within the same endpoint the chat calls,
// so a separate form/page for it was an artifact of the old UI, not a
// backend constraint. This route stays only as a redirect for old links/
// bookmarks (e.g. ?name=X from a previous version of the perfume detail
// page's "Find Dupes for this" button).
export default function DupeRedirect() {
  const router = useRouter();

  useEffect(() => {
    const name = new URLSearchParams(window.location.search).get("name");
    const target = name
      ? `/search?prefill=${encodeURIComponent(`cheaper alternative to ${name}`)}`
      : "/search";
    router.replace(target);
  }, [router]);

  return null;
}
