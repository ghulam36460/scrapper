"use client";

import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronDown,
  Cpu,
  Database,
  Download,
  FileText,
  Flame,
  GitBranch,
  Globe2,
  KeyRound,
  Layers,
  Network,
  Package,
  Play,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  Terminal,
  Trash2,
  Wand2,
  X,
  Zap
} from "lucide-react";
import type { ElementType } from "react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlgorithmState,
  api,
  GraphCandidate,
  JobEvent,
  LLMSettings,
  ObservabilityMetric,
  ProviderPreset,
  RecordRow,
  RuntimeMode,
  ScrapeJob,
  ToolInfo,
  ToolRun,
  ToolRunStatus
} from "../lib/api";
import { EmptyState, JobProgressPanel, KeyValueGrid, RecordTable } from "../components/operator-widgets";
import { Tab, csv, jobProgress, openCSVDownload, parseLLMSnippet, titleFor } from "../lib/page-utils";

const coreTabsConfig: Array<{ id: Tab; label: string; icon: ElementType }> = [
  { id: "setup", label: "Setup & LLM", icon: KeyRound },
  { id: "run", label: "Run", icon: Play },
  { id: "algorithms", label: "Algorithms", icon: Brain },
  { id: "pipeline", label: "Pipeline", icon: Layers },
  { id: "records", label: "Records", icon: Table2 },
  { id: "search", label: "Search", icon: Search },
];
const toolTabsConfig: Array<{ id: Tab; label: string; icon: ElementType }> = [
  { id: "tools", label: "Download Tools", icon: Download },
  { id: "dbmanager", label: "DB Manager", icon: Database },
  { id: "envconfig", label: "ENV Config", icon: Settings },
  { id: "agentreach", label: "Agent-Reach", icon: Zap },
];
const allTabs = [...coreTabsConfig, ...toolTabsConfig];
const tabIds = new Set<Tab>(allTabs.map((item) => item.id));

const emptyLLM: LLMSettings = {
  provider: "disabled",
  model: "",
  api_key: "",
  base_url: "",
  temperature: 0,
  timeout_seconds: 45,
  max_concurrency: 5,
  extra_headers: {}
};
const RUN_DRAFT_KEY = "asagus_run_form_draft";

type RunDraft = {
  query: string;
  location: string;
  limit: string;
  max_pages: string;
  mode: string;
  antibot_preset: string;
  discovery_mode: string;
  lead_target: string;
  website_filter: string;
  proxy_strategy: string;
  allowed_domains: string;
  blocked_domains: string;
  decision_maker_titles: string;
  recipe_set: string;
  resource_profile: string;
  worker_count: string;
  max_browser_actions: string;
  max_seconds_per_page: string;
  max_pages_per_domain: string;
  llm_enabled: boolean;
  archive_raw_html: boolean;
  capture_dom_fingerprint: boolean;
  capture_device_stamp: boolean;
  manual_review_on_challenge: boolean;
  screenshot_on_failure: boolean;
  respect_robots_txt: boolean;
  skip_existing: boolean;
  include_contact_pages: boolean;
  include_social_profiles: boolean;
  require_email: boolean;
  store_partial_records: boolean;
  enable_network_fetch: boolean;
  enable_search_discovery: boolean;
  social_auth_mode: string;
  social_auth_platforms: string[];
  social_auth_session_label: string;
  social_auth_required: boolean;
};

const defaultRunDraft: RunDraft = {
  query: "restaurants",
  location: "Lahore",
  limit: "100",
  max_pages: "",
  mode: "balanced",
  antibot_preset: "balanced",
  discovery_mode: "website_first",
  lead_target: "businesses",
  website_filter: "any",
  proxy_strategy: "auto",
  allowed_domains: "",
  blocked_domains: "",
  decision_maker_titles: "owner, founder, CEO",
  recipe_set: "business",
  resource_profile: "normal",
  worker_count: "",
  max_browser_actions: "10",
  max_seconds_per_page: "30",
  max_pages_per_domain: "",
  llm_enabled: true,
  archive_raw_html: true,
  capture_dom_fingerprint: true,
  capture_device_stamp: true,
  manual_review_on_challenge: true,
  screenshot_on_failure: false,
  respect_robots_txt: true,
  skip_existing: true,
  include_contact_pages: true,
  include_social_profiles: true,
  require_email: false,
  store_partial_records: true,
  enable_network_fetch: true,
  enable_search_discovery: true,
  social_auth_mode: "public",
  social_auth_platforms: ["facebook", "instagram"],
  social_auth_session_label: "default",
  social_auth_required: false,
};

