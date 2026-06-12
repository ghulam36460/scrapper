"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Loader2, RefreshCw, MessageSquare, Check, UserX,
  Send, X, ExternalLink, AlertCircle, Bell
} from "lucide-react";
import { repliesApi } from "@/lib/api";

const MATCH_COLORS: Record<string, string> = {
  message_id: "badge-green",
  subject_similarity: "badge-blue",
  sender_match: "badge-yellow",
  thread_heuristic: "badge-yellow",
  unmatched: "badge-red",
};

function MatchBadge({ method, confidence }: { method: string; confidence: number }) {
  const labels: Record<string, string> = {
    message_id: "Message-ID",
    subject_similarity: "Subject Match",
    sender_match: "Sender Match",
    thread_heuristic: "Thread",
    unmatched: "Unmatched",
  };
  return (
    <span className={`badge ${MATCH_COLORS[method] || "badge-gray"} gap-1`} title={`Confidence: ${Math.round(confidence * 100)}%`}>
      {labels[method] || method}
      <span className="opacity-70">·{Math.round(confidence * 100)}%</span>
    </span>
  );
}

function InlineReplyBox({ reply, onSent }: { reply: any; onSent: () => void }) {
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSend = async () => {
    if (!body.trim()) return;
    setSending(true); setError("");
    try {
      await repliesApi.reply(reply.id, body);
      setSent(true); onSent();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to send reply.");
    } finally { setSending(false); }
  };

  if (sent) return <div className="alert-success flex items-center gap-2 text-xs"><Check size={13} /> Reply sent!</div>;

  return (
    <div className="mt-4 border-t border-gray-100 pt-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Reply to {reply.from_email}</p>
      {error && <div className="alert-error text-xs mb-2">{error}</div>}
      <textarea
        className="input font-mono text-xs resize-none mb-2"
        rows={5}
        value={body}
        onChange={e => setBody(e.target.value)}
        placeholder="Type your reply..."
      />
      <div className="flex justify-end gap-2">
        <button onClick={handleSend} disabled={sending || !body.trim()} className="btn-primary text-xs py-1.5">
          {sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          Send Reply
        </button>
      </div>
    </div>
  );
}

function ReplyDetail({ reply, onClose, onUpdated }: { reply: any; onClose: () => void; onUpdated: () => void }) {
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showReplyBox, setShowReplyBox] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    repliesApi.get(reply.id).then(r => setDetail(r.data)).finally(() => setLoading(false));
  }, [reply.id]);

  const handleUnsubscribe = async () => {
    if (!confirm(`Mark ${reply.from_email} as unsubscribed?`)) return;
    setActionLoading(true);
    try { await repliesApi.markUnsubscribe(reply.id); onUpdated(); onClose(); }
    catch { alert("Failed."); }
    finally { setActionLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-end">
      <div className="bg-white w-full max-w-xl h-full flex flex-col shadow-2xl overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b sticky top-0 bg-white z-10">
          <div>
            <p className="font-semibold text-gray-900 text-sm">{reply.from_name || reply.from_email}</p>
            <p className="text-xs text-gray-400 mt-0.5">{reply.from_email}</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg"><X size={16} /></button>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 size={20} className="animate-spin text-indigo-600" /></div>
        ) : detail ? (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Meta */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-gray-400">Received</p>
                <p className="font-medium">{new Date(detail.received_at).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-gray-400">Match Method</p>
                <MatchBadge method={detail.match_method} confidence={detail.match_confidence} />
              </div>
              {detail.lead?.business_name && (
                <div>
                  <p className="text-gray-400">Business</p>
                  <p className="font-medium">{detail.lead.business_name}</p>
                </div>
              )}
              <div>
                <p className="text-gray-400">Lead Status</p>
                <span className="badge-green">{detail.lead?.status || "—"}</span>
              </div>
            </div>

            {/* Auto-unsub banner */}
            {detail.is_auto_unsubscribe && (
              <div className="alert-warning flex items-center gap-2">
                <AlertCircle size={14} /> Auto-detected unsubscribe request — lead marked unsubscribed
              </div>
            )}

            {/* Subject */}
            <div>
              <p className="text-xs text-gray-400 mb-1">Subject</p>
              <p className="font-semibold text-gray-800">{detail.subject}</p>
            </div>

            {/* Reply body */}
            <div>
              <p className="text-xs text-gray-400 mb-1">Reply Content</p>
              <div className="bg-gray-50 rounded-xl p-4 text-sm text-gray-700 whitespace-pre-wrap font-sans">
                {detail.body}
              </div>
            </div>

            {/* Original email context */}
            {detail.original_email && (
              <div className="border border-gray-100 rounded-xl p-4">
                <p className="text-xs font-semibold text-gray-400 uppercase mb-2">Original Email Sent</p>
                <p className="text-xs font-medium text-gray-700">{detail.original_email.subject}</p>
                <p className="text-xs text-gray-400">{new Date(detail.original_email.sent_at).toLocaleString()}</p>
                <div className="mt-2 bg-gray-50 p-3 rounded-lg text-xs text-gray-600 max-h-28 overflow-y-auto font-mono whitespace-pre-wrap">
                  {detail.original_email.body?.slice(0, 500)}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
              {!detail.replied_back && (
                <button onClick={() => setShowReplyBox(!showReplyBox)} className="btn-primary text-xs py-1.5">
                  <Send size={12} /> Reply
                </button>
              )}
              <button onClick={handleUnsubscribe} disabled={actionLoading} className="btn-danger text-xs py-1.5">
                {actionLoading ? <Loader2 size={12} className="animate-spin" /> : <UserX size={12} />}
                Unsubscribe
              </button>
              {detail.replied_back && (
                <div className="alert-success text-xs flex items-center gap-1">
                  <Check size={12} /> Replied at {new Date(detail.replied_at).toLocaleString()}
                </div>
              )}
            </div>

            {showReplyBox && !detail.replied_back && (
              <InlineReplyBox
                reply={detail}
                onSent={() => { setShowReplyBox(false); onUpdated(); }}
              />
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function RepliesPage() {
  const [replies, setReplies] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [polling, setPolling] = useState(false);
  const [selectedReply, setSelectedReply] = useState<any | null>(null);

  const fetchAll = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const [repliesRes, statsRes] = await Promise.all([
        repliesApi.list({ unread_only: unreadOnly, page: p }),
        repliesApi.stats(),
      ]);
      setReplies(repliesRes.data.items);
      setTotal(repliesRes.data.total);
      setStats(statsRes.data);
      setPage(p);
    } finally { setLoading(false); }
  }, [unreadOnly]);

  useEffect(() => { fetchAll(1); }, [fetchAll]);

  const handlePollNow = async () => {
    setPolling(true);
    try { await repliesApi.poll(); await new Promise(r => setTimeout(r, 2000)); fetchAll(1); }
    finally { setPolling(false); }
  };

  const pages = Math.ceil(total / 20);

  return (
    <div className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Inbox — Replies</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {stats?.unread_count ?? 0} unread · {stats?.total ?? 0} total · IMAP polls every 5 min
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handlePollNow} disabled={polling} className="btn-secondary">
            {polling ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Poll Now
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Unread", value: stats.unread_count, color: "text-red-600" },
            { label: "Total Replies", value: stats.total, color: "text-indigo-600" },
            { label: "Auto-Unsubscribed", value: stats.auto_unsubscribed_count, color: "text-amber-600" },
          ].map(s => (
            <div key={s.label} className="stat-card">
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-gray-400">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3 p-3 card">
        <label className="flex items-center gap-2.5 cursor-pointer text-sm text-gray-700">
          <div onClick={() => setUnreadOnly(!unreadOnly)}
            className={`w-9 h-5 rounded-full relative transition-all cursor-pointer ${unreadOnly ? "bg-indigo-600" : "bg-gray-200"}`}>
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${unreadOnly ? "left-4" : "left-0.5"}`} />
          </div>
          Show Unread Only
        </label>
        {stats?.unread_count > 0 && (
          <span className="ml-auto text-xs text-red-600 flex items-center gap-1">
            <Bell size={12} /> {stats.unread_count} unread
          </span>
        )}
      </div>

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-indigo-600" /></div>
        ) : replies.length === 0 ? (
          <div className="text-center py-12">
            <MessageSquare size={32} className="mx-auto mb-3 text-gray-200" />
            <p className="text-sm text-gray-400">No replies yet</p>
            <p className="text-xs text-gray-300 mt-1">Add IMAP credentials to sender accounts to enable reply detection</p>
          </div>
        ) : (
          <>
            <div className="divide-y divide-gray-50">
              {replies.map(r => (
                <div
                  key={r.id}
                  onClick={() => setSelectedReply(r)}
                  className={`flex items-start gap-4 p-4 cursor-pointer hover:bg-gray-50 transition-colors ${!r.is_read ? "bg-indigo-50/30" : ""}`}
                >
                  {/* Unread indicator */}
                  <div className="w-2 shrink-0 flex justify-center pt-2">
                    {!r.is_read && <span className="w-2 h-2 rounded-full bg-indigo-600" />}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className={`text-sm ${!r.is_read ? "font-semibold text-gray-900" : "font-medium text-gray-700"} truncate`}>
                        {r.from_name || r.from_email}
                      </p>
                      {r.is_auto_unsubscribe && (
                        <span className="badge-yellow text-[10px] shrink-0">Unsub intent</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 truncate">{r.subject}</p>
                    <p className="text-xs text-gray-400 truncate mt-0.5">{r.body?.slice(0, 120)}</p>
                  </div>

                  <div className="shrink-0 text-right space-y-1">
                    <p className="text-[11px] text-gray-400">{new Date(r.received_at).toLocaleDateString()}</p>
                    <MatchBadge method={r.match_method} confidence={r.match_confidence} />
                    {r.replied_back && (
                      <span className="badge-green text-[10px] block">Replied</span>
                    )}
                  </div>
                </div>
              ))}
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

      {selectedReply && (
        <ReplyDetail
          reply={selectedReply}
          onClose={() => setSelectedReply(null)}
          onUpdated={() => fetchAll(page)}
        />
      )}
    </div>
  );
}
