"use client";

import { useEffect, useState, useCallback } from "react";
import { Loader2, RefreshCw, Mail, Search, X, Eye } from "lucide-react";
import { emailsApi, campaignsApi } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = { sent: "badge-green", failed: "badge-red", bounced: "badge-red" };
  return <span className={`badge ${map[status] || "badge-gray"}`}>{status}</span>;
}

function EmailBodyModal({ email, onClose }: { email: any; onClose: () => void }) {
  const [detail, setDetail] = useState<any>(null);
  useEffect(() => {
    emailsApi.get(email.id).then(r => setDetail(r.data));
  }, [email.id]);

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box max-w-2xl">
        <div className="modal-header">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{email.subject}</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              To: {email.lead_email} · From: {email.sender_email} · {new Date(email.sent_at).toLocaleString()}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg"><X size={16} /></button>
        </div>
        <div className="p-6">
          {!detail ? (
            <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-indigo-600" /></div>
          ) : (
            <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
              {detail.body}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SentPage() {
  const [emails, setEmails] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [filterCampaign, setFilterCampaign] = useState<number | null>(null);
  const [filterFollowup, setFilterFollowup] = useState<boolean | null>(null);
  const [viewEmail, setViewEmail] = useState<any | null>(null);

  const fetchEmails = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const params: any = { page: p };
      if (filterCampaign) params.campaign_id = filterCampaign;
      if (filterFollowup !== null) params.is_followup = filterFollowup;
      const res = await emailsApi.list(params);
      setEmails(res.data.items);
      setTotal(res.data.total);
      setPage(p);
    } finally { setLoading(false); }
  }, [filterCampaign, filterFollowup]);

  useEffect(() => { fetchEmails(1); }, [fetchEmails]);
  useEffect(() => { campaignsApi.list().then(r => setCampaigns(r.data)); }, []);

  const pages = Math.ceil(total / 20);

  return (
    <div className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Sent Emails</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total.toLocaleString()} emails in log</p>
        </div>
        <button onClick={() => fetchEmails(page)} className="btn-secondary"><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 p-4 card">
        <div className="form-group min-w-[200px]">
          <label className="label">Campaign</label>
          <select className="select" value={filterCampaign || ""}
            onChange={e => setFilterCampaign(Number(e.target.value) || null)}>
            <option value="">All campaigns</option>
            {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="label">Email Type</label>
          <select className="select" value={filterFollowup === null ? "" : String(filterFollowup)}
            onChange={e => {
              const v = e.target.value;
              setFilterFollowup(v === "" ? null : v === "true");
            }}>
            <option value="">All</option>
            <option value="false">Initial Emails</option>
            <option value="true">Follow-ups</option>
          </select>
        </div>
        {(filterCampaign || filterFollowup !== null) && (
          <div className="form-group flex items-end">
            <button onClick={() => { setFilterCampaign(null); setFilterFollowup(null); }} className="btn-secondary">
              <X size={13} /> Clear Filters
            </button>
          </div>
        )}
      </div>

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-indigo-600" /></div>
        ) : emails.length === 0 ? (
          <div className="text-center py-12">
            <Mail size={32} className="mx-auto mb-3 text-gray-200" />
            <p className="text-sm text-gray-400">No emails match filters</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    {["Lead", "Subject", "Sender", "Type", "Sent At", "Status", ""].map(h => (
                      <th key={h} className="table-header">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {emails.map(e => (
                    <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                      <td className="table-cell">
                        <div>
                          <p className="font-medium text-gray-800 text-xs">{e.lead_name || "—"}</p>
                          <p className="text-gray-400 text-[11px]">{e.lead_email}</p>
                        </div>
                      </td>
                      <td className="table-cell max-w-[240px]">
                        <p className="text-xs text-gray-700 truncate">{e.subject}</p>
                        {e.subject_variant_index > 0 && (
                          <span className="text-[10px] text-violet-500">Variant {String.fromCharCode(64 + e.subject_variant_index + 1)}</span>
                        )}
                      </td>
                      <td className="table-cell text-xs text-gray-500">{e.sender_name || e.sender_email}</td>
                      <td className="table-cell">
                        {e.is_followup ? (
                          <span className="badge-yellow text-[10px]">Day {e.followup_day}</span>
                        ) : (
                          <span className="badge-purple text-[10px]">Initial</span>
                        )}
                      </td>
                      <td className="table-cell text-xs text-gray-400 whitespace-nowrap">
                        {new Date(e.sent_at).toLocaleString()}
                      </td>
                      <td className="table-cell"><StatusBadge status={e.status} /></td>
                      <td className="table-cell">
                        <button onClick={() => setViewEmail(e)} className="p-1.5 hover:bg-indigo-50 rounded-lg text-indigo-400 hover:text-indigo-600">
                          <Eye size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pages > 1 && (
              <div className="flex justify-center gap-2 p-4 border-t border-gray-50">
                <button onClick={() => fetchEmails(page - 1)} disabled={page === 1} className="btn-secondary py-1 px-3 text-xs disabled:opacity-40">Prev</button>
                <span className="text-xs text-gray-500 py-1.5 px-2">Page {page} of {pages}</span>
                <button onClick={() => fetchEmails(page + 1)} disabled={page === pages} className="btn-secondary py-1 px-3 text-xs disabled:opacity-40">Next</button>
              </div>
            )}
          </>
        )}
      </div>

      {viewEmail && <EmailBodyModal email={viewEmail} onClose={() => setViewEmail(null)} />}
    </div>
  );
}
