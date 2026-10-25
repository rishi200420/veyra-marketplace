# VEYRA — Milestone 14: Security & Launch Readiness

This is a pre-launch checklist, not a claim that the marketplace is production-ready. Complete each item against the actual deployment environment before accepting public orders.

## Implemented in this milestone
- Admin sidebar navigation scrolls independently so Sign out remains visible on desktop; mobile navigation retains access to Sign out.
- API adds baseline security response headers (`nosniff`, frame denial, referrer policy, restrictive permissions policy). HSTS is emitted only when `APP_ENV=production`; production must be HTTPS-only.
- CORS methods and request headers are explicit rather than wildcarded. Set `CORS_ORIGINS` to the exact production frontend origin(s).
- FastAPI interactive docs and OpenAPI schema are disabled when `APP_ENV=production`.
- `.env.example` documents the environment switch. Never copy real secrets into source control.

## Required before a public launch
- [ ] Build frontend successfully (`npm ci` then `npm run build`) and test all pages in a real browser.
- [ ] Run backend tests against a backup/staging database; verify customer isolation, all Founder/Manager/Worker permissions, staff deactivation, logout/session expiry, and direct API access denial.
- [ ] Replace all development secrets with unique randomly generated secrets. Rotate any token/password that was shared, screenshotted, or committed. Keep `.env` files out of ZIPs and source control.
- [ ] Set `APP_ENV=production`; set `CORS_ORIGINS` to exact HTTPS origins only. Confirm API is reachable only over HTTPS behind a correctly configured reverse proxy.
- [ ] Use a production database with backups and a tested restore procedure; do not deploy the local SQLite database as a multi-worker production database.
- [ ] Add rate limiting / lockout and monitoring for customer and staff login, registration, and founder bootstrap; verify bootstrap cannot be used after the first Founder exists.
- [ ] Verify upload file type/content, size limits, random filenames, and safe static serving; run malware scanning or a trusted upload policy as appropriate.
- [ ] Add privacy policy, terms, finalized shipping/returns policies, support contact, data retention/deletion process, and consent/notice for customer data.
- [ ] Confirm rights and licensing for every product image and brand asset; replace illustrative products/prices with approved catalogue data.
- [ ] Configure and test email provider, delivery failures, and notification content. Do not include passwords, tokens, payment secrets, or sensitive customer data in logs/emails.
- [ ] Test order, parcel, cancellation, return, and refund workflows using non-production test data. Refund status records do not move money.
- [ ] Payment gateway integration is intentionally skipped for now. Do not advertise online payment as available or accept real paid orders until a provider is integrated and server-side payment verification/webhooks are implemented and tested.
- [ ] Configure error monitoring, backups, dependency/security updates, incident response, and production secrets management.

## Local smoke test
1. Keep `APP_ENV=development` locally.
2. Start backend and frontend; check `/health` and the storefront/admin.
3. Confirm response headers in browser developer tools or `curl -I http://127.0.0.1:8001/health`.
4. In admin, visit every page at a short desktop viewport and verify the sidebar can scroll and Sign out stays visible. On mobile, verify navigation and Sign out remain reachable.
5. Run `npm ci` and `npm run build`; fix any reported TypeScript/build issues before release.

## Known limitations
- This milestone adds baseline hardening and a launch checklist, not a complete independent security audit. Rate limiting, production database/deployment setup, payment integration, carrier integration, and full automated end-to-end testing remain launch blockers.
