"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus, Edit, Trash2, TestTube, Flame, Inbox, X, Check,
  AlertCircle, ChevronDown, Eye, EyeOff, Loader2,
  KeyRound, Link2
} from "lucide-react";
import { sendersApi, gmailIntegrationApi } from "@/lib/api";
import Modal from "@/components/Modal";

const PROVIDERS = [
  { value: "gmail",  label: "Gmail",   emoji: "G" },
  { value: "zoho",   label: "Zoho",    emoji: "Z" },
  { value: "brevo",  label: "Brevo",   emoji: "B" },
  { value: "other",  label: "Custom",  emoji: "?" },
];

const AUTH_TYPES = [
  { value: "smtp", label: "SMTP/IMAP" },
  { value: "gmail_api", label: "Gmail API (OAuth)" },
];

const PROVIDER_PRESETS: Record<string, any> = {
  gmail:  { smtp_host: "smtp.gmail.com",        smtp_port: 587, smtp_use_tls: true,  imap_host: "imap.gmail.com",  imap_port: 993, daily_limit: 40 },
  zoho:   { smtp_host: "smtp.zoho.com",         smtp_port: 587, smtp_use_tls: true,  imap_host: "imap.zoho.com",  imap_port: 993, daily_limit: 40 },
  brevo:  { smtp_host: "smtp-relay.brevo.com",  smtp_port: 587, smtp_use_tls: true,  imap_host: "",               imap_port: 993, daily_limit: 300 },
  other:  { smtp_host: "",                      smtp_port: 587, smtp_use_tls: true,  imap_host: "",               imap_port: 993, daily_limit: 40 },
};

const emptyForm = {
  display_name: "", email: "", provider: "gmail",
  smtp_host: "smtp.gmail.com", smtp_port: 587, smtp_password: "", smtp_use_tls: true,
  imap_host: "imap.gmail.com", imap_port: 993, imap_password: "",
  daily_limit: 40, is_active: true, auth_type: "smtp",
};

function ProviderBadge({ provider }: { provider: string }) {
  const colors: Record<string, string> = {
    gmail: "bg-red-100 text-red-700",
    zoho: "bg-blue-100 text-blue-700",
    brevo: "bg-emerald-100 text-emerald-700",
    other: "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`badge ${colors[provider] || colors.other} capitalize`}>
      {provider}
    </span>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return active
    ? <span className="badge-green">Active</span>
    : <span className="badge-red">Inactive</span>;
}

function SentBoxDrawer({ sender, onClose }: { sender: any; onClose: () => void }) {
  const [emails, setEmails] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const sourceLabel = sender.auth_type === "gmail_api" ? "Gmail API" : "IMAP Sent folder";

  useEffect(() => {
    sendersApi.sentBox(sender.id)
      .then(r => setEmails(r.data.emails || []))
      .catch(() => setError("Failed to load sent box. Check sender connection."))
      .finally(() => setLoading(false));
  }, [sender.id]);

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-end">
      <div className="bg-white w-full max-w-2xl h-full flex flex-col shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b">
          <div>
            <h3 className="font-semibold text-gray-900">Sent Box — {sender.email}</h3>
            <p className="text-xs text-gray-500 mt-0.5">Last 50 emails from {sourceLabel}</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex justify-center items-center h-32">
              <Loader2 size={20} className="animate-spin text-indigo-600" />
            </div>
          )}
          {error && <div className="alert-error m-4">{error}</div>}
          {!loading && !error && emails.length === 0 && (
            <div className="text-center py-12 text-sm text-gray-400">No sent emails found</div>
          )}
          {!loading && emails.map((e, i) => (
            <div key={i} className="px-5 py-3 border-b border-gray-50 hover:bg-gray-50">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{e.subject}</p>
                  <p className="text-xs text-gray-500 mt-0.5">To: {e.to}</p>
                  <p className="text-xs text-gray-400 mt-1 truncate">{e.snippet}</p>
                </div>
                <span className="text-xs text-gray-400 shrink-0 mt-0.5">{e.date}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function GmailConfigModal({
  config,
  onClose,
  onSaved,
}: {
  config: any;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    client_id: config?.client_id || "",
    client_secret: "",
    redirect_uri: config?.redirect_uri || "http://localhost:8000/api/integrations/gmail/callback",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!form.client_id) {
      setError("Client ID is required.");
      return;
    }
    if (!form.client_secret && !config?.client_secret_set) {
      setError("Client Secret is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await gmailIntegrationApi.setConfig({
        ...form,
        client_secret: form.client_secret || undefined,
      });
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to save Gmail API config.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <div className="modal-box max-w-xl" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="text-lg font-semibold text-gray-900">Gmail API Setup</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body space-y-3">
          {error && <div className="alert-error">{error}</div>}
          <div className="form-group">
            <label className="label">Client ID</label>
            <input
              className="input"
              value={form.client_id}
              onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))}
              placeholder="Your Google OAuth Client ID"
            />
          </div>
          <div className="form-group">
            <label className="label">Client Secret</label>
            <input
              className="input"
              type="password"
              value={form.client_secret}
              onChange={e => setForm(f => ({ ...f, client_secret: e.target.value }))}
              placeholder={config?.client_secret_set
                ? "Leave blank to keep existing"
                : "Your Google OAuth Client Secret"
              }
            />
          </div>
          <div className="form-group">
            <label className="label">Redirect URI</label>
            <input
              className="input"
              value={form.redirect_uri}
              onChange={e => setForm(f => ({ ...f, redirect_uri: e.target.value }))}
            />
            <p className="text-xs text-gray-500 mt-1">
              Add this Redirect URI in Google Cloud OAuth consent screen.
            </p>
          </div>
        </div>
        <div className="modal-footer">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
            Save Settings
          </button>
        </div>
      </div>
    </Modal>
  );
}

