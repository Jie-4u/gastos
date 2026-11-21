# Evaluation review against the current project

2026-11-21

> Written by AI after reading `docs/EVALUATION.md` and checking the current code and documentation. This is a review note, not an authoritative product decision. Verify the findings and run the test suite before relying on them.

## Scope

This review compares the Phase 3 evaluation comments in `docs/EVALUATION.md` with the current repository state as of 2026-11-21. It covers the UI, financial modules, family permissions, subscription flow, and the operational roadmap.

The review was read-only. No application code was changed.

**Verification limit:** The test suite could not be executed because `.venv/bin/python` points to a missing `/usr/bin/python3`. The findings below come from reading the code and documentation, not from a runtime test or browser session.

## Status summary

| Evaluation comment | Current state | Evidence |
|---|---|---|
| Sticky “Add Transaction” button and navigation | **Addressed** | Mobile navigation is fixed and contains the FAB (`public/style.css:63,67`); desktop navigation is sticky (`public/style.css:329`); navigation is rendered with each main view (`public/app.js:317-318`). |
| Navigation persistence and lag prevention | **Not verified / unresolved** | The app replaces the whole view and re-fetches on each navigation (`public/app.js:322-334`); no targeted performance work or tests exist. The reported 30-second issue could not be reproduced. |
| Savings entry trigger | **Partially addressed** | Each goal has an “Add” button and there is a dedicated new-goal screen (`public/app.js:257,264`); contribution still starts from a small action button. |
| Savings entry container | **Partially addressed** | `A.fund` uses the shared bottom-sheet component with quick amount buttons (`public/app.js:437`; sheet at `public/app.js:80`). It is still an overlay sheet rather than inline, but matches the report’s “bottom-sheet drawer” option. |
| Savings input feedback | **Partially addressed** | The sheet shows saved/target and a success toast (`public/app.js:437,406`); progress updates after re-render rather than live while entering an amount. |
| Multi-account and wallet management | **Addressed for family-shared wallets** | The `Account` model stores family wallets, type, and opening balance (`app.py:183-203`); `Tx.account_id` links each transaction to a wallet; account APIs and a Wallets tab were added (`app.py:1320-1415`; `public/app.js:265`). |
| Separate wallet balances and initial balances | **Addressed** | `account_snapshot` calculates opening balance plus approved income, minus approved expenses, plus transfers (`app.py:1256-1273`); the dashboard returns wallet balances and a total (`app.py:1595-1605`); the home screen shows a Wallets card. |
| Assign expenses to Cash, BPI, GCash, etc. | **Addressed** | The transaction form now has an account selector (`public/app.js:225-235`), and transaction responses include account names (`app.py:1440-1448`). |
| Savings contribution rules | **Addressed for manual contributions** | Owner/Parent creates goals; members and owners can add manual contributions with a contributor/date/note history. Contributions stop at the target amount. Transactions do not automatically contribute to goals yet. |

| Owner/Parent vs Member permissions | **Addressed** | `can_manage_finances` allows the owner or a Parent (`app.py:113-115`); bills, budgets, goals, approvals, and wallets use it. Members can still add to goals and log their own transactions. `docs/SETUP.md` now reflects the current roles. |
| Family-finance positioning | **Partially addressed** | Family membership, roles, invitations, shared bills/budgets/goals, member attribution, expense approvals, and family-shared wallets now exist. Private per-member wallets are not included. |
| Competitive benchmarking | **No evidence in the repo** | No benchmark notes or comparison document exists under `docs/`. |
| Subscription value and paid tier | **Partially addressed** | Premium tiers and feature gating are present (`public/app.js:305-310`) and the backend has PayMongo checkout (`app.py:1004`), but the served UI still uses the demo upgrade endpoint (`public/app.js:402,450`), not the real checkout. |
| 24-hour UX fixes | **Mixed** | Sticky navigation is done; savings UX is partial; navigation lag is unverified. |
| Multi-account architecture | **Done for shared family wallets** | Account model, opening balances, transaction assignment, transfers, and wallet balance display were added. |
| Parent/owner permissions | **Done in code** | The Parent role and management permissions are implemented; documentation needs updating. |
| Internal self-adoption and external user testing | **No evidence in the repo** | No testing notes, user feedback, or reviewer-access record exists. Only automated tests and setup/payment documentation are present. |
| Business documentation and sandbox integration | **Partially done** | Deployment and PayMongo setup documentation exists in `docs/SETUP.md`; no business or market documentation is present. |
| Phase 3 timeline | **Cannot verify / likely past due** | The report targets the second week of November; today is November 21, and the repository contains no completion evidence for the user-testing and reviewer follow-up items. |

## Main conclusions

1. **Family-shared multi-account/wallet tracking is now implemented.** The app has opening balances, transaction-to-wallet assignment, transfers, and wallet balances. Private per-member wallets remain a separate follow-up.
2. **Savings now has manual contribution rules and history.** Each contribution is recorded with its contributor, date, amount, and note, and cannot exceed the remaining target.
3. **The sticky-control and savings-interaction criticisms are mostly outdated.** The Add Transaction control is persistently visible, and savings contributions use a bottom-sheet flow instead of an unstructured popup.
4. **The permission criticism is largely outdated in code and documentation.** Parent and owner management rights exist, and `docs/SETUP.md` now describes the current model.
5. **The paid subscription path is not fully delivered in the UI.** The backend supports PayMongo checkout, but the served upgrade button still calls the demo endpoint.

## Recommended follow-up

- Add private per-member wallets only if the family visibility and owner-access rules are decided explicitly.
- Decide whether completed income transactions should automatically create savings contributions; the current version is manual-only.
- Review navigation rendering and API loading behavior, then add a regression test or performance check for the reported lag.
- Connect the served Premium flow to `/api/subscriptions/checkout`, or remove the demo upgrade path from production.
- Add evidence for external user testing, reviewer access, and business/market documentation if those tasks have been completed outside the repository.
