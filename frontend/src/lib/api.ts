export interface MatchCriterion {
  label: string;
  status: "met" | "partial" | "unmet";
}

export interface Perfume {
  id: number;
  brand: string;
  perfume: string;
  price_inr?: number;
  currency: string;
  match_score?: number;
  notes: string[];
  main_accords: string[];
  type?: string;
  gender?: string;
  longevity_score?: number;
  sillage_score?: number;
  launch_year?: string;
  image_url?: string;
  url?: string;
  country?: string;
  perfumer?: string;
  savings?: number;
  explanation?: string;
  estimated_wear_hours?: string;
  projection_label?: string;
  best_for: string[];
  match_breakdown: MatchCriterion[];
  has_limited_data?: boolean;
}

export interface PerfumeDetail {
  id: number;
  brand: string;
  perfume: string;
  launch_year?: string;
  price_inr?: number;
  currency: string;
  type?: string;
  gender?: string;
  main_accords: string[];
  notes: string[];
  top_notes: string[];
  heart_notes: string[];
  base_notes: string[];
  longevity_score?: number;
  sillage_score?: number;
  image_url?: string;
  url?: string;
  country?: string;
  perfumer?: string;
  has_limited_data?: boolean;
}

export interface ContextSearchRequest {
  query: string;
  budget?: number;
  limit?: number;
  scenario?: string[];
  skin_type?: string;
  gender?: string;
  age?: number;
  note_families?: string[];
  hours_required?: number;
  projection_preference?: string;
  deal_breaker?: boolean;
  session_id?: string;
}

export interface DupeSearchRequest {
  query: string;
  budget?: number;
  limit?: number;
  scenario?: string[];
  skin_type?: string;
  gender?: string;
  age?: number;
  note_families?: string[];
  hours_required?: number;
  projection_preference?: string;
  deal_breaker?: boolean;
  session_id?: string;
}

export interface HealthResponse {
  status: string;
  db_connected: boolean;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// A "publishable" key (see documentation/THIRD_PARTY_API.md) - safe to embed
// in browser JS by design, restricted server-side by an Origin allowlist
// tied to this frontend's own origin, not a secret.
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

// Thrown when the backend returns a 422 with `needs_clarification: true` -
// e.g. "cheaper alternative to X" with no budget and no recognized X. Lets
// the UI show a targeted prompt instead of a generic error banner.
export class ClarificationNeededError extends Error {
  field: string;
  constructor(message: string, field: string) {
    super(message);
    this.name = "ClarificationNeededError";
    this.field = field;
  }
}

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${endpoint}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    const detail = err.detail;
    if (detail && typeof detail === "object") {
      if (detail.needs_clarification) {
        throw new ClarificationNeededError(
          detail.message || "Could you provide a bit more detail?",
          detail.field || ""
        );
      }
      throw new Error(detail.message || JSON.stringify(detail));
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function searchByContext(req: ContextSearchRequest): Promise<Perfume[]> {
  return fetchAPI<Perfume[]>("/api/v1/search/context", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function searchByDupe(req: DupeSearchRequest): Promise<Perfume[]> {
  return fetchAPI<Perfume[]>("/api/v1/search/dupe", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getPerfumeById(id: number): Promise<PerfumeDetail> {
  return fetchAPI<PerfumeDetail>(`/api/v1/perfume/${id}`);
}

export async function checkHealth(): Promise<HealthResponse> {
  return fetchAPI<HealthResponse>("/api/v1/health");
}

export interface IntentClassification {
  is_fragrance: boolean;
  method: string;
  confidence: number;
}

export async function classifyIntent(text: string): Promise<IntentClassification> {
  return fetchAPI<IntentClassification>("/api/v1/classify-intent", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export interface ExtractedPreferencesResponse {
  gender: "male" | "female" | "unisex" | null;
  scenarios: string[];
  note_families: string[];
  avoid_notes: string[];
  hours_required: number | null;
  longevity_requested: boolean;
  projection_preference: "light" | "moderate" | "strong" | null;
  budget: number | null;
  age: number | null;
  skin_type: "dry" | "oily" | "normal" | null;
  is_dupe_intent: boolean;
  is_off_topic: boolean;
}

export async function extractPreferences(text: string, session_id?: string): Promise<ExtractedPreferencesResponse> {
  return fetchAPI<ExtractedPreferencesResponse>("/api/v1/extract-preferences", {
    method: "POST",
    body: JSON.stringify({ text, session_id }),
  });
}

export async function getMetrics(): Promise<string> {
  const url = `${API_URL}/metrics`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch metrics: ${res.status}`);
  }
  return res.text();
}
