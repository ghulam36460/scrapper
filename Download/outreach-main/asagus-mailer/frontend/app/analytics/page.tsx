"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, Cell
} from "recharts";
import { Loader2, RefreshCw, TrendingUp, Trophy, BarChart2 } from "lucide-react";
import { analyticsApi } from "@/lib/api";

function MetricCard({ label, value, sub, color }: { label: string; value: any; sub?: string; color?: string }) {
  return (
    <div className="stat-card">
      <div className={`text-3xl font-bold ${color || "text-gray-900"}`}>{value}</div>
      <div className="text-sm font-medium text-gray-600">{label}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

function SpamBar({ score }: { score: number }) {
  const pct = Math.min((score / 10) * 100, 100);
  const color = score < 3 ? "#22c55e" : score < 5 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-medium" style={{ color }}>{score.toFixed(1)}</span>
    </div>
  );
}

function ABWinner({ results }: { results: any[] }) {
  if (!results || results.length === 0) return (
    <div className="text-center py-8 text-sm text-gray-400">No A/B test data yet</div>
  );

  // Group by campaign
  const groups: Record<string, any[]> = {};
  results.forEach(r => {
    const key = `Campaign ${r.campaign_id}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  });

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([groupName, groupResults]) => {
        const best = [...groupResults].sort((a, b) => b.reply_rate - a.reply_rate)[0];
        return (
          <div key={groupName} className="border border-gray-100 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-gray-700">{groupName}</p>
              {best && <span className="flex items-center gap-1 text-xs text-amber-600 font-medium"><Trophy size={11} /> Winner: Variant {String.fromCharCode(65 + best.subject_variant_index)}</span>}
            </div>
            <div className="space-y-2">
              {groupResults.map(r => (
                <div key={r.id} className={`p-2.5 rounded-lg ${r.id === best?.id ? "bg-amber-50 border border-amber-200" : "bg-gray-50"}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-600">
                      Variant {String.fromCharCode(65 + r.subject_variant_index)}
                      {r.id === best?.id && " 🏆"}
                    </span>
                    <div className="flex gap-4 text-xs text-gray-500">
                      <span>{r.emails_sent} sent</span>
                      <span>{r.replies_received} replies</span>
                      <span className="font-bold text-indigo-700">{r.reply_rate}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 truncate italic">"{r.subject_text}"</p>
                  <div className="mt-1.5 h-1.5 bg-gray-200 rounded-full">
                    <div className="h-full rounded-full bg-indigo-600" style={{
                      width: `${Math.min(r.reply_rate * 10, 100)}%`
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<any>(null);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [abResults, setAbResults] = useState<any[]>([]);
  const [senderStats, setSenderStats] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [spamLogs, setSpamLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [activeTab, setActiveTab] = useState("campaigns");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, camp, tmpl, ab, sndr, tl, spam] = await Promise.allSettled([
        analyticsApi.overview(),
        analyticsApi.campaigns(),
        analyticsApi.templates(),
        analyticsApi.abTest(),
        analyticsApi.senders(),
        analyticsApi.timeline(days),
        analyticsApi.spamScores(),
      ]);
      if (ov.status === "fulfilled") setOverview(ov.value.data);
      if (camp.status === "fulfilled") setCampaigns(camp.value.data);
      if (tmpl.status === "fulfilled") setTemplates(tmpl.value.data);
      if (ab.status === "fulfilled") setAbResults(ab.value.data);
      if (sndr.status === "fulfilled") setSenderStats(sndr.value.data);
      if (tl.status === "fulfilled") setTimeline(tl.value.data);
      if (spam.status === "fulfilled") setSpamLogs(spam.value.data);
    } finally { setLoading(false); }
  }, [days]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const TABS = [
    { key: "campaigns", label: "Campaigns" },
    { key: "templates", label: "Templates" },
    { key: "senders", label: "Senders" },
    { key: "abtest", label: "A/B Test" },
    { key: "spamcheck", label: "Spam Scores" },
  ];

  return (
    <div className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="text-sm text-gray-500 mt-0.5">Full-funnel performance metrics</p>
        </div>
        <button onClick={fetchAll} disabled={loading} className="btn-secondary">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Refresh
        </button>
      </div>

      {/* Overview Cards */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <MetricCard label="Total Sent" value={overview.total_sent.toLocaleString()} color="text-indigo-600" />
          <MetricCard label="Total Replies" value={overview.total_replies.toLocaleString()} color="text-emerald-600" />
          <MetricCard label="Reply Rate" value={`${overview.reply_rate}%`} color="text-blue-600" />
          <MetricCard label="Bounce Rate" value={`${overview.bounce_rate}%`} color="text-red-600" />
          <MetricCard label="Unsubscribes" value={overview.total_unsubscribes.toLocaleString()} color="text-amber-600" />
          <MetricCard label="Avg Spam Score" value={overview.avg_spam_score} sub="Lower is better" color={overview.avg_spam_score < 3 ? "text-emerald-600" : "text-amber-600"} />
        </div>
      )}

      {/* Timeline Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title mb-0">Email Timeline</h2>
          <div className="flex gap-2">
            {[7, 14, 30].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={d === days ? "tab-btn-active py-1 text-xs" : "tab-btn-inactive py-1 text-xs"}>
                {d}d
              </button>
            ))}
          </div>
        </div>
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-indigo-600" /></div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={timeline} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb", fontSize: "11px" }} />
              <Legend wrapperStyle={{ fontSize: "11px" }} />
              <Line type="monotone" dataKey="sent" stroke="#6c63ff" strokeWidth={2.5} dot={false} name="Sent" />
              <Line type="monotone" dataKey="replied" stroke="#22c55e" strokeWidth={2.5} dot={false} name="Replied" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 bg-white p-1 rounded-xl shadow-sm border border-gray-100 w-fit flex-wrap">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={activeTab === t.key ? "tab-btn-active" : "tab-btn-inactive"}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "campaigns" && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr>
                {["Campaign", "Status", "Sent", "Replied", "Bounced", "Unsub'd", "Reply Rate"].map(h => (
                  <th key={h} className="table-header">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {campaigns.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-8 text-sm text-gray-400">No campaigns yet</td></tr>
              ) : campaigns.map(c => (
                <tr key={c.campaign_id} className="hover:bg-gray-50">
                  <td className="table-cell font-medium">{c.campaign_name}</td>
                  <td className="table-cell"><span className={`badge ${c.status === "running" ? "badge-green" : c.status === "completed" ? "badge-blue" : "badge-gray"}`}>{c.status}</span></td>
                  <td className="table-cell font-semibold text-indigo-600">{c.sent}</td>
                  <td className="table-cell font-semibold text-emerald-600">{c.replied}</td>
                  <td className="table-cell text-red-500">{c.bounced}</td>
                  <td className="table-cell text-amber-600">{c.unsubscribed}</td>
                  <td className="table-cell">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-100 rounded-full">
                        <div className="h-full bg-indigo-600 rounded-full" style={{ width: `${Math.min(c.reply_rate * 5, 100)}%` }} />
                      </div>
                      <span className={`text-xs font-bold ${c.reply_rate > 10 ? "text-emerald-600" : "text-gray-600"}`}>{c.reply_rate}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "templates" && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr>
                {["Template", "Type", "Times Used", "Replies", "Reply Rate"].map(h => (
                  <th key={h} className="table-header">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {templates.length === 0 ? (
                <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-400">No data</td></tr>
              ) : templates.sort((a, b) => b.reply_rate - a.reply_rate).map(t => (
                <tr key={t.template_id} className="hover:bg-gray-50">
                  <td className="table-cell font-medium">{t.template_name}</td>
                  <td className="table-cell"><span className="badge-purple capitalize">{t.template_type.replace("_", " ")}</span></td>
                  <td className="table-cell">{t.times_used}</td>
                  <td className="table-cell text-emerald-600 font-semibold">{t.replies}</td>
                  <td className="table-cell font-bold text-indigo-700">{t.reply_rate}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "senders" && (
        <div>
          <div className="card p-0 overflow-hidden mb-4">
            <table className="w-full">
              <thead>
                <tr>
                  {["Sender", "Provider", "Total Sent", "Bounced", "Bounce Rate", "Warmup"].map(h => (
                    <th key={h} className="table-header">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {senderStats.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-8 text-sm text-gray-400">No data</td></tr>
                ) : senderStats.map(s => (
                  <tr key={s.sender_id} className="hover:bg-gray-50">
                    <td className="table-cell">
                      <p className="text-sm font-medium">{s.display_name}</p>
                      <p className="text-xs text-gray-400">{s.email}</p>
                    </td>
                    <td className="table-cell capitalize"><span className="badge-gray">{s.provider}</span></td>
                    <td className="table-cell font-semibold text-indigo-600">{s.total_sent}</td>
                    <td className="table-cell text-red-500">{s.bounced}</td>
                    <td className="table-cell">
                      <span className={`text-xs font-bold ${s.bounce_rate > 5 ? "text-red-600" : "text-emerald-600"}`}>
                        {s.bounce_rate}%
                      </span>
                    </td>
                    <td className="table-cell text-xs text-gray-500">{s.warmup_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {senderStats.length > 0 && (
            <div className="card">
              <h3 className="section-title">Send Volume by Sender</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={senderStats}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="display_name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: "8px", fontSize: "11px" }} />
                  <Bar dataKey="total_sent" fill="#6c63ff" radius={[4, 4, 0, 0]} name="Total Sent" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {activeTab === "abtest" && (
        <div className="card">
          <h2 className="section-title">A/B Test Results</h2>
          <ABWinner results={abResults} />
        </div>
      )}

      {activeTab === "spamcheck" && (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr>
                {["Template", "Subject", "Spam Score", "Safe", "Checked"].map(h => (
                  <th key={h} className="table-header">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spamLogs.length === 0 ? (
                <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-400">No spam checks yet — use the Templates page to check your templates</td></tr>
              ) : spamLogs.map(l => (
                <tr key={l.id} className="hover:bg-gray-50">
                  <td className="table-cell text-xs text-gray-500">Template #{l.template_id}</td>
                  <td className="table-cell text-xs max-w-[200px] truncate">{l.subject}</td>
                  <td className="table-cell w-48"><SpamBar score={l.spam_score} /></td>
                  <td className="table-cell">
                    <span className={`badge ${l.is_safe ? "badge-green" : "badge-red"}`}>
                      {l.is_safe ? "Safe" : "Risky"}
                    </span>
                  </td>
                  <td className="table-cell text-xs text-gray-400">{new Date(l.checked_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
