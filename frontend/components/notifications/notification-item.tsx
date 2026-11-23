"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import {
  CheckIcon,
  ClipboardIcon,
  ClockIcon,
  ReportIcon,
  ShareIcon,
  StarIcon,
  TargetIcon,
} from "@/components/ui/icons";
import { useAuth } from "@/lib/auth";
import { shortDateTime, timeAgo } from "@/lib/format";
import { apiFetch } from "@/lib/http";
import type { AppNotification } from "@/lib/types";

type Meta = {
  category: "Assignments" | "Reports" | "Recruitment" | "Players";
  tone: string;
  Icon: (p: { className?: string }) => React.ReactNode;
  /** Used on the preferences screen: "Notify me when…" */
  when: string;
};

const GOOD = "bg-ok-soft text-ok";
const BAD = "bg-bad-soft text-bad";
const WARN = "bg-warn-soft text-warn";
const INFO = "bg-info-soft text-info";
const VOLT = "bg-volt/30 text-ink";

export const NOTIFICATION_META: Record<string, Meta> = {
  assignment_assigned: {
    category: "Assignments",
    tone: INFO,
    Icon: ClipboardIcon,
    when: "I'm given a new assignment",
  },
  assignment_accepted: {
    category: "Assignments",
    tone: INFO,
    Icon: ClipboardIcon,
    when: "A scout accepts an assignment",
  },
  assignment_submitted: {
    category: "Assignments",
    tone: INFO,
    Icon: ClipboardIcon,
    when: "A scout submits an assignment",
  },
  assignment_approved: {
    category: "Assignments",
    tone: GOOD,
    Icon: ClipboardIcon,
    when: "My assignment is approved",
  },
  assignment_rejected: {
    category: "Assignments",
    tone: BAD,
    Icon: ClipboardIcon,
    when: "My assignment is rejected",
  },
  assignment_returned: {
    category: "Assignments",
    tone: WARN,
    Icon: ClipboardIcon,
    when: "My assignment is sent back for more work",
  },
  assignment_cancelled: {
    category: "Assignments",
    tone: BAD,
    Icon: ClipboardIcon,
    when: "One of my assignments is cancelled",
  },
  assignment_deadline: {
    category: "Assignments",
    tone: WARN,
    Icon: ClockIcon,
    when: "An assignment deadline is close",
  },
  report_submitted: {
    category: "Reports",
    tone: INFO,
    Icon: ReportIcon,
    when: "A report is submitted for review",
  },
  report_approved: {
    category: "Reports",
    tone: GOOD,
    Icon: ReportIcon,
    when: "My report is approved",
  },
  report_rejected: {
    category: "Reports",
    tone: BAD,
    Icon: ReportIcon,
    when: "My report is rejected",
  },
  report_revision_requested: {
    category: "Reports",
    tone: WARN,
    Icon: ReportIcon,
    when: "Changes are requested on my report",
  },
  recruitment_status_updated: {
    category: "Recruitment",
    tone: VOLT,
    Icon: TargetIcon,
    when: "A candidate moves stage in a pipeline",
  },
  player_shortlisted: {
    category: "Recruitment",
    tone: VOLT,
    Icon: StarIcon,
    when: "A player is added to a shortlist",
  },
  shortlist_shared: {
    category: "Recruitment",
    tone: VOLT,
    Icon: ShareIcon,
    when: "A shortlist is shared with me",
  },
};

NOTIFICATION_META.player_claim_requested = {
  category: "Players",
  tone: INFO,
  Icon: StarIcon,
  when: "A player asks to link their account to your record",
};
NOTIFICATION_META.player_claim_approved = {
  category: "Players",
  tone: GOOD,
  Icon: StarIcon,
  when: "My request to link my profile is approved",
};
NOTIFICATION_META.player_claim_rejected = {
  category: "Players",
  tone: BAD,
  Icon: StarIcon,
  when: "My request to link my profile is declined",
};

NOTIFICATION_META.player_profile_updated = {
  category: "Players",
  tone: INFO,
  Icon: StarIcon,
  when: "A linked player edits their own profile",
};

