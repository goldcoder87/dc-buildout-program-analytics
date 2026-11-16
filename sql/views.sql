-- Reporting views. The dashboard and the decision memo read only from these.

-- One row per project: where it is against its Ready-for-Service (RFS) baseline.
CREATE VIEW v_project_schedule AS
SELECT
    p.project_id,
    p.project_name,
    p.site_id,
    s.metro,
    s.region,
    p.project_type,
    p.it_capacity_mw,
    p.general_contractor,
    p.status,
    COALESCE(ntp.actual_date, ntp.forecast_date)                       AS ntp_date,
    rfs.baseline_date                                                  AS rfs_baseline_date,
    COALESCE(rfs.actual_date, rfs.forecast_date)                       AS rfs_current_date,
    rfs.actual_date IS NOT NULL                                        AS rfs_achieved,
    CAST(julianday(COALESCE(rfs.actual_date, rfs.forecast_date))
         - julianday(rfs.baseline_date) AS INTEGER)                    AS rfs_slip_days,
    (SELECT m.milestone_name
       FROM milestones m
      WHERE m.project_id = p.project_id AND m.actual_date IS NULL
      ORDER BY m.sequence
      LIMIT 1)                                                         AS next_milestone
FROM projects p
JOIN sites s        ON s.site_id = p.site_id
JOIN milestones ntp ON ntp.project_id = p.project_id AND ntp.milestone_code = 'NTP'
JOIN milestones rfs ON rfs.project_id = p.project_id AND rfs.milestone_code = 'RFS';

-- One row per project: budget, commitments and forecast at completion.
CREATE VIEW v_project_cost AS
SELECT
    c.project_id,
    SUM(c.original_budget_usd)                                         AS original_budget_usd,
    SUM(c.original_budget_usd + c.approved_changes_usd)                AS revised_budget_usd,
    SUM(c.committed_usd)                                               AS committed_usd,
    SUM(c.actual_to_date_usd)                                          AS actual_to_date_usd,
    SUM(c.estimate_at_completion_usd)                                  AS eac_usd,
    SUM(c.estimate_at_completion_usd) - SUM(c.original_budget_usd)     AS variance_usd,
    ROUND(100.0 * (SUM(c.estimate_at_completion_usd) - SUM(c.original_budget_usd))
          / SUM(c.original_budget_usd), 2)                             AS variance_pct,
    ROUND(SUM(c.original_budget_usd) / p.it_capacity_mw, 0)            AS budget_usd_per_mw,
    ROUND(SUM(c.estimate_at_completion_usd) / p.it_capacity_mw, 0)     AS eac_usd_per_mw
FROM cost_lines c
JOIN projects p ON p.project_id = c.project_id
GROUP BY c.project_id;

-- One row per purchase-order line with delivery performance worked out.
--   slip_days_vs_promise     : how late the vendor was against its own original promise
--   days_late_vs_required    : how late the gear was against the date the site needed it
--   latest_release_date      : last day the order can be placed and still make the
--                              required-on-site date with the planned float
CREATE VIEW v_po_delivery AS
SELECT
    po.po_line_id,
    po.project_id,
    po.vendor_id,
    v.vendor_name,
    po.equipment_category,
    po.equipment_category IN ('MV Switchgear', 'Generators', 'Transformers', 'LV Switchboards') AS is_long_lead,
    po.description,
    po.quantity,
    po.unit_cost_usd,
    po.po_value_usd,
    po.status,
    po.po_date,
    po.quoted_lead_time_weeks,
    po.required_on_site_date,
    po.original_promise_date,
    COALESCE(po.actual_delivery_date, po.current_promise_date)         AS effective_delivery_date,
    CAST(julianday(COALESCE(po.actual_delivery_date, po.current_promise_date))
         - julianday(po.original_promise_date) AS INTEGER)             AS slip_days_vs_promise,
    CAST(julianday(COALESCE(po.actual_delivery_date, po.current_promise_date))
         - julianday(po.required_on_site_date) AS INTEGER)             AS days_late_vs_required,
    date(po.required_on_site_date,
         '-' || ((po.quoted_lead_time_weeks
                  + (SELECT CAST(value AS INTEGER) FROM program_assumptions
                      WHERE key = 'schedule_float_weeks')) * 7) || ' days') AS latest_release_date
FROM purchase_orders po
LEFT JOIN vendors v ON v.vendor_id = po.vendor_id;

-- Vendor x equipment category delivery scorecard (placed orders only).
-- "On time" = delivered, or currently promised, within 7 days of the original promise.
CREATE VIEW v_vendor_scorecard AS
SELECT
    vendor_name,
    equipment_category,
    COUNT(*)                                                           AS po_lines,
    SUM(status = 'Open')                                               AS open_lines,
    SUM(po_value_usd)                                                  AS po_value_usd,
    ROUND(AVG(slip_days_vs_promise) / 7.0, 1)                          AS avg_slip_weeks,
    ROUND(MAX(slip_days_vs_promise) / 7.0, 1)                          AS worst_slip_weeks,
    ROUND(100.0 * AVG(slip_days_vs_promise <= 7), 0)                   AS on_time_pct,
    ROUND(100.0 * AVG(days_late_vs_required <= 0), 0)                  AS met_site_need_pct
FROM v_po_delivery
WHERE status <> 'Planned'
GROUP BY vendor_name, equipment_category;

