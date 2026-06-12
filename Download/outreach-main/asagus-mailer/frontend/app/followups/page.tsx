"use client";

import { useEffect, useState, useCallback } from "react";
import { Loader2, RefreshCw, Zap, X, AlertCircle, Clock } from "lucide-react";
import { followupsApi } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const m: Record<string, string> = { pending: "badge-yellow", sent: "badge-green", cancelled: "badge-gray" };
  return <span className={`badge ${m[status] || "badge-gray"}`}>{status}</span>;
}

function StatsBar({ stats }: { stats: any }) {
  if (!stats) return null;
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {[
        { label: "Due Today", value: stats.due_today, color: "text-red-600" },
        { label: "Overdue", value: stats.overdue, color: "text-amber-600" },
        { label: "Pending Total", value: stats.pending_total, color: "text-indigo-600" },
        { label: "Sent This Week", value: stats.sent_this_week, color: "text-emerald-600" },
      ].map(s => (
        <div key={s.label} className="stat-card">
          <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
          <div className="text-xs text-gray-400">{s.label}</div>
        </div>
      ))}
    </div>
  );
}

export default function FollowupsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [dayFilter, setDayFilter] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [actionId, setActionId] = useState<number | null>(null);

  const fetchAll = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const params: any = { page: p };
      if (dayFilter) params.followup_day = dayFilter;
      if (statusFilter) params.status = statusFilter;
      const [itemsRes, statsRes] = await Promise.all([
        followupsApi.list(params),
        followupsApi.stats(),
      ]);
      setItems(itemsRes.data.items);
      setTotal(itemsRes.data.total);
      setStats(statsRes.data);
      setPage(p);
    } finally { setLoading(false); }
  }, [dayFilter, statusFilter]);

  useEffect(() => { fetchAll(1); }, [fetchAll]);

  const handleTrigger = async (id: number) => {
    setActionId(id);
    try { await followupsApi.trigger(id); fetchAll(page); }
    catch (e: any) { alert(e.response?.data?.detail || "Failed."); }
    finally { setActionId(null); }
  };

  const handleCancel = async (id: number) => {
    if (!confirm("Cancel this follow-up?")) return;
    setActionId(id);
    try { await followupsApi.cancel(id); fetchAll(page); }
    catch (e: any) { alert(e.response?.data?.detail || "Failed."); }
    finally { setActionId(null); }
  };

  const pages = Math.ceil(total / 20);
  const now = new Date();

  return (
    <div className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Follow-ups</h1>
          <p className="text-sm text-gray-500 mt-0.5">Day 3 & Day 6 sequences · auto-sent every 15 min</p>
        </div>
        <button onClick={() => fetchAll(page)} className="btn-secondary"><RefreshCw size={14} /> Refresh</button>
      </div>

      <StatsBar stats={stats} />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 p-4 card">
        <div className="form-group">
          <label className="label">Follow-up Day</label>
          <select className="select" value={dayFilter || ""} onChange={e => setDayFilter(Number(e.target.value) || null)}>
            <option value="">All days</option>
            <option value="3">Day 3</option>
            <option value="6">Day 6</option>
          </select>
        </div>
        <div className="form-group">
          <label className="label">Status</label>
          <select className="select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="sent">Sent</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-indigo-600" /></div>
        ) : items.length === 0 ? (
          <div className="text-center py-12">
            <RefreshCw size={32} className="mx-auto mb-3 text-gray-200" />
            <p className="text-sm text-gray-400">No follow-ups match filters</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    {["Lead", "Original Subject", "Day", "Scheduled", "Status", "Overdue", "Actions"].map(h => (
                      <th key={h} className="table-header">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => {
                    const scheduledDate = new Date(item.scheduled_at);
                    const isOverdue = item.status === "pending" && scheduledDate < now;
                    return (
                      <tr key={item.id} className={`hover:bg-gray-50 transition-colors ${isOverdue ? "bg-red-50/40" : ""}`}>
                        <td className="table-cell">
                          <p className="text-xs font-medium text-gray-800">{item.lead_name || "—"}</p>
                          <p className="text-[11px] text-indigo-500">{item.lead_email}</p>
                        </td>
                        <td className="table-cell max-w-[200px]">
                          <p className="text-xs text-gray-600 truncate">{item.original_subject || "—"}</p>
                        </td>
                        <td className="table-cell">
                          <span className={`badge ${item.followup_day === 3 ? "badge-blue" : "badge-purple"}`}>
                            Day {item.followup_day}
                          </span>
                        </td>
                        <td className="table-cell text-xs text-gray-400 whitespace-nowrap">
                          {scheduledDate.toLocaleString()}
                        </td>
                        <td className="table-cell"><StatusBadge status={item.status} /></td>
                        <td className="table-cell">
                          {isOverdue ? (
                            <span className="flex items-center gap-1 text-xs text-red-600 font-medium">
                              <AlertCircle size={12} /> Overdue
                            </span>
                          ) : item.status === "pending" ? (
                            <span className="flex items-center gap-1 text-xs text-gray-400">
                              <Clock size={12} /> Scheduled
                            </span>
                          ) : "—"}
                        </td>
                        <td className="table-cell">
                          {item.status === "pending" && (
                            <div className="flex items-center gap-1">
                              <button onClick={() => handleTrigger(item.id)} disabled={actionId === item.id}
                                className="p-1.5 hover:bg-emerald-50 rounded-lg text-emerald-600" title="Send Now">
                                {actionId === item.id ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                              </button>
                              <button onClick={() => handleCancel(item.id)} disabled={actionId === item.id}
                                className="p-1.5 hover:bg-red-50 rounded-lg text-red-400" title="Cancel">
                                <X size={13} />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {pages > 1 && (
              <div className="flex justify-center gap-2 p-4 border-t border-gray-50">
                <button onClick={() => fetchAll(page - 1)} disabled={page === 1} className="btn-secondary py-1 px-3 text-xs disabled:opacity-40">Prev</button>
                <span className="text-xs text-gray-500 py-1.5 px-2">Page {page} of {pages}</span>
                <button onClick={() => fetchAll(page + 1)} disabled={page === pages} className="btn-secondary py-1 px-3 text-xs disabled:opacity-40">Next</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
