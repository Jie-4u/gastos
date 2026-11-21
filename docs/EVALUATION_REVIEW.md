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
| Multi-account and wallet management | **Not addressed** | There is no `Account`/wallet model or `account_id` field. `Tx` only has family, user, kind, amount, category, note, date, status (`app.py:182-193`). |
| Separate wallet balances and initial balances | **Not addressed** | The dashboard computes one global balance from all income minus expenses (`app.py:1330-1338`); no initial-balance field or account-balance screen exists. |
| Assign expenses to Cash, BPI, GCash, etc. | **Not addressed** | The transaction form only collects kind, amount, category, date, and note (`public/app.js:225-233`); there is no account selector. |
| Savings contribution rules | **Partially addressed** | Goals can be created by the owner/Parent and members can add savings (`app.py:1514-1544`), but there is no contribution history and no rule connecting completed transactions to goals. |
| Owner/Parent vs Member permissions | **Addressed in code; documentation is stale** | `can_manage_finances` allows the owner or a Parent (`app.py:113-115`); bills, budgets, goals, and approvals use it (`app.py:1449,1516,1549`). Members can still add to goals (`app.py:1535`). `docs/SETUP.md:41` still says only the owner can manage bills/budgets/goals. |
| Family-finance positioning | **Partially addressed** | Family membership, roles, invitations, shared bills/budgets/goals, member attribution, and expense approvals exist. It is still a single global ledger, so the multi-wallet household workflow is missing. |
| Competitive benchmarking | **No evidence in the repo** | No benchmark notes or comparison document exists under `docs/`. |
| Subscription value and paid tier | **Partially addressed** | Premium tiers and feature gating are present (`public/app.js:305-310`) and the backend has PayMongo checkout (`app.py:1004`), but the served UI still uses the demo upgrade endpoint (`public/app.js:402,450`), not the real checkout. |
| 24-hour UX fixes | **Mixed** | Sticky navigation is done; savings UX is partial; navigation lag is unverified. |
| Multi-account architecture | **Not done** | No account model, initial balance, or transaction-to-account association. |
| Parent/owner permissions | **Done in code** | The Parent role and management permissions are implemented; documentation needs updating. |
| Internal self-adoption and external user testing | **No evidence in the repo** | No testing notes, user feedback, or reviewer-access record exists. Only automated tests and setup/payment documentation are present. |
| Business documentation and sandbox integration | **Partially done** | Deployment and PayMongo setup documentation exists in `docs/SETUP.md`; no business or market documentation is present. |
| Phase 3 timeline | **Cannot verify / likely past due** | The report targets the second week of November; today is November 21, and the repository contains no completion evidence for the user-testing and reviewer follow-up items. |

## Main conclusions

1. **Multi-account/wallet tracking is still completely missing.** The app remains a single global ledger.
2. **The savings module still has no contribution rules or history.** It only increments a saved total manually.
3. **The sticky-control and savings-interaction criticisms are mostly outdated.** The Add Transaction control is persistently visible, and savings contributions use a bottom-sheet flow instead of an unstructured popup.
4. **The permission criticism is largely outdated in code.** Parent and owner management rights exist, but `docs/SETUP.md` still describes an older owner-only model.
5. **The paid subscription path is not fully delivered in the UI.** The backend supports PayMongo checkout, but the served upgrade button still calls the demo endpoint.

## Recommended follow-up

- Build the account/wallet model with opening balances, account-scoped transaction assignment, and account-level balances.
- Add savings contribution history and define whether completed transactions automatically contribute to goals.
- Review navigation rendering and API loading behavior, then add a regression test or performance check for the reported lag.
- Connect the served Premium flow to `/api/subscriptions/checkout`, or remove the demo upgrade path from production.
- Update `docs/SETUP.md:41` to reflect the current Parent and Member permissions.
- Add evidence for external user testing, reviewer access, and business/market documentation if those tasks have been completed outside the repository.
