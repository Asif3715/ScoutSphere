"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { BellIcon } from "@/components/brand/brand";
import {
  NotificationItem,
  useNotificationActions,
} from "@/components/notifications/notification-item";
import { ArrowRightIcon, CheckAllIcon } from "@/components/ui/icons";
import { apiFetch } from "@/lib/http";
import type { AppNotification, Page } from "@/lib/types";

/**
 * The bell shows the unread count and opens a panel with the latest notifications.
 * Polls the count every 30s (real-time delivery over WebSockets is a planned upgrade).
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const { markAll } = useNotificationActions();

  const { data } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => apiFetch<{ unread: number }>("/notifications/unread-count"),
    refetchInterval: 30_000,
  });
  const latest = useQuery({
    queryKey: ["notifications", "peek"],
    queryFn: () =>
      apiFetch<Page<AppNotification>>("/notifications?page=1&page_size=6"),
    enabled: open,
  });
  const unread = data?.unread ?? 0;

  // Close when the route changes, on Escape, or on a click outside the panel.
  const [lastPath, setLastPath] = useState(pathname);
  if (lastPath !== pathname) {
    setLastPath(pathname);
    setOpen(false);
  }
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={wrap} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
        }
        className={`relative grid h-9 w-9 place-items-center rounded-[2px] border bg-surface transition-colors hover:border-ink ${
          open ? "border-ink" : "border-line-strong"
        }`}
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
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label="Latest notifications"
          className="page-pop fixed inset-x-3 top-16 z-40 overflow-hidden rounded-[4px] border border-line-strong bg-surface shadow-[0_24px_48px_-20px_rgb(0_0_0/0.45)] sm:absolute sm:inset-x-auto sm:top-12 sm:right-0 sm:w-[24rem]"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <p className="font-display text-lg leading-none font-bold uppercase">
                Notifications
              </p>
              <p className="eyebrow mt-1 opacity-55">
                {unread > 0 ? `${unread} unread` : "All caught up"}
              </p>
            </div>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markAll.mutate()}
                disabled={markAll.isPending}
                className="eyebrow flex items-center gap-1.5 rounded-[2px] px-2 py-1.5 text-link transition-colors hover:bg-hover"
              >
                <CheckAllIcon className="h-4 w-4" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[min(26rem,60vh)] overflow-y-auto">
            {latest.isLoading && (
              <div className="space-y-3 p-4" aria-busy="true">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="flex gap-3">
                    <span className="skeleton h-8 w-8 shrink-0" />
                    <span className="flex-1 space-y-2">
                      <span className="skeleton block h-3 w-3/4" />
                      <span className="skeleton block h-3 w-1/2" />
                    </span>
                  </div>
                ))}
              </div>
            )}
            {latest.data && latest.data.items.length === 0 && (
              <div className="px-6 py-10 text-center">
                <BellIcon />
                <p className="mt-2 text-sm opacity-70">
                  Nothing yet. Updates about assignments, reports and
                  recruitment will appear here.
                </p>
              </div>
            )}
            {latest.data && latest.data.items.length > 0 && (
              <ul>
                {latest.data.items.map((n) => (
                  <NotificationItem
                    key={n.id}
                    n={n}
                    compact
                    onOpen={() => setOpen(false)}
                  />
                ))}
              </ul>
            )}
          </div>

          <Link
            href="/notifications"
            className="eyebrow flex items-center justify-center gap-2 border-t border-line bg-surface-2/50 px-4 py-3 transition-colors hover:bg-hover"
          >
            See all notifications
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
    </div>
  );
}
