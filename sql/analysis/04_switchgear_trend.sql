-- Q4. Is the incumbent switchgear vendor getting better or worse?
-- Average delivery slip by order year, with year-over-year change.
WITH yearly AS (
    SELECT
        vendor_name,
        strftime('%Y', po_date)                       AS po_year,
        COUNT(*)                                      AS lineups,
        ROUND(AVG(slip_days_vs_promise) / 7.0, 1)     AS avg_slip_weeks,
        ROUND(AVG(unit_cost_usd) / 1e6, 2)            AS avg_unit_cost_usd_m
    FROM v_po_delivery
    WHERE equipment_category = 'MV Switchgear' AND status <> 'Planned'
    GROUP BY vendor_name, po_year
)
SELECT
    *,
    ROUND(avg_slip_weeks - LAG(avg_slip_weeks) OVER (PARTITION BY vendor_name ORDER BY po_year), 1)
        AS change_vs_prior_year_weeks
FROM yearly
ORDER BY vendor_name, po_year;

-- Does late switchgear show up as late capacity? Project-level comparison.
SELECT
    sw.project_id,
    sw.switchgear_vendor,
    sw.first_po_date,
    sw.avg_slip_weeks                                  AS switchgear_avg_slip_weeks,
    sw.max_days_late_vs_required                       AS switchgear_days_late_vs_site_need,
    ps.rfs_slip_days,
    ROUND(COALESCE((SELECT SUM(amount_usd) FROM change_orders co
                     WHERE co.project_id = sw.project_id
                       AND co.cause_category = 'Equipment Delay'
                       AND co.status <> 'Rejected'), 0) / 1e6, 2) AS equipment_delay_co_usd_m
FROM v_project_switchgear sw
JOIN v_project_schedule ps ON ps.project_id = sw.project_id
WHERE sw.switchgear_vendor IS NOT NULL
ORDER BY sw.first_po_date;
