"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from "recharts";
import {
  Send, MessageSquare, RefreshCw, Mail, Rocket, TrendingUp,
  Clock, ArrowRight, Pause, Play
} from "lucide-react";
import { analyticsApi, emailsApi, repliesApi, campaignsApi, followupsApi } from "@/lib/api";

interface StatCard {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
  href?: string;
  suffix?: string;
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [recentSent, setRecentSent] = useState<any[]>([]);
  const [recentReplies, setRecentReplies] = useState<any[]>([]);
  const [activeCampaigns, setActiveCampaigns] = useState<any[]>([]);
  const [followupStats, setFollowupStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [ovRes, tlRes, sentRes, repRes, campRes, fupRes] = await Promise.allSettled([
        analyticsApi.overview(),
        analyticsApi.timeline(7),
        emailsApi.list({ page: 1 }),
        repliesApi.list({ page: 1 }),
        campaignsApi.list(),
        followupsApi.stats(),
      ]);

      if (ovRes.status === "fulfilled") setOverview(ovRes.value.data);
      if (tlRes.status === "fulfilled") setTimeline(tlRes.value.data.slice(-7));
      if (sentRes.status === "fulfilled") setRecentSent(sentRes.value.data.items?.slice(0, 10) || []);
      if (repRes.status === "fulfilled") setRecentReplies(repRes.value.data.items?.slice(0, 5) || []);
      if (campRes.status === "fulfilled") {
        setActiveCampaigns(campRes.value.data.filter((c: any) => c.status === "running").slice(0, 3));
      }
      if (fupRes.status === "fulfilled") setFollowupStats(fupRes.value.data);
    } catch (e) {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const statCards: StatCard[] = [
    {
      label: "Emails Sent Today",
      value: overview?.total_sent ?? "—",
      icon: Send,
      color: "#6c63ff",
      href: "/sent",
    },
    {
      label: "Total Replies",
      value: overview?.total_replies ?? "—",
      icon: MessageSquare,
      color: "#22c55e",
      href: "/replies",
    },
    {
      label: "Pending Follow-ups",
      value: followupStats?.pending_total ?? "—",
      icon: RefreshCw,
      color: "#f59e0b",
      href: "/followups",
    },
    {
      label: "Active Campaigns",
      value: activeCampaigns.length,
      icon: Rocket,
      color: "#3b82f6",
      href: "/campaigns",
    },
    {
      label: "Reply Rate",
      value: overview?.reply_rate ?? "—",
      icon: TrendingUp,
      color: "#8b5cf6",
      suffix: "%",
    },
    {
      label: "Bounce Rate",
      value: overview?.bounce_rate ?? "—",
      icon: Mail,
      color: "#ef4444",
      suffix: "%",
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">ASAGUS Cold Email System — real-time overview</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Clock size={12} />
          <span>Auto-refreshes every 30s</span>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="stat-card group">
              <div className="flex items-center justify-between mb-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center"
                  style={{ background: card.color + "20" }}
                >
                  <Icon size={15} style={{ color: card.color }} />
                </div>
                {card.href && (
                  <Link href={card.href}>
                    <ArrowRight size={13} className="text-gray-300 group-hover:text-indigo-500 transition-colors" />
                  </Link>
                )}
              </div>
              <div className="text-2xl font-bold text-gray-900">
                {card.value}
                {card.suffix && <span className="text-base font-medium text-gray-500">{card.suffix}</span>}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">{card.label}</div>
            </div>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Sent Bar Chart */}
        <div className="card">
          <h2 className="section-title">Emails Sent — Last 7 Days</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={timeline} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb", fontSize: "12px" }}
                labelFormatter={(d) => `Date: ${d}`}
              />
              <Bar dataKey="sent" fill="#6c63ff" radius={[4, 4, 0, 0]} name="Sent" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Replies Line Chart */}
        <div className="card">
          <h2 className="section-title">Replies Received — Last 7 Days</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={timeline} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb", fontSize: "12px" }}
              />
              <Line
                type="monotone" dataKey="replied" stroke="#22c55e"
                strokeWidth={2.5} dot={{ fill: "#22c55e", r: 3 }} name="Replies"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Active Campaigns + Recent Activity */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Active Campaigns */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title mb-0">Active Campaigns</h2>
            <Link href="/campaigns" className="text-xs text-indigo-600 hover:underline">View all</Link>
          </div>
          {activeCampaigns.length === 0 ? (
            <div className="text-center py-8 text-sm text-gray-400">
              <Rocket size={28} className="mx-auto mb-2 text-gray-200" />
              No running campaigns
            </div>
          ) : (
            <div className="space-y-3">
              {activeCampaigns.map((c: any) => {
                const pct = c.total_targets > 0 ? Math.round((c.sent_count / c.total_targets) * 100) : 0;
                return (
                  <div key={c.id} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-800 truncate">{c.name}</span>
                      <span className="badge-green text-[10px]">Running</span>
                    </div>
                    <div className="progress-bar-bg mb-1.5">
                      <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>{c.sent_count} sent</span>
                      <span>{c.total_targets} total ({pct}%)</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title mb-0">Recent Activity</h2>
          </div>
          <div className="space-y-2">
            {recentSent.slice(0, 5).map((e: any) => (
              <div key={`sent-${e.id}`} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-0">
                <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                  <Send size={10} className="text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-700 truncate">
                    {e.lead_name || e.lead_email} — {e.subject}
                  </p>
                  <p className="text-[11px] text-gray-400">
                    {new Date(e.sent_at).toLocaleString()}
                  </p>
                </div>
                <span className={`badge text-[10px] ${e.status === "sent" ? "badge-green" : "badge-red"}`}>
                  {e.status}
                </span>
              </div>
            ))}
            {recentReplies.slice(0, 3).map((r: any) => (
              <div key={`rep-${r.id}`} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-0">
                <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                  <MessageSquare size={10} className="text-emerald-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-700 truncate">
                    Reply from {r.from_name || r.from_email}
                  </p>
                  <p className="text-[11px] text-gray-400">
                    {new Date(r.received_at).toLocaleString()}
                  </p>
                </div>
                {!r.is_read && (
                  <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" title="Unread" />
                )}
              </div>
            ))}
            {recentSent.length === 0 && recentReplies.length === 0 && (
              <div className="text-center py-8 text-sm text-gray-400">No recent activity</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
