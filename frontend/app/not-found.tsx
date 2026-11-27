import Link from "next/link";

import { LogoMark } from "@/components/brand/brand";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center px-6">
      <div className="max-w-md space-y-4 text-center">
        <LogoMark className="mx-auto h-12 w-12" />
        <p className="eyebrow text-link">Error 404</p>
        <h1 className="font-display text-5xl leading-none font-extrabold uppercase">
          Off the pitch
        </h1>
        <p className="text-sm opacity-75">
          That page doesn&apos;t exist, or the link is out of date.
        </p>
        <div className="flex justify-center gap-2">
          <Link href="/dashboard" className="btn btn-primary">
            Go to overview
          </Link>
          <Link href="/" className="btn btn-secondary">
            Home
          </Link>
        </div>
      </div>
    </main>
  );
}
