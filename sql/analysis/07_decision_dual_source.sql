-- Q7. The decision: who should supply MV switchgear on the three unawarded projects?
-- Expected cost of each vendor option, on the full track record and on the last 36 months.
SELECT
    basis,
    vendor_option,
    COUNT(*)                                          AS projects,
    SUM(it_capacity_mw)                               AS it_capacity_mw,
    SUM(lineups)                                      AS lineups,
    MIN(latest_release_date)                          AS first_order_needed_by,
    MAX(observed_premium_pct)                         AS observed_price_premium_pct,
    MAX(expected_rfs_slip_days)                       AS expected_rfs_slip_days,
    ROUND(SUM(switching_cost_usd) / 1e6, 2)           AS switching_cost_usd_m,
    ROUND(SUM(deferred_revenue_usd) / 1e6, 2)         AS deferred_revenue_usd_m,
    ROUND(SUM(delay_change_orders_usd) / 1e6, 2)      AS delay_change_orders_usd_m,
    ROUND(SUM(expected_cost_usd) / 1e6, 2)            AS expected_cost_usd_m
FROM v_decision_switchgear_options
GROUP BY basis, vendor_option
ORDER BY basis, expected_cost_usd_m;

-- Net benefit of switching and the break-even: how many days of RFS slip must the
-- alternate vendor avoid for its price premium to pay for itself?
WITH pivoted AS (
    SELECT
        basis,
        SUM(CASE WHEN vendor_option = 'Kestrel Power Systems' THEN expected_cost_usd END) AS stay_cost_usd,
        SUM(CASE WHEN vendor_option = 'Halvorsen Electric'    THEN expected_cost_usd END) AS switch_cost_usd,
        SUM(CASE WHEN vendor_option = 'Halvorsen Electric'    THEN switching_cost_usd END) AS switching_cost_usd,
        SUM(CASE WHEN vendor_option = 'Halvorsen Electric'
                 THEN deferred_revenue_usd / expected_rfs_slip_days END)                  AS revenue_per_slip_day_usd
    FROM v_decision_switchgear_options
    GROUP BY basis
)
SELECT
    basis,
    ROUND(stay_cost_usd / 1e6, 2)                               AS stay_expected_cost_usd_m,
    ROUND(switch_cost_usd / 1e6, 2)                             AS switch_expected_cost_usd_m,
    ROUND((stay_cost_usd - switch_cost_usd) / 1e6, 2)           AS net_benefit_of_switching_usd_m,
    ROUND(revenue_per_slip_day_usd / 1e3, 0)                    AS deferred_revenue_per_slip_day_usd_k,
    ROUND(switching_cost_usd / revenue_per_slip_day_usd, 1)     AS break_even_slip_days_avoided
FROM pivoted;
