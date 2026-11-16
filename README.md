# Data Center Build-Out Program Analytics

A portfolio project that takes messy program-controls data for a fictional 378 MW data center build-out, loads it into a relational database, and carries it through to a dashboard and a sourcing decision.

**The question it answers:** nine of twelve build phases have started, and every one is late to Ready for Service. Why, and what should the program do differently on the three phases not yet bought out?

**The answer the data gives:** medium-voltage switchgear from the single-source incumbent arrives an average of 10.5 weeks late and is getting worse each year. Moving the next two phases to the alternate vendor costs about $3.3M and avoids about $16.1M of expected delay cost. See the [decision memo](docs/decision_memo.md).

> Everything here is synthetic. The companies, vendors, projects and figures are fictional and were generated for demonstration.

## What is in the repository

| Deliverable | Where | What it shows |
|---|---|---|
| Database | [db/buildout.db](db/buildout.db), [sql/schema.sql](sql/schema.sql) | SQLite, 10 tables, with primary and foreign keys and CHECK constraints |
| Import script | [scripts/import_data.py](scripts/import_data.py) | Cleaning, validation, reject handling, reconciliation checks, audit log |
| SQL | [sql/views.sql](sql/views.sql), [sql/analysis/](sql/analysis) | 7 reporting views and 7 analysis queries using CTEs and window functions |
| Dashboard | [dashboard/index.html](dashboard/index.html) | One self-contained page with filters, tooltips, and light and dark themes |
| Data dictionary | [docs/data_dictionary.md](docs/data_dictionary.md) | Every table, column, view and import rule |
| Decision memo | [docs/decision_memo.md](docs/decision_memo.md) | One-page recommendation with options, break-even and caveats |
| Raw data | [data/raw/](data/raw), [scripts/generate_raw_data.py](scripts/generate_raw_data.py) | Eight source extracts with the kinds of defects real exports have |

## How it fits together

```
data/raw/*.csv ──► scripts/import_data.py ──► db/buildout.db ──► sql/views.sql ──┬─► dashboard/index.html
 (8 extracts)       clean · validate · load      (SQLite)         (7 views)       ├─► sql/analysis/*.sql
                    └─► data/rejects/*.csv                                        └─► docs/decision_memo.md
```

The dashboard and the memo read only from the views, so every published number traces back to a query.

**[Open the live dashboard →](https://goldcoder87.github.io/dc-buildout-program-analytics/dashboard/)**

## Run it

Requires Python 3.9 or later and nothing else. The `sqlite3` command-line tool is only needed for `make analysis`.

```bash
make all
```

That rebuilds the database from the raw extracts and regenerates the dashboard. Individual steps:

```bash
python3 scripts/import_data.py
```

```bash
python3 scripts/build_dashboard.py
```

```bash
make analysis
```

Then open `dashboard/index.html` in a browser. `make data` regenerates the raw extracts; it is seeded, so the output is identical on every run.

## What the import has to deal with

The raw extracts are deliberately untidy. On the current data the import reads 634 rows, removes 18 exact duplicates, rejects 7 rows with a stated reason, and loads 609.

| Source file | Read | Duplicates | Rejected | Loaded |
|---|---:|---:|---:|---:|
| purchase_orders.csv | 255 | 7 | 5 | 243 |
| change_orders.csv | 107 | 5 | 2 | 100 |
| milestones.csv | 100 | 4 | 0 | 96 |
| risk_register.csv | 41 | 2 | 0 | 39 |
| cost_report.csv | 108 | 0 | 0 | 108 |
| projects, sites, assumptions | 23 | 0 | 0 | 23 |

It handles three date formats, currency strings and accounting-style negatives, vendor and category name variants, units embedded in numbers, and mixed casing. Rows that reference unknown projects or contain impossible values (zero quantity, delivery before the order date) are written to `data/rejects/` rather than loaded or silently dropped. Seven reconciliation checks then run across tables, and the import exits with an error if any fail.

## Findings

- **Schedule.** Started projects average 58 days late to Ready for Service. The worst is 105 days.
- **Root cause.** Kestrel switchgear accounts for 66% of all vendor-caused late days. Its average slip by order year went 3.6, 7.3, 11.8, then 15.0 weeks.
- **Cost.** Equipment-delay change orders total $28.0M, 37% of change-order cost, all on projects with Kestrel switchgear. The program forecasts $4.06B against a $4.02B budget (+0.9%).
- **Decision.** The alternate vendor's 7.2% price premium breaks even after 16 days of avoided slip per project. The observed gap is 41 days.

## Publishing the dashboard

`dashboard/index.html` is a single file with the data embedded and no external requests. It is published with GitHub Pages at **https://goldcoder87.github.io/dc-buildout-program-analytics/dashboard/**. To embed it in another site:

```html
<iframe src="https://goldcoder87.github.io/dc-buildout-program-analytics/dashboard/" title="Data center build-out dashboard"
        style="width:100%;height:2400px;border:0"></iframe>
```

## Limits worth knowing

- The data is generated, so the story is cleaner than a real program's would be.
- The alternate vendor's track record is two projects and ten lineups. The memo treats that as a real constraint on the recommendation.
- Deferred revenue depends on two planning assumptions (lease rate and billing ramp) held in the `program_assumptions` table. Change them there and rebuild to test sensitivity.
