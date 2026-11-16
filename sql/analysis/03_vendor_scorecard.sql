-- Q3. Which equipment vendors are late, and how much of the lateness do they own?
WITH placed AS (
    SELECT * FROM v_po_delivery WHERE status <> 'Planned'
)
SELECT
    vendor_name,
    equipment_category,
    COUNT(*)                                                       AS po_lines,
    ROUND(SUM(po_value_usd) / 1e6, 1)                              AS po_value_usd_m,
    ROUND(AVG(slip_days_vs_promise) / 7.0, 1)                      AS avg_slip_weeks,
    ROUND(100.0 * AVG(slip_days_vs_promise <= 7), 0)               AS on_time_pct,
    ROUND(100.0 * AVG(days_late_vs_required <= 0), 0)              AS met_site_need_pct,
    -- share of all vendor-caused late days across the program
    ROUND(100.0 * SUM(MAX(slip_days_vs_promise, 0))
          / SUM(SUM(MAX(slip_days_vs_promise, 0))) OVER (), 1)     AS share_of_late_days_pct,
    RANK() OVER (ORDER BY AVG(slip_days_vs_promise) DESC)          AS lateness_rank
FROM placed
GROUP BY vendor_name, equipment_category
ORDER BY lateness_rank;
