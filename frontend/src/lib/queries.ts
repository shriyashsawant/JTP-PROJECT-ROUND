/**
 * AuraMatch AI - React Query Hooks
 *
 * Wraps each API call in a React Query hook so the UI gets automatic
 * deduplication, stale-while-revalidate caching, retry on failure, and
 * loading/error states without manual setState for every request.
 */
import { useQuery, useMutation } from "@tanstack/react-query";
import type { ContextSearchRequest, DupeSearchRequest, Perfume, PerfumeDetail } from "./api";
import { searchByContext, searchByDupe, getPerfumeById, checkHealth } from "./api";

export function useContextSearch(req: ContextSearchRequest) {
  return useMutation<Perfume[], Error, ContextSearchRequest>({
    mutationKey: ["search", "context"],
    mutationFn: searchByContext,
    retry: 1,
  });
}

export function useDupeSearch() {
  return useMutation<Perfume[], Error, DupeSearchRequest>({
    mutationKey: ["search", "dupe"],
    mutationFn: searchByDupe,
    retry: 1,
  });
}

export function usePerfumeDetail(id: number) {
  return useQuery<PerfumeDetail>({
    queryKey: ["perfume", id],
    queryFn: () => getPerfumeById(id),
    enabled: id > 0,
    staleTime: 60_000,
    retry: 1,
  });
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: 30_000,
    retry: 2,
  });
}
