#!/usr/bin/env python3
"""Generate synthetic, deliberately messy source-system extracts.

Everything here is fictional. The script first builds a clean, internally
consistent "truth" (projects, schedule, purchase orders, change orders, costs,
risks), then writes it to data/raw/*.csv the way real exports tend to arrive:
mixed date formats, currency strings, vendor-name variants, duplicate rows,
orphaned keys and a few impossible records. The import script has to undo that.

Deterministic: the same seed always produces the same files.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261031
AS_OF = date(2026, 10, 31)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

truth = random.Random(SEED)       # drives the underlying story
mess = random.Random(SEED + 1)    # drives formatting noise only

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
SITES = [
    ("LDN", "Loudoun Ridge Campus", "Northern Virginia", "VA", "East", 120),
    ("PHX", "Sonoran Mesa Campus", "Phoenix", "AZ", "West", 90),
    ("DFW", "Red Oak Campus", "Dallas-Fort Worth", "TX", "Central", 72),
    ("CMH", "Licking Fields Campus", "Columbus", "OH", "Central", 96),
    ("ATL", "Chattahoochee Campus", "Atlanta", "GA", "East", 72),
    ("HIO", "Tualatin Valley Campus", "Hillsboro", "OR", "West", 60),
]

# id, site, phase, MW, type, NTP baseline, duration (months), GC,
# MV switchgear vendor, permit slip (days), utility slip (days)
PROJECTS = [
    ("P01", "LDN", 1, 24, "Greenfield", date(2023, 3, 6), 18, "Harlow Brandt Construction", "Kestrel", 5, 0),
    ("P02", "LDN", 2, 36, "Expansion", date(2023, 11, 6), 19, "Harlow Brandt Construction", "Kestrel", 0, 10),
    ("P03", "PHX", 1, 30, "Greenfield", date(2023, 6, 5), 19, "Mesa Verde Builders", "Halvorsen", 12, 8),
    ("P04", "DFW", 1, 24, "Greenfield", date(2023, 9, 11), 18, "Trinity Structural Group", "Kestrel", 40, 0),
    ("P05", "CMH", 1, 36, "Greenfield", date(2024, 4, 1), 19, "Harlow Brandt Construction", "Kestrel", 0, 55),
    ("P06", "ATL", 1, 24, "Greenfield", date(2025, 3, 3), 18, "Trinity Structural Group", "Kestrel", 8, 0),
    ("P07", "PHX", 2, 30, "Expansion", date(2025, 6, 2), 18, "Mesa Verde Builders", "Halvorsen", 0, 0),
    ("P08", "LDN", 3, 36, "Expansion", date(2025, 8, 4), 19, "Harlow Brandt Construction", "Kestrel", 0, 0),
    ("P09", "DFW", 2, 24, "Expansion", date(2025, 11, 3), 18, "Trinity Structural Group", "Kestrel", 0, 0),
    ("P10", "CMH", 2, 48, "Expansion", date(2027, 2, 1), 20, "Harlow Brandt Construction", None, 0, 0),
    ("P11", "HIO", 1, 30, "Greenfield", date(2027, 4, 5), 19, "Cascade Ridge Constructors", None, 0, 0),
    ("P12", "ATL", 2, 36, "Expansion", date(2027, 6, 7), 19, "Trinity Structural Group", None, 0, 0),
]

VENDORS = {
    "Kestrel": "Kestrel Power Systems",
    "Halvorsen": "Halvorsen Electric",
    "Ironcrest": "Ironcrest Power",
    "Northlake": "Northlake Critical Power",
    "Tallgrass": "Tallgrass Transformer Co.",
    "Polar": "Polar Meridian HVAC",
    "Alder": "Alder Air Systems",
    "Cobalt": "Cobalt Distribution",
    "Sentinel": "Sentinel Controls",
}
VENDOR_VARIANTS = {
    "Kestrel": ["Kestrel Power Systems", "Kestrel Power Systems", "KESTREL POWER SYSTEMS", "Kestrel Power Sys.", "Kestrel Power Systems, Inc."],
    "Halvorsen": ["Halvorsen Electric", "Halvorsen Electric", "Halvorsen Electric LLC", "HALVORSEN ELECTRIC"],
    "Ironcrest": ["Ironcrest Power", "Ironcrest Power", "Ironcrest Power Inc", "IronCrest Power"],
    "Northlake": ["Northlake Critical Power", "Northlake Critical Power", "Northlake Crit. Power"],
    "Tallgrass": ["Tallgrass Transformer Co.", "Tallgrass Transformer Co.", "Tallgrass Transformer Company", "TALLGRASS TRANSFORMER CO"],
    "Polar": ["Polar Meridian HVAC", "Polar Meridian HVAC", "Polar Meridian H.V.A.C."],
    "Alder": ["Alder Air Systems", "Alder Air Systems", "Alder Air Sys"],
    "Cobalt": ["Cobalt Distribution", "Cobalt Distribution", "Cobalt Distribution Inc."],
    "Sentinel": ["Sentinel Controls", "Sentinel Controls", "SENTINEL CONTROLS"],
}

# category: (vendor key or None => project's switchgear vendor, ROS offset in
# months on an 18-month build, lead time weeks, baseline unit cost, units per MW,
# extra units, lots, description)
CATEGORIES = {
    "Generators":      ("Ironcrest", 10.0, 60, 1_900_000, 1 / 3, 1, 2, "3 MW diesel generator set"),
    "Transformers":    ("Tallgrass",  9.5, 70,   450_000, 1 / 3, 0, 2, "MV/LV substation transformer"),
    "MV Switchgear":   (None,        10.0, 52, 2_400_000, 1 / 6, 0, 0, "15 kV switchgear lineup"),
    "LV Switchboards": ("Halvorsen", 10.5, 36,   600_000, 1 / 3, 0, 2, "480 V main switchboard"),
    "UPS":             ("Northlake", 11.0, 34,   550_000, 2 / 3, 0, 2, "1.5 MW UPS module"),
    "Chillers":        ("Polar",     10.5, 40,   900_000, 1 / 2, 1, 2, "Air-cooled chiller"),
    "CRAH Units":      ("Alder",     11.5, 26,    85_000, 4,     0, 2, "CRAH / fan wall unit"),
    "PDU / Busway":    ("Cobalt",    12.0, 24,    60_000, 3,     0, 2, "PDU and busway run"),
    "BMS / EPMS":      ("Sentinel",  12.5, 16,   120_000, 1,     0, 1, "Controls and monitoring package (per MW)"),
}
CATEGORY_VARIANTS = {
    "MV Switchgear": ["MV Switchgear", "MV Switchgear", "Medium Voltage Switchgear", "mv switchgear", "MV SWGR"],
    "LV Switchboards": ["LV Switchboards", "LV Switchboards", "LV Switchboard", "Low Voltage Switchboards"],
    "Generators": ["Generators", "Generators", "Generator", "GENERATORS"],
    "Transformers": ["Transformers", "Transformers", "Transformer", "XFMR"],
    "UPS": ["UPS", "UPS", "ups", "UPS Modules"],
    "Chillers": ["Chillers", "Chillers", "Chiller"],
    "CRAH Units": ["CRAH Units", "CRAH Units", "CRAH", "Fan Walls"],
    "PDU / Busway": ["PDU / Busway", "PDU / Busway", "PDU/Busway", "Busway"],
    "BMS / EPMS": ["BMS / EPMS", "BMS / EPMS", "BMS/EPMS", "BMS"],
}
CRITICAL_PATH = {"MV Switchgear", "Generators", "Transformers", "LV Switchboards"}
FLOAT_WEEKS = 4

MILESTONES = [  # code, name, offset in months on an 18-month build
    ("NTP", "Notice to Proceed", 0.0),
    ("PERMIT", "Building Permit Issued", 2.0),
    ("SHELL", "Shell Dry-In", 8.0),
    ("UTILITY", "Utility Power Energized", 11.0),
    ("GEARSET", "Electrical Gear Set", 11.5),
    ("MEP", "MEP Installation Complete", 14.0),
    ("L5", "Level 5 Commissioning Complete", 17.0),
    ("RFS", "Ready for Service", 18.0),
]

COST_SPLIT = {  # share of non-equipment budget
    "Land & Sitework": 0.10, "Shell & Core": 0.26, "MEP Installation": 0.34,
    "Commissioning": 0.05, "General Conditions": 0.10, "Owner Soft Costs": 0.10,
    "Contingency": 0.05,
}


def add_months(d, months):
    return d + timedelta(days=round(months * 30.4375))


def kestrel_mean_slip_weeks(po_date):
    """Incumbent switchgear vendor: delivery slip has been getting worse."""
    years = (po_date - date(2022, 7, 1)).days / 365.25
    return 3.0 + 4.2 * years


# --------------------------------------------------------------------------
# Build the truth
# --------------------------------------------------------------------------
def build():
    projects, po_lines, milestones, change_orders, cost_lines, risks = [], [], [], [], [], []

    for (pid, site, phase, mw, ptype, ntp, dur, gc, swgr, permit_slip, util_slip) in PROJECTS:
        scale = dur / 18
        site_name = next(s[1] for s in SITES if s[0] == site)
        precon = swgr is None

        # ---------------- purchase orders ----------------
        lines = []
        seq = 0
        for cat, (vkey, ros_off, lead, unit, per_mw, extra, lots, desc) in CATEGORIES.items():
            vendor = vkey or swgr
            ros = add_months(ntp, ros_off * scale)
            total_units = max(1, round(mw * per_mw) + extra)
            if cat == "MV Switchgear":
                lot_sizes = [1] * total_units
                if vendor == "Halvorsen":
                    lead = 54
            elif cat == "BMS / EPMS":
                lot_sizes = [mw]
            else:
                first = total_units // 2
                lot_sizes = [n for n in (first, total_units - first) if n > 0]
            for i, qty in enumerate(lot_sizes):
                seq += 1
                lot_ros = ros + timedelta(days=14 * i if cat != "MV Switchgear" else 5 * i)
                lead_wk = lead + truth.randint(-3, 3)
                po_date = lot_ros - timedelta(weeks=lead_wk + FLOAT_WEEKS) - timedelta(days=truth.randint(0, 10))
                esc = 1.04 ** ((po_date - date(2023, 1, 1)).days / 365.25)
                cost = unit * esc * truth.uniform(0.98, 1.03)
                if vendor == "Halvorsen" and cat == "MV Switchgear":
                    cost *= truth.uniform(1.08, 1.11)
                baseline_cost = unit * 1.04 ** ((ntp - date(2023, 1, 1)).days / 365.25 - 0.8)
                line = {
                    "po_line_id": f"PO-{pid}-{seq:03d}", "project_id": pid, "vendor": vendor,
                    "equipment_category": cat,
                    "description": f"{desc} - lot {i + 1}" if cat != "MV Switchgear" else f"{desc} {chr(65 + i)}",
                    "quantity": qty, "unit_cost_usd": round(cost, -3),
                    "baseline_unit_cost": baseline_cost,
                    "quoted_lead_time_weeks": lead_wk, "required_on_site_date": lot_ros,
                    "po_date": None, "original_promise_date": None,
                    "current_promise_date": None, "actual_delivery_date": None, "status": "Planned",
                }
                planned = (precon and cat == "MV Switchgear") or po_date > AS_OF
                if planned:
                    if cat == "MV Switchgear" and precon:
                        line["vendor"] = None
                        line["unit_cost_usd"] = round(unit * 1.04 ** ((AS_OF - date(2023, 1, 1)).days / 365.25), -3)
                else:
                    if vendor == "Kestrel":
                        slip_wk = max(0.0, truth.gauss(kestrel_mean_slip_weeks(po_date), 2.5))
                    elif vendor == "Halvorsen":
                        slip_wk = max(-2.0, truth.gauss(0.3, 1.3))
                    elif vendor == "Tallgrass":
                        slip_wk = max(-1.0, truth.gauss(3.0, 2.5))
                    elif vendor == "Ironcrest":
                        slip_wk = max(-1.0, truth.gauss(2.0, 2.5))
                    else:
                        slip_wk = max(-2.0, truth.gauss(0.0, 1.2))
                    promise = po_date + timedelta(weeks=lead_wk)
                    delivered = promise + timedelta(days=round(slip_wk * 7))
                    line.update(po_date=po_date, original_promise_date=promise)
                    if delivered <= AS_OF:
                        line.update(current_promise_date=delivered, actual_delivery_date=delivered, status="Delivered")
                    else:
                        # vendor's latest promise; never earlier than the original
                        line.update(current_promise_date=max(delivered, promise), status="Open")
                    line["_effective"] = delivered
                lines.append(line)
        po_lines.extend(lines)

        # ---------------- schedule ----------------
        crit_late = 0
        for ln in lines:
            if ln["equipment_category"] in CRITICAL_PATH and "_effective" in ln:
                crit_late = max(crit_late, (ln["_effective"] - ln["required_on_site_date"]).days)
        slip = {}
        slip["NTP"] = truth.randint(0, 6) if not precon else 0
        slip["PERMIT"] = slip["NTP"] + permit_slip + (truth.randint(0, 6) if not precon else 0)
        slip["SHELL"] = slip["PERMIT"] + (truth.randint(0, 12) if not precon else 0)
        slip["UTILITY"] = util_slip + (truth.randint(0, 7) if not precon else 0)
        slip["GEARSET"] = 0 if precon else max(round(slip["SHELL"] * 0.5), crit_late) + truth.randint(3, 10)
        slip["MEP"] = 0 if precon else max(0, round(max(slip["GEARSET"], slip["UTILITY"]) * 0.92) + truth.randint(-3, 8))
        slip["L5"] = 0 if precon else round(slip["MEP"] * 0.9) + truth.randint(0, 8)
        slip["RFS"] = 0 if precon else slip["L5"] + truth.randint(0, 5)

        ms_rows, prev_done = [], True
        for n, (code, name, off) in enumerate(MILESTONES, start=1):
            base = add_months(ntp, off * scale)
            fc = base + timedelta(days=slip[code])
            done = fc <= AS_OF
            status = "Complete" if done else ("In Progress" if prev_done else "Not Started")
            prev_done = done
            ms_rows.append({
                "project_id": pid, "milestone_code": code, "milestone_name": name, "sequence": n,
                "baseline_date": base, "forecast_date": fc, "actual_date": fc if done else None,
                "status": status,
            })
        milestones.extend(ms_rows)
        by_code = {m["milestone_code"]: m for m in ms_rows}
        rfs_fc, ntp_fc = by_code["RFS"]["forecast_date"], by_code["NTP"]["forecast_date"]
        if by_code["RFS"]["actual_date"]:
            pstatus = "Complete"
        elif not by_code["NTP"]["actual_date"]:
            pstatus = "Pre-Construction"
        elif by_code["MEP"]["actual_date"]:
            pstatus = "Commissioning"
        else:
            pstatus = "Construction"
        progress = 1.0 if pstatus == "Complete" else (
            0.0 if pstatus == "Pre-Construction" else (AS_OF - ntp_fc).days / (rfs_fc - ntp_fc).days)

        projects.append({
            "project_id": pid, "site_id": site, "phase_number": phase,
            "project_name": f"{site_name.replace(' Campus', '')} Phase {phase}",
            "project_type": ptype, "it_capacity_mw": mw, "general_contractor": gc, "status": pstatus,
        })

        # ---------------- change orders ----------------
        cos = []
        delay_total = 0
        end = min(rfs_fc, AS_OF)

        def add_co(d, cause, cost_cat, desc, amount, days):
            if d > AS_OF:
                return
            if pstatus != "Complete" and (AS_OF - d).days <= 75:
                status = "Pending"
            else:
                status = "Rejected" if truth.random() < 0.07 else "Approved"
            cos.append({"project_id": pid, "co_date": d, "cause_category": cause, "cost_category": cost_cat,
                        "description": desc, "amount_usd": round(amount, -2), "schedule_impact_days": days,
                        "status": status})

        if not precon:
            general = [
                ("Design Change", "MEP Installation", 520_000, ["Revised busway routing in data hall", "Added leak detection zones", "Mechanical yard piping redesign", "Fire alarm sequence revision"]),
                ("Owner Scope Change", "Shell & Core", 850_000, ["Added office fit-out scope", "Security perimeter upgrade", "Loading dock expansion", "Tenant-requested cage build-out"]),
                ("Unforeseen Site Condition", "Land & Sitework", 560_000, ["Rock excavation at duct bank", "Unsuitable soils at generator yard", "Undocumented utility relocation"]),
                ("Code / AHJ Requirement", "MEP Installation", 300_000, ["Fire marshal egress revision", "Additional emergency responder radio coverage", "Fuel storage containment upgrade"]),
            ]
            span = max(60, (end - ntp).days - 60)
            for _ in range(round(mw / 3 * min(1.0, progress + 0.1)) + truth.randint(-1, 2)):
                cause, cost_cat, median, descs = truth.choices(general, weights=[4, 3, 2, 2])[0]
                amount = median * truth.lognormvariate(0, 0.6) * (mw / 30)
                if truth.random() < 0.06:
                    amount = -amount * 0.4   # credit / deduct change order
                d = ntp + timedelta(days=60 + truth.randint(0, span))
                add_co(d, cause, cost_cat, truth.choice(descs), amount, truth.choice([0, 0, 0, 2, 3, 5]))
            if util_slip >= 20:
                total = util_slip * 45_000 * (mw / 24)
                u_date = by_code["UTILITY"]["baseline_date"]
                add_co(u_date + timedelta(days=util_slip // 2), "Utility Delay", "General Conditions",
                       "Temporary generator power for commissioning", total * 0.55, util_slip // 2)
                add_co(u_date + timedelta(days=util_slip + 20), "Utility Delay", "General Conditions",
                       "Extended general conditions - utility energization", total * 0.45, util_slip - util_slip // 2)
            if crit_late >= 14:
                total = crit_late * 90_000 * (mw / 24) * truth.uniform(0.9, 1.1)
                delay_total = total
                ros = by_code["GEARSET"]["baseline_date"]
                parts = [
                    (0.40, 0.45, "Extended general conditions - late electrical gear"),
                    (0.35, 0.90, "Out-of-sequence electrical installation and remobilization"),
                    (0.25, 1.30, "Commissioning acceleration (second shift) to recover gear delay"),
                ]
                for share, when, desc in parts:
                    add_co(ros + timedelta(days=round(crit_late * when)), "Equipment Delay", "General Conditions",
                           desc, total * share, round(crit_late * share))
        cos.sort(key=lambda c: c["co_date"])
        for n, c in enumerate(cos, start=1):
            c["co_id"] = f"CO-{pid}-{n:03d}"
        change_orders.extend(cos)

        # ---------------- cost report ----------------
        per_mw = truth.uniform(10.4, 11.6) * 1e6 - (700_000 if ptype == "Expansion" else 0)
        total_budget = mw * per_mw
        equip_budget, equip = {}, {"Electrical Equipment": [0, 0, 0], "Mechanical Equipment": [0, 0, 0]}
        for ln in lines:
            bucket = "Mechanical Equipment" if ln["equipment_category"] in ("Chillers", "CRAH Units", "BMS / EPMS") else "Electrical Equipment"
            value = ln["quantity"] * ln["unit_cost_usd"]
            equip_budget[bucket] = equip_budget.get(bucket, 0) + ln["quantity"] * ln["baseline_unit_cost"] * 1.01
            equip[bucket][2] += value
            if ln["status"] != "Planned":
                equip[bucket][0] += value
                equip[bucket][1] += value * (1.0 if ln["status"] == "Delivered" else 0.25)
        rest = total_budget - sum(equip_budget.values())
        approved = {}
        pending = {}
        for c in cos:
            tgt = approved if c["status"] == "Approved" else pending if c["status"] == "Pending" else None
            if tgt is not None:
                tgt[c["cost_category"]] = tgt.get(c["cost_category"], 0) + c["amount_usd"]
        contingency = rest * COST_SPLIT["Contingency"]
        drawdown = min(contingency, max(0, sum(approved.values())))
        scurve = progress ** 2 * (3 - 2 * progress)
        for cat in ["Land & Sitework", "Shell & Core", "Electrical Equipment", "Mechanical Equipment",
                    "MEP Installation", "Commissioning", "General Conditions", "Owner Soft Costs", "Contingency"]:
            if cat in equip_budget:
                budget = round(equip_budget[cat], -3)
                committed, actual, eac = equip[cat]
                chg = 0
            elif cat == "Contingency":
                budget = round(contingency, -3)
                chg = -drawdown
                committed = actual = 0
                eac = budget if precon else (budget + chg) * (1 - progress)
            else:
                budget = round(rest * COST_SPLIT[cat], -3)
                chg = approved.get(cat, 0)
                revised = budget + chg
                early = {"Land & Sitework": 0.5, "Owner Soft Costs": 0.12}.get(cat, 0.0) if not precon else {"Land & Sitework": 0.15, "Owner Soft Costs": 0.08}.get(cat, 0.0)
                commit_pct = 1.0 if progress >= 1 else min(1.0, max(early, progress * 1.25 + (0.1 if not precon else 0)))
                actual_pct = 1.0 if progress >= 1 else max(early * 0.8, scurve)
                trend = truth.gauss(0.004, 0.012) if not precon else 0
                eac = revised * (1 + trend) + 0.6 * pending.get(cat, 0)
                if cat == "General Conditions" and progress < 1:
                    # delay cost already incurred on site but not yet in a change order
                    issued = sum(c["amount_usd"] for c in cos if c["cause_category"] == "Equipment Delay")
                    eac += max(0, delay_total - issued)
                committed = revised * commit_pct
                actual = min(committed, eac * actual_pct)
                if progress >= 1:
                    committed = actual = eac
            cost_lines.append({"project_id": pid, "cost_category": cat, "original_budget_usd": budget,
                               "approved_changes_usd": round(chg, -2), "committed_usd": round(committed, -3),
                               "actual_to_date_usd": round(actual, -3), "estimate_at_completion_usd": round(eac, -3)})

        # ---------------- risk register ----------------
        if pstatus != "Complete":
            templates = [
                ("Utility", "Utility substation energization later than committed", (0.15, 0.40), (0.02, 0.06), (20, 60), "Energy Manager"),
                ("Labor", "Electrical trade labor shortage in metro", (0.25, 0.45), (0.03, 0.07), (10, 30), "Construction Manager"),
                ("Permitting", "AHJ inspection backlog delays energization sign-off", (0.15, 0.35), (0.01, 0.03), (7, 25), "Construction Manager"),
                ("Commissioning", "Commissioning agent availability for L4/L5 scripts", (0.20, 0.40), (0.01, 0.03), (10, 21), "Commissioning Lead"),
                ("Design", "High-density tenant requires liquid-cooling scope change", (0.15, 0.35), (0.08, 0.20), (15, 45), "Design Manager"),
                ("Supply Chain", "Transformer lead-time extension", (0.20, 0.40), (0.02, 0.05), (14, 40), "Procurement Lead"),
                ("Weather", "Winter weather impact on sitework and roofing", (0.20, 0.35), (0.01, 0.02), (5, 15), "Construction Manager"),
            ]
            chosen = truth.sample(templates, 4 if pstatus == "Commissioning" else 5)
            rows = []
            if swgr != "Halvorsen":
                rows.append(("Supply Chain", "MV switchgear delivered late by single-source incumbent",
                             truth.uniform(0.60, 0.78), mw * truth.uniform(0.16, 0.24) * 1e6,
                             truth.randint(60, 100), "Procurement Lead"))
            for cat, title, p, c, d, owner in chosen:
                rows.append((cat, title, truth.uniform(*p), mw * truth.uniform(*c) * 1e6, truth.randint(*d), owner))
            start = min(ntp, AS_OF) - timedelta(days=120)
            for n, (cat, title, p, c, d, owner) in enumerate(rows, start=1):
                raised = start + timedelta(days=truth.randint(0, max(30, (AS_OF - start).days - 20)))
                status = truth.choices(["Open", "Mitigating", "Closed"], weights=[5, 4, 1 if n > 1 else 0])[0]
                risks.append({"risk_id": f"R-{pid}-{n:02d}", "project_id": pid, "category": cat, "title": title,
                              "probability": round(p, 2), "cost_impact_usd": round(c, -4),
                              "schedule_impact_days": d, "status": status, "owner_role": owner,
                              "date_raised": raised})

    return projects, po_lines, milestones, change_orders, cost_lines, risks


# --------------------------------------------------------------------------
# Mess it up and write it out
# --------------------------------------------------------------------------
def m_date(d, blanks=("",)):
    if d is None:
        return mess.choice(blanks)
    r = mess.random()
    if r < 0.68:
        return d.isoformat()
    if r < 0.90:
        return d.strftime("%m/%d/%Y")
    return d.strftime("%d-%b-%Y")


def m_money(x):
    if x is None:
        return ""
    r = mess.random()
    if x < 0:
        return f"({abs(x):,.0f})" if r < 0.6 else f"-{abs(x):.2f}"
    if r < 0.55:
        return f"{x:.2f}"
    if r < 0.88:
        return f"${x:,.0f}"
    return f"{x:,.2f}"


def m_text(s):
    r = mess.random()
    if r < 0.05:
        return s + "  "
    if r < 0.08:
        return " " + s
    return s


def m_case(s):
    r = mess.random()
    if r < 0.10:
        return s.upper()
    if r < 0.18:
        return s.lower()
    return s


def m_pid(p):
    return p.lower() if mess.random() < 0.05 else p


def with_duplicates(rows, n):
    out = list(rows)
    for row in mess.sample(rows, n):
        out.insert(mess.randint(0, len(out)), dict(row))
    return out


def write(name, fieldnames, rows):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_DIR / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {name:<22} {len(rows):>4} rows")


def main():
    projects, po_lines, milestones, change_orders, cost_lines, risks = build()
    print(f"Writing raw extracts to {RAW_DIR}")

    write("sites.csv", ["site_id", "site_name", "metro", "state", "region", "planned_capacity_mw"],
          [dict(zip(["site_id", "site_name", "metro", "state", "region", "planned_capacity_mw"], s)) for s in SITES])

    write("projects.csv",
          ["Project ID", "Site", "Phase", "Project Name", "Type", "IT Capacity", "General Contractor", "Status"],
          [{"Project ID": p["project_id"], "Site": p["site_id"], "Phase": p["phase_number"],
            "Project Name": m_text(p["project_name"]), "Type": m_case(p["project_type"]),
            "IT Capacity": f"{p['it_capacity_mw']} MW" if mess.random() < 0.4 else p["it_capacity_mw"],
            "General Contractor": m_text(p["general_contractor"]), "Status": m_case(p["status"])}
           for p in projects])

    ms = [{"project": m_pid(m["project_id"]), "milestone_code": m["milestone_code"],
           "milestone": m["milestone_name"], "seq": m["sequence"],
           "baseline_finish": m_date(m["baseline_date"]), "forecast_finish": m_date(m["forecast_date"]),
           "actual_finish": m_date(m["actual_date"], ("", "", "N/A")), "status": m_case(m["status"])}
          for m in milestones]
    write("milestones.csv", ["project", "milestone_code", "milestone", "seq", "baseline_finish",
                             "forecast_finish", "actual_finish", "status"], with_duplicates(ms, 4))

    pos = []
    for ln in po_lines:
        vendor = mess.choice(VENDOR_VARIANTS[ln["vendor"]]) if ln["vendor"] else mess.choice(["TBD", "", "tbd"])
        pos.append({
            "PO Line": ln["po_line_id"], "Project": m_pid(ln["project_id"]), "Vendor": m_text(vendor),
            "Category": mess.choice(CATEGORY_VARIANTS[ln["equipment_category"]]),
            "Description": ln["description"], "Qty": ln["quantity"],
            "Unit Cost": m_money(ln["unit_cost_usd"]),
            "Extended Value": m_money(ln["quantity"] * ln["unit_cost_usd"]),
            "PO Date": m_date(ln["po_date"], ("", "TBD")),
            "Lead Time (wks)": ln["quoted_lead_time_weeks"],
            "Required On Site": m_date(ln["required_on_site_date"]),
            "Original Promise": m_date(ln["original_promise_date"], ("", "TBD")),
            "Current Promise": m_date(ln["current_promise_date"], ("", "TBD")),
            "Actual Delivery": m_date(ln["actual_delivery_date"], ("", "", "N/A")),
            "Status": m_case(ln["status"]),
        })
    pos = with_duplicates(pos, 7)
    # Records the import must reject
    template = next(p for p in pos if p["Status"].lower() == "delivered")
    pos.append({**template, "PO Line": "PO-P13-001", "Project": "P13"})            # unknown project
    pos.append({**template, "PO Line": "PO-P99-014", "Project": "P99"})            # unknown project
    pos.append({**template, "PO Line": "PO-P04-901", "Project": "P04", "Qty": 0})  # zero quantity
    pos.append({**template, "PO Line": "PO-P02-902", "Project": "P02",
                "PO Date": "2024-06-03", "Original Promise": "2024-12-02",
                "Current Promise": "2024-05-01", "Actual Delivery": "2024-05-01"})  # delivered before ordered
    pos.append({**template, "PO Line": "PO-P05-903", "Project": "P05", "Unit Cost": "see quote"})
    write("purchase_orders.csv", list(pos[0].keys()), pos)

    cause_variants = {"Equipment Delay": ["Equipment Delay", "Equipment Delay", "Equip. Delay", "equipment delay"],
                      "Code / AHJ Requirement": ["Code / AHJ Requirement", "Code/AHJ Requirement", "AHJ Requirement"],
                      "Owner Scope Change": ["Owner Scope Change", "Owner Scope Change", "Owner Change"]}
    cos = [{"co_number": c["co_id"], "project_id": m_pid(c["project_id"]), "date": m_date(c["co_date"]),
            "cause": mess.choice(cause_variants.get(c["cause_category"], [c["cause_category"]])),
            "cost_category": c["cost_category"], "description": m_text(c["description"]),
            "amount": m_money(c["amount_usd"]), "schedule_days": c["schedule_impact_days"],
            "status": m_case(c["status"])} for c in change_orders]
    cos = with_duplicates(cos, 5)
    cos.append({**cos[0], "co_number": "CO-P77-001", "project_id": "P77"})
    cos.append({**cos[1], "co_number": "CO-P03-900", "project_id": "P03", "date": "13/45/2024"})
    write("change_orders.csv", list(cos[0].keys()), cos)

    write("cost_report.csv",
          ["project_id", "cost_category", "original_budget", "approved_changes", "committed",
           "actual_to_date", "estimate_at_completion"],
          [{"project_id": c["project_id"], "cost_category": c["cost_category"],
            "original_budget": m_money(c["original_budget_usd"]),
            "approved_changes": m_money(c["approved_changes_usd"]),
            "committed": m_money(c["committed_usd"]), "actual_to_date": m_money(c["actual_to_date_usd"]),
            "estimate_at_completion": m_money(c["estimate_at_completion_usd"])} for c in cost_lines])

    rk = [{"risk_id": r["risk_id"], "project_id": r["project_id"], "category": r["category"],
           "title": r["title"],
           "probability": f"{round(r['probability'] * 100)}%" if mess.random() < 0.35 else r["probability"],
           "cost_impact": m_money(r["cost_impact_usd"]), "schedule_impact_days": r["schedule_impact_days"],
           "status": m_case(r["status"]), "owner": r["owner_role"], "date_raised": m_date(r["date_raised"])}
          for r in risks]
    write("risk_register.csv", list(rk[0].keys()), with_duplicates(rk, 2))

    write("assumptions.csv", ["key", "value", "unit", "description"], [
        {"key": "as_of_date", "value": AS_OF.isoformat(), "unit": "date",
         "description": "Data cut-off for every extract in this folder"},
        {"key": "lease_rate_usd_per_kw_month", "value": 165, "unit": "USD/kW-month",
         "description": "Planning lease rate used to value a month of delayed capacity"},
        {"key": "billing_ramp_factor", "value": 0.5, "unit": "ratio",
         "description": "Share of a phase's capacity assumed to be billing during the delay window"},
        {"key": "schedule_float_weeks", "value": FLOAT_WEEKS, "unit": "weeks",
         "description": "Float planned between vendor promise date and required-on-site date"},
        {"key": "dual_source_onboarding_usd_per_project", "value": 350000, "unit": "USD",
         "description": "One-time engineering, factory witness test and drawing re-coordination cost when a project switches switchgear vendor"},
    ])


if __name__ == "__main__":
    main()
