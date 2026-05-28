"use client";

import {
  Activity,
  Brain,
  Clock,
  Database,
  ExternalLink,
  GitBranch,
  KeyRound,
  Layers,
  Network,
  Play,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Square,
  Table2,
  Wand2
} from "lucide-react";
import type { ElementType } from "react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AlgorithmState,
  api,
  GraphCandidate,
  JobEvent,
  LLMSettings,
  ObservabilityMetric,
  ProviderPreset,
  RecordRow,
  ScrapeJob
} from "../lib/api";

type Tab = "setup" | "run" | "algorithms" | "pipeline" | "records" | "search";

const tabs: Array<{ id: Tab; label: string; icon: ElementType }> = [
  { id: "setup", label: "Setup", icon: KeyRound },
  { id: "run", label: "Run", icon: Play },
  { id: "algorithms", label: "Algorithms", icon: Brain },
  { id: "pipeline", label: "Pipeline", icon: Layers },
  { id: "records", label: "Records", icon: Table2 },
  { id: "search", label: "Search", icon: Search }
];

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

export default function Home() {
  const [tab, setTab] = useState<Tab>("setup");
  const [layers, setLayers] = useState<Array<{ id: number; key: string; name: string; status: string }>>([]);
  const [health, setHealth] = useState<{ status: string; services: Record<string, string> }>({ status: "checking", services: {} });
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<ScrapeJob | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [providers, setProviders] = useState<ProviderPreset[]>([]);
  const [algorithm, setAlgorithm] = useState<AlgorithmState | null>(null);
  const [metricsRows, setMetricsRows] = useState<ObservabilityMetric[]>([]);
  const [graphRows, setGraphRows] = useState<GraphCandidate[]>([]);
  const [llm, setLlm] = useState<LLMSettings>(emptyLLM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{ record: RecordRow; score: number; highlights?: string[] }>>([]);
  const [summary, setSummary] = useState("");
  const selectedJobIdRef = useRef<string | null>(null);

  const activeJob = selectedJob || jobs[0] || null;
  const activeProgress = activeJob ? jobProgress(activeJob) : null;
  const currentPreset = providers.find((provider) => provider.provider === llm.provider);
  const completed = jobs.filter((job) => job.status === "completed").length;
  const running = jobs.filter((job) => job.status === "running").length;
  const realScrapingEnabled = health.services.network_fetch === "enabled" && health.services.search_discovery === "enabled";
  const isGatewayProvider = llm.provider === "openai_compatible" || llm.provider === "custom_http";
  const llmReady =
    llm.provider === "disabled"
      ? false
      : llm.provider === "ollama"
        ? Boolean(llm.model)
        : isGatewayProvider
          ? Boolean(llm.model && llm.base_url && (llm.has_api_key || llm.api_key || llm.provider === "custom_http"))
          : Boolean(llm.model && (llm.has_api_key || llm.api_key));

  useEffect(() => {
    selectedJobIdRef.current = selectedJob?.id || null;
  }, [selectedJob?.id]);

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
      setHealth(await api.health());
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
    const timer = window.setInterval(() => refreshLive(false), 1500);
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
    try {
      const job = await api.startJob({
        query: String(form.get("query") || ""),
        location: String(form.get("location") || ""),
        limit: Number(form.get("limit") || 100),
        max_pages: Number(form.get("max_pages") || 0),
        mode: String(form.get("mode") || "balanced"),
        proxy_strategy: String(form.get("proxy_strategy") || "auto"),
        llm_enabled: form.get("llm_enabled") === "on",
        archive_raw_html: form.get("archive_raw_html") === "on",
        respect_robots_txt: form.get("respect_robots_txt") === "on",
        skip_existing: form.get("skip_existing") === "on",
        include_contact_pages: form.get("include_contact_pages") === "on",
        include_social_profiles: form.get("include_social_profiles") === "on",
        require_email: form.get("require_email") === "on",
        allowed_domains: csv(form.get("allowed_domains")),
        blocked_domains: csv(form.get("blocked_domains"))
      });
      setSelectedJob(job);
      setTab("pipeline");
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
      await api.saveLLM(llm);
      await loadSetup();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save LLM settings");
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

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">A3</div>
          <div>
            <strong>ASAGUS Scraper</strong>
            <span>Operator console</span>
          </div>
        </div>
        <nav className="nav">
          {tabs.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>
                <Icon size={17} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{titleFor(tab)}</h1>
            <span className={`pill ${health.status === "ok" ? "ok" : "warn"}`}>
              <ShieldCheck size={14} />
              {health.status}
            </span>
          </div>
          <div className="top-actions">
            {error ? <span className="pill warn">{error.slice(0, 100)}</span> : null}
            <button className="btn" onClick={refreshCurrent} disabled={busy}>
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
        </header>

        <section className="content">
          <div className="metric-grid">
            {metrics.map((metric) => (
              <div className="metric" key={metric.label}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <span className={`pill ${metric.tone}`}>{metric.tone}</span>
              </div>
            ))}
          </div>

          {tab === "setup" && (
            <div className="grid-2 wide-left">
              <section className="panel">
                <div className="panel-header">
                  <h2>LLM Provider</h2>
                  <span className={`pill ${llmReady ? "ok" : "warn"}`}>{llm.provider}</span>
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
                  <button className="btn primary" disabled={busy}>
                    <Settings size={16} />
                    Save Provider
                  </button>
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
            </div>
          )}

          {tab === "run" && (
            <div className="grid-2">
              <section className="panel">
                <div className="panel-header">
                  <h2>New Scrape</h2>
                  <span className="pill info">
                    <Brain size={14} />
                    MDP
                  </span>
                </div>
                {!realScrapingEnabled ? (
                  <div className="notice warn">
                    Real scraping is disabled. Enable `ENABLE_NETWORK_FETCH=true` and `ENABLE_SEARCH_DISCOVERY=true`; preview output is not stored as leads.
                  </div>
                ) : null}
                <form className="form-grid" onSubmit={startJob}>
                  <div className="grid-2 equal">
                    <div className="field">
                      <label>Search</label>
                      <input className="input" name="query" defaultValue="restaurants" required />
                    </div>
                    <div className="field">
                      <label>Location</label>
                      <input className="input" name="location" defaultValue="Lahore" required />
                    </div>
                  </div>
                  <div className="grid-3">
                    <div className="field">
                      <label>Desired records</label>
                      <input className="input" name="limit" type="number" min={1} max={5000} defaultValue={50} />
                    </div>
                    <div className="field">
                      <label>Max pages</label>
                      <input className="input" name="max_pages" type="number" min={0} max={20000} placeholder="auto" />
                    </div>
                    <div className="field">
                      <label>Mode</label>
                      <select className="select" name="mode" defaultValue="balanced">
                        <option value="balanced">Balanced</option>
                        <option value="fast">Fast</option>
                        <option value="deep">Deep</option>
                        <option value="research">Research</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Proxy</label>
                      <select className="select" name="proxy_strategy" defaultValue="auto">
                        <option value="auto">Auto</option>
                        <option value="none">None</option>
                        <option value="residential">Residential</option>
                        <option value="isp_static">ISP Static</option>
                        <option value="datacenter">Datacenter</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid-2 equal">
                    <div className="field">
                      <label>Allowed domains</label>
                      <input className="input" name="allowed_domains" placeholder="optional, comma separated" />
                    </div>
                    <div className="field">
                      <label>Blocked domains</label>
                      <input className="input" name="blocked_domains" placeholder="optional, comma separated" />
                    </div>
                  </div>
                  <div className="inline">
                    <label className="check">
                      <input type="checkbox" name="llm_enabled" defaultChecked />
                      LLM fallback
                    </label>
                    <label className="check">
                      <input type="checkbox" name="archive_raw_html" defaultChecked />
                      Archive HTML
                    </label>
                    <label className="check">
                      <input type="checkbox" name="respect_robots_txt" defaultChecked />
                      Robots rules
                    </label>
                    <label className="check">
                      <input type="checkbox" name="skip_existing" defaultChecked />
                      Skip existing
                    </label>
                    <label className="check">
                      <input type="checkbox" name="include_contact_pages" defaultChecked />
                      Contact pages
                    </label>
                    <label className="check">
                      <input type="checkbox" name="include_social_profiles" defaultChecked />
                      Social profiles
                    </label>
                    <label className="check">
                      <input type="checkbox" name="require_email" defaultChecked />
                      Require email
                    </label>
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
                  {layers.map((layer) => (
                    <div className="layer-row" key={layer.key}>
                      <div className="layer-id">{layer.id}</div>
                      <div>
                        <strong>{layer.name}</strong>
                        <div className="muted">{layer.key}</div>
                      </div>
                      <span className="pill info">{layer.status}</span>
                    </div>
                  ))}
                </div>
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
                <JobProgressPanel job={activeJob} progress={activeProgress} busy={busy} onCancel={cancelJob} />
              ) : null}
              <div className="grid-2">
                <section className="panel">
                <div className="panel-header">
                  <h2>Jobs</h2>
                  <span className="pill">{jobs.length}</span>
                </div>
                <div className="stack">
                  {jobs.map((job) => (
                    <button className="layer-row" key={job.id} onClick={() => setSelectedJob(job)}>
                      <div className="layer-id">{job.status.slice(0, 1).toUpperCase()}</div>
                      <div>
                        <strong>{job.request.query} / {job.request.location}</strong>
                        <div className="muted">
                          {job.processed_targets}/{job.total_targets} pages, {job.records_found}/{job.request.limit} records
                        </div>
                      </div>
                      <span className={`pill ${job.status === "completed" ? "ok" : job.status === "failed" ? "warn" : "info"}`}>{job.status}</span>
                    </button>
                  ))}
                </div>
                </section>
                <section className="panel">
                <div className="panel-header">
                  <h2>{activeJob ? activeJob.id.slice(0, 8) : "No job"}</h2>
                  {activeJob ? <span className="pill info">{activeJob.status}</span> : null}
                </div>
                <div className="stack event-list">
                  {events.map((event) => (
                    <div className="event-row" key={event.id}>
                      <div className="inline">
                        <span className="pill info">{event.layer}</span>
                        <strong>{event.event_type}</strong>
                        <span className="muted">{new Date(event.created_at).toLocaleTimeString()}</span>
                      </div>
                      <div>{event.message}</div>
                    </div>
                  ))}
                </div>
                </section>
              </div>
            </>
          )}

          {tab === "records" && (
            <section className="panel">
              <div className="panel-header">
                <h2>Business Records</h2>
                <span className="pill">{records.length}</span>
              </div>
              <RecordTable rows={records} />
            </section>
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
        </section>
      </main>
    </div>
  );
}

function titleFor(tab: Tab) {
  if (tab === "setup") return "Setup";
  if (tab === "run") return "Run Console";
  if (tab === "algorithms") return "Algorithm Control";
  if (tab === "pipeline") return "Live Pipeline";
  if (tab === "records") return "Business Records";
  return "Retrieval";
}

function csv(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function jobProgress(job: ScrapeJob) {
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
    eta: job.status === "running" ? formatDuration(remaining) : "done"
  };
}

function formatDuration(seconds: number) {
  if (seconds <= 0) return "0s";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (!minutes) return `${rest}s`;
  const hours = Math.floor(minutes / 60);
  const min = minutes % 60;
  if (!hours) return `${minutes}m ${rest}s`;
  return `${hours}h ${min}m`;
}

function KeyValueGrid({ rows }: { rows: Array<[string, unknown]> }) {
  return (
    <div className="kv-grid">
      {rows.map(([key, value]) => (
        <div className="mini-metric" key={key}>
          <span>{key}</span>
          <strong>{String(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function JobProgressPanel({
  job,
  progress,
  busy,
  onCancel
}: {
  job: ScrapeJob;
  progress: ReturnType<typeof jobProgress>;
  busy: boolean;
  onCancel: (jobId: string) => void;
}) {
  const canCancel = job.status === "queued" || job.status === "running";
  return (
    <section className="panel progress-panel">
      <div className="panel-header">
        <h2>{job.request.query} / {job.request.location}</h2>
        <div className="inline">
          {canCancel ? (
            <button className="btn danger" onClick={() => onCancel(job.id)} disabled={busy}>
              <Square size={15} />
              Stop
            </button>
          ) : null}
          <span className={`pill ${job.status === "completed" ? "ok" : job.status === "failed" || job.status === "cancelled" ? "warn" : "info"}`}>{job.status}</span>
        </div>
      </div>
      <div className="progress-track" aria-label="job progress">
        <div className="progress-fill" style={{ width: `${progress.percent}%` }} />
      </div>
      <div className="progress-grid">
        <div className="mini-metric">
          <span>Progress</span>
          <strong>{progress.percent}%</strong>
        </div>
        <div className="mini-metric">
          <span>Pages</span>
          <strong>{job.processed_targets}/{job.total_targets || 0}</strong>
        </div>
        <div className="mini-metric">
          <span>Records</span>
          <strong>{job.records_found}/{job.request.limit}</strong>
        </div>
        <div className="mini-metric">
          <span>Skipped</span>
          <strong>{job.skipped_targets || 0}</strong>
        </div>
        <div className="mini-metric">
          <span>Duplicates</span>
          <strong>{job.duplicate_skips || 0}</strong>
        </div>
        <div className="mini-metric">
          <span>Time</span>
          <strong><Clock size={14} /> {progress.elapsed} / {progress.eta}</strong>
        </div>
      </div>
      <div className="muted progress-message">{job.progress_message || "Waiting"}{job.current_url ? `: ${job.current_url}` : ""}</div>
    </section>
  );
}

function SocialLinks({ row }: { row: RecordRow }) {
  const links: Array<[string, string | undefined]> = [
    ["FB", row.facebook_url],
    ["IG", row.instagram_url],
    ["X", row.twitter_url],
    ["IN", row.linkedin_url]
  ].filter((item): item is [string, string] => Boolean(item[1]));
  if (!links.length) return <>-</>;
  return (
    <div className="social-links">
      {links.map(([label, href]) => (
        <a href={href} target="_blank" rel="noreferrer" className="pill info" key={`${label}-${href}`}>
          <ExternalLink size={12} />
          {label}
        </a>
      ))}
    </div>
  );
}

function RecordTable({ rows }: { rows: RecordRow[] }) {
  if (!rows.length) {
    return <div className="muted">No rows</div>;
  }
  return (
    <div className="table">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>City</th>
            <th>Contact</th>
            <th>Website</th>
            <th>Social</th>
            <th>Quality</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <strong>{row.name || "Unnamed"}</strong>
                <div className="muted">{row.category || row.method || "uncategorized"}</div>
              </td>
              <td>{row.city || "-"}</td>
              <td>
                <div>{row.email || "-"}</div>
                <div className="muted">{row.whatsapp || row.phone || "-"}</div>
              </td>
              <td>{row.website_url || "-"}</td>
              <td><SocialLinks row={row} /></td>
              <td>
                <span className="pill info">{Math.round((row.record_completeness || 0) * 100)}%</span>
                {row.duplicate_score ? <span className="pill warn">dup {Math.round(row.duplicate_score * 100)}%</span> : null}
                {row.gdpr_flag ? <span className="pill warn">GDPR</span> : null}
                {row.pdpa_flag ? <span className="pill warn">PDPA</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
