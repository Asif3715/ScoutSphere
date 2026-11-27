"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  NOTIFICATION_META,
  NotificationItem,
  useNotificationActions,
} from "@/components/notifications/notification-item";
import { PageHeader } from "@/components/ui/data-table";
import { CheckAllIcon, SettingsIcon } from "@/components/ui/icons";
import { Button, ErrorText, Pagination } from "@/components/ui/ui";
import { dayGroup } from "@/lib/format";
import { apiFetch } from "@/lib/http";
import { tabKeys } from "@/lib/tabs";
import type { AppNotification, Page } from "@/lib/types";

type Pref = { type: string; enabled: boolean };
const CATEGORIES = [
  "Assignments",
  "Reports",
  "Recruitment",
  "Players",
] as const;

function groupByDay(items: AppNotification[]) {
  const groups: { day: string; items: AppNotification[] }[] = [];
  for (const n of items) {
    const day = dayGroup(n.created_at);
    const last = groups.at(-1);
    if (last && last.day === day) last.items.push(n);
    else groups.push({ day, items: [n] });
  }
  return groups;
}

function Preferences() {
  const qc = useQueryClient();
  const prefs = useQuery({
    queryKey: ["notifications", "prefs"],
    queryFn: () => apiFetch<Pref[]>("/notifications/preferences"),
  });
  const setPref = useMutation({
    mutationFn: (v: Pref) =>
      apiFetch<Pref[]>("/notifications/preferences", {
        method: "PUT",
        json: { preferences: { [v.type]: v.enabled } },
      }),
    onSuccess: (data) => qc.setQueryData(["notifications", "prefs"], data),
  });
  const byType = new Map(prefs.data?.map((p) => [p.type, p.enabled]));

  return (
    <section
      aria-labelledby="prefs-title"
      className="table-card space-y-0 lg:sticky lg:top-20"
    >
      <div className="border-b border-line px-4 py-3">
        <h2 id="prefs-title" className="flex items-center gap-2">
          <SettingsIcon className="h-4 w-4" />
          Notify me when…
        </h2>
        <p className="mt-1 text-xs opacity-60">
          Switch off what you don&apos;t need. Changes save straight away.
        </p>
      </div>
      {prefs.isLoading && (
        <div className="space-y-3 p-4" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="skeleton block h-4" />
          ))}
        </div>
      )}
      <ErrorText>{prefs.error?.message}</ErrorText>
      {prefs.data &&
        CATEGORIES.map((cat) => {
          const types = Object.entries(NOTIFICATION_META).filter(
            ([t, m]) => m.category === cat && byType.has(t),
          );
          if (types.length === 0) return null;
          return (
            <fieldset
              key={cat}
              className="border-b border-line-soft px-4 py-3 last:border-b-0"
            >
              <legend className="eyebrow float-left mb-2 w-full opacity-55">
                {cat}
              </legend>
              <div className="clear-both space-y-2.5">
                {types.map(([type, m]) => (
                  <label
                    key={type}
                    className="flex cursor-pointer items-center justify-between gap-3 text-sm"
                  >
                    <span>{m.when}</span>
                    <input
                      type="checkbox"
                      role="switch"
                      className="switch"
                      checked={byType.get(type) ?? true}
                      disabled={setPref.isPending}
                      onChange={(e) =>
                        setPref.mutate({ type, enabled: e.target.checked })
                      }
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          );
        })}
    </section>
  );
}

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const { markAll } = useNotificationActions();

  const list = useQuery({
    queryKey: ["notifications", "list", page, unreadOnly],
    queryFn: () =>
      apiFetch<Page<AppNotification>>(
        `/notifications?page=${page}&page_size=15${unreadOnly ? "&unread=true" : ""}`,
      ),
    placeholderData: (prev) => prev,
  });
  const count = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => apiFetch<{ unread: number }>("/notifications/unread-count"),
  });
  const unread = count.data?.unread ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inbox"
        title="Notifications"
        meta={
          unread > 0
            ? `You have ${unread} unread notification${unread === 1 ? "" : "s"}.`
            : "You're all caught up."
        }
        actions={
          unread > 0 && (
            <Button
              variant="secondary"
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending}
            >
              <CheckAllIcon className="h-4 w-4" />
              Mark all read
            </Button>
          )
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="table-card" aria-label="Notifications">
          <div className="table-toolbar items-center! py-2!">
            <div
              role="tablist"
              onKeyDown={tabKeys}
              aria-label="Filter"
              className="flex rounded-[2px] border border-line-strong p-0.5"
            >
              {[
                { key: false, text: "All" },
                { key: true, text: "Unread" },
              ].map((t) => (
                <button
                  key={t.text}
                  role="tab"
                  aria-selected={unreadOnly === t.key}
                  tabIndex={unreadOnly === t.key ? 0 : -1}
                  onClick={() => (setUnreadOnly(t.key), setPage(1))}
                  className={`eyebrow flex items-center gap-2 rounded-[1px] px-3 py-2 transition-colors ${
                    unreadOnly === t.key
                      ? "bg-accent text-accent-ink"
                      : "opacity-70 hover:opacity-100"
                  }`}
                >
                  {t.text}
                  {t.key && unread > 0 && (
                    <span className="rounded-[2px] bg-volt px-1 text-volt-ink">
                      {unread}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {list.isLoading && (
            <div className="space-y-5 p-5" aria-busy="true">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="flex gap-3">
                  <span className="skeleton h-10 w-10 shrink-0" />
                  <span className="flex-1 space-y-2">
                    <span className="skeleton block h-3.5 w-2/3" />
                    <span className="skeleton block h-3 w-1/2" />
                  </span>
                </div>
              ))}
            </div>
          )}
          {list.error && (
            <div className="p-5">
              <ErrorText>{list.error.message}</ErrorText>
            </div>
          )}
          {list.data && list.data.items.length === 0 && (
            <div className="px-6 py-16 text-center">
              <p className="font-display text-2xl font-bold uppercase">
                {unreadOnly ? "Nothing unread" : "No notifications yet"}
              </p>
              <p className="mt-2 text-sm opacity-65">
                {unreadOnly
                  ? "You've read everything. Nice work."
                  : "Updates about assignments, reports and recruitment will appear here."}
              </p>
            </div>
          )}
          {list.data &&
            groupByDay(list.data.items).map((g) => (
              <section key={g.day} aria-label={g.day}>
                <h3 className="border-b border-line-soft bg-surface-2/60 px-5 py-1.5 opacity-80">
                  {g.day}
                </h3>
                <ul>
                  {g.items.map((n) => (
                    <NotificationItem key={n.id} n={n} />
                  ))}
                </ul>
              </section>
            ))}
          {list.data && list.data.total > list.data.page_size && (
            <div className="table-footer">
              <Pagination
                page={list.data.page}
                pageSize={list.data.page_size}
                total={list.data.total}
                onChange={setPage}
              />
            </div>
          )}
        </section>

        <Preferences />
      </div>
    </div>
  );
}
