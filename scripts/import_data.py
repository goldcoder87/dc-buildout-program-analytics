#!/usr/bin/env python3
"""Load the raw source-system extracts into the SQLite program database.

    python3 scripts/import_data.py            # rebuilds db/buildout.db

What it does, per file:
  1. reads every row as text,
  2. drops exact duplicate rows,
  3. cleans each field (dates, money, percentages, names, casing),
  4. validates the row; anything that fails goes to data/rejects/<file> with a
     reason instead of being silently dropped or loaded,
  5. loads the survivors inside one transaction,
then runs reconciliation checks across tables and prints an audit summary.

The run is idempotent: the schema is dropped and rebuilt every time.
Standard library only.
"""
import argparse
import csv
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REJECT_DIR = ROOT / "data" / "rejects"
SQL_DIR = ROOT / "sql"
DEFAULT_DB = ROOT / "db" / "buildout.db"

NULL_TOKENS = {"", "n/a", "na", "tbd", "null", "none", "-"}
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y")   # non-ISO slashes are US month/day/year

VENDOR_ALIASES = {   # normalized key -> canonical name
    "kestrel power systems": "Kestrel Power Systems",
    "kestrel power sys": "Kestrel Power Systems",
    "halvorsen electric": "Halvorsen Electric",
    "ironcrest power": "Ironcrest Power",
    "northlake critical power": "Northlake Critical Power",
    "northlake crit power": "Northlake Critical Power",
    "tallgrass transformer co": "Tallgrass Transformer Co.",
    "tallgrass transformer company": "Tallgrass Transformer Co.",
    "polar meridian hvac": "Polar Meridian HVAC",
    "alder air systems": "Alder Air Systems",
    "alder air sys": "Alder Air Systems",
    "cobalt distribution": "Cobalt Distribution",
    "sentinel controls": "Sentinel Controls",
}
CATEGORY_ALIASES = {
    "mv switchgear": "MV Switchgear", "medium voltage switchgear": "MV Switchgear", "mv swgr": "MV Switchgear",
    "lv switchboards": "LV Switchboards", "lv switchboard": "LV Switchboards", "low voltage switchboards": "LV Switchboards",
    "generators": "Generators", "generator": "Generators",
    "transformers": "Transformers", "transformer": "Transformers", "xfmr": "Transformers",
    "ups": "UPS", "ups modules": "UPS",
    "chillers": "Chillers", "chiller": "Chillers",
    "crah units": "CRAH Units", "crah": "CRAH Units", "fan walls": "CRAH Units",
    "pdu / busway": "PDU / Busway", "pdu/busway": "PDU / Busway", "busway": "PDU / Busway",
    "bms / epms": "BMS / EPMS", "bms/epms": "BMS / EPMS", "bms": "BMS / EPMS",
}
CAUSE_ALIASES = {
    "equipment delay": "Equipment Delay", "equip. delay": "Equipment Delay",
    "utility delay": "Utility Delay", "design change": "Design Change",
    "owner scope change": "Owner Scope Change", "owner change": "Owner Scope Change",
    "unforeseen site condition": "Unforeseen Site Condition",
    "code / ahj requirement": "Code / AHJ Requirement", "code/ahj requirement": "Code / AHJ Requirement",
    "ahj requirement": "Code / AHJ Requirement",
}
COST_CATEGORIES = {"Land & Sitework", "Shell & Core", "Electrical Equipment", "Mechanical Equipment",
                   "MEP Installation", "Commissioning", "General Conditions", "Owner Soft Costs", "Contingency"}


class RowError(ValueError):
    """Raised by a cleaner or validator; the row is rejected with this message."""


# --------------------------------------------------------------------------
# Field cleaners
# --------------------------------------------------------------------------
def text(value):
    value = re.sub(r"\s+", " ", (value or "")).strip()
    return None if value.lower() in NULL_TOKENS else value


def required(value, field):
    value = text(value)
    if value is None:
        raise RowError(f"{field} is missing")
    return value


