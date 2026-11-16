# Data dictionary

Database: `db/buildout.db` (SQLite). Schema: `sql/schema.sql`. Reporting views: `sql/views.sql`.

All data is synthetic. Data cut-off ("as of") date: **2026-10-31**, stored in `program_assumptions`.

Conventions

- Dates are ISO-8601 text (`YYYY-MM-DD`).
- Money is US dollars, stored as numbers with no formatting. Negative amounts are credits.
- Capacity is critical IT load in megawatts (MW).
- "Slip" is always *current minus baseline* in days. Positive means late.

## Glossary

| Term | Meaning |
|---|---|
| RFS | Ready for Service. The date a phase can be handed to the customer and start billing. |
| NTP | Notice to Proceed. Formal start of construction. |
| Long-lead equipment | Equipment ordered a year or more ahead: MV switchgear, generators, transformers, LV switchboards. |
| Lineup | One assembled row of MV switchgear. Ordered and delivered as a unit. |
| Required-on-site date | The date the construction schedule needs a piece of equipment delivered. |
| Float | Planned buffer between the vendor's promise date and the required-on-site date (4 weeks). |
| EAC | Estimate at Completion. Current forecast of final cost. |
| Change order (CO) | A priced change to the construction contract. |
| General conditions | The contractor's time-based site costs (staff, trailers, cranes). Grows when a job runs long. |
| L5 | Level 5 commissioning, the final integrated systems test before RFS. |
| AHJ | Authority Having Jurisdiction, the local permitting and inspection body. |

## Tables

### `sites` (6 rows)
One row per campus. Source: `sites.csv`.

| Column | Type | Description |
|---|---|---|
| `site_id` | TEXT, PK | Three-letter campus code, e.g. `LDN`. |
| `site_name` | TEXT | Campus name. |
| `metro` | TEXT | Metro market. |
| `state` | TEXT | Two-letter US state. |
| `region` | TEXT | `East`, `Central` or `West`. |
| `planned_capacity_mw` | REAL | Total IT capacity the campus is planned to hold across all phases. |

### `projects` (12 rows)
One row per build phase. Source: `projects.csv`.

| Column | Type | Description |
|---|---|---|
| `project_id` | TEXT, PK | `P01` to `P12`. |
| `site_id` | TEXT, FK → `sites` | Campus the phase is built on. |
| `phase_number` | INTEGER | Phase sequence on that campus. Unique with `site_id`. |
| `project_name` | TEXT | Campus name plus phase. |
| `project_type` | TEXT | `Greenfield` (first phase on a site) or `Expansion`. |
| `it_capacity_mw` | REAL | IT capacity delivered by this phase. |
| `general_contractor` | TEXT | Construction firm. |
| `status` | TEXT | `Pre-Construction`, `Construction`, `Commissioning` or `Complete`. |

### `milestones` (96 rows)
Eight schedule gates per project. Source: `milestones.csv` (schedule export).

| Column | Type | Description |
|---|---|---|
| `milestone_id` | INTEGER, PK | Surrogate key. |
| `project_id` | TEXT, FK → `projects` | |
| `milestone_code` | TEXT | `NTP`, `PERMIT`, `SHELL`, `UTILITY`, `GEARSET`, `MEP`, `L5`, `RFS`. Unique per project. |
| `milestone_name` | TEXT | Display name. |
| `sequence` | INTEGER | Order of the gate, 1 to 8. |
| `baseline_date` | TEXT | Date in the approved baseline schedule. |
| `forecast_date` | TEXT | Current expected date. Equals `actual_date` once complete. |
| `actual_date` | TEXT, nullable | Date achieved. NULL until complete. |
| `status` | TEXT | `Not Started`, `In Progress` or `Complete`. A CHECK constraint keeps it consistent with `actual_date`. |

### `vendors` (9 rows)
Equipment vendor master. Derived during import from the cleaned vendor names on purchase orders.

