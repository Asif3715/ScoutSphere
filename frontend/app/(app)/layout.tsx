import { Suspense } from "react";

import { Protected } from "@/components/layout/protected";

// usePathname() inside Protected reads request-time data on dynamic routes, so it must sit
// under a Suspense boundary.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <main className="p-10" aria-busy="true">
          Loading…
        </main>
      }
    >
      <Protected>{children}</Protected>
    </Suspense>
  );
}