def iso_date(value, field, nullable=True):
    value = text(value)
    if value is None:
        if nullable:
            return None
        raise RowError(f"{field} is missing")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise RowError(f"{field} is not a recognizable date: {value!r}")


def money(value, field, nullable=False):
    value = text(value)
    if value is None:
        if nullable:
            return None
        raise RowError(f"{field} is missing")
    negative = value.startswith("(") and value.endswith(")")   # accounting-style credit
    cleaned = value.strip("()").replace("$", "").replace(",", "").strip()
    try:
        number = float(cleaned)
    except ValueError:
        raise RowError(f"{field} is not a number: {value!r}")
    return -number if negative else number


def integer(value, field):
    value = text(value)
    if value is None:
        raise RowError(f"{field} is missing")
    match = re.fullmatch(r"(-?\d+)(\.0+)?\s*(mw)?", value.lower())
    if not match:
        raise RowError(f"{field} is not a whole number: {value!r}")
    return int(match.group(1))


def probability(value, field):
    value = required(value, field)
    number = float(value.rstrip("%")) / (100 if value.endswith("%") else 1)
    if not 0 <= number <= 1:
        raise RowError(f"{field} is outside 0-1: {value!r}")
    return round(number, 4)


def choice(value, field, allowed):
    """Case-insensitive match against an allowed list; returns canonical casing."""
    value = required(value, field)
    lookup = {a.lower(): a for a in allowed}
    if value.lower() not in lookup:
        raise RowError(f"{field} has an unexpected value: {value!r}")
    return lookup[value.lower()]


def alias(value, field, aliases):
    value = required(value, field)
    key = value.lower()
    if key not in aliases:
        raise RowError(f"{field} is not a known value: {value!r}")
    return aliases[key]


def vendor_name(value):
    value = text(value)
    if value is None:
        return None                      # not yet awarded
    key = re.sub(r"[.,]", "", value.lower())
    key = re.sub(r"\s+(inc|llc)$", "", key).strip()
    if key not in VENDOR_ALIASES:
        raise RowError(f"Vendor is not in the vendor master: {value!r}")
    return VENDOR_ALIASES[key]


def project_id(value, known):
    value = required(value, "project id").upper()
    if value not in known:
        raise RowError(f"project {value!r} does not exist in projects.csv")
    return value


# --------------------------------------------------------------------------
# Row transforms: raw dict -> clean dict (or raise RowError)
# --------------------------------------------------------------------------
def clean_site(r, ctx):
    return {"site_id": required(r["site_id"], "site_id").upper(), "site_name": required(r["site_name"], "site_name"),
            "metro": required(r["metro"], "metro"), "state": required(r["state"], "state").upper(),
            "region": choice(r["region"], "region", ["East", "Central", "West"]),
            "planned_capacity_mw": integer(r["planned_capacity_mw"], "planned_capacity_mw")}


def clean_project(r, ctx):
    site = required(r["Site"], "Site").upper()
    if site not in ctx["sites"]:
        raise RowError(f"site {site!r} does not exist in sites.csv")
    return {"project_id": required(r["Project ID"], "Project ID").upper(), "site_id": site,
            "phase_number": integer(r["Phase"], "Phase"), "project_name": required(r["Project Name"], "Project Name"),
            "project_type": choice(r["Type"], "Type", ["Greenfield", "Expansion"]),
            "it_capacity_mw": integer(r["IT Capacity"], "IT Capacity"),
            "general_contractor": required(r["General Contractor"], "General Contractor"),
            "status": choice(r["Status"], "Status", ["Pre-Construction", "Construction", "Commissioning", "Complete"])}


def clean_milestone(r, ctx):
    row = {"project_id": project_id(r["project"], ctx["projects"]),
           "milestone_code": required(r["milestone_code"], "milestone_code").upper(),
           "milestone_name": required(r["milestone"], "milestone"), "sequence": integer(r["seq"], "seq"),
           "baseline_date": iso_date(r["baseline_finish"], "baseline_finish", nullable=False),
           "forecast_date": iso_date(r["forecast_finish"], "forecast_finish", nullable=False),
           "actual_date": iso_date(r["actual_finish"], "actual_finish"),
           "status": choice(r["status"], "status", ["Not Started", "In Progress", "Complete"])}
    if (row["status"] == "Complete") != (row["actual_date"] is not None):
        raise RowError("status and actual_finish disagree")
    if row["actual_date"] and row["actual_date"] > ctx["as_of"]:
        raise RowError("actual_finish is after the data cut-off")
    return row