-- One row per project: who supplies the MV switchgear and how it performed.
CREATE VIEW v_project_switchgear AS
SELECT
    project_id,
    MAX(vendor_name)                                                   AS switchgear_vendor,   -- NULL = not awarded
    COUNT(*)                                                           AS lineups,
    SUM(po_value_usd)                                                  AS switchgear_value_usd,
    MIN(po_date)                                                       AS first_po_date,
    MIN(latest_release_date)                                           AS latest_release_date,
    ROUND(AVG(slip_days_vs_promise) / 7.0, 1)                          AS avg_slip_weeks,
    MAX(days_late_vs_required)                                         AS max_days_late_vs_required
FROM v_po_delivery
WHERE equipment_category = 'MV Switchgear'
GROUP BY project_id;

-- Switchgear vendor track record on two bases, so the decision can be tested
-- against both a recent window and the full history.
CREATE VIEW v_switchgear_vendor_outlook AS
WITH as_of AS (
    SELECT value AS as_of_date FROM program_assumptions WHERE key = 'as_of_date'
),
project_record AS (
    SELECT
        sw.project_id,
        sw.switchgear_vendor,
        sw.first_po_date,
        sw.lineups,
        sw.avg_slip_weeks,
        ps.it_capacity_mw,
        ps.rfs_slip_days,
        COALESCE((SELECT SUM(co.amount_usd)
                    FROM change_orders co
                   WHERE co.project_id = sw.project_id
                     AND co.cause_category = 'Equipment Delay'
                     AND co.status <> 'Rejected'), 0)                  AS delay_co_usd
    FROM v_project_switchgear sw
    JOIN v_project_schedule ps ON ps.project_id = sw.project_id
    WHERE sw.switchgear_vendor IS NOT NULL
),
by_basis AS (
    SELECT 'All history' AS basis, r.* FROM project_record r
    UNION ALL
    SELECT 'Last 36 months', r.*
      FROM project_record r, as_of
     WHERE r.first_po_date >= date(as_of.as_of_date, '-36 months')
)
SELECT
    switchgear_vendor,
    basis,
    COUNT(*)                                                           AS projects,
    SUM(lineups)                                                       AS lineups,
    ROUND(SUM(avg_slip_weeks * lineups) / SUM(lineups), 1)             AS avg_delivery_slip_weeks,
    ROUND(AVG(rfs_slip_days), 0)                                       AS avg_rfs_slip_days,
    ROUND(SUM(delay_co_usd) / SUM(it_capacity_mw), 0)                  AS delay_co_usd_per_mw
FROM by_basis
GROUP BY switchgear_vendor, basis;

-- Decision model: expected cost of each switchgear vendor option on every
-- project whose switchgear is not yet awarded.
--   price premium     = observed same-year unit-price gap between the two vendors
--   deferred revenue  = MW x lease rate x billing ramp x expected months of RFS slip
--   delay change orders = MW x historical equipment-delay change-order cost per MW
CREATE VIEW v_decision_switchgear_options AS
WITH assumptions AS (
    SELECT
        MAX(CASE WHEN key = 'lease_rate_usd_per_kw_month'            THEN CAST(value AS REAL) END) AS lease_rate,
        MAX(CASE WHEN key = 'billing_ramp_factor'                    THEN CAST(value AS REAL) END) AS ramp,
        MAX(CASE WHEN key = 'dual_source_onboarding_usd_per_project' THEN CAST(value AS REAL) END) AS onboarding
    FROM program_assumptions
),
yearly_price AS (
    SELECT vendor_name, strftime('%Y', po_date) AS po_year, AVG(unit_cost_usd) AS avg_unit_cost
    FROM v_po_delivery
    WHERE equipment_category = 'MV Switchgear' AND po_date IS NOT NULL
    GROUP BY vendor_name, po_year
),
premium AS (   -- alternate vendor vs incumbent, compared only within the same order year
    SELECT AVG(alt.avg_unit_cost / inc.avg_unit_cost - 1) AS premium_pct
    FROM yearly_price alt
    JOIN yearly_price inc ON inc.po_year = alt.po_year
    WHERE alt.vendor_name = 'Halvorsen Electric' AND inc.vendor_name = 'Kestrel Power Systems'
),
unawarded AS (
    SELECT project_id, COUNT(*) AS lineups, SUM(po_value_usd) AS base_spend_usd,
           MIN(latest_release_date) AS latest_release_date
    FROM v_po_delivery
    WHERE equipment_category = 'MV Switchgear' AND status = 'Planned' AND vendor_id IS NULL
    GROUP BY project_id
),
costed AS (
    SELECT
        o.basis,
        u.project_id,
        ps.project_name,
        ps.it_capacity_mw,
        o.switchgear_vendor                                            AS vendor_option,
        u.lineups,
        u.latest_release_date,
        u.base_spend_usd,
        ROUND(100 * premium.premium_pct, 1)                            AS observed_premium_pct,
        CASE WHEN o.switchgear_vendor = 'Halvorsen Electric'
             THEN u.base_spend_usd * premium.premium_pct + a.onboarding ELSE 0 END AS switching_cost_usd,
        o.avg_rfs_slip_days                                            AS expected_rfs_slip_days,
        ps.it_capacity_mw * 1000 * a.lease_rate * a.ramp
            * o.avg_rfs_slip_days / 30.4375                            AS deferred_revenue_usd,
        ps.it_capacity_mw * o.delay_co_usd_per_mw                      AS delay_change_orders_usd
    FROM unawarded u
    JOIN v_project_schedule ps ON ps.project_id = u.project_id
    CROSS JOIN v_switchgear_vendor_outlook o
    CROSS JOIN assumptions a
    CROSS JOIN premium
)
SELECT
    *,
    ROUND(switching_cost_usd + deferred_revenue_usd + delay_change_orders_usd, 0) AS expected_cost_usd
FROM costed;
