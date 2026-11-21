# Gastos implementation audit

## Architecture found

- Flask serves the UI and JSON API from one process (`app.py`).
- The browser UI is vanilla JavaScript and CSS in `public/`; there is no frontend build step.
- Flask-SQLAlchemy uses SQLite in development (`instance/gastos.db`) and requires PostgreSQL in production through `DATABASE_URL`.
- Passwords use Werkzeug password hashing. Bearer sessions use signed `itsdangerous` tokens.
- The schema is created with `db.create_all()` plus additive compatibility changes at startup. The starting repository lacked a migration framework, provider adapters, tests, project README, and external integration instructions; the local `.env` now contains the user-configured service settings.

## Implementation checklist

### Critical bugs

- [x] Remove automatic family joining during signup.
- [x] Stop the upgrade endpoint from assigning Premium without payment.
- [x] Fix authorization header validation and expired-session handling.
- [x] Prevent duplicate bill payment transactions.
- [x] Add transaction editing and deletion.
- [ ] Add server-side membership and owner permissions to every family action.

### Authentication and account management

- [x] Enforce an eight-character minimum password and validate required signup fields.
- [x] Keep password hashing and signed session tokens.
- [x] Add one-time, 15-minute password reset links with generic responses and session invalidation.
- [ ] Add account verification and broader per-IP rate limiting.

### Family and invitations

- [x] Persist expiring, revocable, email-specific signed invitations; upgrade legacy pending invitation rows during startup migration.
- [x] Use the configured public app origin, provide branded HTML/plain-text messages, persist delivery status, and support copy, resend, and cancel.
- [x] Require matching email; new invited users join the authoritative family in the same database transaction as signup.
- [x] Make same-family invitation acceptance idempotent and allow expired invitations to be resent.
- [x] Enforce Free/Premium member slot limits during invitation and acceptance.
- [x] Add optional SMTP email delivery with a share-link fallback and persistent delivery status.
- [ ] Complete a real Brevo delivery check and verify the sender/domain in Brevo.
- [x] Enforce baseline Owner/Member permissions on the server: members can add/edit their own transactions and contribute to shared savings goals; owners control other members' records and family administration.
- [x] Add owner removal of family members while preserving the member account and history.

### Financial features

- [x] Keep family-scoped reads and writes for existing transactions, bills, goals, and reports.
- [x] Add transaction editing/deletion, search, category/type/month filters, sorting, and monthly category budgets.
- [ ] Add debt/tuition ledgers, expense approvals, and goal contribution history (these modules do not exist in the original schema).
- [x] Reject malformed dates/transaction kinds and non-finite amounts; prevent duplicate bill payment transactions.

### Premium and payments

- [x] Remove one-click Premium activation; the legacy upgrade endpoint now fails closed.
- [x] Keep plan prices visible, enforce server-side ownership checks, and fail closed at the checkout boundary.
- [x] Store a subscription lifecycle schema for future verified payment events.
- [x] Add PayMongo plan validation, customer/subscription creation, first-payment setup, status refresh, signed webhook validation, event deduplication, and subscription cancellation. Premium remains fail-closed until a provider status confirms active.
- [ ] Complete test-mode checkout, renewal, failure, and cancellation against PayMongo after Subscriptions/Card Vaulting are enabled and test plans are created. The account's subscriptions endpoint previously returned HTTP 403.
- [ ] Add refund handling and reconcile payment status from asynchronous renewal events in the enabled account.
- [ ] Add API entitlement checks for individual Premium features as those features are implemented.

### UI/UX

- [x] Add data-backed category donut and six-month income/expense chart, summary cards, budget progress, recent transactions, and upcoming bills.
- [x] Improve invitation, family, budget, transaction, password-reset, and plan-selection screens; add responsive layouts, focus styles, touch targets, and submit loading feedback.
- [ ] Complete loading/empty/error states throughout the app and implement missing debt/tuition and notification screens.

### Testing and security

- [x] Remove unsafe implicit invitation acceptance and restrict invitation administration to the owner.
- [x] Require `SECRET_KEY` and `APP_BASE_URL` in production configuration for relevant flows.
- [x] Add regression tests for Free defaults, fail-closed Premium, invitation expiry/resend/revocation/acceptance/signup, email matching and HTML delivery, password reset, transaction/budget behavior, family isolation, and duplicate bill payment prevention.
- [ ] Add end-to-end testing against real ngrok, Brevo, and an activated PayMongo test account.
- [ ] Configure deployment HTTPS, CSRF strategy, rate limiting, database access policies, and production logging.

## Database changes

`Invite` gained token digest/nonce, role, inviter, timestamps, and revocation/acceptance fields. Startup applies additive `ALTER TABLE` changes for existing databases, while `create_all()` creates the new subscription table. Existing data is preserved. There is no migration runner in this repository; a formal versioned migration framework should replace startup DDL before multi-instance production deployment.

## Configuration and running

- Copy `.env.example` to `.env`, install `requirements.txt`, then run `python app.py`. Details are in [docs/SETUP.md](docs/SETUP.md).
- Run regression checks with `python -m unittest discover -s tests`.
- `DATABASE_URL` is optional in development/test; unset uses SQLite. Production requires a PostgreSQL URL.
- Startup requires an explicit `APP_ENV` of `development`, `test`, or `production`. Production also requires a persistent 32+ character `SECRET_KEY`, canonical HTTPS `APP_BASE_URL`, and PostgreSQL; unsafe configuration fails before the app serves traffic.
- SMTP variables are private local configuration. Delivery logic is covered with a mocked SMTP server; a real Brevo delivery is not yet verified.
- PayMongo checkout and webhook handling are implemented and mocked in regression tests. Real checkout is not verified; the account previously returned HTTP 403 for subscription plans and still needs capability activation, test plan IDs, and a registered webhook.

## Verification status

- JavaScript syntax check, Python syntax compilation, and `git diff --check` passed using the bundled runtimes.
- All 11 Flask regression tests pass, including invitation flows, mocked SMTP, password resets, budgets, transaction CRUD, family isolation, financial validation, and fail-closed Premium.
- Python compilation, JavaScript syntax checking, and `git diff --check` pass.
- The app's current ngrok tunnel was observed forwarding to local port 80 while Gastos responds on port 5000. The tunnel must be restarted with port 5000, and the Flask process must reload the current `APP_BASE_URL`, before remote invitation links work.
- Real Brevo delivery and PayMongo checkout remain unverified. The PayMongo subscription API returned 403 previously, and its application adapter is not implemented.
- Debt/tuition ledgers, scheduled notifications, budgets entitlement limits, and production migration automation remain incomplete.
- The app has not been verified as a complete production-ready application.