function SenderModal({
  sender, onClose, onSave,
}: { sender: any | null; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState<any>(sender
    ? {
        display_name: sender.display_name, email: sender.email, provider: sender.provider,
        smtp_host: sender.smtp_host, smtp_port: sender.smtp_port, smtp_password: "",
        smtp_use_tls: sender.smtp_use_tls, imap_host: sender.imap_host,
        imap_port: sender.imap_port, imap_password: "",
        daily_limit: sender.daily_limit, is_active: sender.is_active,
        auth_type: sender.auth_type || "smtp",
      }
    : { ...emptyForm }
  );
  const [showSmtpPass, setShowSmtpPass] = useState(false);
  const [showImapPass, setShowImapPass] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState(false);

  const isGmailApi = form.auth_type === "gmail_api";

  const applyPreset = (provider: string) => {
    const preset = PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.other;
    setForm((f: any) => ({ ...f, provider, ...preset }));
  };

  const handleProviderChange = (p: string) => {
    applyPreset(p);
  };

  const handleAuthTypeChange = (value: string) => {
    setForm((f: any) => {
      const preset = value === "gmail_api" && f.provider !== "gmail" ? PROVIDER_PRESETS.gmail : {};
      return {
        ...f,
        ...preset,
        provider: value === "gmail_api" ? "gmail" : f.provider,
        auth_type: value,
      };
    });
  };

  const handleConnectGmail = async () => {
    if (!sender) {
      setError("Save the sender first, then connect Gmail.");
      return;
    }
    setConnecting(true);
    try {
      const res = await gmailIntegrationApi.getAuthUrl(sender.id);
      const url = res.data.auth_url;
      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
      } else {
        setError("Gmail auth URL not available. Check Gmail API setup.");
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || "Gmail API setup missing. Configure Gmail API first.");
    } finally {
      setConnecting(false);
    }
  };

  const handleTest = async () => {
    if (!sender) return;
    setTesting(true);
    setTestResult(null);
    // Pehle save karo agar password fill hai
    if (form.smtp_password) {
      try {
        const params: any = { ...form };
        if (!params.smtp_password) delete params.smtp_password;
        if (!params.imap_password) delete params.imap_password;
        await sendersApi.update(sender.id, params);
        onSave();
      } catch { /* ignore save error, still try test */ }
    }
    try {
      const res = await sendersApi.test(sender.id, {
        smtp_password: form.smtp_password || undefined,
        imap_password: form.imap_password || undefined,
      });
      setTestResult(res.data);
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      setTestResult({ smtp_ok: false, smtp_error: detail || "Request failed", imap_ok: false, imap_error: detail || "Request failed" });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!form.display_name || !form.email) {
      setError("Display name and email are required.");
      return;
    }
    if (!sender && form.auth_type === "smtp" && !form.smtp_password) {
      setError("SMTP password is required for new SMTP accounts.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const params: any = { ...form };
      if (!params.smtp_password) delete params.smtp_password;
      if (!params.imap_password) delete params.imap_password;

      if (sender) {
        await sendersApi.update(sender.id, params);
      } else {
        await sendersApi.create(params);
      }
      onSave();
      onClose();
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((err: any) => `${err.loc?.join('.')||'Error'}: ${err.msg}`).join(', '));
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError("Failed to save sender account.");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal onClose={onClose}>
      <div className="modal-box max-w-2xl" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="text-lg font-semibold text-gray-900">
            {sender ? "Edit Sender Account" : "Add Sender Account"}
          </h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          {error && <div className="alert-error">{error}</div>}

          {/* Provider Selector */}
          <div className="form-group">
            <label className="label">Email Provider</label>
            <div className="grid grid-cols-4 gap-2">
              {PROVIDERS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => handleProviderChange(p.value)}
                  className={`py-2 px-3 rounded-lg border-2 text-sm font-medium transition-all ${
                    form.provider === p.value
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {form.provider === "gmail" && !isGmailApi && (
              <p className="text-xs text-amber-600 mt-1.5">
                Gmail: Use an App Password (not your account password). Enable IMAP in Gmail settings.
              </p>
            )}
            {form.provider === "brevo" && (
              <p className="text-xs text-blue-600 mt-1.5">
                Brevo has no IMAP. Set the IMAP fields to your reply inbox (Gmail/Zoho) to detect replies.
              </p>
            )}
          </div>

          {/* Auth Method */}
          <div className="form-group">
            <label className="label">Auth Method</label>
            <div className="grid grid-cols-2 gap-2">
              {AUTH_TYPES.map((a) => (
                <button
                  key={a.value}
                  type="button"
                  onClick={() => handleAuthTypeChange(a.value)}
                  className={`py-2 px-3 rounded-lg border-2 text-sm font-medium transition-all ${
                    form.auth_type === a.value
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {a.label}
                </button>
              ))}
            </div>
            {isGmailApi && (
              <p className="text-xs text-indigo-600 mt-1.5">
                Gmail API uses OAuth. No SMTP/IMAP password needed. Save sender, then connect Gmail.
              </p>
            )}
          </div>

          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="form-group">
              <label className="label">Display Name</label>
              <input className="input" placeholder="John Smith" value={form.display_name}
                onChange={e => setForm((f: any) => ({ ...f, display_name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="label">Email Address</label>
              <input className="input" type="email" placeholder="john@company.com" value={form.email}
                onChange={e => setForm((f: any) => ({ ...f, email: e.target.value }))} />
            </div>
          </div>

          {!isGmailApi ? (
            <>
              {/* SMTP */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">SMTP Settings</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="form-group">
                    <label className="label">SMTP Host</label>
                    <input className="input" value={form.smtp_host}
                      onChange={e => setForm((f: any) => ({ ...f, smtp_host: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="label">SMTP Port</label>
                    <input className="input" type="number" value={form.smtp_port}
                      onChange={e => setForm((f: any) => ({ ...f, smtp_port: Number(e.target.value) }))} />
                  </div>
                  <div className="form-group col-span-2">
                    <label className="label">
                      SMTP Password {sender && <span className="font-normal text-gray-400">(leave blank to keep current)</span>}
                    </label>
                    <div className="relative">
                      <input className="input pr-10" type={showSmtpPass ? "text" : "password"}
                        placeholder={sender ? "••••••••" : "Enter password"}
                        value={form.smtp_password}
                        onChange={e => setForm((f: any) => ({ ...f, smtp_password: e.target.value }))} />
                      <button type="button" onClick={() => setShowSmtpPass(!showSmtpPass)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        {showSmtpPass ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="label">TLS Mode</label>
                    <select className="select" value={form.smtp_use_tls ? "starttls" : "ssl"}
                      onChange={e => setForm((f: any) => ({ ...f, smtp_use_tls: e.target.value === "starttls" }))}>
                      <option value="starttls">STARTTLS (port 587)</option>
                      <option value="ssl">SSL/TLS (port 465)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* IMAP */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">IMAP Settings (Reply Detection)</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="form-group">
                    <label className="label">IMAP Host</label>
                    <input className="input" value={form.imap_host}
                      onChange={e => setForm((f: any) => ({ ...f, imap_host: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="label">IMAP Port</label>
                    <input className="input" type="number" value={form.imap_port}
                      onChange={e => setForm((f: any) => ({ ...f, imap_port: Number(e.target.value) }))} />
                  </div>
                  <div className="form-group col-span-2">
                    <label className="label">
                      IMAP Password {sender && <span className="font-normal text-gray-400">(leave blank to keep current)</span>}
                    </label>
                    <div className="relative">
                      <input className="input pr-10" type={showImapPass ? "text" : "password"}
                        placeholder={sender ? "••••••••" : "Usually same as SMTP password"}
                        value={form.imap_password}
                        onChange={e => setForm((f: any) => ({ ...f, imap_password: e.target.value }))} />
                      <button type="button" onClick={() => setShowImapPass(!showImapPass)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        {showImapPass ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="border border-indigo-100 rounded-lg p-4 bg-indigo-50">
              <p className="text-sm font-medium text-indigo-800">Gmail API Selected</p>
              <p className="text-xs text-indigo-700 mt-1">
                SMTP/IMAP fields not needed. Sender save karein, phir neeche Connect Gmail se OAuth karain.
              </p>
              <div className="text-[11px] text-indigo-700 mt-2 space-y-1">
                <p>1) Gmail API Setup card me Client ID/Secret save karein.</p>
                <p>2) Sender add karein, phir Connect Gmail dabayein.</p>
                <p>3) OAuth complete ho to yahan wapas aa kar refresh karein.</p>
              </div>
            </div>
          )}

          {/* Sending Limits */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Sending Limits</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="form-group">
                <label className="label">Daily Limit</label>
                <input className="input" type="number" min="1" max="500" value={form.daily_limit}
                  onChange={e => setForm((f: any) => ({ ...f, daily_limit: Number(e.target.value) }))} />
              </div>
            </div>
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Account Active</span>
            <button
              type="button"
              onClick={() => setForm((f: any) => ({ ...f, is_active: !f.is_active }))}
              className={`w-10 h-5 rounded-full transition-all duration-200 relative ${
                form.is_active ? "bg-indigo-600" : "bg-gray-300"
              }`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all duration-200 ${
                form.is_active ? "left-5" : "left-0.5"
              }`} />
            </button>
          </div>

          {/* Gmail OAuth Connect */}
          {sender && isGmailApi && (
            <div className="border border-indigo-100 rounded-lg p-4 bg-indigo-50">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-sm font-medium text-indigo-800">Gmail API اتصال</p>
                  <p className="text-xs text-indigo-600">
                    {sender.gmail_connected ? "Connected" : "Not connected"}
                  </p>
                </div>
                <button onClick={handleConnectGmail} disabled={connecting} className="btn-primary text-xs py-1.5">
                  {connecting ? <Loader2 size={12} className="animate-spin" /> : <Link2 size={12} />}
                  Connect Gmail
                </button>
              </div>
              <p className="text-xs text-indigo-700">
                OAuth window open ho gi — successful connect ke baad yahan wapas aa kar refresh karein.
              </p>
            </div>
          )}

          {/* Test Connection (only for existing senders) */}
          {sender && (
            <div className="border border-gray-100 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-gray-700">Test Connection</p>
                <button onClick={handleTest} disabled={testing} className="btn-secondary text-xs py-1.5">
                  {testing ? <Loader2 size={13} className="animate-spin" /> : <TestTube size={13} />}
                  Test Now
                </button>
              </div>
              {testResult && (
                <div className="grid grid-cols-2 gap-2">
                  <div className={`flex items-center gap-2 p-2 rounded-lg text-xs ${
                    testResult.smtp_ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                  }`}>
                    {testResult.smtp_ok ? <Check size={13} /> : <AlertCircle size={13} />}
                    SMTP: {testResult.smtp_ok ? "OK" : testResult.smtp_error}
                  </div>
                  <div className={`flex items-center gap-2 p-2 rounded-lg text-xs ${
                    testResult.imap_ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                  }`}>
                    {testResult.imap_ok ? <Check size={13} /> : <AlertCircle size={13} />}
                    IMAP: {testResult.imap_ok ? "OK" : testResult.imap_error}
                  </div>
                  {testResult.smtp_help && (
                    <div className="col-span-2 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">
                      {testResult.smtp_help}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            {sender ? "Save Changes" : "Add Sender"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function SendersPage() {
  const [senders, setSenders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalSender, setModalSender] = useState<any | null>(undefined as any);
  const [showModal, setShowModal] = useState(false);
  const [sentBoxSender, setSentBoxSender] = useState<any | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [warmupLoading, setWarmupLoading] = useState<number | null>(null);
  const [gmailConfig, setGmailConfig] = useState<any>(null);
  const [showGmailConfig, setShowGmailConfig] = useState(false);

  const fetchSenders = useCallback(async () => {
    try {
      const res = await sendersApi.list();
      setSenders(res.data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGmailConfig = useCallback(async () => {
    try {
      const res = await gmailIntegrationApi.getConfig();
      setGmailConfig(res.data);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => { fetchSenders(); }, [fetchSenders]);
  useEffect(() => { fetchGmailConfig(); }, [fetchGmailConfig]);

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this sender account? This cannot be undone.")) return;
    setDeletingId(id);
    try {
      await sendersApi.delete(id);
      fetchSenders();
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to delete sender.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleWarmupToggle = async (sender: any) => {
    setWarmupLoading(sender.id);
    try {
      if (sender.warmup_enabled) {
        await sendersApi.stopWarmup(sender.id);
      } else {
        await sendersApi.startWarmup(sender.id);
      }
      fetchSenders();
    } catch {
      alert("Failed to toggle warmup.");
    } finally {
      setWarmupLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Sender Accounts</h1>
          <p className="text-sm text-gray-500 mt-0.5">{senders.length} accounts configured</p>
        </div>
        <button
          onClick={() => { setModalSender(null); setShowModal(true); }}
          className="btn-primary"
        >
          <Plus size={15} />
          Add Sender
        </button>
      </div>

      {/* Gmail API Setup */}
      <div className="card border-indigo-100 bg-indigo-50/40">
        <div className="flex items-center justify-between">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-100 flex items-center justify-center">
              <KeyRound size={16} className="text-indigo-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-indigo-800">Gmail API Setup</p>
              <p className="text-xs text-indigo-600 mt-0.5">
                OAuth client for Gmail API. Required for Gmail API sender accounts.
              </p>
              {gmailConfig && (
                <p className="text-[11px] text-indigo-700 mt-1">
                  Client ID: {gmailConfig.client_id || "Not set"} · Redirect: {gmailConfig.redirect_uri}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => setShowGmailConfig(true)}
            className="btn-secondary"
          >
            <KeyRound size={14} /> Configure
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 size={24} className="animate-spin text-indigo-600" />
          </div>
        ) : senders.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center mx-auto mb-3">
              <Plus size={20} className="text-indigo-400" />
            </div>
            <p className="text-sm font-medium text-gray-600">No sender accounts yet</p>
            <p className="text-xs text-gray-400 mt-1 mb-4">Add your first Gmail, Zoho, or Brevo account</p>
            <button onClick={() => { setModalSender(null); setShowModal(true); }} className="btn-primary mx-auto">
              <Plus size={14} /> Add Sender Account
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  {["Account", "Provider", "Auth", "Daily Limit", "Sent Today", "Remaining", "Warmup", "Status", "Actions"].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {senders.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                    <td className="table-cell">
                      <div>
                        <p className="font-medium text-gray-800">{s.display_name}</p>
                        <p className="text-xs text-gray-400">{s.email}</p>
                      </div>
                    </td>
                    <td className="table-cell"><ProviderBadge provider={s.provider} /></td>
                    <td className="table-cell">
                      <div className="flex flex-col gap-1">
                        <span className="badge-gray text-[10px]">
                          {s.auth_type === "gmail_api" ? "Gmail API" : "SMTP"}
                        </span>
                        {s.auth_type === "gmail_api" && (
                          <span className={`text-[10px] ${s.gmail_connected ? "text-emerald-600" : "text-amber-600"}`}>
                            {s.gmail_connected ? "Connected" : "Not connected"}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="table-cell font-medium">{s.daily_limit}</td>
                    <td className="table-cell">
                      <span className={s.sent_today >= s.daily_limit ? "text-red-600 font-semibold" : "text-gray-700"}>
                        {s.sent_today}
                      </span>
                    </td>
                    <td className="table-cell">
                      <span className="font-medium text-emerald-600">
                        {Math.max(0, s.daily_limit - s.sent_today)}
                      </span>
                    </td>
                    <td className="table-cell">
                      <button
                        onClick={() => handleWarmupToggle(s)}
                        disabled={warmupLoading === s.id}
                        title={s.warmup_enabled ? `Warmup active — Day ${s.warmup_day}` : "Warmup disabled"}
                        className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full transition-all ${
                          s.warmup_enabled
                            ? "bg-orange-100 text-orange-700 hover:bg-orange-200"
                            : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                        }`}
                      >
                        {warmupLoading === s.id ? (
                          <Loader2 size={11} className="animate-spin" />
                        ) : (
                          <Flame size={11} />
                        )}
                        {s.warmup_enabled ? `Day ${s.warmup_day}` : "Off"}
                      </button>
                    </td>
                    <td className="table-cell"><StatusBadge active={s.is_active} /></td>
                    <td className="table-cell">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => { setModalSender(s); setShowModal(true); }}
                          className="p-1.5 hover:bg-blue-50 rounded-lg text-blue-600 transition-colors"
                          title="Edit"
                        >
                          <Edit size={14} />
                        </button>
                        <button
                          onClick={() => setSentBoxSender(s)}
                          className="p-1.5 hover:bg-purple-50 rounded-lg text-purple-600 transition-colors"
                          title="View Sent Box"
                        >
                          <Inbox size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(s.id)}
                          disabled={deletingId === s.id}
                          className="p-1.5 hover:bg-red-50 rounded-lg text-red-500 transition-colors"
                          title="Delete"
                        >
                          {deletingId === s.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Warmup info card */}
      {senders.some(s => s.warmup_enabled) && (
        <div className="card bg-gradient-to-r from-orange-50 to-amber-50 border-orange-100">
          <div className="flex items-start gap-3">
            <Flame size={18} className="text-orange-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-orange-800">Warmup Active</p>
              <p className="text-xs text-orange-600 mt-1">
                Warmup sends emails between your own accounts daily at 9am to build sender reputation.
                New inboxes should warm up for 10+ days before running campaigns.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <SenderModal
          sender={modalSender}
          onClose={() => setShowModal(false)}
          onSave={fetchSenders}
        />
      )}

      {showGmailConfig && (
        <GmailConfigModal
          config={gmailConfig}
          onClose={() => setShowGmailConfig(false)}
          onSaved={fetchGmailConfig}
        />
      )}

      {/* Sent Box Drawer */}
      {sentBoxSender && (
        <SentBoxDrawer
          sender={sentBoxSender}
          onClose={() => setSentBoxSender(null)}
        />
      )}
    </div>
  );
}
