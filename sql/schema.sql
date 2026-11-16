-- Data center build-out program database (SQLite)
-- Dates are ISO-8601 text (YYYY-MM-DD). Money is USD. All data is synthetic.

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_decision_switchgear_options;
DROP VIEW  IF EXISTS v_switchgear_vendor_outlook;
DROP VIEW  IF EXISTS v_project_switchgear;
DROP VIEW  IF EXISTS v_vendor_scorecard;
DROP VIEW  IF EXISTS v_po_delivery;
DROP VIEW  IF EXISTS v_project_cost;
DROP VIEW  IF EXISTS v_project_schedule;
DROP TABLE IF EXISTS import_audit;
DROP TABLE IF EXISTS program_assumptions;
DROP TABLE IF EXISTS risks;
DROP TABLE IF EXISTS cost_lines;
DROP TABLE IF EXISTS change_orders;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS milestones;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS sites;

CREATE TABLE sites (
    site_id              TEXT PRIMARY KEY,
    site_name            TEXT NOT NULL,
    metro                TEXT NOT NULL,
    state                TEXT NOT NULL CHECK (length(state) = 2),
    region               TEXT NOT NULL CHECK (region IN ('East', 'Central', 'West')),
    planned_capacity_mw  REAL NOT NULL CHECK (planned_capacity_mw > 0)
);

CREATE TABLE vendors (
    vendor_id    INTEGER PRIMARY KEY,
    vendor_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE projects (
    project_id          TEXT PRIMARY KEY,
    site_id             TEXT NOT NULL REFERENCES sites (site_id),
    phase_number        INTEGER NOT NULL CHECK (phase_number >= 1),
    project_name        TEXT NOT NULL,
    project_type        TEXT NOT NULL CHECK (project_type IN ('Greenfield', 'Expansion')),
    it_capacity_mw      REAL NOT NULL CHECK (it_capacity_mw > 0),
    general_contractor  TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('Pre-Construction', 'Construction', 'Commissioning', 'Complete')),
    UNIQUE (site_id, phase_number)
);

CREATE TABLE milestones (
    milestone_id    INTEGER PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects (project_id),
    milestone_code  TEXT NOT NULL CHECK (milestone_code IN ('NTP', 'PERMIT', 'SHELL', 'UTILITY', 'GEARSET', 'MEP', 'L5', 'RFS')),
    milestone_name  TEXT NOT NULL,
    sequence        INTEGER NOT NULL,
    baseline_date   TEXT NOT NULL,
    forecast_date   TEXT NOT NULL,
    actual_date     TEXT,
    status          TEXT NOT NULL CHECK (status IN ('Not Started', 'In Progress', 'Complete')),
    UNIQUE (project_id, milestone_code),
    CHECK ((status = 'Complete') = (actual_date IS NOT NULL))
);

CREATE TABLE purchase_orders (
    po_line_id              TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL REFERENCES projects (project_id),
    vendor_id               INTEGER REFERENCES vendors (vendor_id),   -- NULL = not yet awarded
    equipment_category      TEXT NOT NULL,
    description             TEXT,
    quantity                INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost_usd           REAL NOT NULL CHECK (unit_cost_usd > 0),
    po_value_usd            REAL NOT NULL,
    po_date                 TEXT,
    quoted_lead_time_weeks  INTEGER NOT NULL CHECK (quoted_lead_time_weeks > 0),
    required_on_site_date   TEXT NOT NULL,
    original_promise_date   TEXT,
    current_promise_date    TEXT,
    actual_delivery_date    TEXT,
    status                  TEXT NOT NULL CHECK (status IN ('Planned', 'Open', 'Delivered')),
    CHECK (status = 'Planned' OR (po_date IS NOT NULL AND original_promise_date IS NOT NULL)),
    CHECK ((status = 'Delivered') = (actual_delivery_date IS NOT NULL)),
    CHECK (actual_delivery_date IS NULL OR actual_delivery_date >= po_date)
);

CREATE TABLE change_orders (
    co_id                 TEXT PRIMARY KEY,
    project_id            TEXT NOT NULL REFERENCES projects (project_id),
    co_date               TEXT NOT NULL,
    cause_category        TEXT NOT NULL CHECK (cause_category IN (
                              'Equipment Delay', 'Utility Delay', 'Design Change',
                              'Owner Scope Change', 'Unforeseen Site Condition', 'Code / AHJ Requirement')),
    cost_category         TEXT NOT NULL,
    description           TEXT,
    amount_usd            REAL NOT NULL,          -- negative = credit
    schedule_impact_days  INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL CHECK (status IN ('Approved', 'Pending', 'Rejected'))
);

CREATE TABLE cost_lines (
    project_id                  TEXT NOT NULL REFERENCES projects (project_id),
    cost_category               TEXT NOT NULL,
    original_budget_usd         REAL NOT NULL,
    approved_changes_usd        REAL NOT NULL DEFAULT 0,
    committed_usd               REAL NOT NULL DEFAULT 0,
    actual_to_date_usd          REAL NOT NULL DEFAULT 0,
    estimate_at_completion_usd  REAL NOT NULL,
    PRIMARY KEY (project_id, cost_category)
);

CREATE TABLE risks (
    risk_id               TEXT PRIMARY KEY,
    project_id            TEXT NOT NULL REFERENCES projects (project_id),
    category              TEXT NOT NULL,
    title                 TEXT NOT NULL,
    probability           REAL NOT NULL CHECK (probability BETWEEN 0 AND 1),
    cost_impact_usd       REAL NOT NULL CHECK (cost_impact_usd >= 0),
    schedule_impact_days  INTEGER NOT NULL CHECK (schedule_impact_days >= 0),
    status                TEXT NOT NULL CHECK (status IN ('Open', 'Mitigating', 'Closed')),
    owner_role            TEXT,
    date_raised           TEXT NOT NULL
);

CREATE TABLE program_assumptions (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL,
    unit         TEXT,
    description  TEXT
);

CREATE TABLE import_audit (
    source_file         TEXT PRIMARY KEY,
    target_table        TEXT NOT NULL,
    rows_read           INTEGER NOT NULL,
    duplicates_removed  INTEGER NOT NULL,
    rows_rejected       INTEGER NOT NULL,
    rows_loaded         INTEGER NOT NULL,
    loaded_at           TEXT NOT NULL
);

CREATE INDEX ix_milestones_project   ON milestones (project_id);
CREATE INDEX ix_po_project           ON purchase_orders (project_id);
CREATE INDEX ix_po_vendor_category   ON purchase_orders (vendor_id, equipment_category);
CREATE INDEX ix_co_project           ON change_orders (project_id);
CREATE INDEX ix_risks_project        ON risks (project_id);