def clean_po(r, ctx):
    row = {"po_line_id": required(r["PO Line"], "PO Line").upper(),
           "project_id": project_id(r["Project"], ctx["projects"]),
           "vendor_name": vendor_name(r["Vendor"]),
           "equipment_category": alias(r["Category"], "Category", CATEGORY_ALIASES),
           "description": text(r["Description"]), "quantity": integer(r["Qty"], "Qty"),
           "unit_cost_usd": money(r["Unit Cost"], "Unit Cost"),
           "po_date": iso_date(r["PO Date"], "PO Date"),
           "quoted_lead_time_weeks": integer(r["Lead Time (wks)"], "Lead Time (wks)"),
           "required_on_site_date": iso_date(r["Required On Site"], "Required On Site", nullable=False),
           "original_promise_date": iso_date(r["Original Promise"], "Original Promise"),
           "current_promise_date": iso_date(r["Current Promise"], "Current Promise"),
           "actual_delivery_date": iso_date(r["Actual Delivery"], "Actual Delivery"),
           "status": choice(r["Status"], "Status", ["Planned", "Open", "Delivered"])}
    if row["quantity"] <= 0:
        raise RowError("Qty must be greater than zero")
    if row["unit_cost_usd"] <= 0:
        raise RowError("Unit Cost must be greater than zero")
    # Extended value is recomputed rather than trusted; reject if the source disagrees by > $1
    row["po_value_usd"] = row["quantity"] * row["unit_cost_usd"]
    stated = money(r["Extended Value"], "Extended Value")
    if abs(stated - row["po_value_usd"]) > 1:
        raise RowError(f"Extended Value {stated:,.0f} does not equal Qty x Unit Cost {row['po_value_usd']:,.0f}")
    if row["status"] != "Planned" and not (row["po_date"] and row["original_promise_date"]):
        raise RowError("placed order is missing PO Date or Original Promise")
    if (row["status"] == "Delivered") != (row["actual_delivery_date"] is not None):
        raise RowError("Status and Actual Delivery disagree")
    if row["actual_delivery_date"] and row["actual_delivery_date"] < row["po_date"]:
        raise RowError("Actual Delivery is earlier than PO Date")
    if row["status"] != "Planned" and row["vendor_name"] is None:
        raise RowError("placed order has no vendor")
    return row


def clean_change_order(r, ctx):
    category = required(r["cost_category"], "cost_category")
    if category not in COST_CATEGORIES:
        raise RowError(f"cost_category is not a known value: {category!r}")
    return {"co_id": required(r["co_number"], "co_number").upper(),
            "project_id": project_id(r["project_id"], ctx["projects"]),
            "co_date": iso_date(r["date"], "date", nullable=False),
            "cause_category": alias(r["cause"], "cause", CAUSE_ALIASES), "cost_category": category,
            "description": text(r["description"]), "amount_usd": money(r["amount"], "amount"),
            "schedule_impact_days": integer(r["schedule_days"], "schedule_days"),
            "status": choice(r["status"], "status", ["Approved", "Pending", "Rejected"])}


def clean_cost_line(r, ctx):
    category = required(r["cost_category"], "cost_category")
    if category not in COST_CATEGORIES:
        raise RowError(f"cost_category is not a known value: {category!r}")
    return {"project_id": project_id(r["project_id"], ctx["projects"]), "cost_category": category,
            "original_budget_usd": money(r["original_budget"], "original_budget"),
            "approved_changes_usd": money(r["approved_changes"], "approved_changes"),
            "committed_usd": money(r["committed"], "committed"),
            "actual_to_date_usd": money(r["actual_to_date"], "actual_to_date"),
            "estimate_at_completion_usd": money(r["estimate_at_completion"], "estimate_at_completion")}


