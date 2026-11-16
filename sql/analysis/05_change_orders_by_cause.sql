-- Q5. What is driving change-order cost?
SELECT
    cause_category,
    COUNT(*)                                                        AS change_orders,
    ROUND(SUM(amount_usd) / 1e6, 2)                                 AS amount_usd_m,
    ROUND(100.0 * SUM(amount_usd) / SUM(SUM(amount_usd)) OVER (), 1) AS share_pct,
    ROUND(AVG(amount_usd) / 1e3, 0)                                 AS avg_amount_usd_k,
    SUM(schedule_impact_days)                                       AS schedule_impact_days
FROM change_orders
WHERE status <> 'Rejected'
GROUP BY cause_category
ORDER BY amount_usd_m DESC;

-- Change-order cost per MW, split by who supplied the switchgear.
WITH per_project AS (
    SELECT
        sw.switchgear_vendor,
        ps.project_id,
        ps.it_capacity_mw,
        COALESCE(SUM(co.amount_usd), 0)                                                       AS all_co_usd,
        COALESCE(SUM(CASE WHEN co.cause_category = 'Equipment Delay' THEN co.amount_usd END), 0) AS delay_co_usd
    FROM v_project_switchgear sw
    JOIN v_project_schedule ps ON ps.project_id = sw.project_id
    LEFT JOIN change_orders co ON co.project_id = sw.project_id AND co.status <> 'Rejected'
    WHERE sw.switchgear_vendor IS NOT NULL
    GROUP BY sw.switchgear_vendor, ps.project_id, ps.it_capacity_mw
)
SELECT
    switchgear_vendor,
    COUNT(*)                                              AS projects,
    SUM(it_capacity_mw)                                   AS it_capacity_mw,
    ROUND(SUM(all_co_usd) / SUM(it_capacity_mw) / 1e3, 0)   AS all_co_usd_k_per_mw,
    ROUND(SUM(delay_co_usd) / SUM(it_capacity_mw) / 1e3, 0) AS equipment_delay_co_usd_k_per_mw
FROM per_project
GROUP BY switchgear_vendor;
