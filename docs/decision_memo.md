# Decision memo: MV switchgear sourcing for the next three build phases

| | |
|---|---|
| **To** | VP, Data Center Delivery |
| **From** | Solomon Goldiamond, Program Manager |
| **Date** | November 2, 2026 (data as of October 31, 2026) |
| **Decision needed by** | November 11, 2026 |

> All companies, projects and figures in this memo are fictional. The data is synthetic and was generated for this portfolio project.

## Recommendation

Award the medium-voltage switchgear for Licking Fields Phase 2 (P10) and Tualatin Valley Phase 1 (P11) to Halvorsen Electric instead of the incumbent, Kestrel Power Systems. Hold Chattahoochee Phase 2 (P12) open as a competitive award to be decided by February 2027.

The switch costs about **$3.3M** on those two projects and avoids about **$16.1M** of expected delay cost.

## Why now

Late switchgear is the largest single cause of schedule slip in the program, and the incumbent is getting worse each year.

- **Kestrel deliveries are late and the trend is one direction.** Across 34 lineups, Kestrel averaged 10.5 weeks behind its own promise date and met that date on 3% of lines. Average slip by order year: 3.6 weeks (2022), 7.3 (2023), 11.8 (2024), 15.0 (2025).
- **The lateness reaches the customer.** The seven projects with Kestrel switchgear are an average of 67 days late to Ready for Service. The four ordered in the last 36 months average 88 days. The two projects with Halvorsen switchgear average 26 days, and all 10 Halvorsen lineups arrived before the site needed them.
- **It is already the biggest change-order line.** Equipment-delay change orders total $28.0M, 37% of all change-order cost, and every dollar of it sits on a Kestrel project.
- **The first order is due.** P10 needs its first lineup released by November 25 on Kestrel's lead time. Halvorsen quotes about two weeks longer, which makes the effective deadline November 11.

## Options compared

Expected cost across all three unawarded projects (114 MW, 19 lineups, $53.0M of planned switchgear spend), using each vendor's full track record:

| Option | Switching cost | Deferred revenue | Delay change orders | Expected cost |
|---|---:|---:|---:|---:|
| A. Stay with Kestrel on all three | $0 | $20.7M | $15.6M | **$36.3M** |
| B. Halvorsen on all three | $4.9M | $8.0M | $0 | **$12.9M** |
| C. Halvorsen on P10 and P11, compete P12 (recommended) | $3.3M | $5.5M on P10 and P11 | $0 | **$8.8M** vs $24.9M for the same two projects under A |

How the numbers are built:

- **Switching cost** is the 7.2% price premium Halvorsen has charged over Kestrel in the same order years, plus $350K per project for engineering re-coordination and factory witness testing.
- **Deferred revenue** values each day of Ready-for-Service slip at $165 per kW-month, with only 50% of the phase assumed to be billing during the delay window.
- **Delay change orders** apply Kestrel's historical $137K per MW of equipment-delay change orders. Halvorsen projects have had none.

On Kestrel's last 36 months alone, option A rises to $46.7M and the gap widens to $34.8M.

## Why not move all three

Option B has the lowest expected cost on paper, but Halvorsen's record with us is 10 lineups on two projects. P10 and P11 together are 13 lineups, already more than everything they have delivered for this program. Holding P12 back limits exposure to an unproven volume, keeps Kestrel bidding, and gives four months of evidence on Halvorsen's P10 production slots before the next commitment.

## What would change this recommendation

- **Break-even is 16 days.** The premium pays for itself if Halvorsen beats Kestrel by 16 days of slip per project. The observed gap is 41 days on the full record and 65 days on recent orders.
- **The evidence is thin on one side.** Two Halvorsen projects is a small sample. If their factory cannot confirm slots for 13 lineups in writing, fall back to splitting P10 between both vendors.
- **Not every late day is Kestrel's.** On Licking Fields Phase 1 the utility energized 57 days late, so its 60-day slip cannot be pinned on switchgear alone. Excluding that project, the Kestrel average is 68 days and the conclusion is unchanged.
- **Delay costs are understated for projects still in construction**, because change orders for delay already incurred have not all been issued. That biases the comparison in Kestrel's favor.

## Next steps

1. Approve the P10 and P11 award to Halvorsen by November 11.
2. Procurement obtains written production-slot confirmation and liquidated damages for late delivery before release.
3. Issue Kestrel a formal recovery-plan request for the 4 lineups still undelivered on Red Oak Phase 2 (P09).
4. Revisit P12 in February 2027 with Halvorsen's P10 factory progress and Kestrel's response in hand.

---

*Sources: `sql/analysis/03_vendor_scorecard.sql`, `04_switchgear_trend.sql`, `05_change_orders_by_cause.sql` and `07_decision_dual_source.sql`, run against `db/buildout.db`. Planning assumptions are stored in the `program_assumptions` table.*
