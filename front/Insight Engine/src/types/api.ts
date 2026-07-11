export interface ReportSection {
  heading: string;
  content: string;
  supporting_sources: string[];
}

export interface Report {
  title: string;
  sections: ReportSection[];
  citations: string[];
  generated_at: string;
  quality_score: number;
}

export interface HealthResponse {
  status: "ok" | "error";
  memory_count?: number;
  detail?: string;
}

export interface BenchmarkResult {
  query: string;
  category: string;
  status: string;
  quality_score: number;
  latency_s: number;
  from_memory: boolean;
}

export interface HistoryEntry {
  query: string;
  title: string;
  quality_score: number;
  generated_at: string;
}
