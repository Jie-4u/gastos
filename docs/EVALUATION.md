Project Evaluation and Technical Recommendation Report: Gastos App

1. Executive Summary and Evaluation Context

This report provides a comprehensive synthesis of the evaluation comments, technical critiques, and strategic suggestions recorded during the Phase 3 project evaluation for Group 4 (Section 31) regarding the Gastos App—a mobile financial management application.

During the feedback review, the evaluator assessed the current build as straddling the boundary between an Early Prototype and a Minimum Viable Product (MVP). While the foundation is in place, the application currently functions primarily as a basic Create, Read, Update, and Delete (CRUD) input system rather than a feature-complete financial management platform. To progress toward a market-ready release, the development team must establish robust business rules, implement multi-account tracking, redesign the savings experience, and strengthen the app's family-oriented value proposition.

"Ah siguro for me, masyado pa siyang hindi pa tumatawid. Silver lining between MVP and Prototype. Medyo parang yung paa nakapasok na pero yung ibang parts hindi pa. Imagine-in niyo nung i-re-release niyo na 'to: is this something you would use?" — Feedback Transcript, Gastos App Evaluation

The sections that follow detail all specific critiques and recommendations organized by domain, providing Group 4 with an actionable development blueprint.

2. User Interface and Navigation Enhancements

Testing during the evaluation session highlighted several user experience (UX) bottlenecks that impede fluid transaction logging and financial tracking. Addressing these interface mechanics is critical to ensuring baseline usability.

2.1 Persistent Controls and Navigation Stability

* Sticky "Add Transaction" Action Button: In the current implementation, when a user accumulates a large number of entries (such as 100 or more recorded transactions), the primary "Add Transaction" button disappears off-screen or gets buried at the bottom of the scroll list. The layout structure must be updated so that the primary entry button and navigation bar remain permanently visible and pinned (sticky) regardless of list length.
* Navigation Persistence and Lag Prevention: The review noted technical lag and state dropouts during specific user actions (such as copying data or executing background routines within 30-second windows). The team must optimize navigation handlers so that navigation bars do not freeze or disappear during active use.

2.2 Savings Input Interface Redesign

The input mechanism for entering savings data was singled out as a notable UX flaw. The current implementation relies on jarring modal popups that disrupt the user's flow and lack aesthetic integration.

The development team must replace modal popups with contextual input drawers or inline screens. The table below outlines the specific UX upgrades required for the savings workflow.

Interface Element	Current State	Target Enhancement
Savings Entry Trigger	Unclear or non-intuitive action button	Prominent, dedicated visual call-to-action
Data Entry Container	Disrupted popup modal overlay	Polished bottom-sheet drawer or dedicated sub-screen
Input Feedback	Minimal confirmation upon entry	Visual progress updates toward target savings goals

3. Core Financial Modules and Data Architecture

The evaluation's most significant functional feedback targeted missing data structures and incomplete financial rules. The recorded feedback highlights that the application currently lacks core accounting logic and account segregation.

3.1 Multi-Account and Wallet Management (Critical Missed Module)

A primary structural oversight in the current build is the absence of distinct financial account entities (such as Cash wallets, Bank accounts like BPI, or E-wallets like GCash).

1. Unified vs. Segregated Balances: Currently, the application displays a single, global balance across all entries. Users cannot establish distinct initial balances for individual wallets or bank accounts, causing wallet balances to default repeatedly back to zero.
2. Real-World Expense Attribution: Real-world financial tracking requires deducting expenses from specific liquidity sources (e.g., paying an expense out of GCash vs. physical cash). The data schema must be expanded to support multiple sub-accounts under a user profile, allowing transactions to be assigned to specific funding sources.

3.2 Savings Business Rules and Permission Roles

The savings module requires explicit business logic to support family collaboration:

* Clear Contribution Rules: The application must establish clear automated rules defining how completed transactions or manual inputs update overall savings progress.
* Owner vs. Member Permissions: In a family setting, Parent/Owner accounts must have administrative authority to create and adjust family savings goals, while Member accounts should have defined contribution rights to add to shared targets.

4. Strategic Product Positioning and Monetization

Beyond immediate bug fixes, the reviewer urged the development team to re-align the app with its intended market niche and articulate a viable subscription model.

4.1 Transitioning from Personal to Family Finance

Although early iterations leaned toward basic personal budgeting, the primary selling point of the Gastos App is intended to be Family Finance Management.

"Ang selling point mo diyan is family finance management... i-iterate niyo naman na pampamilya siya. Masyado siyang simple." — Feedback Transcript, Gastos App Evaluation

The current feature set is overly simplified, operating like a generic personal expense logger. Group 4 must iterate on features tailored specifically to household dynamics, such as shared family budgets, multi-member tracking, and collaborative household goals.

4.2 Competitive Benchmarking and Subscription Value

To build a product that attracts and retains users, the team must analyze existing financial applications in the market:

* Market Benchmarking: Study established finance apps online to identify intuitive user flows, adapt their simplest core features, and expand them into a multi-user "Family Mode."
* Building "Ka-Subscribe-Subscribe" Value: The app currently lacks high-value capabilities that justify a paid tier. The development team must introduce features compelling enough that users naturally want to subscribe ("ka-subscribe-subscribe"), initially prototyping subscription tiers manually or via sandbox APIs if full payment gateway integration is not yet ready.

5. Action Plan, Operational Tasks, and Deadlines

Following the Phase 3 evaluation, Group 4 must execute a series of technical, operational, and documentation tasks to fulfill project requirements.

5.1 Operational Roadmap

1. Immediate UX and Navigation Fixes (24-Hour Window):
  * Fix the layout to keep the "Add Transaction" button pinned and visible regardless of transaction volume.
  * Resolve navigation state dropouts and lag during user operations.
  * Redesign the savings popup modal into a streamlined input flow.
2. Core Architecture Expansion (Mid-November Target):
  * Build multi-account models supporting separate balances for Cash, BPI, and GCash.
  * Implement initial balance configuration and clear account-selection dropdowns for transactions.
  * Establish explicit parent/owner versus member permission rules for family accounts.
3. User Acquisition, Testing, and Documentation:
  * Internal Self-Adoption: Group 4 team members must actively use the Gastos App for their personal daily expense tracking to identify friction points firsthand.
  * External User Testing: Recruit actual users outside the dev team to gather empirical feedback on family features.
  * Business Documentation & Integrations: Prepare required business documentation and outline sandbox API integration architecture for third-party services and payment gateways.
  * Reviewer Access & Follow-Up: Provide the evaluator with direct access links and forward any additional supplementary feedback (such as Kenneth's detailed notes) for further review.

5.2 Phase 3 Evaluation Timeline

As specified during the session, Group 4 is subject to a strict post-evaluation timeline:

* Immediate Revisions: Address core feedback items within 24 hours of completing the Phase 3 evaluation session.
* Final Phase 3 Target: Complete full system updates and user testing targets by the second week of November.
