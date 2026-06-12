"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, Send, Users, FileText, Rocket, Inbox,
  RefreshCw, MessageSquare, Flame, BarChart2, Zap
} from "lucide-react";
import { repliesApi } from "@/lib/api";

const navItems = [
  { href: "/dashboard",  label: "Dashboard",   icon: LayoutDashboard },
  { href: "/senders",    label: "Senders",      icon: Send },
  { href: "/leads",      label: "Leads",        icon: Users },
  { href: "/templates",  label: "Templates",    icon: FileText },
  { href: "/campaigns",  label: "Campaigns",    icon: Rocket },
  { href: "/sent",       label: "Sent",         icon: Inbox },
  { href: "/followups",  label: "Follow-ups",   icon: RefreshCw },
  { href: "/replies",    label: "Replies",      icon: MessageSquare, badge: true },
  { href: "/warmup",     label: "Warm-up",      icon: Flame },
  { href: "/analytics",  label: "Analytics",    icon: BarChart2 },
];

export function Sidebar() {
  const pathname = usePathname();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const fetchUnread = async () => {
      try {
        const res = await repliesApi.stats();
        setUnreadCount(res.data.unread_count || 0);
      } catch {
        // Backend might not be ready yet
      }
    };
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside
      className="flex flex-col h-screen overflow-y-auto"
      style={{
        width: "220px",
        minWidth: "220px",
        background: "linear-gradient(180deg, #0f0f1a 0%, #1a1040 100%)",
        borderRight: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: "linear-gradient(135deg, #6c63ff, #a78bfa)" }}
        >
          <Zap size={16} color="white" />
        </div>
        <div>
          <div className="text-white font-bold text-sm leading-tight">ASAGUS</div>
          <div className="text-purple-300 text-[10px] leading-tight">Mailer v2.0</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group relative
                ${isActive
                  ? "text-white bg-white/10 border border-white/10"
                  : "text-gray-400 hover:text-white hover:bg-white/5"
                }
              `}
            >
              {/* Active indicator */}
              {isActive && (
                <span
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full"
                  style={{ background: "#a78bfa" }}
                />
              )}
              <Icon
                size={16}
                className={isActive ? "text-purple-300" : "text-gray-500 group-hover:text-gray-300"}
              />
              <span className="flex-1">{item.label}</span>
              {item.badge && unreadCount > 0 && (
                <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none min-w-[18px] text-center">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/10">
        <div className="text-[11px] text-gray-600 leading-relaxed">
          <div className="text-gray-500 font-medium mb-1">Cold Email System</div>
          <div>© 2025 ASAGUS</div>
        </div>
      </div>
    </aside>
  );
}
