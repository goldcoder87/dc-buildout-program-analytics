#!/usr/bin/env python3
"""Build the self-contained dashboard page from the database.

    python3 scripts/build_dashboard.py     # writes dashboard/index.html

Every number on the page comes from the reporting views in sql/views.sql. The
query results are embedded as JSON in dashboard/template.html, so the output is
a single static file with no server, no network calls and no dependencies.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db" / "buildout.db"
TEMPLATE = ROOT / "dashboard" / "template.html"
OUTPUT = ROOT / "dashboard" / "index.html"

QUERIES = {
    "projects": """
        SELECT ps.project_id, ps.project_name, ps.metro, ps.region, ps.status, ps.it_capacity_mw AS mw,
               ps.rfs_baseline_date, ps.rfs_current_date, ps.rfs_slip_days, ps.next_milestone,
               pc.original_budget_usd AS budget, pc.eac_usd AS eac, pc.variance_usd, pc.variance_pct,
               sw.switchgear_vendor, sw.latest_release_date
        FROM v_project_schedule ps
        JOIN v_project_cost pc       ON pc.project_id = ps.project_id
        JOIN v_project_switchgear sw ON sw.project_id = ps.project_id
        ORDER BY ps.project_id""",
    "milestones": """
        SELECT project_id, milestone_code AS code, status,
               CAST(julianday(COALESCE(actual_date, forecast_date)) - julianday(baseline_date) AS INTEGER) AS slip_days,
               baseline_date, COALESCE(actual_date, forecast_date) AS current_date
        FROM milestones ORDER BY project_id, sequence""",
    "po_lines": """
        SELECT project_id, vendor_name, equipment_category AS category, is_long_lead, status, po_date,
               po_value_usd AS value, slip_days_vs_promise AS slip_days, days_late_vs_required AS late_days,
               description
        FROM v_po_delivery WHERE status <> 'Planned' ORDER BY po_date""",
    "change_orders": """
        SELECT project_id, cause_category AS cause, SUM(amount_usd) AS amount, COUNT(*) AS n
        FROM change_orders WHERE status <> 'Rejected' GROUP BY project_id, cause_category""",
    "risks": """
        SELECT risk_id, project_id, category, title, probability, cost_impact_usd AS cost,
               schedule_impact_days AS days, status, owner_role
        FROM risks WHERE status <> 'Closed'
        ORDER BY probability * cost_impact_usd DESC""",
    "decision": """
        SELECT basis, vendor_option, SUM(it_capacity_mw) AS mw, SUM(lineups) AS lineups,
               MIN(latest_release_date) AS order_by, MAX(observed_premium_pct) AS premium_pct,
               MAX(expected_rfs_slip_days) AS slip_days, SUM(switching_cost_usd) AS switching_cost,
               SUM(deferred_revenue_usd) AS deferred_revenue, SUM(delay_change_orders_usd) AS delay_cos,
               SUM(expected_cost_usd) AS expected_cost
        FROM v_decision_switchgear_options GROUP BY basis, vendor_option""",
    "assumptions": "SELECT key, value, unit, description FROM program_assumptions",
}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    data = {name: [dict(r) for r in conn.execute(sql)] for name, sql in QUERIES.items()}
    data["as_of"] = next(a["value"] for a in data["assumptions"] if a["key"] == "as_of_date")
    conn.close()
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(html) / 1024:.0f} KB, "
          + ", ".join(f"{len(v)} {k}" for k, v in data.items() if isinstance(v, list)) + ")")


if __name__ == "__main__":
    main()
