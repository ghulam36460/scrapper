import { LLMSettings, ScrapeJob } from "./api";

export type Tab = "setup" | "run" | "algorithms" | "pipeline" | "records" | "search" | "tools" | "dbmanager" | "envconfig";

export type JobProgress = {
  percent: number;
  elapsed: string;
  eta: string;
};

export function titleFor(tab: Tab) {
  if (tab === "setup") return "Setup & LLM";
  if (tab === "run") return "Run Console";
  if (tab === "algorithms") return "Algorithm Control";
  if (tab === "pipeline") return "Live Pipeline";
  if (tab === "records") return "Business Records";
  if (tab === "tools") return "Download Tools";
  if (tab === "dbmanager") return "DB Manager";
  if (tab === "envconfig") return "ENV Config";
  return "Retrieval";
}

export function downloadCSV(filename: string, csvText: string): void {
  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function openCSVDownload(url: string): void {
  window.open(url, "_blank");
}

export function csv(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseLLMSnippet(code: string): Partial<LLMSettings> & { found: string[] } {
  const found: string[] = [];
  const text = code || "";
  const readString = (patterns: RegExp[]) => {
    for (const pattern of patterns) {
      const match = text.match(pattern);
      const value = match?.[1]?.trim();
      if (value && !/^(process\.env|os\.getenv|env\[)/i.test(value)) return value;
    }
    return "";
  };
  const readNumber = (patterns: RegExp[]) => {
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1] !== undefined) {
        const parsed = Number(match[1]);
        if (Number.isFinite(parsed)) return parsed;
      }
    }
    return undefined;
  };

  const base_url = readString([
    /base_url\s*=\s*["']([^"']+)["']/i,
    /baseURL\s*[:=]\s*["']([^"']+)["']/i,
    /baseUrl\s*[:=]\s*["']([^"']+)["']/i,
    /configuration\s*:\s*\{[\s\S]*?baseURL\s*:\s*["']([^"']+)["']/i,
  ]);
  const api_key = readString([
    /api_key\s*=\s*["']([^"']+)["']/i,
    /apiKey\s*[:=]\s*["']([^"']+)["']/i,
    /api_key\s*:\s*["']([^"']+)["']/i,
    /authorization\s*:\s*["']Bearer\s+([^"']+)["']/i,
  ]);
  const model = readString([
    /model\s*=\s*["']([^"']+)["']/i,
    /model\s*:\s*["']([^"']+)["']/i,
    /modelName\s*:\s*["']([^"']+)["']/i,
  ]);
  const temperature = readNumber([
    /temperature\s*=\s*([0-9.]+)/i,
    /temperature\s*:\s*([0-9.]+)/i,
  ]);

  const imported: Partial<LLMSettings> & { found: string[] } = { found };
  if (base_url) {
    imported.base_url = base_url;
    imported.provider = providerFromBaseUrl(base_url);
    found.push("base_url");
    found.push("provider");
  }
  if (api_key) {
    imported.api_key = api_key;
    found.push("api_key");
  }
  if (model) {
    imported.model = model;
    found.push("model");
  }
  if (temperature !== undefined) {
    imported.temperature = Math.max(0, Math.min(2, temperature));
    found.push("temperature");
  }
  return imported;
}

export function providerFromBaseUrl(baseUrl: string): LLMSettings["provider"] {
  const url = baseUrl.toLowerCase();
  if (url.includes("integrate.api.nvidia.com")) return "nvidia";
  if (url.includes("api.openai.com")) return "openai";
  if (url.includes("api.anthropic.com")) return "anthropic";
  if (url.includes("generativelanguage.googleapis.com")) return "google";
  if (url.includes("api.mistral.ai")) return "mistral";
  if (url.includes("api.groq.com")) return "groq";
  if (url.includes("api.together.xyz")) return "together";
  if (url.includes("openrouter.ai")) return "openrouter";
  if (url.includes("api.deepinfra.com")) return "deepinfra";
  if (url.includes("api.cerebras.ai")) return "cerebras";
  if (url.includes("fireworks.ai")) return "fireworks";
  if (url.includes("huggingface.co")) return "huggingface";
  if (url.includes("perplexity.ai")) return "perplexity";
  if (url.includes("localhost:11434")) return "ollama";
  return "openai_compatible";
}

export function jobProgress(job: ScrapeJob): JobProgress {
  const total = Math.max(job.total_targets || job.request.limit || 1, 1);
  const rawPercent = Math.round((Math.min(job.processed_targets, total) / total) * 100);
  const percent = job.status === "completed" ? 100 : job.status === "failed" ? rawPercent : Math.min(rawPercent, 99);
  const start = new Date(job.started_at || job.created_at).getTime();
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now();
  const elapsedSeconds = Math.max(0, Math.round((end - start) / 1000));
  const rate = job.processed_targets > 0 ? elapsedSeconds / job.processed_targets : 0;
  const remaining = job.status === "running" && rate ? Math.max(0, Math.round((total - job.processed_targets) * rate)) : 0;
  return {
    percent,
    elapsed: formatDuration(elapsedSeconds),
    eta: job.status === "running" ? formatDuration(remaining) : "done",
  };
}

export function formatDuration(seconds: number) {
  if (seconds <= 0) return "0s";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (!minutes) return `${rest}s`;
  const hours = Math.floor(minutes / 60);
  const min = minutes % 60;
  if (!hours) return `${minutes}m ${rest}s`;
  return `${hours}h ${min}m`;
}
