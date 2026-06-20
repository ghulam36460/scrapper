"use client";

import {
  AlertCircle,
  CheckCircle2,
  FileText,
  KeyRound,
  Loader2,
  Play,
  RefreshCw,
  Settings,
  Terminal,
  X,
  XCircle,
  Zap
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  agentReachApi,
  type AgentReachChannel,
  type AgentReachRunResult,
  type AgentReachStatistics
} from "../../lib/agent-reach-api";

export default function AgentReachPage() {
  const [channels, setChannels] = useState<AgentReachChannel[]>([]);
  const [stats, setStats] = useState<AgentReachStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedChannel, setSelectedChannel] = useState<AgentReachChannel | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [actionMessages, setActionMessages] = useState<Record<string, string>>({});
  const [runQuery, setRunQuery] = useState("audit firms");
  const [runLocation, setRunLocation] = useState("Qatar");
  const [runLimit, setRunLimit] = useState("25");
  const [selectedRunChannels, setSelectedRunChannels] = useState<string[]>([]);
  const [runLoading, setRunLoading] = useState(false);
  const [runResult, setRunResult] = useState<AgentReachRunResult | null>(null);

  const readyChannels = useMemo(
    () => channels.filter((channel) => channel.ready).map((channel) => channel.name),
    [channels]
  );

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    setSelectedRunChannels((current) => {
      if (current.length) return current.filter((name) => readyChannels.includes(name));
      return readyChannels;
    });
  }, [readyChannels]);

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const [channelsRes, statsRes] = await Promise.all([
        agentReachApi.listChannels(),
        agentReachApi.getStatistics()
      ]);
      setChannels(channelsRes.channels);
      setStats(statsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Agent-Reach data");
    } finally {
      setLoading(false);
    }
  }

  function setAction(channelName: string, loadingValue: boolean, message?: string) {
    setActionLoading((prev) => ({ ...prev, [channelName]: loadingValue }));
    if (message !== undefined) {
      setActionMessages((prev) => ({ ...prev, [channelName]: message }));
    }
  }

  async function handleInstall(channelName: string) {
    setAction(channelName, true, "");
    try {
      const result = await agentReachApi.installChannel(channelName);
      setAction(channelName, false, `${result.success ? "OK" : "Needs setup"}: ${result.message}`);
      await loadData();
    } catch (err) {
      setAction(channelName, false, `Error: ${err instanceof Error ? err.message : "Installation failed"}`);
    }
  }

  async function handleTest(channelName: string) {
    setAction(`test_${channelName}`, true);
    setActionMessages((prev) => ({ ...prev, [channelName]: "" }));
    try {
      const result = await agentReachApi.testChannel(channelName);
      setActionMessages((prev) => ({ ...prev, [channelName]: `${result.success ? "OK" : "Warn"}: ${result.message}` }));
      await loadData();
    } catch (err) {
      setActionMessages((prev) => ({ ...prev, [channelName]: `Error: ${err instanceof Error ? err.message : "Test failed"}` }));
    } finally {
      setActionLoading((prev) => ({ ...prev, [`test_${channelName}`]: false }));
    }
  }

  async function handleConfigure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedChannel) return;
    const key = `config_${selectedChannel.name}`;
    setActionLoading((prev) => ({ ...prev, [key]: true }));
    try {
      const config: Record<string, string> = {};
      if (configValues.cookie) config.cookie = configValues.cookie;
      if (configValues.token) config.token = configValues.token;
      if (configValues.proxy) config.proxy = configValues.proxy;
      if (configValues.groq_key) config.groq_key = configValues.groq_key;
      const result = await agentReachApi.configureChannel(selectedChannel.name, config);
      setActionMessages((prev) => ({ ...prev, [selectedChannel.name]: `${result.success ? "OK" : "Error"}: ${result.message}` }));
      setSelectedChannel(null);
      setConfigValues({});
      await loadData();
    } catch (err) {
      setActionMessages((prev) => ({ ...prev, [selectedChannel.name]: `Error: ${err instanceof Error ? err.message : "Configuration failed"}` }));
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function handleRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRunLoading(true);
    setRunResult(null);
    setError("");
    try {
      const result = await agentReachApi.runScrape(runQuery, {
        location: runLocation,
        limit: Number(runLimit || 25),
        channels: selectedRunChannels
      });
      setRunResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent-Reach run failed");
    } finally {
      setRunLoading(false);
    }
  }

  function toggleRunChannel(name: string) {
    setSelectedRunChannels((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name]
    );
  }

  function statusIcon(channel: AgentReachChannel) {
    if (channel.ready) return <CheckCircle2 size={18} className="status-ok" />;
    if (channel.status === "warn") return <AlertCircle size={18} className="status-warn" />;
    return <XCircle size={18} className="status-off" />;
  }

  if (loading) {
    return (
      <div className="content agent-reach-console">
        <section className="panel loading-panel">
          <Loader2 className="spin" size={24} />
          <span>Loading Agent-Reach</span>
        </section>
      </div>
    );
  }

  return (
    <div className="content agent-reach-console">
      {error ? (
        <div className="alert-banner">
          <AlertCircle size={17} />
          <span>{error}</span>
          <button className="icon-btn" type="button" onClick={() => setError("")} aria-label="Dismiss error">
            <X size={15} />
          </button>
        </div>
      ) : null}

      <div className="metric-grid agent-reach-metrics">
        <div className="metric">
          <span>Total Channels</span>
          <strong>{stats?.total_channels ?? channels.length}</strong>
          <span className="pill info">detected</span>
        </div>
        <div className="metric">
          <span>Ready</span>
          <strong>{stats?.ready_channels ?? readyChannels.length}</strong>
          <span className="pill ok">usable</span>
        </div>
        <div className="metric">
          <span>Warnings</span>
          <strong>{stats?.warning_channels ?? 0}</strong>
          <span className="pill warn">setup</span>
        </div>
        <div className="metric">
          <span>Availability</span>
          <strong>{Math.round(stats?.availability_percentage ?? 0)}%</strong>
          <span className="pill violet">doctor</span>
        </div>
      </div>

      <div className="grid-2 wide-left">
        <section className="panel">
          <div className="panel-header">
            <h2>Agent-Reach Run</h2>
            <span className="pill info"><Zap size={13} /> adapter</span>
          </div>
          <form className="form-grid" onSubmit={handleRun}>
            <div className="grid-2 equal">
              <div className="field">
                <label>Search</label>
                <input className="input" value={runQuery} onChange={(event) => setRunQuery(event.target.value)} required />
              </div>
              <div className="field">
                <label>Location</label>
                <input className="input" value={runLocation} onChange={(event) => setRunLocation(event.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Limit</label>
              <input className="input" type="number" min={1} max={5000} value={runLimit} onChange={(event) => setRunLimit(event.target.value)} />
            </div>
            <div className="field">
              <label>Ready channels for this run</label>
              <div className="tag-row">
                {readyChannels.map((name) => (
                  <button
                    type="button"
                    key={name}
                    className={`btn compact-btn ${selectedRunChannels.includes(name) ? "success" : ""}`}
                    onClick={() => toggleRunChannel(name)}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>
            <button className="btn primary" disabled={runLoading || !runQuery.trim()}>
              {runLoading ? <Loader2 className="spin" size={15} /> : <Play size={15} />}
              Start Agent-Reach
            </button>
          </form>
          {runResult ? (
            <div className="notice ok agent-run-result">
              <Terminal size={15} />
              <span>Run {runResult.run_id} started for job {runResult.job_id}. Output will be written under Download/.asagus-runs.</span>
            </div>
          ) : null}
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Configuration</h2>
            <button className="btn compact-btn" onClick={loadData} type="button">
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
          <div className="kv-grid">
            <div className="kv-row">
              <dt>config_path</dt>
              <dd>~/.agent-reach/config.yaml</dd>
            </div>
            <div className="kv-row">
              <dt>run_contract</dt>
              <dd>ASAGUS job context to Agent-Reach adapter CSV/JSON artifacts</dd>
            </div>
            <div className="kv-row">
              <dt>max_mode</dt>
              <dd>ASAGUS launches Agent-Reach in parallel and merges tool output into combined CSV</dd>
            </div>
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <h2>Channels</h2>
          <span className="pill">{channels.length}</span>
        </div>
        <div className="agent-channel-grid">
          {channels.map((channel) => (
            <div className={`tool-card ${channel.ready ? "agent-ready" : ""}`} key={channel.name}>
              <div className="tool-header">
                <div>
                  <div className="tool-title">
                    {statusIcon(channel)}
                    <span>{channel.display_name}</span>
                  </div>
                  <div className="tool-desc">{channel.description}</div>
                </div>
                <span className={`pill ${channel.ready ? "ok" : channel.status === "warn" ? "warn" : "info"}`}>{channel.status}</span>
              </div>
              <div className="muted">{channel.message}</div>
              {channel.requires.length ? (
                <div className="tag-row compact-tags">
                  {channel.requires.map((item) => <span className="pill" key={item}>{item}</span>)}
                </div>
              ) : null}
              <div className="button-row">
                {channel.install_command !== "none" && !channel.ready ? (
                  <button className="btn compact-btn" onClick={() => handleInstall(channel.name)} disabled={actionLoading[channel.name]}>
                    {actionLoading[channel.name] ? <Loader2 className="spin" size={13} /> : <FileText size={13} />}
                    Install
                  </button>
                ) : null}
                {channel.config_needed !== "none" && channel.config_needed !== "mcp_config" ? (
                  <button className="btn compact-btn" onClick={() => setSelectedChannel(channel)}>
                    <KeyRound size={13} />
                    Configure
                  </button>
                ) : null}
                <button className="btn compact-btn" onClick={() => handleTest(channel.name)} disabled={actionLoading[`test_${channel.name}`]}>
                  {actionLoading[`test_${channel.name}`] ? <Loader2 className="spin" size={13} /> : <RefreshCw size={13} />}
                  Test
                </button>
              </div>
              {actionMessages[channel.name] ? <div className="tool-output">{actionMessages[channel.name]}</div> : null}
            </div>
          ))}
        </div>
      </section>

      {selectedChannel ? (
        <div className="modal-backdrop">
          <section className="panel config-modal">
            <div className="panel-header">
              <h2>Configure {selectedChannel.display_name}</h2>
              <button className="icon-btn" type="button" onClick={() => setSelectedChannel(null)} aria-label="Close">
                <X size={15} />
              </button>
            </div>
            <form className="form-grid" onSubmit={handleConfigure}>
              {selectedChannel.config_needed.includes("cookie") ? (
                <div className="field">
                  <label>Cookie</label>
                  <textarea
                    className="textarea"
                    value={configValues.cookie || ""}
                    onChange={(event) => setConfigValues({ ...configValues, cookie: event.target.value })}
                    rows={4}
                  />
                </div>
              ) : null}
              {selectedChannel.config_needed.includes("token") ? (
                <div className="field">
                  <label>Token</label>
                  <input className="input" type="password" value={configValues.token || ""} onChange={(event) => setConfigValues({ ...configValues, token: event.target.value })} />
                </div>
              ) : null}
              {selectedChannel.config_needed.includes("proxy") ? (
                <div className="field">
                  <label>Proxy URL</label>
                  <input className="input" value={configValues.proxy || ""} onChange={(event) => setConfigValues({ ...configValues, proxy: event.target.value })} />
                </div>
              ) : null}
              {selectedChannel.config_needed.includes("groq") ? (
                <div className="field">
                  <label>Groq API Key</label>
                  <input className="input" type="password" value={configValues.groq_key || ""} onChange={(event) => setConfigValues({ ...configValues, groq_key: event.target.value })} />
                </div>
              ) : null}
              <div className="button-row">
                <button className="btn" type="button" onClick={() => setSelectedChannel(null)}>
                  Cancel
                </button>
                <button className="btn primary" disabled={actionLoading[`config_${selectedChannel.name}`]}>
                  {actionLoading[`config_${selectedChannel.name}`] ? <Loader2 className="spin" size={15} /> : <Settings size={15} />}
                  Save
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
