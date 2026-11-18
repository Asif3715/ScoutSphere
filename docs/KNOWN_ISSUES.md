# Known issues and open decisions

Found during the manual QA round (adversarial API probing, concurrency races, a ~4,000 request fuzz of every endpoint, cross-organization access sweeps and UI checks). Everything not listed here either passed or was fixed in the same round (see the git history for "QA").

## Open: needs a product decision
1. **Signing another club's network player leaks your club name.** Adding a player that another organization shared on the network to your squad opens a career spell at *your* club on their record. Their owner, and every organization that can see the player, can then read your private club's name and the date. Options: record such spells only on your own side (an org-private overlay), or let owners/clubs opt in to public career entries.
2. **Open assignment gets stuck when its scout leaves or is deactivated.** The scout loses access to it, and the manager's only option is to cancel and recreate. Reassigning an accepted/in-progress assignment would also have to decide what happens to the old scout's draft reports.

## Open: security hardening before production
3. **No login rate limiting or lockout** (40 wrong passwords in 3.5 s were all processed). Needs per-IP and per-account throttling (Redis is already available).
4. No limit on how many organizations one user can create.
5. No Content-Security-Policy on the frontend (needs nonce handling for Next.js inline scripts).
6. Access tokens stay valid for up to 15 minutes after logout (standard JWT trade-off).
7. Password recovery and email verification are still missing (planned).

## Dev-only noise
8. Next.js 16 dev mode logs "instant navigation" validation errors in the browser console for every route. They do not appear in production builds and do not affect behaviour.