function outreachFitScore(record: RecordRow) {
  const raw = record.raw_fields || {};
  const profileValue = raw.outreach_profile;
  const profile =
    profileValue && typeof profileValue === "object" && !Array.isArray(profileValue)
      ? (profileValue as Record<string, unknown>)
      : {};
  return Number(raw.outreach_fit_score ?? profile.score ?? 0) || 0;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("setup");
  const [layers, setLayers] = useState<Array<{ id: number; key: string; name: string; status: string }>>([]);
  const [health, setHealth] = useState<{ status: string; services: Record<string, string> }>({ status: "checking", services: {} });
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode | null>(null);
  const [realDefaultsHydrated, setRealDefaultsHydrated] = useState(false);
  const [realFetch, setRealFetch] = useState(false);
  const [realDiscovery, setRealDiscovery] = useState(false);
  const [antibotPreset, setAntibotPreset] = useState("balanced");
  const [runDraft, setRunDraft] = useState<RunDraft>(defaultRunDraft);
  const [runFormVersion, setRunFormVersion] = useState(0);
  const [jobFilter, setJobFilter] = useState("");
  const [jobSort, setJobSort] = useState("newest");
  const [recordFilter, setRecordFilter] = useState("");
  const [recordSort, setRecordSort] = useState("quality_desc");
  const [operatorToken, setOperatorToken] = useState("");
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<ScrapeJob | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [providers, setProviders] = useState<ProviderPreset[]>([]);
  const [algorithm, setAlgorithm] = useState<AlgorithmState | null>(null);
  const [metricsRows, setMetricsRows] = useState<ObservabilityMetric[]>([]);
  const [graphRows, setGraphRows] = useState<GraphCandidate[]>([]);
  const [llm, setLlm] = useState<LLMSettings>(emptyLLM);
  const [llmTest, setLlmTest] = useState("");
  const [llmSnippet, setLlmSnippet] = useState("");
  const [advancedRunOpen, setAdvancedRunOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{ record: RecordRow; score: number; highlights?: string[] }>>([]);
  const [summary, setSummary] = useState("");
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [toolRuns, setToolRuns] = useState<Record<string, ToolRunStatus>>({});
  const [toolRunning, setToolRunning] = useState<Record<string, boolean>>({});
  const [secondaryCount, setSecondaryCount] = useState(0);
  const [combinedCsvStatus, setCombinedCsvStatus] = useState("");
  const [envSettings, setEnvSettings] = useState<Record<string, { value: string; set: boolean }>>({});
  const [envEdits, setEnvEdits] = useState<Record<string, string>>({});
  const [envSaving, setEnvSaving] = useState(false);
  const [envMsg, setEnvMsg] = useState("");
  const [pkgName, setPkgName] = useState("");
  const [pkgResult, setPkgResult] = useState("");
  const [pkgRunning, setPkgRunning] = useState(false);
  const selectedJobIdRef = useRef<string | null>(null);

  const activeJob = selectedJob || jobs[0] || null;
  const activeProgress = activeJob ? jobProgress(activeJob) : null;
  const currentPreset = providers.find((provider) => provider.provider === llm.provider);
  const completed = jobs.filter((job) => job.status === "completed").length;
  const running = jobs.filter((job) => job.status === "running").length;
  const backendRealFetch = runtimeMode?.network_fetch_enabled ?? health.services.network_fetch === "enabled";
  const backendRealDiscovery = runtimeMode?.search_discovery_enabled ?? health.services.search_discovery === "enabled";
  const realScrapingEnabled = realFetch && realDiscovery;
  const isGatewayProvider = llm.provider === "openai_compatible" || llm.provider === "custom_http";
  const providerLabel = providers.find((provider) => provider.provider === llm.provider)?.label || llm.provider;
  const latestJob = jobs[0] || null;
  const serviceRows = Object.entries(health.services).sort(([a], [b]) => a.localeCompare(b));
  const socialAuthActive = runDraft.social_auth_mode === "authenticated";
  const backendConnected = health.status === "ok";
  const serviceCount = Object.keys(health.services).length;
  const llmReady =
    llm.provider === "disabled"
      ? false
      : llm.provider === "ollama"
        ? Boolean(llm.model)
        : isGatewayProvider
          ? Boolean(llm.model && llm.base_url && (llm.has_api_key || llm.api_key || llm.provider === "custom_http"))
          : Boolean(llm.model && (llm.has_api_key || llm.api_key));
  const readinessRows = [
    {
      label: "Network",
      value: realFetch ? "Real fetch" : "Preview fetch",
      tone: realFetch ? "ok" : "warn",
      icon: Globe2,
    },
    {
      label: "Discovery",
      value: realDiscovery ? "Live discovery" : "Seed preview",
      tone: realDiscovery ? "ok" : "warn",
      icon: Search,
    },
    {
      label: "LLM",
      value: llmReady ? providerLabel : "Rules only",
      tone: llmReady ? "ok" : "info",
      icon: Brain,
    },
    {
      label: "Social",
      value: socialAuthActive ? "Saved login" : "Public",
      tone: socialAuthActive ? "ok" : "info",
      icon: KeyRound,
    },
  ];
  const filteredJobs = useMemo(() => {
    const needle = jobFilter.trim().toLowerCase();
    const rows = needle
      ? jobs.filter((job) =>
          [
            job.status,
            job.request.query,
            job.request.location,
            job.request.mode,
            job.request.antibot_preset || "",
            job.request.social_auth_mode || "",
            (job.request.social_auth_platforms || []).join(" "),
          ].some((value) => String(value || "").toLowerCase().includes(needle))
        )
      : jobs;
    return [...rows].sort((a, b) => {
      if (jobSort === "records") return b.records_found - a.records_found;
      if (jobSort === "status") return a.status.localeCompare(b.status);
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [jobFilter, jobSort, jobs]);
  const filteredRecords = useMemo(() => {
    const needle = recordFilter.trim().toLowerCase();
    const rows = needle
      ? records.filter((record) =>
          [
            record.name,
            record.email,
            record.phone,
            record.whatsapp,
            record.city,
            record.category,
            record.website_url,
            record.source_url,
          ].some((value) => String(value || "").toLowerCase().includes(needle))
        )
      : records;
    return [...rows].sort((a, b) => {
      if (recordSort === "name_asc") return (a.name || "").localeCompare(b.name || "");
      if (recordSort === "city_asc") return (a.city || "").localeCompare(b.city || "");
      if (recordSort === "confidence_desc") return (b.confidence || 0) - (a.confidence || 0);
      if (recordSort === "outreach_desc") return outreachFitScore(b) - outreachFitScore(a);
      return (b.record_completeness || 0) - (a.record_completeness || 0);
    });
  }, [recordFilter, recordSort, records]);

  useEffect(() => {
    selectedJobIdRef.current = selectedJob?.id || null;
  }, [selectedJob?.id]);

  useEffect(() => {
    setOperatorToken(api.getOperatorToken());
    try {
      const saved = window.localStorage.getItem(RUN_DRAFT_KEY);
      if (saved) {
        const parsed = { ...defaultRunDraft, ...JSON.parse(saved) } as RunDraft;
        setRunDraft(parsed);
        setAntibotPreset(parsed.antibot_preset);
        setRealFetch(parsed.enable_network_fetch);
        setRealDiscovery(parsed.enable_search_discovery);
        setRealDefaultsHydrated(true);
        setRunFormVersion((version) => version + 1);
      }
    } catch {
      window.localStorage.removeItem(RUN_DRAFT_KEY);
    }
    const fromHash = window.location.hash.replace("#", "") as Tab;
    if (tabIds.has(fromHash)) setTab(fromHash);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const fromHash = window.location.hash.replace("#", "") as Tab;
      if (tabIds.has(fromHash)) setTab(fromHash);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function selectTab(nextTab: Tab) {
    setTab(nextTab);
    window.history.replaceState(null, "", `#${nextTab}`);
  }

  function runDraftFromForm(form: HTMLFormElement): RunDraft {
    const formData = new FormData(form);
    const discoveryMode = String(formData.get("discovery_mode") || defaultRunDraft.discovery_mode);
    const websiteFilter = discoveryMode === "social_only"
      ? "no_website"
      : String(formData.get("website_filter") || defaultRunDraft.website_filter);
    return {
      query: String(formData.get("query") || defaultRunDraft.query),
      location: String(formData.get("location") || defaultRunDraft.location),
      limit: String(formData.get("limit") || defaultRunDraft.limit),
      max_pages: String(formData.get("max_pages") || ""),
      mode: String(formData.get("mode") || defaultRunDraft.mode),
      antibot_preset: String(formData.get("antibot_preset") || antibotPreset),
      discovery_mode: discoveryMode,
      lead_target: String(formData.get("lead_target") || defaultRunDraft.lead_target),
      website_filter: websiteFilter,
      proxy_strategy: String(formData.get("proxy_strategy") || defaultRunDraft.proxy_strategy),
      allowed_domains: String(formData.get("allowed_domains") || ""),
      blocked_domains: String(formData.get("blocked_domains") || ""),
      decision_maker_titles: String(formData.get("decision_maker_titles") || defaultRunDraft.decision_maker_titles),
      recipe_set: String(formData.get("recipe_set") || defaultRunDraft.recipe_set),
      resource_profile: String(formData.get("resource_profile") || defaultRunDraft.resource_profile),
      worker_count: String(formData.get("worker_count") || ""),
      max_browser_actions: String(formData.get("max_browser_actions") || defaultRunDraft.max_browser_actions),
      max_seconds_per_page: String(formData.get("max_seconds_per_page") || defaultRunDraft.max_seconds_per_page),
      max_pages_per_domain: String(formData.get("max_pages_per_domain") || ""),
      llm_enabled: formData.get("llm_enabled") === "on",
      archive_raw_html: formData.get("archive_raw_html") === "on",
      capture_dom_fingerprint: formData.get("capture_dom_fingerprint") === "on",
      capture_device_stamp: formData.get("capture_device_stamp") === "on",
      manual_review_on_challenge: formData.get("manual_review_on_challenge") === "on",
      screenshot_on_failure: formData.get("screenshot_on_failure") === "on",
      respect_robots_txt: formData.get("respect_robots_txt") === "on",
      skip_existing: formData.get("skip_existing") === "on",
      include_contact_pages: formData.get("include_contact_pages") === "on",
      include_social_profiles: formData.get("include_social_profiles") === "on",
      require_email: formData.get("require_email") === "on",
      store_partial_records: formData.get("store_partial_records") === "on",
      enable_network_fetch: formData.get("enable_network_fetch") === "on",
      enable_search_discovery: formData.get("enable_search_discovery") === "on",
      social_auth_mode: String(formData.get("social_auth_mode") || defaultRunDraft.social_auth_mode),
      social_auth_platforms: formData.getAll("social_auth_platforms").map(String),
      social_auth_session_label: String(formData.get("social_auth_session_label") || defaultRunDraft.social_auth_session_label),
      social_auth_required: formData.get("social_auth_required") === "on",
    };
  }

  function persistRunDraft(form: HTMLFormElement) {
    const nextDraft = runDraftFromForm(form);
    setRunDraft(nextDraft);
    window.localStorage.setItem(RUN_DRAFT_KEY, JSON.stringify(nextDraft));
  }

  async function retryConnection() {
    setError("");
    await loadHealth();
    await loadSetup();
    await refreshLive(true);
  }

  useEffect(() => {
    if (realDefaultsHydrated || !("network_fetch" in health.services) || !("search_discovery" in health.services)) {
      return;
    }
    setRealFetch(backendRealFetch);
    setRealDiscovery(backendRealDiscovery);
    setRealDefaultsHydrated(true);
  }, [backendRealDiscovery, backendRealFetch, health.services, realDefaultsHydrated]);

  async function loadSetup() {
    try {
      const [blueprint, llmData, providerData] = await Promise.all([api.blueprint(), api.getLLM(), api.providers()]);
      setLayers(blueprint.layers);
      setLlm({ ...emptyLLM, ...llmData, api_key: "" });
      setProviders(providerData.providers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load setup");
    }
  }

  async function loadHealth() {
    try {
      const [healthData, modeData] = await Promise.all([api.health(), api.runtimeMode()]);
      setHealth(healthData);
      setRuntimeMode(modeData);
    } catch (err) {
      setHealth({ status: "degraded", services: {} });
    }
  }

  async function loadAlgorithms() {
    try {
      const [algorithmData, obsData, graphData] = await Promise.all([
        api.algorithmState(),
        api.observability(),
        api.graphCandidates()
      ]);
      setAlgorithm(algorithmData);
      setMetricsRows(obsData.metrics);
      setGraphRows(graphData.candidates);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load algorithms");
    }
  }

  async function loadRecords() {
    try {
      const recordData = await api.records();
      setRecords(recordData.records);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load records");
    }
  }

  async function refreshLive(includeRecords = false) {
    setError("");
    try {
      const jobRows = await api.jobs();
      setJobs(jobRows);

      const jobForEvents = selectedJobIdRef.current || jobRows[0]?.id;
      if (jobForEvents) {
        const detail = await api.job(jobForEvents);
        setSelectedJob(detail.job);
        setEvents(detail.events);
      }
      if (includeRecords) {
        await loadRecords();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh");
    }
  }

  async function refreshCurrent() {
    await refreshLive(tab === "records" || tab === "search");
    await loadHealth();
    if (tab === "setup" || tab === "run") await loadSetup();
    if (tab === "algorithms") await loadAlgorithms();
    if (tab === "records") await loadRecords();
  }

  useEffect(() => {
    loadSetup();
    loadHealth();
    refreshLive(true);
    const timer = window.setInterval(() => refreshLive(false), 5000);
    const healthTimer = window.setInterval(loadHealth, 30000);
    return () => {
      window.clearInterval(timer);
      window.clearInterval(healthTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (tab === "algorithms") loadAlgorithms();
    if (tab === "records" || tab === "search") loadRecords();
    if (tab === "setup" || tab === "run") loadSetup();
    if (tab === "tools") loadTools();
    if (tab === "dbmanager") loadSecondaryCount();
    if (tab === "envconfig") loadEnvSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const metrics = useMemo(
    () => [
      { label: "Running", value: running.toString(), tone: "info" },
      { label: "Completed", value: completed.toString(), tone: "ok" },
      { label: "Records", value: records.length.toString(), tone: "info" },
      { label: "Mode", value: realScrapingEnabled ? "Real" : "Preview", tone: realScrapingEnabled ? "ok" : "warn" },
      { label: "LLM", value: llm.provider === "disabled" ? "Off" : llm.provider, tone: llmReady ? "ok" : "warn" }
    ],
    [completed, llm.provider, llmReady, realScrapingEnabled, records.length, running]
  );

  async function startJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const selectedMode = String(form.get("mode") || "balanced");
    const submittedDiscoveryMode = String(form.get("discovery_mode") || "website_first");
    const discoveryMode = selectedMode === "max" && submittedDiscoveryMode === "social_only"
      ? "website_first"
      : submittedDiscoveryMode;
    const websiteFilter = discoveryMode === "social_only"
      ? "no_website"
      : String(form.get("website_filter") || "any");
    persistRunDraft(event.currentTarget);
    try {
      const job = await api.startJob({
        query: String(form.get("query") || ""),
        location: String(form.get("location") || ""),
        limit: Number(form.get("limit") || 100),
        max_pages: Number(form.get("max_pages") || 0),
        mode: selectedMode,
        antibot_preset: selectedMode === "max" ? "high-stealth" : String(form.get("antibot_preset") || antibotPreset),
        discovery_mode: discoveryMode,
        lead_target: String(form.get("lead_target") || "businesses"),
        website_filter: websiteFilter,
        decision_maker_titles: String(form.get("decision_maker_titles") || "owner, founder, CEO"),
        proxy_strategy: String(form.get("proxy_strategy") || "auto"),
        llm_enabled: form.get("llm_enabled") === "on",
        archive_raw_html: form.get("archive_raw_html") === "on",
        capture_dom_fingerprint: form.get("capture_dom_fingerprint") === "on",
        capture_device_stamp: form.get("capture_device_stamp") === "on",
        screenshot_on_failure: form.get("screenshot_on_failure") === "on",
        manual_review_on_challenge: form.get("manual_review_on_challenge") === "on",
        max_browser_actions: selectedMode === "max" ? 50 : Number(form.get("max_browser_actions") || 10),
        max_seconds_per_page: selectedMode === "max" ? Math.max(60, Number(form.get("max_seconds_per_page") || 30)) : Number(form.get("max_seconds_per_page") || 30),
        max_pages_per_domain: Number(form.get("max_pages_per_domain") || 0),
        recipe_set: String(form.get("recipe_set") || "business"),
        resource_profile: selectedMode === "max" ? "high" : String(form.get("resource_profile") || "normal"),
        worker_count: Number(form.get("worker_count") || 0),
        respect_robots_txt: form.get("respect_robots_txt") === "on",
        skip_existing: form.get("skip_existing") === "on",
        include_contact_pages: form.get("include_contact_pages") === "on",
        include_social_profiles: form.get("include_social_profiles") === "on",
        require_email: form.get("require_email") === "on",
        store_partial_records: form.get("store_partial_records") === "on",
        enable_network_fetch: realFetch,
        enable_search_discovery: realDiscovery,
        social_auth_mode: String(form.get("social_auth_mode") || "public"),
        social_auth_platforms: form.getAll("social_auth_platforms").map(String),
        social_auth_session_label: String(form.get("social_auth_session_label") || "default"),
        social_auth_required: form.get("social_auth_required") === "on",
        allowed_domains: csv(form.get("allowed_domains")),
        blocked_domains: csv(form.get("blocked_domains"))
      });
      setSelectedJob(job);
      selectTab("pipeline");
      await refreshLive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start job");
    } finally {
      setBusy(false);
    }
  }

  async function saveLLM(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const saved = await api.saveLLM(llm);
      setLlm({ ...emptyLLM, ...saved, api_key: "" });
      setLlmTest("Provider saved");
      await loadSetup();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save LLM settings");
    } finally {
      setBusy(false);
    }
  }

  async function testLLM() {
    setBusy(true);
    setError("");
    setLlmTest("");
    try {
      const result = await api.testLLM();
      setLlmTest(`${result.ok ? "OK" : "Failed"}: ${result.message}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "LLM test failed");
    } finally {
      setBusy(false);
    }
  }

  async function cancelJob(jobId: string) {
    setBusy(true);
    setError("");
    try {
      const cancelled = await api.cancelJob(jobId);
      setSelectedJob(cancelled);
      await refreshLive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to stop job");
    } finally {
      setBusy(false);
    }
  }

  async function deleteJob(jobId: string) {
    if (!window.confirm("Delete this job history and its raw HTML archive folder? Running jobs must be stopped first.")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteJob(jobId);
      if (selectedJob?.id === jobId) {
        setSelectedJob(null);
        setEvents([]);
      }
      await refreshLive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete job");
    } finally {
      setBusy(false);
    }
  }

  async function clearJobs() {
    if (!window.confirm("Delete all previous job history, event logs, and raw HTML archive folders?")) return;
    setBusy(true);
    setError("");
    try {
      await api.clearJobs();
      setSelectedJob(null);
      setEvents([]);
      await refreshLive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to clear jobs");
    } finally {
      setBusy(false);
    }
  }

  async function deleteRecord(recordId: string) {
    if (!window.confirm("Delete this record from local storage?")) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteRecord(recordId);
      await loadRecords();
      await refreshLive(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete record");
    } finally {
      setBusy(false);
    }
  }

  async function clearRecords() {
    if (!window.confirm("Delete all stored records from local storage? Job history and raw HTML archives stay unless cleared separately.")) return;
    setBusy(true);
    setError("");
    try {
      await api.clearRecords();
      await loadRecords();
      await refreshLive(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to clear records");
    } finally {
      setBusy(false);
    }
  }

  async function clearLocalData() {
    if (!window.confirm("Delete ALL local jobs, events, records, and raw HTML archive folders? This cannot be undone.")) return;
    setBusy(true);
    setError("");
    try {
      await api.clearLocalData();
      setSelectedJob(null);
      setEvents([]);
      setRecords([]);
      await refreshLive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to clear local data");
    } finally {
      setBusy(false);
    }
  }

  async function runSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await api.search({
        query: String(form.get("search") || ""),
        city: String(form.get("city") || ""),
        category: String(form.get("category") || ""),
        has_website: form.get("has_website") === "any" ? null : form.get("has_website") === "yes",
        has_whatsapp: form.get("has_whatsapp") === "any" ? null : form.get("has_whatsapp") === "yes",
        top_k: Number(form.get("top_k") || 20),
        rerank: form.get("rerank") === "on"
      });
      setSearchResults(result.results);
      setSummary(result.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  function chooseProvider(provider: ProviderPreset) {
    setLlm({
      ...llm,
      provider: provider.provider,
      model: provider.example_models[0] || llm.model || "",
      base_url: provider.default_base_url || ""
    });
  }

  function importLLMSnippet() {
    const imported = parseLLMSnippet(llmSnippet);
    if (!imported.found.length) {
      setLlmTest("Failed: no base_url, api_key or model was found in the pasted code");
      return;
    }
    setLlm({
      ...llm,
      provider: imported.provider || llm.provider,
      base_url: imported.base_url ?? llm.base_url,
      api_key: imported.api_key ?? llm.api_key,
      model: imported.model ?? llm.model,
      temperature: imported.temperature ?? llm.temperature,
    });
    setLlmTest(`Imported: ${imported.found.join(", ")}`);
  }

  function saveOperatorToken() {
    api.setOperatorToken(operatorToken);
    setError(operatorToken.trim() ? "Operator token saved in this browser" : "Operator token cleared");
  }

  async function loadTools() {
    try {
      const result = await api.listTools();
      setTools(result.tools);
    } catch { /* ignore if backend not reachable */ }
  }

  async function loadSecondaryCount() {
    try {
      const result = await api.secondaryRecords();
      setSecondaryCount(result.count);
    } catch { /* ignore */ }
  }

  async function loadEnvSettings() {
    try {
      const result = await api.getEnvSettings();
      const typed: Record<string, { value: string; set: boolean }> = {};
      for (const [k, v] of Object.entries(result)) {
        if (k.startsWith("_")) continue;
        typed[k] = typeof v === "object" && v !== null && "value" in (v as object)
          ? (v as { value: string; set: boolean })
          : { value: String(v), set: Boolean(v) };
      }
      setEnvSettings(typed);
    } catch { /* ignore */ }
  }

  async function saveEnvSettings() {
    setEnvSaving(true);
    setEnvMsg("");
    try {
      const result = await api.saveEnvSettings(envEdits);
      setEnvMsg(`✓ Saved ${result.updated_keys.length} settings to ${result.env_path}. Restart backend to apply.`);
      setEnvEdits({});
      await loadEnvSettings();
    } catch (err) {
      setEnvMsg(`Error: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setEnvSaving(false);
    }
  }

  async function runTool(toolId: string) {
    setToolRunning((prev) => ({ ...prev, [toolId]: true }));
    try {
      const run = await api.runTool(toolId);
      // Poll status
      const poll = setInterval(async () => {
        try {
          const status = await api.toolStatus(run.run_id);
          setToolRuns((prev) => ({ ...prev, [toolId]: status }));
          if (status.status !== "running") {
            clearInterval(poll);
            setToolRunning((prev) => ({ ...prev, [toolId]: false }));
          }
        } catch {
          clearInterval(poll);
          setToolRunning((prev) => ({ ...prev, [toolId]: false }));
        }
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start tool");
      setToolRunning((prev) => ({ ...prev, [toolId]: false }));
    }
  }

  async function killTool(toolId: string, runId: string) {
    try {
      await api.killTool(runId);
      setToolRunning((prev) => ({ ...prev, [toolId]: false }));
      setToolRuns((prev) => ({ ...prev, [toolId]: { ...prev[toolId], status: "killed" } as ToolRunStatus }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to kill tool");
    }
  }

  async function installPackage() {
    if (!pkgName.trim()) return;
    setPkgRunning(true);
    setPkgResult("");
    try {
      const result = await api.installPackage(pkgName.trim());
      setPkgResult(result.ok ? `✓ Installed ${result.package}\n${result.stdout}` : `✗ Failed\n${result.stderr}`);
    } catch (err) {
      setPkgResult(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    } finally {
      setPkgRunning(false);
    }
  }

  async function buildCombinedCsv(jobId?: string | null) {
    const id = jobId || activeJob?.id || latestJob?.id;
    if (!id) {
      setError("Start or select a job before building a combined CSV.");
      return;
    }
    setCombinedCsvStatus("Building combined CSV...");
    try {
      const result = await api.buildCombinedCSV(id);
      setCombinedCsvStatus(`Combined CSV ready: ${result.records_merged ?? 0} records`);
    } catch (err) {
      setCombinedCsvStatus(`Error: ${err instanceof Error ? err.message : "combined CSV failed"}`);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">A3</div>
          <div>
            <strong>ASAGUS Scraper</strong>
            <span>v3.0 · Operator</span>
          </div>
        </div>
        <nav className="nav">
          <div className="nav-section">Core</div>
          {coreTabsConfig.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => selectTab(item.id)}>
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
          <div className="nav-section" style={{ marginTop: "8px" }}>Tools & Config</div>
          {toolTabsConfig.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={`${tab === item.id ? "active" : ""}`} onClick={() => selectTab(item.id)}>
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1>{titleFor(tab)}</h1>
            <span className={`pill ${health.status === "ok" ? "ok" : "warn"}`}>
              <ShieldCheck size={12} />
              {health.status}
            </span>
          </div>
          <div className="top-actions">
            {tab === "records" && records.length > 0 && (
              <>
                <button className="btn" onClick={() => openCSVDownload(api.exportRecordsCSV())} title="Download primary DB as CSV">
                  <FileText size={15} />
                  Export CSV
                </button>
                <button className="btn" onClick={() => openCSVDownload(api.exportSecondaryCSV())} title="Download all events DB as CSV">
                  <Database size={15} />
                  Full DB CSV
                </button>
                {activeJob && (
                  <button className="btn" onClick={() => openCSVDownload(api.exportCombinedCSV(activeJob.id))} title="Download ASAGUS primary rows plus MAX-mode tool rows">
                    <GitBranch size={15} />
                    Combined CSV
                  </button>
                )}
              </>
            )}
            <button className="btn" onClick={refreshCurrent} disabled={busy}>
              <RefreshCw size={15} />
              Refresh
            </button>
          </div>
        </header>

        <section className="content">
          {error ? (
            <div className="alert-banner">
              <AlertTriangle size={17} />
              <span>{error}</span>
              <button className="icon-btn" type="button" onClick={() => setError("")} aria-label="Dismiss error">
                <X size={15} />
              </button>
            </div>
          ) : null}
          <div className="metric-grid">
            {metrics.map((metric) => (
              <div className="metric" key={metric.label}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <span className={`pill ${metric.tone}`}>{metric.tone}</span>
              </div>
            ))}
          </div>
          <div className="status-strip">
            <span className={`pill ${backendRealFetch ? "ok" : "warn"}`}>Fetch default {backendRealFetch ? "on" : "off"}</span>
            <span className={`pill ${backendRealDiscovery ? "ok" : "warn"}`}>Discovery default {backendRealDiscovery ? "on" : "off"}</span>
            <span className={`pill ${llmReady ? "ok" : "warn"}`}>LLM {llmReady ? llm.provider : "off"}</span>
            <span className="muted">{runtimeMode?.message || "Backend status loading"}</span>
          </div>
          <div className={`connection-strip ${backendConnected ? "ok" : "warn"}`}>
            <div>
              <strong>{backendConnected ? "Backend connected" : "Backend needs attention"}</strong>
              <span>{backendConnected ? `${serviceCount} services reported` : "Retry after starting the API server or checking the backend URL."}</span>
            </div>
            <button className="btn" type="button" onClick={retryConnection} disabled={busy}>
              <RefreshCw size={16} />
              Retry connection
            </button>
          </div>

          <div className="overview-grid">
            <section className="overview-card">
              <div className="overview-title">
                <ShieldCheck size={16} />
                Scraping Access
              </div>
              <strong>{realScrapingEnabled ? "Real web scraping is on for the next job" : "Preview unless switches are enabled"}</strong>
              <div className="muted">
                Fetch default: {backendRealFetch ? "on" : "off"} / Discovery default: {backendRealDiscovery ? "on" : "off"}
              </div>
            </section>
            <section className="overview-card">
              <div className="overview-title">
                <Brain size={16} />
                LLM In Use
              </div>
              <strong>{llmReady ? providerLabel : "No LLM provider active"}</strong>
              <div className="muted">{llmReady ? llm.model || "model not set" : "Extraction uses rules and heuristics only"}</div>
            </section>
            <section className="overview-card">
              <div className="overview-title">
                <Layers size={16} />
                Latest Job
              </div>
              <strong>{latestJob ? `${latestJob.request.query} / ${latestJob.request.location}` : "No job yet"}</strong>
              <div className="muted">{latestJob ? `${latestJob.status}, ${latestJob.records_found}/${latestJob.request.limit} records` : "Start from Run"}</div>
            </section>
            <section className="overview-card">
              <div className="overview-title">
                <Database size={16} />
                Data Stored
              </div>
              <strong>{records.length} business records</strong>
              <div className="muted">Names, contacts, websites, social links, quality and source evidence</div>
            </section>
          </div>

          {tab === "setup" && (
            <div className="grid-2 wide-left">
              <section className="panel">
                <div className="panel-header">
                  <h2>LLM Provider</h2>
                  <span className={`pill ${llmReady ? "ok" : "warn"}`}>{llm.provider}</span>
                </div>
                {runtimeMode?.auth_required ? (
                  <div className="notice info">
                    Operator token is enabled on the backend. Save it here once so Start, Stop and Provider updates can be sent securely.
                  </div>
                ) : (
                  <div className="notice warn">
                    Operator token is not set. Local use is open; set `OPERATOR_TOKEN` before sharing this API.
                  </div>
                )}
                <div className="grid-2 equal auth-row">
                  <div className="field">
                    <label>Operator token</label>
                    <input className="input" type="password" value={operatorToken} onChange={(event) => setOperatorToken(event.target.value)} placeholder="required only when backend auth is enabled" />
                  </div>
                  <button className="btn" type="button" onClick={saveOperatorToken}>
                    <KeyRound size={16} />
                    Save Token
                  </button>
                </div>
                <form className="form-grid" onSubmit={saveLLM}>
                  <div className="grid-2 equal">
                    <div className="field">
                      <label>Provider</label>
                      <select
                        className="select"
                        value={llm.provider}
                        onChange={(event) => {
                          const preset = providers.find((item) => item.provider === event.target.value);
                          preset ? chooseProvider(preset) : setLlm({ ...llm, provider: event.target.value as LLMSettings["provider"] });
                        }}
                      >
                        <option value="disabled">Disabled</option>
                        {providers.map((provider) => (
                          <option value={provider.provider} key={provider.provider}>
                            {provider.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label>Model</label>
                      <input className="input" value={llm.model} onChange={(event) => setLlm({ ...llm, model: event.target.value })} placeholder={currentPreset?.example_models[0] || "model id"} />
                    </div>
                  </div>
                  <div className="field">
                    <label>API key</label>
                    <input className="input" type="password" value={llm.api_key || ""} onChange={(event) => setLlm({ ...llm, api_key: event.target.value })} placeholder={llm.has_api_key ? "saved for this backend session" : currentPreset?.key_hint || "paste key"} />
                  </div>
                  <div className="field">
                    <label>Base URL</label>
                    <input className="input" value={llm.base_url || ""} onChange={(event) => setLlm({ ...llm, base_url: event.target.value })} placeholder={currentPreset?.default_base_url || "optional gateway URL"} />
                    {currentPreset?.notes ? <div className="muted">{currentPreset.notes}</div> : null}
                  </div>
                  <div className="snippet-importer">
                    <div className="panel-header compact">
                      <h2>Import From Code</h2>
                      <span className="pill info">Python / Node / LangChain</span>
                    </div>
                    <textarea
                      className="textarea code-input"
                      value={llmSnippet}
                      onChange={(event) => setLlmSnippet(event.target.value)}
                      placeholder="Paste OpenAI SDK, LangChain, or Node code here. The app will read base_url, api_key, model and temperature."
                    />
                    <div className="button-row">
                      <button className="btn" type="button" onClick={importLLMSnippet}>
                        <Wand2 size={16} />
                        Fill Provider From Code
                      </button>
                      <button className="btn" type="button" onClick={() => setLlmSnippet("")}>
                        Clear Code
                      </button>
                    </div>
                    <div className="muted">Nothing is saved until Save Provider is clicked. Extra fields such as top_p, stream and max_tokens are ignored by the current extractor.</div>
                  </div>
                    <div className="grid-3">
                    <div className="field">
                      <label>Temperature</label>
                      <input className="input" type="number" step="0.1" min="0" max="2" value={llm.temperature} onChange={(event) => setLlm({ ...llm, temperature: Number(event.target.value) })} />
                    </div>
                    <div className="field">
                      <label>Timeout</label>
                      <input className="input" type="number" min="5" max="240" value={llm.timeout_seconds} onChange={(event) => setLlm({ ...llm, timeout_seconds: Number(event.target.value) })} />
                    </div>
                    <div className="field">
                      <label>Concurrency</label>
                      <input className="input" type="number" min="1" max="50" value={llm.max_concurrency} onChange={(event) => setLlm({ ...llm, max_concurrency: Number(event.target.value) })} />
                    </div>
                  </div>
                  {llmTest ? <div className={`notice ${llmTest.startsWith("OK") || llmTest === "Provider saved" ? "info" : "warn"}`}>{llmTest}</div> : null}
                  <div className="button-row">
                    <button className="btn primary" disabled={busy}>
                      <Settings size={16} />
                      Save Provider
                    </button>
                    <button className="btn" type="button" disabled={busy || !llmReady} onClick={testLLM}>
                      <ShieldCheck size={16} />
                      Test Provider
                    </button>
                  </div>
                </form>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Provider Library</h2>
                  <span className="pill">{providers.length}</span>
                </div>
                <div className="stack compact-list">
                  {providers.map((provider) => (
                    <button className="layer-row" key={provider.provider} onClick={() => chooseProvider(provider)}>
                      <div className="layer-id">
                        <KeyRound size={15} />
                      </div>
                      <div>
                        <strong>{provider.label}</strong>
                        <div className="muted">{provider.example_models[0] || provider.notes || provider.key_hint}</div>
                      </div>
                      <span className={`pill ${provider.local_only ? "info" : "ok"}`}>{provider.local_only ? "local" : "key"}</span>
                    </button>
                  ))}
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>Runtime & Services</h2>
                  <span className={`pill ${health.status === "ok" ? "ok" : "warn"}`}>{health.status}</span>
                </div>
                <KeyValueGrid
                  rows={[
                    ["environment", runtimeMode?.environment || "loading"],
                    ["auth_required", runtimeMode?.auth_required ? "yes" : "no"],
                    ["real_fetch_default", backendRealFetch ? "on" : "off"],
                    ["real_discovery_default", backendRealDiscovery ? "on" : "off"],
                    ["operator_api", "127.0.0.1:8000"],
                    ["frontend", "127.0.0.1:3000"],
                  ]}
                />
                <div className="service-grid">
                  {serviceRows.map(([name, value]) => (
                    <div className="service-row" key={name}>
                      <span>{name}</span>
                      <span className={`pill ${value === "enabled" || value === "optional" ? "ok" : value.includes("unreachable") ? "warn" : "info"}`}>{value}</span>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>Mode Guide</h2>
                  <span className="pill info">controls</span>
                </div>
                <div className="stack">
                  {Object.entries(runtimeMode?.modes || {}).map(([name, description]) => (
                    <div className="mode-row" key={name}>
                      <strong>{name}</strong>
                      <span className="muted">{description}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {tab === "run" && (
            <div className="grid-2 wide-left">
              <section className="panel">
                <div className="panel-header">
                  <h2>New Scrape</h2>
                  <span className="pill info">
                    <Brain size={14} />
                    MDP
                  </span>
                </div>
                <div className="notice info">Backend defaults are preview-safe. Use the Real fetch and Real discovery switches per job for educational research runs.</div>
                <form key={runFormVersion} className="form-grid" onSubmit={startJob} onChange={(event) => persistRunDraft(event.currentTarget)}>
                  <div className="run-cockpit">
                    {readinessRows.map((item) => {
                      const Icon = item.icon;
                      return (
                        <div className="readiness-card" key={item.label}>
                          <div className={`readiness-icon ${item.tone}`}>
                            <Icon size={17} />
                          </div>
                          <span>{item.label}</span>
                          <strong>{item.value}</strong>
                        </div>
                      );
                    })}
                    <div className="readiness-card emphasis">
                      <div className="readiness-icon ok">
                        <CheckCircle2 size={17} />
                      </div>
                      <span>Scope</span>
                      <strong>Research mode</strong>
                    </div>
                  </div>
                  <div className="grid-2 equal">
                    <div className="field">
                      <label>Search</label>
                      <input className="input" name="query" defaultValue={runDraft.query} required />
                    </div>
                    <div className="field">
                      <label>Location</label>
                      <input className="input" name="location" defaultValue={runDraft.location} required />
                    </div>
                  </div>
                  <div className="grid-3">
                    <div className="field">
                      <label>Desired records</label>
                       <input className="input" name="limit" type="number" min={5} max={5000} defaultValue={runDraft.limit} />
                    </div>
                    <div className="field">
                      <label>Max pages</label>
                       <input className="input" name="max_pages" type="number" min={0} max={50000} defaultValue={runDraft.max_pages} placeholder="auto" />
                    </div>
                    <div className="field">
                      <label>Mode</label>
                      <select className="select" name="mode" defaultValue={runDraft.mode}>
                        <option value="balanced">Balanced</option>
                        <option value="fast">Fast</option>
                        <option value="focused">Focused</option>
                        <option value="adaptive">Adaptive</option>
                        <option value="deep">Deep</option>
                        <option value="deep_agent">Deep Agent</option>
                        <option value="parallel">Parallel</option>
                        <option value="comprehensive">Comprehensive</option>
                        <option value="research">Research</option>
                        <option value="max">MAX — All Resources, All Layers</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Anti-bot preset</label>
                      <select className="select" name="antibot_preset" value={antibotPreset} onChange={(event) => setAntibotPreset(event.target.value)}>
                        <option value="high-stealth">High stealth</option>
                        <option value="balanced">Balanced</option>
                        <option value="high-speed">High speed</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Discovery</label>
                      <select className="select" name="discovery_mode" defaultValue={runDraft.discovery_mode}>
                        <option value="website_first">Website first</option>
                        <option value="social_first">Social first</option>
                        <option value="social_only">Social only: no owned website</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Target</label>
                      <select className="select" name="lead_target" defaultValue={runDraft.lead_target}>
                        <option value="businesses">Businesses</option>
                        <option value="decision_makers">Owners / CEOs</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Website</label>
                      <select className="select" name="website_filter" defaultValue={runDraft.website_filter}>
                        <option value="any">Any website status</option>
                        <option value="no_website">No owned website</option>
                        <option value="has_website">Has owned website</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Proxy</label>
                      <select className="select" name="proxy_strategy" defaultValue={runDraft.proxy_strategy}>
                        <option value="auto">Auto</option>
                        <option value="none">None</option>
                        <option value="residential">Residential</option>
                        <option value="isp_static">ISP Static</option>
                        <option value="datacenter">Datacenter</option>
                      </select>
                    </div>
                  </div>
                  <div className="preset-grid">
                    <div className={`preset-card ${antibotPreset === "high-stealth" ? "active" : ""}`}>
                      <ShieldCheck size={17} />
                      <strong>High stealth</strong>
                      <span>Prefers Camoufox when available; manual review stays on for challenges.</span>
                    </div>
                    <div className={`preset-card ${antibotPreset === "balanced" ? "active" : ""}`}>
                      <SlidersHorizontal size={17} />
                      <strong>Balanced</strong>
                      <span>Prefers Patchright with static HTTP impersonation fallback.</span>
                    </div>
                    <div className={`preset-card ${antibotPreset === "high-speed" ? "active" : ""}`}>
                      <Cpu size={17} />
                      <strong>High speed</strong>
                      <span>Fast local renderer path for broad educational sweeps.</span>
                    </div>
                  </div>
                  <div className="grid-2 equal">
                    <div className="field">
                      <label>Allowed domains</label>
                      <input className="input" name="allowed_domains" defaultValue={runDraft.allowed_domains} placeholder="optional, comma separated" />
                    </div>
                    <div className="field">
                      <label>Blocked domains</label>
                      <input className="input" name="blocked_domains" defaultValue={runDraft.blocked_domains} placeholder="optional, comma separated" />
                    </div>
                    <div className="field">
                      <label>Decision-maker titles</label>
                      <input className="input" name="decision_maker_titles" defaultValue={runDraft.decision_maker_titles} />
                    </div>
                  </div>
                  <button className="advanced-toggle" type="button" onClick={() => setAdvancedRunOpen((open) => !open)}>
                    <span>
                      <ChevronDown size={16} className={advancedRunOpen ? "rotate" : ""} />
                      Advanced controls
                    </span>
                    <span className="pill info">{advancedRunOpen ? "shown" : "hidden"}</span>
                  </button>
                  <div className={`advanced-panel ${advancedRunOpen ? "open" : ""}`}>
                  <div className="control-band">
                    <div className="panel-header compact">
                      <h2>Mode Controls</h2>
                      <span className="pill info">frontend controlled</span>
                    </div>
                    <div className="grid-3">
                      <div className="field">
                        <label>Recipe</label>
                        <select className="select" name="recipe_set" defaultValue={runDraft.recipe_set}>
                          <option value="generic">Generic</option>
                          <option value="business">Business</option>
                          <option value="restaurant">Restaurant</option>
                          <option value="clinic">Clinic</option>
                          <option value="directory">Directory</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>CPU profile</label>
                        <select className="select" name="resource_profile" defaultValue={runDraft.resource_profile}>
                          <option value="low">Low</option>
                          <option value="normal">Normal</option>
                          <option value="high">High</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>Workers</label>
                        <input className="input" name="worker_count" type="number" min={0} max={128} defaultValue={runDraft.worker_count} placeholder="auto" />
                      </div>
                    </div>
                  <div className="grid-3">
                      <div className="field">
                        <label>Browser actions</label>
                        <input className="input" name="max_browser_actions" type="number" min={0} max={50} defaultValue={runDraft.max_browser_actions} />
                      </div>
                      <div className="field">
                        <label>Seconds/page</label>
                        <input className="input" name="max_seconds_per_page" type="number" min={5} max={180} defaultValue={runDraft.max_seconds_per_page} />
                      </div>
                      <div className="field">
                        <label>Pages/domain</label>
                        <input className="input" name="max_pages_per_domain" type="number" min={0} max={5000} defaultValue={runDraft.max_pages_per_domain} placeholder="unlimited" />
                      </div>
                    </div>
                  </div>
                  <div className="control-band">
                    <div className="panel-header compact">
                      <h2>Social Login Layer</h2>
                      <span className="pill info">isolated</span>
                    </div>
                    <div className="grid-3">
                      <div className="field">
                        <label>Login mode</label>
                        <select className="select" name="social_auth_mode" defaultValue={runDraft.social_auth_mode}>
                          <option value="public">Public only</option>
                          <option value="authenticated">Saved login</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>Session</label>
                        <input className="input" name="social_auth_session_label" defaultValue={runDraft.social_auth_session_label} maxLength={64} />
                      </div>
                      <div className="field">
                        <label>Platforms</label>
                        <div className="platform-checks">
                          <label className="mini-check">
                            <input
                              type="checkbox"
                              name="social_auth_platforms"
                              value="facebook"
                              defaultChecked={runDraft.social_auth_platforms.includes("facebook")}
                            />
                            <span>Facebook</span>
                          </label>
                          <label className="mini-check">
                            <input
                              type="checkbox"
                              name="social_auth_platforms"
                              value="instagram"
                              defaultChecked={runDraft.social_auth_platforms.includes("instagram")}
                            />
                            <span>Instagram</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="switch-grid">
                    <label className="switch">
                      <input type="checkbox" name="llm_enabled" defaultChecked={runDraft.llm_enabled} />
                      <span />
                      <strong>LLM fallback</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="archive_raw_html" defaultChecked={runDraft.archive_raw_html} />
                      <span />
                      <strong>Archive HTML</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="capture_dom_fingerprint" defaultChecked={runDraft.capture_dom_fingerprint} />
                      <span />
                      <strong>DOM stamp</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="capture_device_stamp" defaultChecked={runDraft.capture_device_stamp} />
                      <span />
                      <strong>Device stamp</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="manual_review_on_challenge" defaultChecked={runDraft.manual_review_on_challenge} />
                      <span />
                      <strong>Challenge review</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="screenshot_on_failure" defaultChecked={runDraft.screenshot_on_failure} />
                      <span />
                      <strong>Failure screenshot</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="respect_robots_txt" defaultChecked={runDraft.respect_robots_txt} />
                      <span />
                      <strong>Robots rules</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="skip_existing" defaultChecked={runDraft.skip_existing} />
                      <span />
                      <strong>Skip existing</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="include_contact_pages" defaultChecked={runDraft.include_contact_pages} />
                      <span />
                      <strong>Contact pages</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="include_social_profiles" defaultChecked={runDraft.include_social_profiles} />
                      <span />
                      <strong>Social profiles</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="social_auth_required" defaultChecked={runDraft.social_auth_required} />
                      <span />
                      <strong>Require social login</strong>
                    </label>
                    <label className="switch">
                      {/* Default OFF — requiring email drops 60-80% of valid leads */}
                      <input type="checkbox" name="require_email" defaultChecked={runDraft.require_email} />
                      <span />
                      <strong>Require email</strong>
                    </label>
                    <label className="switch">
                      <input type="checkbox" name="store_partial_records" defaultChecked={runDraft.store_partial_records} />
                      <span />
                      <strong>Keep partial leads</strong>
                    </label>
                    <label className="switch" title="Enable real HTTP fetching for this educational/research job">
                      <input
                        type="checkbox"
                        name="enable_network_fetch"
                        checked={realFetch}
                        onChange={(event) => setRealFetch(event.target.checked)}
                      />
                      <span />
                      <strong>Real fetch</strong>
                    </label>
                    <label className="switch" title="Enable DDGS search discovery for this educational/research job">
                      <input
                        type="checkbox"
                        name="enable_search_discovery"
                        checked={realDiscovery}
                        onChange={(event) => setRealDiscovery(event.target.checked)}
                      />
                      <span />
                      <strong>Real discovery</strong>
                    </label>
                  </div>
                  </div>
                  <button className="btn primary" disabled={busy}>
                    <Play size={16} />
                    Start
                  </button>
                </form>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Layer Stack</h2>
                  <span className="pill">{layers.length} layers</span>
                </div>
                <div className="stack compact-list">
                  {layers.length ? layers.map((layer) => (
                    <div className="layer-row" key={layer.key}>
                      <div className="layer-id">{layer.id}</div>
                      <div>
                        <strong>{layer.name}</strong>
                        <div className="muted">{layer.key}</div>
                      </div>
                      <span className="pill info">{layer.status}</span>
                    </div>
                  )) : <EmptyState title="Layer catalog unavailable" detail="Start or reconnect the backend to load the blueprint stack." />}
                </div>
                <div className="notice info">Every job goes through policy, discovery, compliance, fetch, extraction, enrichment, storage, indexing, retrieval, and AI application layers.</div>
              </section>
            </div>
          )}

          {tab === "algorithms" && algorithm && (
            <div className="grid-2">
              <section className="panel">
                <div className="panel-header">
                  <h2>MDP Scheduler</h2>
                  <span className="pill info">
                    <Network size={14} />
                    Frontier
                  </span>
                </div>
                <div className="stack">
                  {algorithm.mdp.cold_start_phases.map((phase) => (
                    <div className="layer-row" key={phase.phase}>
                      <div className="layer-id">{phase.phase}</div>
                      <div>
                        <strong>{phase.range}</strong>
                        <div className="muted">{phase.policy}</div>
                      </div>
                      <span className="pill info">eps {phase.epsilon}</span>
                    </div>
                  ))}
                </div>
                <KeyValueGrid
                  rows={[
                    ["state_space", algorithm.mdp.state_space_size || 0],
                    ["discount", algorithm.mdp.discount || 0],
                    ["iterations", algorithm.mdp.value_iteration_iterations || 0],
                    ["model", algorithm.mdp.markov_model || "MDP"]
                  ]}
                />
                <div className="tag-row">
                  {algorithm.mdp.frontier_tiers.map((tier) => (
                    <span className="pill" key={tier}>{tier}</span>
                  ))}
                </div>
                <div className="tag-row">
                  {(algorithm.mdp.outcomes || []).map((outcome) => (
                    <span className="pill info" key={outcome}>{outcome}</span>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Policy Engine</h2>
                  <span className="pill ok">rules + bayes</span>
                </div>
                <div className="tag-row">
                  {(algorithm.policy.rules as string[] | undefined)?.map((rule) => (
                    <span className="pill info" key={rule}>{rule}</span>
                  ))}
                </div>
                <KeyValueGrid rows={Object.entries(algorithm.policy).filter(([key]) => !["rules", "domains"].includes(key)).slice(0, 8)} />
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>MDP Policy Table</h2>
                  <span className="pill info">Q-values</span>
                </div>
                <div className="stack compact-list">
                  {(algorithm.mdp.policy_snapshot || []).slice(0, 10).map((row) => (
                    <div className="layer-row" key={row.state}>
                      <div className="layer-id">{Math.round(row.value)}</div>
                      <div>
                        <strong>{row.best_action}</strong>
                        <div className="muted">{row.state}</div>
                      </div>
                      <span className="pill">{row.value}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Extraction Cascade</h2>
                  <span className="pill info">
                    <Wand2 size={14} />
                    Self-heal
                  </span>
                </div>
                <div className="stack">
                  {algorithm.extraction.cascade.map((stage) => (
                    <div className="layer-row" key={stage.stage}>
                      <div className="layer-id">
                        <Sparkles size={15} />
                      </div>
                      <div>
                        <strong>{stage.stage}</strong>
                        <div className="muted">accept at {stage.accept_confidence}</div>
                      </div>
                      <span className="pill">{stage.accept_confidence}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Discovery & Throughput</h2>
                  <span className="pill info">
                    <Activity size={14} />
                    async + CPU
                  </span>
                </div>
                <KeyValueGrid rows={Object.entries(algorithm.throughput).slice(0, 8)} />
                {algorithm.accelerators ? <KeyValueGrid rows={Object.entries(algorithm.accelerators).slice(0, 6)} /> : null}
                <div className="tag-row">
                  {String(algorithm.discovery.engines || "")
                    .split(",")
                    .filter(Boolean)
                    .map((engine) => (
                      <span className="pill info" key={engine}>{engine.replace(/[\[\]'"]/g, "").trim()}</span>
                    ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Search Algorithms</h2>
                  <span className="pill ok">hybrid</span>
                </div>
                <div className="stack compact-list">
                  {algorithm.search_algorithms.map((item) => (
                    <div className="layer-row" key={item.name}>
                      <div className="layer-id">{item.year.toString().slice(-2)}</div>
                      <div>
                        <strong>{item.name}</strong>
                        <div className="muted">{item.role}</div>
                      </div>
                      <span className={`pill ${item.implementation_status === "implemented" ? "ok" : "info"}`}>{item.implementation_status}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Capability Map</h2>
                  <span className="pill">{algorithm.capabilities.length}</span>
                </div>
                <div className="stack compact-list">
                  {algorithm.capabilities.map((item) => (
                    <div className="layer-row" key={item.key}>
                      <div className="layer-id">{item.category.slice(0, 1).toUpperCase()}</div>
                      <div>
                        <strong>{item.name}</strong>
                        <div className="muted">{item.practical_use || item.source_module}</div>
                      </div>
                      <span className={`pill ${item.status === "implemented" ? "ok" : item.status === "guarded" ? "warn" : "info"}`}>{item.status}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>Proxy, Graph, Metrics</h2>
                  <span className="pill">{graphRows.length} edges</span>
                </div>
                <div className="tag-row">
                  {algorithm.proxy.tier_order.map((tier) => (
                    <span className="pill info" key={tier}>{tier}</span>
                  ))}
                </div>
                <div className="tag-row">
                  {algorithm.graph.relationships.map((relationship) => (
                    <span className="pill" key={relationship}>{relationship}</span>
                  ))}
                </div>
                <div className="metrics-list">
                  {metricsRows.slice(0, 6).map((metric) => (
                    <div className="mini-metric" key={metric.name}>
                      <span>{metric.name}</span>
                      <strong>{metric.value}{metric.unit}</strong>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {tab === "pipeline" && (
            <>
              {activeJob && activeProgress ? (
                <JobProgressPanel job={activeJob} progress={activeProgress} busy={busy} onCancel={cancelJob} onDelete={deleteJob} />
              ) : null}
              <div className="grid-2">
                <section className="panel">
                <div className="panel-header">
                  <h2>Jobs</h2>
                  <div className="button-row">
                    <span className="pill">{filteredJobs.length}/{jobs.length}</span>
                    <button className="btn danger" type="button" onClick={clearJobs} disabled={busy || jobs.length === 0}>
                      <Trash2 size={15} />
                      Clear Jobs
                    </button>
                    <button className="btn danger" type="button" onClick={clearLocalData} disabled={busy || (jobs.length === 0 && records.length === 0)}>
                      <Trash2 size={15} />
                      Clear All Data
                    </button>
                  </div>
                </div>
                <div className="filter-bar">
                  <div className="field">
                    <label>Filter jobs</label>
                    <input className="input" value={jobFilter} onChange={(event) => setJobFilter(event.target.value)} placeholder="status, query, city, preset" />
                  </div>
                  <div className="field">
                    <label>Sort</label>
                    <select className="select" value={jobSort} onChange={(event) => setJobSort(event.target.value)}>
                      <option value="newest">Newest</option>
                      <option value="records">Most records</option>
                      <option value="status">Status</option>
                    </select>
                  </div>
                </div>
                <div className="stack">
                  {filteredJobs.length ? filteredJobs.map((job) => (
                    <button className={`layer-row ${activeJob?.id === job.id ? "selected" : ""}`} key={job.id} onClick={() => setSelectedJob(job)}>
                      <div className="layer-id">{job.status.slice(0, 1).toUpperCase()}</div>
                      <div>
                        <strong>{job.request.query} / {job.request.location}</strong>
                        <div className="muted">
                          {job.processed_targets}/{job.total_targets} pages, {job.records_found}/{job.request.limit} records
                        </div>
                      </div>
                      <span className={`pill ${job.status === "completed" ? "ok" : job.status === "failed" ? "warn" : "info"}`}>{job.status}</span>
                    </button>
                  )) : <EmptyState title={jobs.length ? "No matching jobs" : "No jobs yet"} detail={jobs.length ? "Clear the filter or choose a different sort." : "Start a scrape from the Run tab and this timeline will populate."} />}
                </div>
                </section>
                <section className="panel">
                <div className="panel-header">
                  <h2>{activeJob ? activeJob.id.slice(0, 8) : "No job"}</h2>
                  {activeJob ? <span className="pill info">{activeJob.status}</span> : null}
                </div>
                <div className="stack event-list">
                  {events.length ? events.map((event) => (
                    <div className="event-row" key={event.id}>
                      <div className="inline">
                        <span className="pill info">{event.layer}</span>
                        <strong>{event.event_type}</strong>
                        <span className="muted">{new Date(event.created_at).toLocaleTimeString()}</span>
                      </div>
                      <div>{event.message}</div>
                      {Object.keys(event.payload || {}).length ? (
                        <details className="payload-details">
                          <summary>Details</summary>
                          <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                        </details>
                      ) : null}
                    </div>
                  )) : <EmptyState title="No events selected" detail="Pick a job from the list to inspect its pipeline events." />}
                </div>
                </section>
              </div>
            </>
          )}

          {tab === "records" && (
            <div className="grid-2 wide-left">
              <section className="panel">
                <div className="panel-header">
                  <h2>Business Records</h2>
                  <div className="button-row">
                    <span className="pill">{filteredRecords.length}/{records.length}</span>
                    <button className="btn danger" type="button" onClick={clearRecords} disabled={busy || records.length === 0}>
                      <Trash2 size={15} />
                      Clear Records
                    </button>
                  </div>
                </div>
                <div className="filter-bar">
                  <div className="field">
                    <label>Filter records</label>
                    <input className="input" value={recordFilter} onChange={(event) => setRecordFilter(event.target.value)} placeholder="name, city, email, phone, website" />
                  </div>
                  <div className="field">
                    <label>Sort</label>
                    <select className="select" value={recordSort} onChange={(event) => setRecordSort(event.target.value)}>
                      <option value="quality_desc">Best quality</option>
                      <option value="outreach_desc">Best outreach fit</option>
                      <option value="confidence_desc">Highest confidence</option>
                      <option value="name_asc">Name A-Z</option>
                      <option value="city_asc">City A-Z</option>
                    </select>
                  </div>
                </div>
                <RecordTable rows={filteredRecords} onDelete={deleteRecord} busy={busy} />
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>Data Captured</h2>
                  <span className="pill info">transparent</span>
                </div>
                <div className="stack">
                  {["Business name", "City and country", "Email, phone and WhatsApp", "Website and source URL", "Public social profiles", "Extraction method and confidence", "Duplicate, GDPR and PDPA flags", "Raw HTML archive when enabled"].map((item) => (
                    <div className="mode-row" key={item}>
                      <strong>{item}</strong>
                      <span className="muted">shown or stored when available</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {tab === "search" && (
            <div className="grid-2">
              <section className="panel">
                <div className="panel-header">
                  <h2>Hybrid Search</h2>
                  <span className="pill info">
                    <GitBranch size={14} />
                    BM25 + Dense + RRF
                  </span>
                </div>
                <form className="form-grid" onSubmit={runSearch}>
                  <div className="field">
                    <label>Query</label>
                    <input className="input" name="search" defaultValue="restaurants with WhatsApp no website" required />
                  </div>
                  <div className="grid-2 equal">
                    <div className="field">
                      <label>City</label>
                      <input className="input" name="city" placeholder="optional" />
                    </div>
                    <div className="field">
                      <label>Category</label>
                      <input className="input" name="category" placeholder="optional" />
                    </div>
                  </div>
                  <div className="grid-3">
                    <div className="field">
                      <label>Website</label>
                      <select className="select" name="has_website" defaultValue="any">
                        <option value="any">Any</option>
                        <option value="yes">Yes</option>
                        <option value="no">No</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>WhatsApp</label>
                      <select className="select" name="has_whatsapp" defaultValue="any">
                        <option value="any">Any</option>
                        <option value="yes">Yes</option>
                        <option value="no">No</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Top K</label>
                      <input className="input" name="top_k" type="number" min={1} max={100} defaultValue={20} />
                    </div>
                  </div>
                  <label className="check">
                    <input type="checkbox" name="rerank" defaultChecked />
                    Cross-encoder rerank policy
                  </label>
                  <button className="btn primary" disabled={busy}>
                    <Search size={16} />
                    Search
                  </button>
                </form>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>Results</h2>
                  <span className="pill">{searchResults.length}</span>
                </div>
                {summary ? <p>{summary}</p> : null}
                <RecordTable rows={searchResults.map((item) => item.record)} />
              </section>
            </div>
          )}

          {/* ─── TOOLS TAB ─────────────────────────────────────────────── */}
          {tab === "tools" && (
            <div className="grid-2 wide-left">
              <section className="panel">
                <div className="panel-header">
                  <h2>Download Tools</h2>
                  <span className="pill info">{tools.length} tools</span>
                </div>
                <div className="notice info" style={{ marginBottom: "14px" }}>
                  These tools are in your Download/ folder. Click Run to launch them as background subprocesses using the backend Python environment.
                </div>
                <div className="stack">
                  {tools.length === 0 && (
                    <div className="empty-state">
                      <Download size={32} />
                      <span>No tools found. Click Refresh to scan the Download folder.</span>
                    </div>
                  )}
                  {tools.map((tool) => {
                    const run = toolRuns[tool.id];
                    const running = toolRunning[tool.id];
                    return (
                      <div
                        key={tool.id}
                        className={`tool-card ${running || run?.status === "running" ? "running" : ""} ${!tool.available ? "unavailable" : ""}`}
                      >
                        <div className="tool-header">
                          <div>
                            <div className="tool-title">{tool.name}</div>
                            <div className="tool-desc">{tool.description}</div>
                          </div>
                          <div style={{ display: "flex", gap: "6px", alignItems: "center", flexShrink: 0 }}>
                            <span className={`pill ${tool.available ? "ok" : "danger"}`}>
                              {tool.available ? "available" : "missing"}
                            </span>
                            <span className="pill violet">{tool.category}</span>
                            {tool.available && !running && run?.status !== "running" && (
                              <button className="btn primary compact-btn" onClick={() => runTool(tool.id)}>
                                <Play size={13} /> Run
                              </button>
                            )}
                            {(running || run?.status === "running") && (
                              <button className="btn danger compact-btn" onClick={() => run?.run_id && killTool(tool.id, run.run_id)}>
                                <X size={13} /> Kill
                              </button>
                            )}
                          </div>
                        </div>
                        {tool.entry_point && (
                          <div className="muted" style={{ fontSize: "11px", fontFamily: "monospace" }}>
                            Entry: {tool.entry_point}
                          </div>
                        )}
                        {run && (
                          <div>
                            <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
                              <span className={`pill ${run.status === "completed" ? "ok" : run.status === "failed" ? "danger" : run.status === "running" ? "info" : ""}`}>
                                {run.status}
                              </span>
                              {run.exit_code !== null && run.exit_code !== undefined && (
                                <span className="muted">exit: {run.exit_code}</span>
                              )}
                            </div>
                            {run.stdout && run.stdout.length > 0 && (
                              <div className="tool-output">
                                {run.stdout.slice(-30).join("\n")}
                              </div>
                            )}
                            {run.stderr && run.stderr.length > 0 && (
                              <div className="tool-output tool-output-err">
                                {run.stderr.slice(-10).join("\n")}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
              <div className="grid-2 equal" style={{ gridColumn: "1/-1", gridTemplateColumns: "1fr" }}>
                <section className="panel">
                  <div className="panel-header">
                    <h2>Package Installer</h2>
                    <span className="pill info">pip install</span>
                  </div>
                  <div className="form-grid">
                    <div className="field">
                      <label>Package name (e.g. requests, scrapy==2.11.0)</label>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <input
                          className="input"
                          value={pkgName}
                          onChange={(e) => setPkgName(e.target.value)}
                          placeholder="package-name or package==version"
                          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); installPackage(); } }}
                        />
                        <button className="btn primary" onClick={installPackage} disabled={pkgRunning || !pkgName.trim()}>
                          <Package size={15} />
                          {pkgRunning ? "Installing..." : "Install"}
                        </button>
                      </div>
                    </div>
                    {pkgResult && (
                      <div className="tool-output" style={{ marginTop: "8px" }}>
                        {pkgResult}
                      </div>
                    )}
                  </div>
                </section>
              </div>
            </div>
          )}

          {/* ─── DB MANAGER TAB ────────────────────────────────────────── */}
          {tab === "dbmanager" && (
            <div className="stack">
              <div className="db-stat-grid">
                <div className="db-stat-card">
                  <span>Primary DB</span>
                  <strong>{records.length}</strong>
                  <span style={{ fontSize: "12px" }}>Enriched business records</span>
                </div>
                <div className="db-stat-card">
                  <span>Secondary DB</span>
                  <strong>{secondaryCount}</strong>
                  <span style={{ fontSize: "12px" }}>All scraped URLs (incl. skipped)</span>
                </div>
                <div className="db-stat-card">
                  <span>Jobs Tracked</span>
                  <strong>{jobs.length}</strong>
                  <span style={{ fontSize: "12px" }}>Completed + running</span>
                </div>
              </div>
              <div className="grid-2 equal">
                <section className="panel">
                  <div className="panel-header">
                    <h2>Primary Database</h2>
                    <span className="pill ok">{records.length} records</span>
                  </div>
                  <div className="notice info">Enriched records with deduplication. These are your final business leads.</div>
                  <div className="button-row">
                    <button className="btn primary" onClick={() => { window.open(api.exportRecordsCSV(), "_blank"); }}>
                      <FileText size={15} />
                      Export CSV
                    </button>
                    <button className="btn danger" onClick={clearRecords} disabled={busy}>
                      <Trash2 size={15} />
                      Clear All Records
                    </button>
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-header">
                    <h2>Combined Job CSV</h2>
                    <span className="pill info">{activeJob ? activeJob.request.mode : "no job"}</span>
                  </div>
                  <div className="notice info">One export built from ASAGUS primary records plus Agent-Reach and other MAX-mode tool CSV outputs for the selected job.</div>
                  <div className="button-row">
                    <button className="btn" onClick={() => buildCombinedCsv(activeJob?.id)} disabled={busy || !activeJob}>
                      <GitBranch size={15} />
                      Build Combined CSV
                    </button>
                    <button className="btn primary" onClick={() => activeJob && window.open(api.exportCombinedCSV(activeJob.id), "_blank")} disabled={!activeJob}>
                      <FileText size={15} />
                      Download Combined
                    </button>
                  </div>
                  {combinedCsvStatus ? <div className={`notice ${combinedCsvStatus.startsWith("Error") ? "warn" : "ok"}`}>{combinedCsvStatus}</div> : null}
                </section>
                <section className="panel">
                  <div className="panel-header">
                    <h2>Secondary Database</h2>
                    <span className="pill violet">{secondaryCount} entries</span>
                  </div>
                  <div className="notice info">Real-time log of all scraped URLs including skipped and partial entries. Use for audit and debugging.</div>
                  <div className="button-row">
                    <button className="btn primary" onClick={() => { window.open(api.exportSecondaryCSV(), "_blank"); }}>
                      <FileText size={15} />
                      Export Full DB CSV
                    </button>
                    <button className="btn" onClick={loadSecondaryCount} disabled={busy}>
                      <RefreshCw size={15} />
                      Refresh Count
                    </button>
                  </div>
                </section>
              </div>
              <section className="panel">
                <div className="panel-header">
                  <h2>Data Management</h2>
                  <span className="pill warn">destructive</span>
                </div>
                <div className="button-row">
                  <button className="btn danger" onClick={clearJobs} disabled={busy}>
                    <Trash2 size={15} />
                    Clear Job History
                  </button>
                  <button className="btn danger" onClick={clearLocalData} disabled={busy}>
                    <Trash2 size={15} />
                    Clear ALL Local Data
                  </button>
                </div>
              </section>
            </div>
          )}

          {/* ─── ENV CONFIG TAB ────────────────────────────────────────── */}
          {tab === "envconfig" && (
            <div className="grid-2 wide-left">
              <section className="panel">
                <div className="panel-header">
                  <h2>Backend .env Settings</h2>
                  <span className="pill info">{Object.keys(envSettings).length} keys</span>
                </div>
                <div className="notice warn">
                  Changes are written to your .env file. <strong>Restart the backend</strong> for most settings to take effect.
                </div>
                {envMsg && (
                  <div className={`notice ${envMsg.startsWith("Error") ? "warn" : "ok"}`}>
                    {envMsg}
                  </div>
                )}

                {/* Runtime Gates */}
                <div className="env-group">
                  <div className="env-group-title"><Settings size={12} /> Runtime Gates</div>
                  {["ENABLE_NETWORK_FETCH", "ENABLE_SEARCH_DISCOVERY", "ENVIRONMENT", "BROWSER_AUTOMATION_ENGINE"].map((key) => (
                    <div className="env-row" key={key}>
                      <div className="field">
                        <label>{key}</label>
                        <input
                          className="input"
                          defaultValue={envEdits[key] ?? envSettings[key]?.value ?? ""}
                          onChange={(e) => setEnvEdits((prev) => ({ ...prev, [key]: e.target.value }))}
                          placeholder={envSettings[key]?.set ? "currently set" : "not set"}
                        />
                      </div>
                      <span className={`pill ${envSettings[key]?.set ? "ok" : "warn"}`} style={{ alignSelf: "end", marginBottom: "1px" }}>
                        {envSettings[key]?.set ? "set" : "empty"}
                      </span>
                    </div>
                  ))}
                </div>

                {/* LLM Keys */}
                <div className="env-group">
                  <div className="env-group-title"><Brain size={12} /> LLM API Keys</div>
                  {["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"].map((key) => (
                    <div className="env-row" key={key}>
                      <div className="field">
                        <label>{key}</label>
                        <input
                          className="input"
                          type="password"
                          onChange={(e) => setEnvEdits((prev) => ({ ...prev, [key]: e.target.value }))}
                          placeholder={envSettings[key]?.set ? "***set***" : "paste key"}
                        />
                      </div>
                      <span className={`pill ${envSettings[key]?.set ? "ok" : "warn"}`} style={{ alignSelf: "end", marginBottom: "1px" }}>
                        {envSettings[key]?.set ? "set" : "empty"}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Proxy */}
                <div className="env-group">
                  <div className="env-group-title"><Globe2 size={12} /> Proxy Settings</div>
                  {["RESIDENTIAL_PROXY_URL", "ISP_STATIC_PROXY_URL", "DATACENTER_PROXY_URL"].map((key) => (
                    <div className="env-row" key={key}>
                      <div className="field">
                        <label>{key}</label>
                        <input
                          className="input"
                          type="password"
                          onChange={(e) => setEnvEdits((prev) => ({ ...prev, [key]: e.target.value }))}
                          placeholder={envSettings[key]?.set ? "***set***" : "proxy://user:pass@host:port"}
                        />
                      </div>
                      <span className={`pill ${envSettings[key]?.set ? "ok" : "warn"}`} style={{ alignSelf: "end", marginBottom: "1px" }}>
                        {envSettings[key]?.set ? "set" : "empty"}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="button-row">
                  <button
                    className="btn primary"
                    onClick={saveEnvSettings}
                    disabled={envSaving || Object.keys(envEdits).length === 0}
                  >
                    <Settings size={15} />
                    {envSaving ? "Saving..." : `Save ${Object.keys(envEdits).length} Change(s)`}
                  </button>
                  <button className="btn" onClick={loadEnvSettings} disabled={envSaving}>
                    <RefreshCw size={15} />
                    Reload from Disk
                  </button>
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <h2>All ENV Keys</h2>
                  <span className="pill">{Object.keys(envSettings).length}</span>
                </div>
                <div className="compact-list">
                  {Object.entries(envSettings).map(([key, meta]) => (
                    <div key={key} style={{
                      display: "grid",
                      gridTemplateColumns: "1fr auto",
                      gap: "8px",
                      padding: "6px 8px",
                      borderBottom: "1px solid var(--line)",
                      alignItems: "center"
                    }}>
                      <div>
                        <div style={{ fontFamily: "monospace", fontSize: "12px", color: "var(--ink-2)" }}>{key}</div>
                        {meta.set && meta.value !== "***" && (
                          <div style={{ fontFamily: "monospace", fontSize: "11px", color: "var(--muted)" }}>
                            {meta.value.length > 40 ? meta.value.substring(0, 40) + "..." : meta.value}
                          </div>
                        )}
                      </div>
                      <span className={`pill ${meta.set ? "ok" : "warn"}`} style={{ fontSize: "10px" }}>
                        {meta.set ? "set" : "empty"}
                      </span>
                    </div>
                  ))}
                  {Object.keys(envSettings).length === 0 && (
                    <div className="empty-state" style={{ minHeight: "80px" }}>
                      <Settings size={24} />
                      <span>Click Reload to read .env settings</span>
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}

          {/* ─── AGENT-REACH TAB ────────────────────────────────────────── */}
          {tab === "agentreach" && (
            <div style={{ width: "100%", maxWidth: "none" }}>
              <section className="panel">
                <div className="panel-header">
                  <h2>Agent-Reach Configuration</h2>
                  <span className="pill info">Co-Engine Integration</span>
                </div>
                <div className="notice info">
                  <Zap size={16} />
                  <span>
                    Agent-Reach is a powerful multi-channel scraping engine that works alongside ASAGUS.
                    Configure channels below to enable enhanced data enrichment in MAX mode.
                  </span>
                </div>
                <div style={{ marginTop: "1rem" }}>
                  <iframe
                    src="/agent-reach"
                    style={{
                      width: "100%",
                      height: "calc(100vh - 280px)",
                      border: "1px solid var(--line)",
                      borderRadius: "8px",
                      background: "#f9fafb"
                    }}
                    title="Agent-Reach Configuration"
                  />
                </div>
              </section>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
