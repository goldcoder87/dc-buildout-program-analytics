-- Q2. How far behind plan is capacity delivery?
-- Cumulative MW by Ready-for-Service date: baseline plan vs current forecast.
WITH events AS (
    SELECT rfs_baseline_date AS rfs_date, 'Baseline' AS plan, project_id, it_capacity_mw FROM v_project_schedule
    UNION ALL
    SELECT rfs_current_date,              'Current',          project_id, it_capacity_mw FROM v_project_schedule
)
SELECT
    plan,
    rfs_date,
    project_id,
    it_capacity_mw,
    SUM(it_capacity_mw) OVER (PARTITION BY plan ORDER BY rfs_date, project_id) AS cumulative_mw
FROM events
ORDER BY plan, rfs_date;

-- MW-months of capacity lost to schedule slip, by project, ranked.
SELECT
    project_id,
    project_name,
    it_capacity_mw,
    rfs_slip_days,
    ROUND(it_capacity_mw * rfs_slip_days / 30.4375, 1)            AS mw_months_lost,
    RANK() OVER (ORDER BY it_capacity_mw * rfs_slip_days DESC)    AS rank_by_mw_months
FROM v_project_schedule
WHERE rfs_slip_days > 0
ORDER BY rank_by_mw_months;
