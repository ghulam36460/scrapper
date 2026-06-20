/**
 * Agent-Reach API client - extends the main API with Agent-Reach specific endpoints
 */

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

// ─── Types ──────────────────────────────────────────────────────────────

export type AgentReachChannel = {
  name: string;
  display_name: string;
  status: "ok" | "warn" | "off" | "unknown";
  ready: boolean;
  message: string;
  description: string;
  requires: string[];
  config_needed: string;
  install_command: string;
};

export type AgentReachStatus = {
  available: boolean;
  channels: Record<string, {
    status: string;
    message: string;
    ready: boolean;
  }>;
  total_channels: number;
  ready_channels: number;
  warning_channels: number;
  disabled_channels: number;
  error?: string;
};

export type AgentReachStatistics = {
  total_channels: number;
  ready_channels: number;
  warning_channels: number;
  disabled_channels: number;
  availability_percentage: number;
};

export type ChannelConfig = {
  cookie?: string;
  token?: string;
  proxy?: string;
  groq_key?: string;
  mcp_config?: Record<string, unknown>;
};

export type ChannelTestResult = {
  success: boolean;
  status?: string;
  message: string;
  ready?: boolean;
};

export type InstallResult = {
  success: boolean;
  message: string;
  output?: string;
  command?: string;
  manual_steps?: string;
};

export type AgentReachRunResult = {
  success: boolean;
  message: string;
  query: string;
  location?: string;
  limit?: number;
  job_id: string;
  run_id: string;
  tool_id: string;
  tool_name: string;
  pid?: number;
  status: string;
  channels_requested?: string[];
};

// ─── API Functions ──────────────────────────────────────────────────────

export const agentReachApi = {
  /**
   * Check if Agent-Reach is available and healthy
   */
  async health(): Promise<{ available: boolean; status: string; agent_reach_dir: string }> {
    return request("/api/agent-reach/health");
  },

  /**
   * Get comprehensive status of all channels
   */
  async getStatus(): Promise<AgentReachStatus> {
    return request("/api/agent-reach/status");
  },

  /**
   * List all available channels with details
   */
  async listChannels(): Promise<{ count: number; channels: AgentReachChannel[] }> {
    return request("/api/agent-reach/channels");
  },

  /**
   * Get detailed info about a specific channel
   */
  async getChannel(name: string): Promise<AgentReachChannel> {
    return request(`/api/agent-reach/channels/${name}`);
  },

  /**
   * Install dependencies for a channel
   */
  async installChannel(name: string): Promise<InstallResult> {
    return request(`/api/agent-reach/channels/${name}/install`, {
      method: "POST"
    });
  },

  /**
   * Configure a channel with credentials
   */
  async configureChannel(name: string, config: ChannelConfig): Promise<{ success: boolean; message: string }> {
    return request(`/api/agent-reach/channels/${name}/configure`, {
      method: "POST",
      body: JSON.stringify(config)
    });
  },

  /**
   * Test if a channel is working
   */
  async testChannel(name: string): Promise<ChannelTestResult> {
    return request(`/api/agent-reach/channels/${name}/test`, {
      method: "POST"
    });
  },

  /**
   * Get usage statistics
   */
  async getStatistics(): Promise<AgentReachStatistics> {
    return request("/api/agent-reach/statistics");
  },

  /**
   * Trigger Agent-Reach scraping job
   */
  async runScrape(
    query: string,
    options?: { location?: string; limit?: number; channels?: string[]; real_run?: boolean }
  ): Promise<AgentReachRunResult> {
    const params = new URLSearchParams({ query });
    if (options?.location) params.set("location", options.location);
    if (options?.limit) params.set("limit", String(options.limit));
    if (options?.real_run !== undefined) params.set("real_run", String(options.real_run));
    const channels = options?.channels;
    if (channels && channels.length) {
      params.append("channels", channels.join(","));
    }
    return request(`/api/agent-reach/run-scrape?${params.toString()}`, {
      method: "POST"
    });
  }
};
