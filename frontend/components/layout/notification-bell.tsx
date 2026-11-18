"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiFetch } from "@/lib/http";

/** Polls the unread count. (Real-time delivery over WebSockets is a planned upgrade.) */
export function NotificationBell() {
  const { data } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => apiFetch<{ unread: number }>("/notifications/unread-count"),
    refetchInterval: 30_000,
  });
  const unread = data?.unread ?? 0;
  return (
    <Link
      href="/notifications"
      aria-label={
        unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
      }
      className="relative rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
    >
      <span aria-hidden="true">🔔</span>
      {unread > 0 && (
        <span
          data-testid="unread-badge"
          className="absolute -right-2 -top-2 min-w-5 rounded-full bg-teal-600 px-1.5 text-center text-xs font-semibold text-white"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