| Column | Type | Description |
|---|---|---|
| `vendor_id` | INTEGER, PK | Surrogate key. |
| `vendor_name` | TEXT, unique | Canonical name after alias matching. |

### `purchase_orders` (243 rows)
One row per equipment order line. Source: `purchase_orders.csv` (ERP export).

| Column | Type | Description |
|---|---|---|
| `po_line_id` | TEXT, PK | e.g. `PO-P08-011`. |
| `project_id` | TEXT, FK → `projects` | |
| `vendor_id` | INTEGER, FK → `vendors`, nullable | NULL means the line is not yet awarded. |
| `equipment_category` | TEXT | `Generators`, `Transformers`, `MV Switchgear`, `LV Switchboards`, `UPS`, `Chillers`, `CRAH Units`, `PDU / Busway`, `BMS / EPMS`. |
| `description` | TEXT | Item and lot. |
| `quantity` | INTEGER | Units on the line. Greater than zero. |
| `unit_cost_usd` | REAL | Price per unit. For `Planned` lines this is the budgetary price. |
| `po_value_usd` | REAL | `quantity × unit_cost_usd`, recomputed at import and checked against the source. |
| `po_date` | TEXT, nullable | Date the order was placed. NULL for `Planned` lines. |
| `quoted_lead_time_weeks` | INTEGER | Vendor's quoted lead time at order. |
| `required_on_site_date` | TEXT | Date the schedule needs delivery. |
| `original_promise_date` | TEXT, nullable | Delivery date the vendor committed to at order. |
| `current_promise_date` | TEXT, nullable | Vendor's latest promise. Equals the delivery date once delivered. |
| `actual_delivery_date` | TEXT, nullable | Date delivered. NULL until then. |
| `status` | TEXT | `Planned` (not ordered), `Open` (ordered, not delivered) or `Delivered`. |

### `change_orders` (100 rows)
One row per change order. Source: `change_orders.csv` (change-order log).

| Column | Type | Description |
|---|---|---|
| `co_id` | TEXT, PK | e.g. `CO-P05-007`. |
| `project_id` | TEXT, FK → `projects` | |
| `co_date` | TEXT | Date raised. |
| `cause_category` | TEXT | `Equipment Delay`, `Utility Delay`, `Design Change`, `Owner Scope Change`, `Unforeseen Site Condition`, `Code / AHJ Requirement`. |
| `cost_category` | TEXT | Budget line the change is charged to. Matches `cost_lines.cost_category`. |
| `description` | TEXT | Short scope description. |
| `amount_usd` | REAL | Priced value. Negative is a credit. |
| `schedule_impact_days` | INTEGER | Days of schedule impact claimed. |
| `status` | TEXT | `Approved`, `Pending` or `Rejected`. Analysis excludes `Rejected`. |

### `cost_lines` (108 rows)
Nine budget lines per project. Source: `cost_report.csv` (monthly cost report). Primary key: (`project_id`, `cost_category`).

| Column | Type | Description |
|---|---|---|
| `project_id` | TEXT, FK → `projects` | |
| `cost_category` | TEXT | `Land & Sitework`, `Shell & Core`, `Electrical Equipment`, `Mechanical Equipment`, `MEP Installation`, `Commissioning`, `General Conditions`, `Owner Soft Costs`, `Contingency`. |
| `original_budget_usd` | REAL | Approved budget at sanction. |
| `approved_changes_usd` | REAL | Approved change orders charged to the line. On `Contingency` it is the drawdown, shown negative. |
| `committed_usd` | REAL | Value under contract or purchase order. |
| `actual_to_date_usd` | REAL | Cost incurred to the as-of date. |
| `estimate_at_completion_usd` | REAL | Forecast final cost. |

### `risks` (39 rows)
Risk register for projects not yet complete. Source: `risk_register.csv`.