NOTIFICATION_META.candidate_signed = {
  category: "Recruitment",
  tone: VOLT,
  Icon: TargetIcon,
  when: "A candidate signs and needs adding to a team",
};
NOTIFICATION_META.squad_joined = {
  category: "Players",
  tone: GOOD,
  Icon: TargetIcon,
  when: "I'm added to or moved between a club's teams",
};
NOTIFICATION_META.squad_left = {
  category: "Players",
  tone: WARN,
  Icon: TargetIcon,
  when: "I'm released from a team",
};

const FALLBACK: Meta = {
  category: "Assignments",
  tone: "bg-surface-2 text-ink",
  Icon: ClipboardIcon,
  when: "",
};

export function metaFor(type: string): Meta {
  return NOTIFICATION_META[type] ?? FALLBACK;
}

/** Mark-one and mark-all, refreshing every notification query (list, bell, count). */
export function useNotificationActions() {
  const qc = useQueryClient();
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
  return { markRead, markAll };
}

/**
 * One notification. The whole item opens its link; a notification from another of your
 * organizations switches to that organization first, so the link resolves.
 */
export function NotificationItem({
  n,
  compact = false,
  onOpen,
}: {
  n: AppNotification;
  compact?: boolean;
  onOpen?: () => void;
}) {
  const { memberships, activeOrgId, selectOrg } = useAuth();
  const { markRead } = useNotificationActions();
  const meta = metaFor(n.type);
  const otherOrg =
    n.organization_id && n.organization_id !== activeOrgId
      ? memberships.find((m) => m.organization_id === n.organization_id)
      : undefined;

  const open = () => {
    if (!n.read) markRead.mutate(n.id);
    if (otherOrg) selectOrg(otherOrg.organization_id);
    onOpen?.();
  };

  return (
    <li
      className={`notif group relative flex gap-3 border-b border-line-soft transition-colors last:border-b-0 hover:bg-hover ${
        compact ? "px-4 py-3" : "px-4 py-4 sm:px-5"
      } ${n.read ? "" : "bg-volt/[0.06]"}`}
    >
      {!n.read && (
        <span
          aria-hidden="true"
          className="absolute inset-y-0 left-0 w-[3px] bg-volt"
        />
      )}
      <span
        aria-hidden="true"
        className={`grid shrink-0 place-items-center rounded-[3px] ${meta.tone} ${
          compact ? "h-8 w-8" : "h-10 w-10"
        }`}
      >
        <meta.Icon className={compact ? "h-4 w-4" : "h-5 w-5"} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <p
            className={`text-sm leading-snug ${n.read ? "opacity-75" : "font-semibold"}`}
          >
            {!n.read && <span className="sr-only">Unread: </span>}
            {n.link_path ? (
              <Link href={n.link_path} onClick={open} className="row-link">
                {n.title}
              </Link>
            ) : (
              n.title
            )}
          </p>
          <time
            dateTime={n.created_at}
            title={shortDateTime(n.created_at)}
            className="shrink-0 pt-0.5 font-mono text-[0.68rem] whitespace-nowrap opacity-55"
          >
            {timeAgo(n.created_at)}
          </time>
        </div>
        {n.body && (
          <p
            className={`mt-0.5 text-sm opacity-70 ${compact ? "line-clamp-1" : "line-clamp-2"}`}
          >
            {n.body}
          </p>
        )}
        {!compact && (
          <p className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="eyebrow opacity-50">{meta.category}</span>
            {otherOrg && (
              <span className="chip chip-outline">
                {otherOrg.organization_name}
              </span>
            )}
          </p>
        )}
      </div>
      {!n.read && (
        <button
          type="button"
          onClick={() => markRead.mutate(n.id)}
          disabled={markRead.isPending}
          aria-label={`Mark "${n.title}" as read`}
          title="Mark as read"
          className="relative z-10 grid h-7 w-7 shrink-0 place-items-center self-center rounded-[2px] border border-line-strong bg-surface opacity-100 transition-opacity hover:border-ink sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
        >
          <CheckIcon className="h-3.5 w-3.5" />
        </button>
      )}
    </li>
  );
}
