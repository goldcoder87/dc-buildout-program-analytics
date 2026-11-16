-- Q1. Where does the program stand? Capacity, schedule and cost by project stage.
SELECT
    ps.status                                             AS stage,
    COUNT(*)                                              AS projects,
    SUM(ps.it_capacity_mw)                                AS it_capacity_mw,
    ROUND(AVG(ps.rfs_slip_days), 0)                       AS avg_rfs_slip_days,
    MAX(ps.rfs_slip_days)                                 AS worst_rfs_slip_days,
    ROUND(SUM(pc.original_budget_usd) / 1e6, 1)           AS budget_usd_m,
    ROUND(SUM(pc.eac_usd) / 1e6, 1)                       AS eac_usd_m,
    ROUND(100.0 * (SUM(pc.eac_usd) - SUM(pc.original_budget_usd))
          / SUM(pc.original_budget_usd), 2)               AS variance_pct
FROM v_project_schedule ps
JOIN v_project_cost pc ON pc.project_id = ps.project_id
GROUP BY ps.status
ORDER BY CASE ps.status WHEN 'Complete' THEN 1 WHEN 'Commissioning' THEN 2
                        WHEN 'Construction' THEN 3 ELSE 4 END;
