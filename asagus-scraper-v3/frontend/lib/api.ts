const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...((init?.headers as Record<string, string> | undefined) || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

export type LLMProvider =
  | "disabled"
  | "anthropic"
  | "openai"
  | "azure_openai"
  | "google"
  | "mistral"
  | "groq"
  | "together"
  | "openrouter"
  | "nvidia"
  | "deepinfra"
  | "cerebras"
  | "fireworks"
  | "huggingface"
  | "perplexity"
  | "openai_compatible"
  | "ollama"
  | "custom_http";

export type LLMSettings = {
  provider: LLMProvider;
  model: string;
  api_key?: string;
  base_url?: string;
  temperature: number;
  timeout_seconds: number;
  max_concurrency: number;
  extra_headers?: Record<string, string>;
  has_api_key?: boolean;
};

export type ProviderPreset = {
  provider: LLMProvider;
  label: string;
  default_base_url: string;
  example_models: string[];
  key_hint: string;
  local_only: boolean;
  supports_json_mode: boolean;
  notes: string;
};

export type ScrapeJob = {
  id: string;
  status: string;
  request: {
    query: string;
    location: string;
    limit: number;
    max_pages?: number;
    mode: string;
    llm_enabled: boolean;
    archive_raw_html: boolean;
    respect_robots_txt: boolean;
    skip_existing?: boolean;
    include_contact_pages?: boolean;
    include_social_profiles?: boolean;
    require_email?: boolean;
    enable_network_fetch?: boolean | null;
    enable_search_discovery?: boolean | null;
    proxy_strategy?: string;
  };
  total_targets: number;
  processed_targets: number;
  skipped_targets?: number;
  duplicate_skips?: number;
  records_found: number;
  llm_calls: number;
  browser_renders: number;
  current_url?: string;
  progress_message?: string;
  error: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type JobEvent = {
  id: string;
  job_id: string;
  layer: string;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type RecordRow = {
  id: string;
  name: string;
  phone: string;
  whatsapp: string;
  email: string;
  city: string;
  country_code?: string;
  category: string;
  website_url: string;
  facebook_url?: string;
  instagram_url?: string;
  twitter_url?: string;
  linkedin_url?: string;
  record_completeness: number;
  confidence: number;
  duplicate_score?: number;
  gdpr_flag: boolean;
  pdpa_flag?: boolean;
  source_url: string;
  method?: string;
  extraction_trace?: Array<{ stage: string; accepted: boolean; confidence: number; fields_found: string[]; reason: string }>;
};

export type AlgorithmState = {
  policy: Record<string, unknown>;
  mdp: {
    cold_start_phases: Array<{ phase: string; range: string; policy: string; epsilon: number }>;
    transition_priors: Record<string, number[]>;
    state_space_size?: number;
    discount?: number;
    value_iteration_iterations?: number;
    policy_snapshot?: Array<{ state: string; value: number; best_action: string }>;
    frontier_tiers: string[];
    actions: string[];
    outcomes?: string[];
    action_counts: Record<string, number>;
    markov_model?: string;
    bandit?: string;
  };
  compliance: Record<string, unknown>;
  discovery: Record<string, unknown>;
  throughput: Record<string, unknown>;
  proxy: { tiers: string[]; tier_order: string[]; endpoints: Array<Record<string, unknown>>; backoff: string };
  extraction: { cascade: Array<{ stage: string; accept_confidence: number | string }>; llm_cache_days: number };
  graph: { relationships: string[]; thresholds: Record<string, number> };
  search_algorithms: Array<{ name: string; category: string; year: number; role: string; implementation_status: string; source_url?: string; notes?: string }>;
  index_state: Record<string, unknown>;
  nlp: Record<string, unknown>;
  osint: Record<string, unknown>;
  dom_tools: Record<string, unknown>;
  analytics: Record<string, unknown>;
  geoint: Record<string, unknown>;
  vision: Record<string, unknown>;
  capabilities: Array<{ key: string; name: string; category: string; status: string; safety_boundary?: string; practical_use?: string; source_module?: string }>;
  observability_catalog: Array<{ name: string; unit: string; description: string }>;
};

export type ObservabilityMetric = {
  name: string;
  value: number;
  unit: string;
  status: string;
  description: string;
};

export type GraphCandidate = {
  source_record_id: string;
  target_record_id: string;
  relationship: string;
  confidence: number;
  evidence: string[];
  created_at: string;
};

export const api = {
  blueprint: () => request<{ layers: Array<{ id: number; key: string; name: string; status: string }> }>("/api/blueprint"),
  health: () => request<{ status: string; services: Record<string, string> }>("/api/health"),
  providers: () => request<{ providers: ProviderPreset[] }>("/api/providers"),
  algorithmState: () => request<AlgorithmState>("/api/algorithm/state"),
  observability: () => request<{ metrics: ObservabilityMetric[] }>("/api/observability"),
  graphCandidates: () => request<{ count: number; candidates: GraphCandidate[] }>("/api/graph/candidates"),
  getLLM: () => request<LLMSettings>("/api/llm/settings"),
  saveLLM: (settings: LLMSettings) => request<LLMSettings>("/api/llm/settings", { method: "POST", body: JSON.stringify(settings) }),
  jobs: () => request<ScrapeJob[]>("/api/jobs"),
  startJob: (payload: Record<string, unknown>) => request<ScrapeJob>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  cancelJob: (id: string) => request<ScrapeJob>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  job: (id: string) => request<{ job: ScrapeJob; events: JobEvent[] }>(`/api/jobs/${id}`),
  records: () => request<{ count: number; records: RecordRow[] }>("/api/records"),
  search: (payload: Record<string, unknown>) =>
    request<{ count: number; summary: string; chain_queries: string[]; results: Array<{ record: RecordRow; score: number; highlights: string[] }> }>("/api/search", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  policyStats: () => request<Record<string, unknown>>("/api/policy/stats")
};

export { API_URL };