def clean_risk(r, ctx):
    return {"risk_id": required(r["risk_id"], "risk_id").upper(),
            "project_id": project_id(r["project_id"], ctx["projects"]),
            "category": required(r["category"], "category"), "title": required(r["title"], "title"),
            "probability": probability(r["probability"], "probability"),
            "cost_impact_usd": money(r["cost_impact"], "cost_impact"),
            "schedule_impact_days": integer(r["schedule_impact_days"], "schedule_impact_days"),
            "status": choice(r["status"], "status", ["Open", "Mitigating", "Closed"]),
            "owner_role": text(r["owner"]), "date_raised": iso_date(r["date_raised"], "date_raised", nullable=False)}


def clean_assumption(r, ctx):
    return {"key": required(r["key"], "key"), "value": required(r["value"], "value"),
            "unit": text(r["unit"]), "description": text(r["description"])}


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
def process(filename, cleaner, key_fields, ctx):
    """Read, de-duplicate, clean and validate one file. Returns (rows, stats)."""
    with open(RAW_DIR / filename, newline="", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))
    seen_rows, seen_keys, clean, rejects, duplicates = set(), set(), [], [], 0
    for line_no, raw in enumerate(raw_rows, start=2):
        fingerprint = tuple((v or "").strip() for v in raw.values())
        if fingerprint in seen_rows:
            duplicates += 1
            continue
        seen_rows.add(fingerprint)
        try:
            row = cleaner(raw, ctx)
            key = tuple(row[k] for k in key_fields)
            if key in seen_keys:
                raise RowError(f"duplicate key {key} with different content")
            seen_keys.add(key)
            clean.append(row)
        except RowError as err:
            rejects.append({"source_line": line_no, "reject_reason": str(err), **raw})
    REJECT_DIR.mkdir(parents=True, exist_ok=True)
    reject_path = REJECT_DIR / filename
    if rejects:
        with open(reject_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rejects[0].keys()))
            writer.writeheader()
            writer.writerows(rejects)
    elif reject_path.exists():
        reject_path.unlink()
    stats = {"rows_read": len(raw_rows), "duplicates_removed": duplicates,
             "rows_rejected": len(rejects), "rows_loaded": len(clean), "rejects": rejects}
    return clean, stats


def insert(conn, table, rows):
    if rows:
        cols = list(rows[0].keys())
        conn.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})", rows)


