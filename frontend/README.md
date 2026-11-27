# ScoutSphere frontend

Next.js 16 (App Router, `cacheComponents`), React 19, TypeScript, Tailwind CSS v4, TanStack Query,
React Hook Form + Zod, Vitest. See the repository [README](../README.md) for running the whole
stack and [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how the pieces fit.

```bash
pnpm install
pnpm dev          # http://localhost:3000 (expects the API on NEXT_PUBLIC_API_URL)
pnpm lint && pnpm typecheck && pnpm test
pnpm build        # production build (also what the Docker `prod` target runs)
```

## Layout

- `app/` routes. `(auth)` holds sign-in and registration; `(app)` is everything behind sign-in,
  wrapped by `components/layout/protected.tsx` (club staff get the sidebar shell, player accounts
  get the player portal). `error.tsx` and `not-found.tsx` handle crashes and unknown URLs.
- `components/ui/` shared building blocks: `data-table.tsx` (page header, table frame, filters,
  skeleton rows), `person.tsx` (role badges, avatars), `icons.tsx`, `ui.tsx` (buttons, cards).
- `lib/http.ts` the API client: in-memory access token, silent refresh, and a session-expired
  event the auth provider listens to. `lib/auth.tsx` holds the user, memberships and active
  organization, and clears cached data when any of those change.
- `lib/fetch-all.ts` fetches every page of a list for pickers; `lib/format.ts` dates;
  `lib/tabs.ts` keyboard support for tab bars.
- `app/globals.css` design tokens (light and dark) and component classes.

The browser never stores tokens: the access token lives in memory, the refresh token in an
httpOnly cookie. Everything the UI hides is also enforced by the API.
