"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Plus, Play, Pause, Trash2, RefreshCw, ChevronRight,
  X, Check, Loader2, AlertCircle, ArrowLeft, ArrowRight, Rocket, Eye
} from "lucide-react";
import { campaignsApi, leadsApi, templatesApi, sendersApi } from "@/lib/api";
import Modal from "@/components/Modal";

// ─── Step Components ────────────────────────────────────────────────────────

function StepIndicator({ step, total }: { step: number; total: number }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
            i < step ? "bg-indigo-600 text-white" : i === step ? "bg-indigo-100 text-indigo-700 ring-2 ring-indigo-600" : "bg-gray-100 text-gray-400"
          }`}>
            {i < step ? <Check size={13} /> : i + 1}
          </div>
          {i < total - 1 && <div className={`h-0.5 w-8 ${i < step ? "bg-indigo-600" : "bg-gray-200"}`} />}
        </div>
      ))}
    </div>
  );
}

function CampaignWizard({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Step data
  const [name, setName] = useState("");
  const [fileId, setFileId] = useState<number | null>(null);
  const [leadLimit, setLeadLimit] = useState<number | null>(null);
  const [useLimitToggle, setUseLimitToggle] = useState(false);
  const [fileStats, setFileStats] = useState<any>(null);
  const [initTemplateIds, setInitTemplateIds] = useState<number[]>([]);
  const [d3TemplateIds, setD3TemplateIds] = useState<number[]>([]);
  const [d6TemplateIds, setD6TemplateIds] = useState<number[]>([]);
  const [abEnabled, setAbEnabled] = useState(false);
  const [senderIds, setSenderIds] = useState<number[]>([]);
  const [senderLimits, setSenderLimits] = useState<Record<string, number>>({});

  // Data from API
  const [leadFiles, setLeadFiles] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [senders, setSenders] = useState<any[]>([]);
  const [previewStats, setPreviewStats] = useState<any>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  useEffect(() => {
    leadsApi.listFiles().then(r => setLeadFiles(r.data));
    templatesApi.list().then(r => setTemplates(r.data));
    sendersApi.list().then(r => setSenders(r.data.filter((s: any) => s.is_active)));
  }, []);

  useEffect(() => {
    if (fileId) leadsApi.getFileStats(fileId).then(r => setFileStats(r.data));
  }, [fileId]);

  const STEPS = ["Info", "Lead File", "Templates", "Senders", "Review"];

  const initialTemplates = templates.filter(t => t.template_type === "initial");
  const d3Templates = templates.filter(t => t.template_type === "followup_day3");
  const d6Templates = templates.filter(t => t.template_type === "followup_day6");

  const toggleArr = (arr: number[], setArr: (v: number[]) => void, id: number) => {
    setArr(arr.includes(id) ? arr.filter(x => x !== id) : [...arr, id]);
  };

  const handleCreate = async () => {
    setSaving(true); setError("");
    try {
      const limits: Record<string, number> = {};
      senderIds.forEach(sid => {
        const sender = senders.find(s => s.id === sid);
        limits[String(sid)] = senderLimits[String(sid)] ?? sender?.daily_limit ?? 40;
      });
      await campaignsApi.create({
        name,
        lead_file_id: fileId!,
        initial_template_ids: initTemplateIds,
        followup_day3_template_ids: d3TemplateIds.length > 0 ? d3TemplateIds : undefined,
        followup_day6_template_ids: d6TemplateIds.length > 0 ? d6TemplateIds : undefined,
        sender_account_ids: senderIds,
        lead_limit: useLimitToggle ? leadLimit : undefined,
        ab_test_enabled: abEnabled,
        sender_limits: limits,
      });
      onCreated(); onClose();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to create campaign.");
    } finally { setSaving(false); }
  };

  const canNext = [
    name.length > 0,
    fileId !== null,
    initTemplateIds.length > 0,
    senderIds.length > 0,
    true,
  ];

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-4">
            <div className="form-group">
              <label className="label">Campaign Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)}
                placeholder="e.g. Local Business Outreach — May 2025" autoFocus />
            </div>
            <div className="p-4 bg-indigo-50 rounded-xl text-sm text-indigo-700">
              <p className="font-semibold mb-1">What this campaign does:</p>
              <ul className="space-y-1 text-xs list-disc pl-4">
                <li>Sends personalized emails to your leads</li>
                <li>Rotates across your sender accounts with daily limits</li>
                <li>Automatically schedules Day 3 & Day 6 follow-ups</li>
                <li>Tracks replies and handles unsubscribes</li>
              </ul>
            </div>
          </div>
        );

      case 1:
        return (
          <div className="space-y-4">
            <div className="form-group">
              <label className="label">Lead File</label>
              <select className="select" value={fileId || ""} onChange={e => setFileId(Number(e.target.value) || null)}>
                <option value="">— Select a lead file —</option>
                {leadFiles.map(f => <option key={f.id} value={f.id}>{f.original_name} ({f.valid_leads} leads)</option>)}
              </select>
            </div>
            {fileStats && (
              <div className="grid grid-cols-3 gap-2 text-xs">
                {[
                  { label: "Total Leads", value: fileStats.total, color: "text-gray-800" },
                  { label: "Available", value: fileStats.available, color: "text-emerald-600" },
                  { label: "Sent / Skipped", value: fileStats.sent + fileStats.skipped, color: "text-blue-600" },
                  { label: "Replied", value: fileStats.replied, color: "text-green-600" },
                  { label: "Bounced", value: fileStats.bounced, color: "text-red-600" },
                  { label: "Unsubscribed", value: fileStats.unsubscribed, color: "text-amber-600" },
                ].map(s => (
                  <div key={s.label} className="p-2.5 bg-gray-50 rounded-lg text-center">
                    <div className={`font-bold text-lg ${s.color}`}>{s.value}</div>
                    <div className="text-gray-400">{s.label}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-700">Limit number of leads</p>
                <p className="text-xs text-gray-400">Cap this campaign to N leads from the file</p>
              </div>
              <button onClick={() => setUseLimitToggle(!useLimitToggle)}
                className={`w-10 h-5 rounded-full relative transition-all ${useLimitToggle ? "bg-indigo-600" : "bg-gray-300"}`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${useLimitToggle ? "left-5" : "left-0.5"}`} />
              </button>
            </div>
            {useLimitToggle && (
              <div className="form-group">
                <label className="label">Lead Limit</label>
                <input className="input" type="number" min={1} value={leadLimit || ""} onChange={e => setLeadLimit(Number(e.target.value) || null)}
                  placeholder="e.g. 50" />
                {fileStats && leadLimit && (
                  <p className="text-xs text-indigo-600 mt-1">
                    Will send to: {Math.min(leadLimit, fileStats.available)} leads
                  </p>
                )}
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-700">A/B Subject Testing</p>
              <div className="flex items-center gap-2 text-xs cursor-pointer" onClick={() => setAbEnabled(v => !v)}>
                <div className={`w-8 h-4 rounded-full relative transition-all ${abEnabled ? "bg-indigo-600" : "bg-gray-200"}`}>
                  <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${abEnabled ? "left-4" : "left-0.5"}`} />
                </div>
                <span className="text-gray-600">{abEnabled ? "Enabled" : "Disabled"}</span>
              </div>
            </div>

            {[
              { label: "Initial Templates *", templates: initialTemplates, selected: initTemplateIds, setSelected: setInitTemplateIds },
              { label: "Day 3 Follow-up Templates (optional)", templates: d3Templates, selected: d3TemplateIds, setSelected: setD3TemplateIds },
              { label: "Day 6 Follow-up Templates (optional)", templates: d6Templates, selected: d6TemplateIds, setSelected: setD6TemplateIds },
            ].map(({ label, templates: tList, selected, setSelected }) => (
              <div key={label}>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</p>
                {tList.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">No templates of this type. Create one in Templates.</p>
                ) : (
                  <div className="space-y-1.5">
                    {tList.map(t => (
                      <div key={t.id} onClick={() => toggleArr(selected, setSelected, t.id)}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                        selected.includes(t.id) ? "border-indigo-500 bg-indigo-50" : "border-gray-100 hover:border-gray-200"
                      }`}>
                        <input type="checkbox" className="w-4 h-4 accent-indigo-600 pointer-events-none"
                          checked={selected.includes(t.id)} onChange={() => {}} />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-800">{t.name}</p>
                          <p className="text-xs text-gray-400 truncate">{t.subject_variants?.join(" / ")}</p>
                        </div>
                        {t.ab_test_enabled && <span className="badge bg-violet-100 text-violet-700 text-[10px]">A/B</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {d3TemplateIds.length === 0 && <p className="text-xs text-gray-400">Day 3 & 6: If empty, initial templates are used as fallback.</p>}
          </div>
        );

      case 3:
        return (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Select Sender Accounts</p>
            {senders.map(s => (
              <div key={s.id} className={`p-3 rounded-xl border transition-all ${
                senderIds.includes(s.id) ? "border-indigo-500 bg-indigo-50" : "border-gray-100"
              }`}>
                <div className="flex items-center gap-3 cursor-pointer" onClick={() => {
                      if (senderIds.includes(s.id)) {
                        setSenderIds(senderIds.filter(id => id !== s.id));
                      } else {
                        setSenderIds([...senderIds, s.id]);
                        setSenderLimits(l => ({ ...l, [s.id]: s.daily_limit }));
                      }
                    }}>
                  <input type="checkbox" className="w-4 h-4 accent-indigo-600 pointer-events-none"
                    checked={senderIds.includes(s.id)} onChange={() => {}} />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">{s.display_name}</p>
                    <p className="text-xs text-gray-400">{s.email} · {s.sent_today}/{s.daily_limit} today</p>
                  </div>
                  <span className="badge-gray text-[10px] capitalize">{s.provider}</span>
                </div>
                {senderIds.includes(s.id) && (
                  <div className="mt-2 ml-7 flex items-center gap-3">
                    <span className="text-xs text-gray-500">Campaign limit:</span>
                    <input
                      type="number" min={1} max={s.daily_limit}
                      value={senderLimits[String(s.id)] ?? s.daily_limit}
                      onClick={e => e.stopPropagation()}
                      onChange={e => setSenderLimits(l => ({ ...l, [String(s.id)]: Number(e.target.value) }))}
                      className="input w-20 py-1 text-xs"
                    />
                    <span className="text-xs text-gray-400">/ {s.daily_limit} daily max</span>
                  </div>
                )}
              </div>
            ))}
            {senderIds.length > 0 && (
              <div className="p-3 bg-emerald-50 rounded-lg text-xs text-emerald-700">
                Total campaign capacity: {senderIds.reduce((sum, sid) => sum + (senderLimits[String(sid)] ?? senders.find(s => s.id === sid)?.daily_limit ?? 0), 0)} emails
              </div>
            )}
          </div>
        );

      case 4:
        const selFile = leadFiles.find(f => f.id === fileId);
        const selSenders = senders.filter(s => senderIds.includes(s.id));
        const selInitial = templates.filter(t => initTemplateIds.includes(t.id));
        return (
          <div className="space-y-4">
            {error && <div className="alert-error">{error}</div>}
            {[
              { label: "Campaign Name", value: name },
              { label: "Lead File", value: selFile ? `${selFile.original_name} (${selFile.valid_leads} leads)` : "—" },
              { label: "Lead Limit", value: useLimitToggle && leadLimit ? `${leadLimit} leads` : "All available leads" },
              { label: "Initial Templates", value: selInitial.map(t => t.name).join(", ") || "—" },
              { label: "A/B Testing", value: abEnabled ? "Enabled" : "Disabled" },
              { label: "Sender Accounts", value: selSenders.map(s => s.display_name).join(", ") || "—" },
            ].map(row => (
              <div key={row.label} className="flex items-start justify-between py-2 border-b border-gray-50 last:border-0">
                <span className="text-xs font-semibold text-gray-400 uppercase">{row.label}</span>
                <span className="text-sm text-gray-800 font-medium text-right max-w-xs">{row.value}</span>
              </div>
            ))}
            <div className="p-4 bg-indigo-50 rounded-xl">
              <p className="text-sm font-semibold text-indigo-800 mb-1">Ready to launch?</p>
              <p className="text-xs text-indigo-600">
                After creating, go to the campaign detail and click Run to start sending.
                Emails are sent with 20–120 second random delays. Follow-ups auto-schedule.
              </p>
            </div>
          </div>
        );

      default: return null;
    }
  };

  return (
    <Modal onClose={onClose}>
      <div className="modal-box max-w-xl" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="text-lg font-semibold">New Campaign</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg"><X size={16} /></button>
        </div>
        <div className="p-6">
          <StepIndicator step={step} total={STEPS.length} />
          <h3 className="text-base font-semibold text-gray-800 mb-4">{STEPS[step]}</h3>
          {renderStep()}
        </div>
        <div className="modal-footer">
          {step > 0 && (
            <button onClick={() => setStep(s => s - 1)} className="btn-secondary">
              <ArrowLeft size={14} /> Back
            </button>
          )}
          <div className="flex-1" />
          {step < STEPS.length - 1 ? (
            <button onClick={() => setStep(s => s + 1)} disabled={!canNext[step]} className="btn-primary">
              Next <ArrowRight size={14} />
            </button>
          ) : (
            <button onClick={handleCreate} disabled={saving} className="btn-primary">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              Create Campaign
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}

function CampaignProgress({ campaign, onRefresh }: { campaign: any; onRefresh: () => void }) {
  const [progress, setProgress] = useState<any>(null);
  const [senderStats, setSenderStats] = useState<any[]>([]);
  const [running, setRunning] = useState(false);

  const fetchProgress = useCallback(async () => {
    const [pr, ss] = await Promise.all([
      campaignsApi.progress(campaign.id),
      campaignsApi.senderStats(campaign.id),
    ]);
    setProgress(pr.data);
    setSenderStats(ss.data);
  }, [campaign.id]);

  useEffect(() => {
    fetchProgress();
    if (campaign.status === "running") {
      const interval = setInterval(fetchProgress, 5000);
      return () => clearInterval(interval);
    }
  }, [fetchProgress, campaign.status]);

  const handleRun = async () => {
    setRunning(true);
    try { await campaignsApi.run(campaign.id); onRefresh(); fetchProgress(); }
    catch (e: any) { alert(e.response?.data?.detail || "Failed to start."); }
    finally { setRunning(false); }
  };

  const handlePause = async () => {
    try { await campaignsApi.pause(campaign.id); onRefresh(); fetchProgress(); }
    catch (e: any) { alert(e.response?.data?.detail || "Failed to pause."); }
  };

  const pct = progress?.progress_pct || 0;

  return (
    <div className="space-y-4">
      {/* Progress */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{progress?.sent_count || 0} sent</span>
          <span>{progress?.total_targets || 0} total ({pct}%)</span>
        </div>
        <div className="progress-bar-bg">
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Sender table */}
      {senderStats.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                {["Sender", "Campaign Sent", "Limit", "Today", "Remaining"].map(h => (
                  <th key={h} className="text-left py-1.5 px-2 text-gray-400 font-semibold bg-gray-50">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {senderStats.map(s => (
                <tr key={s.sender_id} className="border-t border-gray-50">
                  <td className="py-1.5 px-2 font-medium text-gray-700">{s.display_name}</td>
                  <td className="py-1.5 px-2">{s.sent_this_campaign}</td>
                  <td className="py-1.5 px-2">{s.campaign_limit}</td>
                  <td className="py-1.5 px-2">{s.sent_today}</td>
                  <td className="py-1.5 px-2 text-emerald-600 font-medium">{s.remaining_today}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Recent sends */}
      {progress?.recent_sends?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase mb-2">Recent Sends</p>
          <div className="space-y-1.5">
            {progress.recent_sends.map((s: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs text-gray-600 py-1 border-b border-gray-50">
                <span className="w-2 h-2 rounded-full bg-indigo-400 shrink-0" />
                <span className="flex-1 truncate">{s.lead_name} — {s.subject}</span>
                <span className="text-gray-400 shrink-0">{new Date(s.sent_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {campaign.status === "running" ? (
          <button onClick={handlePause} className="btn-danger">
            <Pause size={13} /> Pause
          </button>
        ) : campaign.status !== "completed" ? (
          <button onClick={handleRun} disabled={running} className="btn-success">
            {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {campaign.status === "paused" ? "Resume" : "Run Campaign"}
          </button>
        ) : null}
        {campaign.pause_reason && (
          <p className="text-xs text-amber-600 flex items-center gap-1">
            <AlertCircle size={12} /> {campaign.pause_reason}
          </p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    draft: "badge-gray",
    running: "badge-green",
    paused: "badge-yellow",
    completed: "badge-blue",
  };
  return <span className={`badge ${map[status] || "badge-gray"}`}>{status}</span>;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showWizard, setShowWizard] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const fetchCampaigns = useCallback(async () => {
    try { const r = await campaignsApi.list(); setCampaigns(r.data); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this campaign?")) return;
    try { await campaignsApi.delete(id); fetchCampaigns(); }
    catch (e: any) { alert(e.response?.data?.detail || "Failed."); }
  };

  return (
    <div className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Campaigns</h1>
          <p className="text-sm text-gray-500 mt-0.5">{campaigns.length} campaign{campaigns.length !== 1 ? "s" : ""}</p>
        </div>
        <button onClick={() => setShowWizard(true)} className="btn-primary"><Plus size={15} /> New Campaign</button>
      </div>

      {loading ? <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-indigo-600" /></div> :
        campaigns.length === 0 ? (
          <div className="card text-center py-16">
            <Rocket size={36} className="mx-auto mb-3 text-gray-200" />
            <p className="text-sm font-medium text-gray-600">No campaigns yet</p>
            <button onClick={() => setShowWizard(true)} className="btn-primary mt-4 mx-auto"><Plus size={14} /> Create First Campaign</button>
          </div>
        ) : (
          <div className="space-y-3">
            {campaigns.map(c => {
              const pct = c.total_targets > 0 ? Math.round((c.sent_count / c.total_targets) * 100) : 0;
              const isExpanded = expanded === c.id;
              return (
                <div key={c.id} className="card p-0 overflow-hidden">
                  <div className="p-4 cursor-pointer" onClick={() => setExpanded(isExpanded ? null : c.id)}>
                    <div className="flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-gray-800 truncate">{c.name}</h3>
                          <StatusBadge status={c.status} />
                        </div>
                        <div className="progress-bar-bg mt-2" style={{ height: "4px" }}>
                          <div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${pct}%` }} />
                        </div>
                        <p className="text-xs text-gray-400 mt-1">{c.sent_count} / {c.total_targets || "?"} sent · {pct}%</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {c.status !== "running" && c.status !== "completed" && (
                          <button onClick={e => { e.stopPropagation(); handleDelete(c.id); }}
                            className="p-1.5 hover:bg-red-50 rounded-lg text-red-400"><Trash2 size={14} /></button>
                        )}
                        {isExpanded ? <ChevronRight size={16} className="rotate-90 text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
                      </div>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="border-t border-gray-100 p-4 bg-gray-50">
                      <CampaignProgress campaign={c} onRefresh={fetchCampaigns} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
      }

      {showWizard && (
        <CampaignWizard
          onClose={() => setShowWizard(false)}
          onCreated={fetchCampaigns}
        />
      )}
    </div>
  );
}