def reconcile(conn):
    """Cross-table checks. Returns a list of (name, passed, detail)."""
    checks = []

    def check(name, sql, detail):
        bad = conn.execute(sql).fetchall()
        checks.append((name, not bad, "ok" if not bad else f"{len(bad)} {detail}: {bad[:3]}"))

    check("Every project has all 8 milestones",
          "SELECT project_id, COUNT(*) FROM milestones GROUP BY 1 HAVING COUNT(*) <> 8", "projects off")
    check("Every project has all 9 cost lines",
          "SELECT project_id, COUNT(*) FROM cost_lines GROUP BY 1 HAVING COUNT(*) <> 9", "projects off")
    check("RFS falls after NTP on every project",
          """SELECT a.project_id, a.milestone_code FROM milestones a JOIN milestones b
               ON b.project_id = a.project_id AND b.milestone_code = 'RFS' AND a.milestone_code = 'NTP'
              WHERE b.forecast_date <= a.forecast_date""", "projects off")
    check("Project status agrees with the RFS milestone",
          """SELECT p.project_id FROM projects p JOIN milestones m
               ON m.project_id = p.project_id AND m.milestone_code = 'RFS'
              WHERE (p.status = 'Complete') <> (m.actual_date IS NOT NULL)""", "projects off")
    check("Approved change orders tie to the cost report (non-contingency lines)",
          """SELECT c.project_id, c.cost_category FROM cost_lines c
              LEFT JOIN (SELECT project_id, cost_category, SUM(amount_usd) amt FROM change_orders
                          WHERE status = 'Approved' GROUP BY 1, 2) o USING (project_id, cost_category)
              WHERE c.cost_category <> 'Contingency'
                AND ABS(c.approved_changes_usd - COALESCE(o.amt, 0)) > 100""", "cost lines off")
    check("Phase capacity fits within each campus plan",
          """SELECT s.site_id FROM sites s JOIN projects p USING (site_id)
              GROUP BY s.site_id HAVING SUM(p.it_capacity_mw) > MAX(s.planned_capacity_mw)""", "sites over plan")
    check("No foreign-key violations", "PRAGMA foreign_key_check", "violations")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file to (re)build")
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((SQL_DIR / "schema.sql").read_text())

    ctx = {"sites": set(), "projects": set(), "as_of": date.today().isoformat()}
    audit, loaded_at = [], datetime.now().isoformat(timespec="seconds")

    def run(filename, table, cleaner, keys):
        rows, stats = process(filename, cleaner, keys, ctx)
        audit.append((filename, table, stats))
        return rows

    with conn:   # one transaction: all tables load or none do
        rows = run("assumptions.csv", "program_assumptions", clean_assumption, ["key"])
        insert(conn, "program_assumptions", rows)
        ctx["as_of"] = next(r["value"] for r in rows if r["key"] == "as_of_date")

        rows = run("sites.csv", "sites", clean_site, ["site_id"])
        insert(conn, "sites", rows)
        ctx["sites"] = {r["site_id"] for r in rows}

        rows = run("projects.csv", "projects", clean_project, ["project_id"])
        insert(conn, "projects", rows)
        ctx["projects"] = {r["project_id"] for r in rows}

        insert(conn, "milestones", run("milestones.csv", "milestones", clean_milestone, ["project_id", "milestone_code"]))

        po_rows = run("purchase_orders.csv", "purchase_orders", clean_po, ["po_line_id"])
        names = sorted({r["vendor_name"] for r in po_rows if r["vendor_name"]})
        conn.executemany("INSERT INTO vendors (vendor_name) VALUES (?)", [(n,) for n in names])
        vendor_ids = dict(conn.execute("SELECT vendor_name, vendor_id FROM vendors"))
        for r in po_rows:
            r["vendor_id"] = vendor_ids.get(r.pop("vendor_name"))
        insert(conn, "purchase_orders", po_rows)

        insert(conn, "change_orders", run("change_orders.csv", "change_orders", clean_change_order, ["co_id"]))
        insert(conn, "cost_lines", run("cost_report.csv", "cost_lines", clean_cost_line, ["project_id", "cost_category"]))
        insert(conn, "risks", run("risk_register.csv", "risks", clean_risk, ["risk_id"]))

        conn.executemany(
            "INSERT INTO import_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(f, t, s["rows_read"], s["duplicates_removed"], s["rows_rejected"], s["rows_loaded"], loaded_at)
             for f, t, s in audit])

    conn.executescript((SQL_DIR / "views.sql").read_text())
    checks = reconcile(conn)
    conn.execute("VACUUM")
    conn.close()

    print(f"\nLoaded {args.db.relative_to(ROOT)}  (data as of {ctx['as_of']})\n")
    print(f"{'source file':<22}{'table':<22}{'read':>6}{'dupes':>7}{'rejected':>10}{'loaded':>8}")
    for f, t, s in audit:
        print(f"{f:<22}{t:<22}{s['rows_read']:>6}{s['duplicates_removed']:>7}{s['rows_rejected']:>10}{s['rows_loaded']:>8}")
    print(f"{'(derived)':<22}{'vendors':<22}{'':>6}{'':>7}{'':>10}{len(names):>8}")

    rejected = [(f, r) for f, _, s in audit for r in s["rejects"]]
    if rejected:
        print(f"\nRejected rows (full records in {REJECT_DIR.relative_to(ROOT)}/):")
        for f, r in rejected:
            print(f"  {f}:{r['source_line']:<4} {r['reject_reason']}")

    print("\nReconciliation checks:")
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + ("" if passed else f" -> {detail}"))
    if not all(passed for _, passed, _ in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
