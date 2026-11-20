"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { BellIcon } from "@/components/brand/brand";
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
      className="relative grid h-9 w-9 place-items-center rounded-[2px] border border-line-strong bg-surface transition-colors hover:border-ink"
    >
      <BellIcon />
      {unread > 0 && (
        <span
          data-testid="unread-badge"
          className="absolute -top-2 -right-2 min-w-5 rounded-[2px] bg-volt px-1 text-center font-mono text-[0.65rem] leading-5 font-bold text-volt-ink"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
