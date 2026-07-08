"use client";

import { useEffect, useState } from "react";
import { Activity, ShieldAlert, Clock, RefreshCw, AlertTriangle, CheckCircle, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getMetrics } from "@/lib/api";

interface RateLimitReject {
  keyType: string;
  count: number;
}

interface HttpRouteMetric {
  route: string;
  status: string;
  count: number;
  sum: number;
}

interface MetricsDashboardData {
  circuitBreakerGroq: "CLOSED" | "OPEN" | "HALF-OPEN" | "UNKNOWN";
  rateLimitRejections: RateLimitReject[];
  httpFailedTotal: number;
  totalRequests: number;
  averageLatencyMs: number;
  routes: HttpRouteMetric[];
}

export default function AdminMetricsPage() {
  const [metricsText, setMetricsText] = useState<string>("");
  const [data, setData] = useState<MetricsDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAndParseMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const text = await getMetrics();
      setMetricsText(text);

      // Parsing logic
      let groqState: "CLOSED" | "OPEN" | "HALF-OPEN" | "UNKNOWN" = "UNKNOWN";
      const rateLimitRejects: RateLimitReject[] = [];
      let totalFailed = 0;
      let totalReq = 0;
      let totalDuration = 0;

      // Track routes
      const routeCounts: { [key: string]: number } = {};
      const routeSums: { [key: string]: number } = {};

      const lines = text.split("\n");
      for (const line of lines) {
        if (line.startsWith("#") || !line.trim()) continue;

        // Circuit breaker parse
        if (line.startsWith('auramatch_circuit_breaker_state{breaker="groq"}')) {
          const match = line.match(/state\{breaker="groq"\}\s+([\d.]+)/);
          if (match) {
            const val = parseFloat(match[1]);
            if (val === 0) groqState = "CLOSED";
            else if (val === 1) groqState = "OPEN";
            else if (val === 2) groqState = "HALF-OPEN";
          }
        }

        // Rate limiter rejections parse
        if (line.startsWith("auramatch_rate_limit_rejections_total")) {
          const match = line.match(/key_type="([^"]+)"\}\s+([\d.]+)/);
          if (match) {
            rateLimitRejects.push({
              keyType: match[1],
              count: parseInt(match[2], 10),
            });
          }
        }

        // Unhandled exceptions parse
        if (line.startsWith("auramatch_http_requests_failed_total")) {
          const match = line.match(/failed_total\{route="([^"]+)"\}\s+([\d.]+)/);
          if (match) {
            totalFailed += parseInt(match[2], 10);
          }
        }

        // Latency count parse
        if (line.startsWith("auramatch_http_request_duration_seconds_count")) {
          const match = line.match(/_count\{route="([^"]+)",status="([^"]+)"\}\s+([\d.]+)/);
          if (match) {
            const route = match[1];
            const status = match[2];
            const count = parseInt(match[3], 10);
            totalReq += count;
            const key = `${route}||${status}`;
            routeCounts[key] = count;
          }
        }

        // Latency sum parse
        if (line.startsWith("auramatch_http_request_duration_seconds_sum")) {
          const match = line.match(/_sum\{route="([^"]+)",status="([^"]+)"\}\s+([\d.]+)/);
          if (match) {
            const route = match[1];
            const status = match[2];
            const sum = parseFloat(match[3]);
            totalDuration += sum;
            const key = `${route}||${status}`;
            routeSums[key] = sum;
          }
        }
      }

      // Build routes table list
      const routesList: HttpRouteMetric[] = [];
      for (const key of Object.keys(routeCounts)) {
        const [route, status] = key.split("||");
        const count = routeCounts[key];
        const sum = routeSums[key] || 0;
        routesList.push({ route, status, count, sum });
      }

      setData({
        circuitBreakerGroq: groqState,
        rateLimitRejections: rateLimitRejects,
        httpFailedTotal: totalFailed,
        totalRequests: totalReq,
        averageLatencyMs: totalReq > 0 ? (totalDuration / totalReq) * 1000 : 0,
        routes: routesList,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to fetch metrics";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    Promise.resolve().then(() => {
      fetchAndParseMetrics();
    });
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="flex items-center justify-between border-b border-border/70 pb-6 mb-8">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            Developer Metrics Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time observability parsed directly from backend Prometheus endpoints.
          </p>
        </div>
        <Button onClick={fetchAndParseMetrics} size="sm" className="gap-2">
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <ShieldAlert size={18} />
          <span>{error}</span>
        </div>
      )}

      {loading && !data ? (
        <div className="flex h-64 items-center justify-center">
          <RefreshCw className="animate-spin text-muted-foreground" size={30} />
        </div>
      ) : (
        data && (
          <div className="space-y-8">
            {/* Summary Cards */}
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
              {/* Circuit Breaker */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Circuit Breaker
                  </span>
                  <Shield
                    size={20}
                    className={
                      data.circuitBreakerGroq === "CLOSED"
                        ? "text-emerald-500"
                        : "text-amber-500"
                    }
                  />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono">
                    {data.circuitBreakerGroq}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                  {data.circuitBreakerGroq === "CLOSED" ? (
                    <>
                      <CheckCircle size={12} className="text-emerald-500" />
                      <span>Groq API is Healthy</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle size={12} className="text-amber-500" />
                      <span>Groq API is Tripped/Degraded</span>
                    </>
                  )}
                </div>
              </div>

              {/* Total Requests */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Total Requests
                  </span>
                  <Activity size={20} className="text-primary" />
                </div>
                <div className="text-2xl font-bold font-mono">
                  {data.totalRequests}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  All HTTP requests served, any status
                </p>
              </div>

              {/* Avg Latency */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Avg Latency
                  </span>
                  <Clock size={20} className="text-blue-500" />
                </div>
                <div className="text-2xl font-bold font-mono">
                  {data.averageLatencyMs.toFixed(1)} ms
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Average round-trip response time
                </p>
              </div>

              {/* Rate Limit Rejections */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Rejections (429)
                  </span>
                  <ShieldAlert size={20} className="text-rose-500" />
                </div>
                <div className="text-2xl font-bold font-mono">
                  {data.rateLimitRejections.reduce((a, b) => a + b.count, 0)}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Total blocked key-abuse requests
                </p>
              </div>

              {/* Failed Requests */}
              <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Failed Requests
                  </span>
                  <AlertTriangle
                    size={20}
                    className={data.httpFailedTotal > 0 ? "text-rose-500" : "text-emerald-500"}
                  />
                </div>
                <div className="text-2xl font-bold font-mono">
                  {data.httpFailedTotal}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Unhandled exceptions (5xx crashes, not 4xx responses)
                </p>
              </div>
            </div>

            {/* Detailed route stats */}
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
              <h2 className="font-heading text-lg font-semibold mb-4">
                Endpoint Performance
              </h2>
              {data.routes.length === 0 ? (
                <p className="text-sm text-muted-foreground">No route traffic captured yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-border/70 text-muted-foreground font-medium">
                        <th className="pb-3 pr-4 font-semibold uppercase text-xs">Route</th>
                        <th className="pb-3 px-4 font-semibold uppercase text-xs">Status</th>
                        <th className="pb-3 px-4 font-semibold uppercase text-xs text-right">Requests</th>
                        <th className="pb-3 pl-4 font-semibold uppercase text-xs text-right">Avg Latency</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40 font-mono">
                      {data.routes.map((r, idx) => (
                        <tr key={idx} className="hover:bg-muted/10 transition-colors">
                          <td className="py-3 pr-4 text-foreground font-semibold">{r.route}</td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                                r.status.startsWith("2")
                                  ? "bg-emerald-500/10 text-emerald-500"
                                  : "bg-rose-500/10 text-rose-500"
                              }`}
                            >
                              {r.status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">{r.count}</td>
                          <td className="py-3 pl-4 text-right">
                            {r.count > 0 ? `${((r.sum / r.count) * 1000).toFixed(1)}ms` : "0ms"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Raw metrics viewer */}
            <details className="group rounded-2xl border border-border bg-card/40 p-4 shadow-sm">
              <summary className="flex cursor-pointer items-center justify-between text-sm font-medium text-muted-foreground select-none">
                <span>View Raw Prometheus Metrics Output</span>
                <span className="transition-transform group-open:rotate-180">▼</span>
              </summary>
              <pre className="mt-4 max-h-96 overflow-y-auto rounded-lg bg-zinc-950 p-4 text-xs text-zinc-300 font-mono whitespace-pre-wrap">
                {metricsText}
              </pre>
            </details>
          </div>
        )
      )}
    </div>
  );
}
