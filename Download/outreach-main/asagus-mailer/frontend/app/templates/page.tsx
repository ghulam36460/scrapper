"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus, Edit, Trash2, Eye, Zap, X, Check, AlertCircle,
  Loader2, Shield, ChevronDown, ChevronUp, Search
} from "lucide-react";
import { templatesApi } from "@/lib/api";
import Modal from "@/components/Modal";

const TEMPLATE_TYPES = [
  { value: "initial",       label: "Initial Email",    color: "badge-purple" },
  { value: "followup_day3", label: "Follow-up Day 3",  color: "badge-blue" },
  { value: "followup_day6", label: "Follow-up Day 6",  color: "badge-yellow" },
];

const VARS = [
  { v: "{{name}}",              desc: "Lead's name" },
  { v: "{{business}}",          desc: "Business name" },
  { v: "{{sender_name}}",       desc: "Your display name" },
  { v: "{{unsubscribe_link}}", desc: "Unsubscribe URL (required)" },
];

function SpamGauge({ score }: { score: number }) {
  const color = score < 3 ? "#22c55e" : score < 5 ? "#f59e0b" : "#ef4444";
  const pct = Math.min((score / 10) * 100, 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="font-semibold" style={{ color }}>Score: {score.toFixed(1)}/10</span>
        <span className={score < 5 ? "text-emerald-600" : "text-red-600"}>
          {score < 3 ? "Excellent" : score < 5 ? "Moderate risk" : "High risk"}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function TemplateModal({ template, onClose, onSave }: { template: any | null; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    name: template?.name || "",
    template_type: template?.template_type || "initial",
    subject_variants: template?.subject_variants || [""],
    body: template?.body || "Hi {{name}},\n\nI noticed {{business}} and wanted to reach out...\n\n[Your message here]\n\nBest,\n{{sender_name}}\n\n---\nTo unsubscribe: {{unsubscribe_link}}",
    ab_test_enabled: template?.ab_test_enabled || false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [previewing, setPreviewing] = useState(false);
  const [spamResult, setSpamResult] = useState<any>(null);
  const [checkingSpam, setCheckingSpam] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const missingUnsub = !form.body.includes("{{unsubscribe_link}}");

  const addVariant = () => {
    if (form.subject_variants.length < 5) {
      setForm(f => ({ ...f, subject_variants: [...f.subject_variants, ""] }));
    }
  };
  const removeVariant = (i: number) => {
    setForm(f => ({ ...f, subject_variants: f.subject_variants.filter((_: any, idx: number) => idx !== i) }));
  };
  const updateVariant = (i: number, val: string) => {
    const vs = [...form.subject_variants];
    vs[i] = val;
    setForm(f => ({ ...f, subject_variants: vs }));
  };

  const handleSave = async () => {
    if (!form.name || !form.subject_variants[0]) { setError("Name and subject are required."); return; }
    setSaving(true); setError("");
    try {
      if (template) {
        await templatesApi.update(template.id, form);
      } else {
        await templatesApi.create(form);
      }
      onSave(); onClose();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to save template.");
    } finally { setSaving(false); }
  };

  const handlePreview = async () => {
    if (!template) { setError("Save the template first to preview."); return; }
    setPreviewing(true);
    try {
      const res = await templatesApi.preview(template.id);
      setPreview(res.data); setShowPreview(true);
    } catch { setError("Preview failed."); }
    finally { setPreviewing(false); }
  };

  const handleSpamCheck = async () => {
    if (!template) { setError("Save the template first to check spam score."); return; }
    setCheckingSpam(true); setSpamResult(null);
    try {
      const res = await templatesApi.spamCheck(template.id);
      setSpamResult(res.data);
    } catch { setError("Spam check failed."); }
    finally { setCheckingSpam(false); }
  };

  return (
    <Modal onClose={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[92vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="modal-header sticky top-0 bg-white z-10">
          <h2 className="text-lg font-semibold">{template ? "Edit Template" : "New Template"}</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg"><X size={16} /></button>
        </div>
        <div className="p-6 space-y-5">
          {error && <div className="alert-error">{error}</div>}
          {missingUnsub && (
            <div className="alert-warning flex items-center gap-2">
              <AlertCircle size={15} /> Missing <code className="font-mono bg-amber-100 px-1 rounded">{"{{unsubscribe_link}}"}</code> — required for legal compliance
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="form-group">
              <label className="label">Template Name</label>
              <input className="input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Cold Outreach v1" />
            </div>
            <div className="form-group">
              <label className="label">Type</label>
              <select className="select" value={form.template_type} onChange={e => setForm(f => ({ ...f, template_type: e.target.value }))}>
                {TEMPLATE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>

          {/* Subject Variants */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="label mb-0">Subject Lines</label>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                  <div
                    onClick={() => setForm(f => ({ ...f, ab_test_enabled: !f.ab_test_enabled }))}
                    className={`w-8 h-4 rounded-full relative transition-all cursor-pointer ${form.ab_test_enabled ? "bg-indigo-600" : "bg-gray-200"}`}
                  >
                    <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${form.ab_test_enabled ? "left-4" : "left-0.5"}`} />
                  </div>
                  A/B Test
                </label>
                {form.subject_variants.length < 5 && (
                  <button onClick={addVariant} className="text-xs text-indigo-600 hover:underline">+ Add Variant</button>
                )}
              </div>
            </div>
            <div className="space-y-2">
              {form.subject_variants.map((sv: string, i: number) => (
                <div key={i} className="flex items-center gap-2">
                  {form.ab_test_enabled && (
                    <span className="text-xs font-bold text-gray-400 w-5 shrink-0 text-center">{String.fromCharCode(65 + i)}</span>
                  )}
                  <input
                    className="input"
                    value={sv}
                    onChange={e => updateVariant(i, e.target.value)}
                    placeholder={`Subject line ${i + 1}`}
                  />
                  {form.subject_variants.length > 1 && (
                    <button onClick={() => removeVariant(i)} className="p-1.5 text-gray-400 hover:text-red-500">
                      <X size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            {form.ab_test_enabled && form.subject_variants.length > 1 && (
              <p className="text-xs text-indigo-600 mt-1.5">
                A/B variants are distributed evenly across leads. Reply rates tracked per variant.
              </p>
            )}
          </div>

          {/* Body */}
          <div className="form-group">
            <label className="label">Email Body</label>
            <div className="grid grid-cols-4 gap-4">
              <div className="col-span-3">
                <textarea
                  className="input font-mono text-xs resize-none"
                  rows={14}
                  value={form.body}
                  onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
                  placeholder="Write your email body here..."
                />
              </div>
              <div className="space-y-1.5">
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Variables</p>
                {VARS.map(v => (
                  <div key={v.v} className="p-2 bg-gray-50 rounded-lg">
                    <code
                      className="text-[10px] text-indigo-600 font-mono block cursor-pointer hover:text-indigo-800"
                      title="Click to copy"
                      onClick={() => navigator.clipboard.writeText(v.v)}
                    >{v.v}</code>
                    <p className="text-[10px] text-gray-400 mt-0.5">{v.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Actions */}
          {template && (
            <div className="grid grid-cols-2 gap-3">
              <div className="border border-gray-100 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-700">HTML Preview</p>
                  <button onClick={handlePreview} disabled={previewing} className="btn-secondary py-1 text-xs">
                    {previewing ? <Loader2 size={12} className="animate-spin" /> : <Eye size={12} />}
                    Preview
                  </button>
                </div>
                {showPreview && preview && (
                  <div className="mt-2 p-3 bg-gray-50 rounded-lg text-xs">
                    <p className="font-semibold text-gray-700 mb-1">Subject: {preview.subject}</p>
                    <pre className="whitespace-pre-wrap text-gray-600 max-h-32 overflow-y-auto">{preview.body}</pre>
                  </div>
                )}
              </div>
              <div className="border border-gray-100 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-700">Spam Score</p>
                  <button onClick={handleSpamCheck} disabled={checkingSpam} className="btn-secondary py-1 text-xs">
                    {checkingSpam ? <Loader2 size={12} className="animate-spin" /> : <Shield size={12} />}
                    Check
                  </button>
                </div>
                {spamResult && (
                  <div className="mt-2 space-y-2">
                    <SpamGauge score={spamResult.score} />
                    <p className="text-xs text-gray-500">{spamResult.recommendation}</p>
                    {spamResult.flags?.length > 0 && (
                      <div className="space-y-1">
                        {spamResult.flags.map((f: any) => (
                          <div key={f.rule} className="flex justify-between text-[10px] bg-red-50 text-red-600 px-2 py-1 rounded">
                            <span>{f.rule.replace(/_/g, ' ')}</span>
                            <span>+{f.weight}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        <div className="modal-footer sticky bottom-0 bg-white">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            {template ? "Save Changes" : "Create Template"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function TemplateCard({ template, onEdit, onDelete }: { template: any; onEdit: () => void; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const typeInfo = TEMPLATE_TYPES.find(t => t.value === template.template_type);

  return (
    <div className="card p-0 overflow-hidden hover:shadow-md transition-shadow">
      <div className="p-4 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-gray-800 truncate">{template.name}</h3>
              <span className={`badge ${typeInfo?.color || "badge-gray"} shrink-0`}>{typeInfo?.label}</span>
              {template.ab_test_enabled && (
                <span className="badge bg-violet-100 text-violet-700">A/B</span>
              )}
            </div>
            <p className="text-xs text-gray-500 truncate">
              {template.subject_variants.join(" / ")}
            </p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={e => { e.stopPropagation(); onEdit(); }} className="p-1.5 hover:bg-blue-50 rounded-lg text-blue-600"><Edit size={14} /></button>
            <button onClick={e => { e.stopPropagation(); onDelete(); }} className="p-1.5 hover:bg-red-50 rounded-lg text-red-500"><Trash2 size={14} /></button>
            {expanded ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
          </div>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-gray-100 p-4 bg-gray-50">
          <pre className="text-xs text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto font-mono">
            {template.body}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("initial");
  const [showModal, setShowModal] = useState(false);
  const [editTemplate, setEditTemplate] = useState<any | null>(null);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await templatesApi.list();
      setTemplates(res.data);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this template?")) return;
    try { await templatesApi.delete(id); fetchTemplates(); }
    catch (e: any) { alert(e.response?.data?.detail || "Failed to delete."); }
  };

  const filtered = templates.filter(t => t.template_type === activeTab);

  return (
    <div className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Email Templates</h1>
          <p className="text-sm text-gray-500 mt-0.5">{templates.length} template{templates.length !== 1 ? "s" : ""} total</p>
        </div>
        <button onClick={() => { setEditTemplate(null); setShowModal(true); }} className="btn-primary">
          <Plus size={15} /> New Template
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 bg-white p-1 rounded-xl shadow-sm border border-gray-100 w-fit">
        {TEMPLATE_TYPES.map(t => (
          <button
            key={t.value}
            onClick={() => setActiveTab(t.value)}
            className={activeTab === t.value ? "tab-btn-active" : "tab-btn-inactive"}
          >
            {t.label}
            <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
              activeTab === t.value ? "bg-white/20 text-white" : "bg-gray-100 text-gray-500"
            }`}>
              {templates.filter(x => x.template_type === t.value).length}
            </span>
          </button>
        ))}
      </div>

      {/* Template List */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-indigo-600" /></div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center mx-auto mb-3">
            <Plus size={20} className="text-indigo-400" />
          </div>
          <p className="text-sm font-medium text-gray-600">No {TEMPLATE_TYPES.find(t => t.value === activeTab)?.label} templates</p>
          <button onClick={() => { setEditTemplate(null); setShowModal(true); }} className="btn-primary mt-4 mx-auto">
            <Plus size={14} /> Create Template
          </button>
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map(t => (
            <TemplateCard
              key={t.id}
              template={t}
              onEdit={() => { setEditTemplate(t); setShowModal(true); }}
              onDelete={() => handleDelete(t.id)}
            />
          ))}
        </div>
      )}

      {showModal && (
        <TemplateModal
          template={editTemplate}
          onClose={() => setShowModal(false)}
          onSave={fetchTemplates}
        />
      )}
    </div>
  );
}
