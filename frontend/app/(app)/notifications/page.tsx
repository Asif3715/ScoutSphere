"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button, Card, Empty, ErrorText, Pagination } from "@/components/ui/ui";
import { apiFetch } from "@/lib/http";
import { label, type AppNotification, type Page } from "@/lib/types";

type Pref = { type: string; enabled: boolean };

export default function NotificationsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);

  const list = useQuery({
    queryKey: ["notifications", "list", page, unreadOnly],
    queryFn: () =>
      apiFetch<Page<AppNotification>>(
        `/notifications?page=${page}&page_size=15${unreadOnly ? "&unread=true" : ""}`,
      ),
  });
  const prefs = useQuery({
    queryKey: ["notifications", "prefs"],
    queryFn: () => apiFetch<Pref[]>("/notifications/preferences"),
    enabled: showPrefs,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["notifications"] });

  const markRead = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: refresh,
  });
  const markAll = useMutation({
    mutationFn: () => apiFetch("/notifications/read-all", { method: "POST" }),
    onSuccess: refresh,
  });
  const setPref = useMutation({
    mutationFn: (v: Pref) =>
      apiFetch<Pref[]>("/notifications/preferences", {
        method: "PUT",
        json: { preferences: { [v.type]: v.enabled } },
      }),
    onSuccess: (data) => qc.setQueryData(["notifications", "prefs"], data),
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowPrefs((s) => !s)}>
            {showPrefs ? "Hide preferences" : "Preferences"}
          </Button>
          <Button variant="secondary" onClick={() => markAll.mutate()}>
            Mark all read
          </Button>
        </div>
      </header>

      {showPrefs && (
        <Card className="space-y-2">
          <h2 className="font-semibold">Which notifications do you want?</h2>
          {prefs.data?.map((p) => (
            <label key={p.type} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={p.enabled}
                onChange={(e) =>
                  setPref.mutate({ type: p.type, enabled: e.target.checked })
                }
              />
              {label(p.type)}
            </label>
          ))}
        </Card>
      )}

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(e) => {
            setUnreadOnly(e.target.checked);
            setPage(1);
          }}
        />
        Unread only
      </label>

      {list.isLoading && <p aria-busy="true">Loading…</p>}
      <ErrorText>{list.error?.message}</ErrorText>
      {list.data && list.data.items.length === 0 && (
        <Empty>You are all caught up.</Empty>
      )}
      {list.data && list.data.items.length > 0 && (
        <>
          <ul className="space-y-2">
            {list.data.items.map((n) => (
              <li
                key={n.id}
                className={`flex items-start justify-between gap-3 rounded-md border px-3 py-2 text-sm ${
                  n.read
                    ? "border-slate-200 opacity-70 dark:border-slate-800"
                    : "border-teal-400"
                }`}
              >
                <div>
                  <p className="font-medium">
                    {!n.read && (
                      <span
                        aria-label="unread"
                        className="mr-2 inline-block size-2 rounded-full bg-teal-600"
                      />
                    )}
                    {n.link_path ? (
                      <Link
                        href={n.link_path}
                        className="text-teal-600 hover:underline"
                        onClick={() => !n.read && markRead.mutate(n.id)}
                      >
                        {n.title}
                      </Link>
                    ) : (
                      n.title
                    )}
                  </p>
                  {n.body && <p className="text-xs opacity-80">{n.body}</p>}
                  <p className="text-xs opacity-50">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </div>
                {!n.read && (
                  <Button
                    variant="secondary"
                    onClick={() => markRead.mutate(n.id)}
                  >
                    Mark read
                  </Button>
                )}
              </li>
            ))}
          </ul>
          <Pagination
            page={list.data.page}
            pageSize={list.data.page_size}
            total={list.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
