# Known issues and open decisions

Found during the manual QA round (adversarial API probing, concurrency races, a ~4,000 request fuzz of every endpoint, cross-organization access sweeps and UI checks). Everything not listed here either passed or was fixed in the same round (see the git history for "QA").

## Open: needs a product decision
1. **Signing another club's network player leaks your club name.** Adding a player that another organization shared on the network to your squad (now only possible after signing them in your pipeline) opens a career spell at *your* club on their record. Their owner, and every organization that can see the player, can then read your private club's name and the date. Options: record such spells only on your own side (an org-private overlay), or let owners/clubs opt in to public career entries.
2. **Open assignment gets stuck when its scout leaves or is deactivated.** The scout loses access to it, and the manager's only option is to cancel and recreate. Reassigning an accepted/in-progress assignment would also have to decide what happens to the old scout's draft reports.

## Open: security hardening before production
3. No limit on how many organizations one user can create.
4. No Content-Security-Policy on the frontend (needs nonce handling for Next.js inline scripts).
5. Access tokens stay valid for up to 5 minutes after logout (standard JWT trade-off; was 15).
6. **Password recovery and email verification are still missing.** `users.email_verified_at` exists but is never set or checked, so any email can register. Needs an email provider decision.
7. The backend image runs as root (the frontend production image does not). Switching needs the existing `media` volume's ownership changed first.

Fixed in the hardening round: sign-in throttling (per email and per IP, in Redis), a startup guard that refuses development settings in staging/production, HSTS outside local, tighter CORS, a production frontend image, and a database rule allowing one pending player claim per account.

## Dev-only noise
8. Next.js 16 dev mode logs "instant navigation" validation errors in the browser console for every route. They do not appear in production builds and do not affect behaviour.

## Player photos
- Photos are stored on the backend's local disk (Docker volume `media`). Before running more than one backend instance, or for backups, move them to object storage (S3 / MinIO) behind the existing storage interface.
- Signed photo URLs are bearer-like: anyone holding one can view that photo until it expires (2 to 4 hours). They are only ever given to users allowed to see the player.

## Player accounts
- Claims are verified by name plus exact date of birth, then approved by the owning organization. There is no email or document check, and no way yet for a club to invite a player to claim a specific record.
- Minors cannot change their visibility or contact settings until a parent/guardian consent flow exists; the club has to act on their behalf.
- A player account sees only its own profile and career. Viewing who has looked at or shortlisted them, trial invitations and messaging are not built.

## Engineering follow-ups (not bugs)
- Transactions are committed inside individual services rather than at one request boundary, and some database errors are classified by message text. Both work and are covered by tests; tidy them when the next large refactor happens.
- Headings are styled by unlayered `main h1/h2/h3` rules, which win over utility classes on purpose; moving them into a CSS layer needs every page's leftover `text-2xl` heading classes removed first.
- There are unit and API tests but no browser end-to-end tests yet.
