/**
 * AuraMatch AI - Search Finite State Machine
 *
 * Formalizes the search conversation into explicit states so the UI always
 * knows what it should be rendering (questions, loading, results, or error)
 * and transitions atomically rather than threading raw booleans through
 * component state.
 *
 * States:
 *   idle        — No conversation started yet (empty state / hero screen)
 *   clarifying  — Asking one of the 9 Q&A questions to build the query
 *   searching   — Waiting for the backend /search/context response
 *   results     — Showing perfume results (may offer "Show More")
 *   error       — Network or backend error, user can retry
 *   off_topic   — User is asking about something non-fragrance
 */
export type SearchState =
  | { type: "idle" }
  | { type: "clarifying"; question: string; questionType: string }
  | { type: "searching" }
  | { type: "results"; perfumes: import("./api").Perfume[]; limit: number; query: string }
  | { type: "error"; message: string }
  | { type: "off_topic" };

export type SearchAction =
  | { type: "ASK_QUESTION"; question: string; questionType: string }
  | { type: "SEARCH" }
  | { type: "SHOW_RESULTS"; perfumes: import("./api").Perfume[]; limit: number; query: string }
  | { type: "SHOW_MORE"; perfumes: import("./api").Perfume[]; limit: number }
  | { type: "ERROR"; message: string }
  | { type: "OFF_TOPIC" }
  | { type: "RESET" };

export function searchReducer(state: SearchState, action: SearchAction): SearchState {
  switch (action.type) {
    case "ASK_QUESTION":
      return { type: "clarifying", question: action.question, questionType: action.questionType };
    case "SEARCH":
      return { type: "searching" };
    case "SHOW_RESULTS":
      return { type: "results", perfumes: action.perfumes, limit: action.limit, query: action.query };
    case "SHOW_MORE": {
      if (state.type !== "results") return state;
      return { ...state, perfumes: action.perfumes, limit: action.limit };
    }
    case "ERROR":
      return { type: "error", message: action.message };
    case "OFF_TOPIC":
      return { type: "off_topic" };
    case "RESET":
      return { type: "idle" };
    default:
      return state;
  }
}

export function fsmLabel(state: SearchState): string {
  switch (state.type) {
    case "idle": return "Ready";
    case "clarifying": return `Asking: ${state.questionType}`;
    case "searching": return "Searching...";
    case "results": return `${state.perfumes.length} results`;
    case "error": return "Error";
    case "off_topic": return "Off-topic";
  }
}
