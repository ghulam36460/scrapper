const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "asagus_operator_token";

function operatorToken() {
  if (typeof window === "undefined") return process.env.NEXT_PUBLIC_OPERATOR_TOKEN || "";
  return window.localStorage.getItem(TOKEN_KEY) || process.env.NEXT_PUBLIC_OPERATOR_TOKEN || "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = operatorToken();
  const hasBody = init?.body !== undefined;
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...((init?.headers as Record<string, string> | undefined) || {})
      },
      cache: "no-store"
    });
  } catch (error) {
    const reason = error instanceof Error && error.message ? error.message : "network request failed";
    throw new Error(`Backend unreachable at ${API_URL}${path}: ${reason}`);
  }
  if (!response.ok) {
    const text = await response.text();
    let message = text || response.statusText;
    try {
      const data = JSON.parse(text);
      message = String(data.detail || data.message || message);
    } catch {
      // keep raw response text
    }
    throw new Error(message);
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

function llmSettingsPayload(settings: LLMSettings): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    provider: settings.provider || "disabled",
    model: (settings.model || "").trim(),
    temperature: Number.isFinite(settings.temperature) ? settings.temperature : 0,
    timeout_seconds: Number.isFinite(settings.timeout_seconds) ? settings.timeout_seconds : 45,
    max_concurrency: Number.isFinite(settings.max_concurrency) ? settings.max_concurrency : 5,
    extra_headers: settings.extra_headers || {},
  };
  const apiKey = settings.api_key?.trim();
  if (apiKey) payload.api_key = apiKey;
  const baseUrl = settings.base_url?.trim();
  if (baseUrl) payload.base_url = baseUrl;
  return payload;
}

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
    antibot_preset?: string;
    discovery_mode?: string;
    lead_target?: string;
    website_filter?: string;
    decision_maker_titles?: string;
    llm_enabled: boolean;
    archive_raw_html: boolean;
    capture_dom_fingerprint?: boolean;
    capture_device_stamp?: boolean;
    screenshot_on_failure?: boolean;
    manual_review_on_challenge?: boolean;
    max_browser_actions?: number;
    max_seconds_per_page?: number;
    max_pages_per_domain?: number;
    recipe_set?: string;
    resource_profile?: string;
    worker_count?: number;
    respect_robots_txt: boolean;
    skip_existing?: boolean;
    include_contact_pages?: boolean;
    include_social_profiles?: boolean;
    require_email?: boolean;
    store_partial_records?: boolean;
    enable_network_fetch?: boolean | null;
    enable_search_discovery?: boolean | null;
    proxy_strategy?: string;
    social_auth_mode?: string;
    social_auth_platforms?: string[];
    social_auth_session_label?: string;
    social_auth_required?: boolean;
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
  raw_fields?: Record<string, unknown>;
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
  browser: Record<string, unknown>;
  captcha_solver?: Record<string, unknown>;
  native_layer6?: Record<string, unknown>;
  social_auth?: Record<string, unknown>;
  antibot_presets: Record<string, Record<string, unknown>>;
  discovery: Record<string, unknown>;
  throughput: Record<string, unknown>;
  accelerators?: Record<string, unknown>;
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

export type RuntimeMode = {
  environment: string;
  auth_required: boolean;
  network_fetch_enabled: boolean;
  search_discovery_enabled: boolean;
  per_job_controls: {
    network_fetch: "can_disable_only" | "locked_off" | "can_override";
    search_discovery: "can_disable_only" | "locked_off" | "can_override";
  };
  message: string;
  modes?: Record<string, string>;
  resource_profiles?: Record<string, string>;
};

export type LLMTestResult = {
  ok: boolean;
  provider: string;
  model: string;
  enabled: boolean;
  message: string;
};

export type GraphCandidate = {
  source_record_id: string;
  target_record_id: string;
  relationship: string;
  confidence: number;
  evidence: string[];
  created_at: string;
};

export type ToolInfo = {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  folder: string;
  available: boolean;
  entry_point: string | null;
  folder_path: string | null;
};

export type ToolRun = {
  run_id: string;
  tool_id: string;
  tool_name: string;
  pid?: number;
  status: "running" | "completed" | "failed" | "killed";
  command?: string;
  started_at?: number;
  exit_code?: number | null;
};

export type ToolRunStatus = ToolRun & {
  stdout: string[];
  stderr: string[];
};