| Column | Type | Description |
|---|---|---|
| `risk_id` | TEXT, PK | e.g. `R-P10-01`. |
| `project_id` | TEXT, FK → `projects` | |
| `category` | TEXT | `Supply Chain`, `Utility`, `Labor`, `Permitting`, `Commissioning`, `Design`, `Weather`. |
| `title` | TEXT | Risk statement. |
| `probability` | REAL | Likelihood, 0 to 1. |
| `cost_impact_usd` | REAL | Cost if the risk occurs. |
| `schedule_impact_days` | INTEGER | Delay if the risk occurs. |
| `status` | TEXT | `Open`, `Mitigating` or `Closed`. |
| `owner_role` | TEXT | Role accountable for the response. |
| `date_raised` | TEXT | Date logged. |

### `program_assumptions` (5 rows)
Planning assumptions used by the decision model. Source: `assumptions.csv`.

| Key | Value | Meaning |
|---|---|---|
| `as_of_date` | 2026-10-31 | Data cut-off for every extract. |
| `lease_rate_usd_per_kw_month` | 165 | Rate used to value a month of delayed capacity. |
| `billing_ramp_factor` | 0.5 | Share of a phase assumed to be billing during the delay window. |
| `schedule_float_weeks` | 4 | Planned float between vendor promise and required-on-site date. |
| `dual_source_onboarding_usd_per_project` | 350000 | One-time cost when a project changes switchgear vendor. |

### `import_audit` (8 rows)
One row per source file, written by the import script: rows read, duplicates removed, rows rejected, rows loaded, and load timestamp.

## Views

| View | Grain | Purpose and key derived fields |
|---|---|---|
| `v_project_schedule` | project | RFS baseline, current date and `rfs_slip_days`; `next_milestone` is the first gate not yet achieved. |
| `v_project_cost` | project | Budget, committed, actual, `eac_usd`, `variance_usd` and `variance_pct` (EAC minus original budget), cost per MW. |
| `v_po_delivery` | order line | `slip_days_vs_promise` (vendor performance against its own promise), `days_late_vs_required` (impact on the site), `latest_release_date` (last day to order and still hold the float), `is_long_lead`. |
| `v_vendor_scorecard` | vendor × category | Lines, value, `avg_slip_weeks`, `on_time_pct` (within 7 days of promise), `met_site_need_pct`. Placed orders only. |
| `v_project_switchgear` | project | Switchgear vendor, lineups, value, average slip and worst lateness against the site need. |
| `v_switchgear_vendor_outlook` | vendor × basis | Track record on `All history` and `Last 36 months`: delivery slip, average RFS slip, equipment-delay change orders per MW. |
| `v_decision_switchgear_options` | basis × unawarded project × vendor | Expected cost of each option: `switching_cost_usd`, `deferred_revenue_usd`, `delay_change_orders_usd`, `expected_cost_usd`. |

## Import rules

Applied by `scripts/import_data.py` before anything is loaded.

| Issue in the raw extracts | Handling |
|---|---|
| Exact duplicate rows | Dropped and counted in `import_audit`. |
| Mixed date formats (`2025-03-14`, `03/14/2025`, `14-Mar-2025`) | Parsed to ISO. Slash dates are read as month/day/year. |
| Blank, `N/A`, `TBD` | Treated as NULL. |
| Currency text (`$2,400,000`, `2,400,000.00`, `(125,000)`) | Parsed to a number. Parentheses mean negative. |
| Capacity with units (`36 MW`) and percentages (`65%`) | Parsed to numbers. |
| Vendor name variants (`KESTREL POWER SYSTEMS`, `Kestrel Power Sys.`) | Mapped to one canonical name through an alias table. Unknown names are rejected, not guessed. |
| Category and cause variants (`MV SWGR`, `Equip. Delay`) | Mapped through alias tables. |
| Inconsistent casing and stray whitespace | Normalized. |
| Unknown project, zero quantity, delivery before order date, unparseable values | Row is rejected and written to `data/rejects/` with the reason. |

Reconciliation checks run after the load and fail the import if any do not pass: complete milestone and cost-line sets per project, project status consistent with the RFS milestone, approved change orders tie to the cost report, phase capacity fits each campus plan, and no foreign-key violations.
