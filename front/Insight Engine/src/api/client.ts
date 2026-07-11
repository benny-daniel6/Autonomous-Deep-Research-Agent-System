import type { Report, HealthResponse, BenchmarkResult } from "@/types/api";

const API_BASE =
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

export function runResearch(query: string): Promise<Report> {
  return req<Report>("/research", {
    method: "POST",
    body: JSON.stringify({ query, stream: false }),
  });
}

export function checkHealth(): Promise<HealthResponse> {
  return req<HealthResponse>("/health");
}

export function getBenchmarks(): Promise<BenchmarkResult[]> {
  return req<BenchmarkResult[]>("/benchmark/results");
}