export const api = {
  setOperatorToken: (token: string) => {
    if (typeof window !== "undefined") {
      if (token.trim()) window.localStorage.setItem(TOKEN_KEY, token.trim());
      else window.localStorage.removeItem(TOKEN_KEY);
    }
  },
  getOperatorToken: () => operatorToken(),
  blueprint: () => request<{ layers: Array<{ id: number; key: string; name: string; status: string }> }>("/api/blueprint"),
  health: () => request<{ status: string; services: Record<string, string> }>("/api/health"),
  runtimeMode: () => request<RuntimeMode>("/api/runtime/mode"),
  providers: () => request<{ providers: ProviderPreset[] }>("/api/providers"),
  algorithmState: () => request<AlgorithmState>("/api/algorithm/state"),
  observability: () => request<{ metrics: ObservabilityMetric[] }>("/api/observability"),
  graphCandidates: () => request<{ count: number; candidates: GraphCandidate[] }>("/api/graph/candidates"),
  getLLM: () => request<LLMSettings>("/api/llm/settings"),
  saveLLM: (settings: LLMSettings) => request<LLMSettings>("/api/llm/settings", { method: "POST", body: JSON.stringify(llmSettingsPayload(settings)) }),
  testLLM: () => request<LLMTestResult>("/api/llm/test", { method: "POST", body: JSON.stringify({}) }),
  jobs: () => request<ScrapeJob[]>("/api/jobs"),
  startJob: (payload: Record<string, unknown>) => request<ScrapeJob>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  cancelJob: (id: string) => request<ScrapeJob>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  deleteJob: (id: string) => request<{ ok: boolean; job_id: string; deleted: string[] }>(`/api/jobs/${id}`, { method: "DELETE" }),
  clearJobs: () => request<{ ok: boolean; jobs_deleted: number; events_deleted: number; archives_deleted: number }>("/api/jobs", { method: "DELETE" }),
  job: (id: string) => request<{ job: ScrapeJob; events: JobEvent[] }>(`/api/jobs/${id}`),
  records: () => request<{ count: number; records: RecordRow[] }>("/api/records"),
  deleteRecord: (id: string) => request<{ ok: boolean; record_id: string }>(`/api/records/${id}`, { method: "DELETE" }),
  clearRecords: () => request<{ ok: boolean; records_deleted: number; graph_candidates_deleted: number }>("/api/records", { method: "DELETE" }),
  clearLocalData: () => request<Record<string, unknown>>("/api/runtime/local-data", { method: "DELETE" }),
  search: (payload: Record<string, unknown>) =>
    request<{ count: number; summary: string; chain_queries: string[]; results: Array<{ record: RecordRow; score: number; highlights: string[] }> }>("/api/search", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  policyStats: () => request<Record<string, unknown>>("/api/policy/stats"),
  // ENV Settings
  getEnvSettings: () => request<Record<string, { value: string; set: boolean } | string | boolean>>("/api/env/settings"),
  saveEnvSettings: (updates: Record<string, string>) => request<{ ok: boolean; updated_keys: string[]; env_path: string }>("/api/env/settings", { method: "POST", body: JSON.stringify(updates) }),
  // CSV Export
  exportRecordsCSV: () => `${API_URL}/api/records/export/csv`,
  exportSecondaryCSV: () => `${API_URL}/api/records/secondary/export/csv`,
  // Secondary DB
  secondaryRecords: () => request<{ count: number; records: Record<string, unknown>[] }>("/api/records/secondary"),
  // Tools Runner
  listTools: () => request<{ count: number; tools: ToolInfo[] }>("/api/tools"),
  listToolRuns: () => request<{ count: number; runs: ToolRun[] }>("/api/tools/runs"),
  runTool: (toolId: string, args?: string[], env?: Record<string, string>) =>
    request<ToolRun>(`/api/tools/${toolId}/run`, { method: "POST", body: JSON.stringify({ args: args || [], env: env || {} }) }),
  toolStatus: (runId: string) => request<ToolRunStatus>(`/api/tools/status/${runId}`),
  killTool: (runId: string) => request<{ ok: boolean; run_id: string }>(`/api/tools/kill/${runId}`, { method: "POST" }),
  // Package Installer
  installPackage: (packageName: string) =>
    request<{ ok: boolean; package: string; return_code: number; stdout: string; stderr: string }>("/api/packages/install", { method: "POST", body: JSON.stringify({ package: packageName }) }),
};

export { API_URL };
