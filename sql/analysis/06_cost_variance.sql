-- Q6. Which projects and cost categories are forecast over budget?
SELECT
    ps.project_id,
    ps.project_name,
    ps.status,
    ROUND(pc.original_budget_usd / 1e6, 1)   AS budget_usd_m,
    ROUND(pc.eac_usd / 1e6, 1)               AS eac_usd_m,
    ROUND(pc.variance_usd / 1e6, 1)          AS variance_usd_m,
    pc.variance_pct,
    ROUND(pc.eac_usd_per_mw / 1e6, 2)        AS eac_usd_m_per_mw
FROM v_project_cost pc
JOIN v_project_schedule ps ON ps.project_id = pc.project_id
ORDER BY pc.variance_pct DESC;

-- Program-level variance by cost category.
SELECT
    cost_category,
    ROUND(SUM(original_budget_usd) / 1e6, 1)                                      AS budget_usd_m,
    ROUND(SUM(estimate_at_completion_usd) / 1e6, 1)                               AS eac_usd_m,
    ROUND(SUM(estimate_at_completion_usd - original_budget_usd) / 1e6, 1)         AS variance_usd_m,
    ROUND(100.0 * SUM(estimate_at_completion_usd - original_budget_usd)
          / SUM(original_budget_usd), 1)                                          AS variance_pct
FROM cost_lines
GROUP BY cost_category
ORDER BY variance_usd_m DESC;
