"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/ui";

/** Shown in place of a page that crashed while rendering. The rest of the app keeps working. */
export default function PageError({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div className="space-y-4 py-10">
      <p className="eyebrow text-bad">Something went wrong</p>
      <h1>This page hit a problem</h1>
      <p className="max-w-lg text-sm opacity-75">
        It wasn&apos;t anything you did. Try again; if it keeps happening, go
        back to the overview and carry on from there.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => retry()}>Try again</Button>
        <Link href="/dashboard" className="btn btn-secondary">
          Back to overview
        </Link>
      </div>
    </div>
  );
}
