"use client";

import { useEffect, useState, useCallback } from "react";
import { Flame, Loader2, RefreshCw, Check, Send, Inbox } from "lucide-react";
import { warmupApi, sendersApi } from "@/lib/api";

const SCHEDULE = [5, 8, 12, 16, 20, 24, 28, 32, 36, 40];

function WarmupProgress({ session }: { session: any }) {
  const daysDone = Math.max(0, session.day_number - 1);
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-800">{session.sender_name || session.sender_email}</h3>
          <p className="text-xs text-gray-400 mt-0.5">{session.sender_email}</p>
        </div>
        <span className={`badge ${session.status === "active" ? "badge-green" : session.status === "completed" ? "badge-blue" : "badge-gray"}`}>
          {session.status === "active" ? `Day ${session.day_number}` : session.status}
        </span>
      </div>

      {/* Day tiles */}
      <div className="flex gap-1.5 mb-4">
        {SCHEDULE.map((target, i) => {
          const isDone = i < daysDone;
          const isCurrent = i === daysDone && session.status === "active";
          return (
            <div
              key={i}
              title={`Day ${i + 1}: ${target} emails`}
              className={`flex-1 h-10 rounded-lg flex flex-col items-center justify-center text-[10px] font-bold transition-all ${
                isDone
                  ? "bg-indigo-600 text-white"
                  : isCurrent
                  ? "bg-indigo-100 text-indigo-700 ring-2 ring-indigo-600"
                  : "bg-gray-100 text-gray-400"
              }`}
            >
              {isDone ? <Check size={10} /> : <span>{i + 1}</span>}
              <span className="text-[9px] opacity-70">{target}e</span>
            </div>
          );
        })}
      </div>

      {/* Today's progress */}
      {session.status === "active" && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Today's target: {session.target_today} emails</span>
            <span>{session.emails_sent_today} sent</span>
          </div>
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{
              width: `${Math.min((session.emails_sent_today / Math.max(session.target_today, 1)) * 100, 100)}%`
            }} />
          </div>
        </div>
      )}

      {session.last_run_at && (
        <p className="text-[11px] text-gray-400 mt-2">Last run: {new Date(session.last_run_at).toLocaleString()}</p>
      )}
    </div>
  );
}

function WarmupLogTable({ logs, loading }: { logs: any[]; loading: boolean }) {
  if (loading) return <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-indigo-600" /></div>;
  if (logs.length === 0) return (
    <div className="text-center py-8 text-sm text-gray-400">No warmup activity yet</div>
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr>
            {["Direction", "To / From", "Subject", "Time", "Status"].map(h => (
              <th key={h} className="table-header">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {logs.map(l => (
            <tr key={l.id} className="hover:bg-gray-50">
              <td className="table-cell">
                <span className={`flex items-center gap-1 text-xs font-medium ${l.direction === "sent" ? "text-indigo-600" : "text-emerald-600"}`}>
                  {l.direction === "sent" ? <Send size={11} /> : <Inbox size={11} />}
                  {l.direction}
                </span>
              </td>
              <td className="table-cell text-xs text-gray-600">{l.to_from_email}</td>
              <td className="table-cell text-xs text-gray-500 truncate max-w-[200px]">{l.subject}</td>
              <td className="table-cell text-xs text-gray-400 whitespace-nowrap">
                {new Date(l.sent_at).toLocaleString()}
              </td>
              <td className="table-cell">
                <span className={`badge ${l.status === "ok" ? "badge-green" : "badge-red"}`}>{l.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function WarmupPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(true);
  const [senders, setSenders] = useState<any[]>([]);
  const [warmupLoading, setWarmupLoading] = useState<number | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [sessRes, logRes, senderRes] = await Promise.all([
        warmupApi.sessions(),
        warmupApi.log(),
        sendersApi.list(),
      ]);
      setSessions(sessRes.data);
      setLogs(logRes.data.items || []);
      setSenders(senderRes.data);
    } finally {
      setLoading(false);
      setLogsLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleWarmupToggle = async (sender: any) => {
    setWarmupLoading(sender.id);
    try {
      if (sender.warmup_enabled) {
        await sendersApi.stopWarmup(sender.id);
      } else {
        await sendersApi.startWarmup(sender.id);
      }
      fetchAll();
    } finally { setWarmupLoading(null); }
  };

  const activeSessions = sessions.filter(s => s.status === "active");
  const completedSessions = sessions.filter(s => s.status === "completed");

  return (
    <div className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Inbox Warm-up</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {activeSessions.length} active · {completedSessions.length} completed · Runs daily at 9am
          </p>
        </div>
        <button onClick={fetchAll} className="btn-secondary"><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* Info card */}
      <div className="card bg-gradient-to-r from-orange-50 to-amber-50 border-orange-100">
        <div className="flex gap-3">
          <Flame size={20} className="text-orange-500 shrink-0 mt-0.5" />
          <div className="text-sm text-orange-700">
            <p className="font-semibold mb-1">How Warmup Works</p>
            <p className="text-xs">
              Warmup sends emails between your own accounts (5→40/day over 10 days) to build Gmail/Zoho spam filter trust.
              After 10 days, accounts are ready for cold outreach. Requires at least 2 active sender accounts.
            </p>
          </div>
        </div>
      </div>

      {/* Sender Warmup Controls */}
      <div>
        <h2 className="section-title">Sender Accounts</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {senders.map(s => (
            <div key={s.id} className={`card flex items-center gap-4 p-4 ${s.warmup_enabled ? "border-orange-200" : ""}`}>
              <div className={`w-9 h-9 rounded-full flex items-center justify-center ${s.warmup_enabled ? "bg-orange-100" : "bg-gray-100"}`}>
                <Flame size={16} className={s.warmup_enabled ? "text-orange-500" : "text-gray-400"} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{s.display_name}</p>
                <p className="text-xs text-gray-400">{s.email}</p>
                {s.warmup_enabled && (
                  <p className="text-xs text-orange-600 font-medium mt-0.5">Day {s.warmup_day} of 10</p>
                )}
              </div>
              <button
                onClick={() => handleWarmupToggle(s)}
                disabled={warmupLoading === s.id}
                className={`shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  s.warmup_enabled
                    ? "bg-red-50 text-red-600 hover:bg-red-100"
                    : "bg-orange-50 text-orange-600 hover:bg-orange-100"
                }`}
              >
                {warmupLoading === s.id ? <Loader2 size={12} className="animate-spin inline" /> : null}
                {s.warmup_enabled ? "Stop" : "Start"}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Session Progress Cards */}
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 size={24} className="animate-spin text-indigo-600" /></div>
      ) : sessions.length === 0 ? (
        <div className="card text-center py-10">
          <Flame size={32} className="mx-auto mb-3 text-gray-200" />
          <p className="text-sm text-gray-400">No warmup sessions yet — start warmup from a sender above</p>
        </div>
      ) : (
        <div>
          <h2 className="section-title">Session Progress</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {sessions.map(s => <WarmupProgress key={s.id} session={s} />)}
          </div>
        </div>
      )}

      {/* Log */}
      <div>
        <h2 className="section-title">Activity Log</h2>
        <div className="card p-0 overflow-hidden">
          <WarmupLogTable logs={logs} loading={logsLoading} />
        </div>
      </div>
    </div>
  );
}
