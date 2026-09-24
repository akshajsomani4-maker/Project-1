#!/usr/bin/env python3
"""
MetricMind demo dataset generator.

Produces (deterministic, seed=42):
  * regions.csv           - EU / US / APAC markets + governed margin targets
  * customers.csv         - 800 B2B customers across those markets
  * orders.csv            - 10,000 orders across the last 4 completed quarters
                            (2025-Q3 .. 2026-Q2), net revenue + COGS
  * customer_quarters.csv - per-customer, per-quarter retention status (churn)

Story baked into the data (what the demo agent must discover through the
semantic layer, never through hardcoded numbers):

  European margin = (revenue - cogs) / revenue drops from ~43% (2026-Q1)
  to ~34% (2026-Q2) because of:
    1. a COGS spike concentrated in Hardware (+18% unit cost, supply chain)
       and Services (+6% delivery cost),
    2. discounting that widened by ~4pp across EU channels,
  while US/APAC margins stay flat / improve slightly.

Run:  python seeds/generate_seeds.py
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 42
CUSTOMER_COUNT = 800
ORDER_COUNT = 10_000

# ---------------------------------------------------------------------------
# Calendar: the last four *completed* quarters relative to the demo dataset.
# ---------------------------------------------------------------------------
QUARTERS: list[tuple[date, date, str]] = [
    (date(2025, 7, 1), date(2025, 9, 30), "2025-Q3"),
    (date(2025, 10, 1), date(2025, 12, 31), "2025-Q4"),
    (date(2026, 1, 1), date(2026, 3, 31), "2026-Q1"),
    (date(2026, 4, 1), date(2026, 6, 30), "2026-Q2"),
]

REGIONS = [
    # code, name, continent, margin_target, markets: (market, country, weight)
    ("EU", "Europe", "Europe", 0.290, [
        ("DACH", "Germany", 0.34),
        ("UK & Ireland", "United Kingdom", 0.28),
        ("Southern Europe", "France", 0.22),
        ("Benelux & Nordics", "Netherlands", 0.16),
    ]),
    ("US", "North America", "North America", 0.295, [
        ("US East", "United States", 0.42),
        ("US West", "United States", 0.36),
        ("US Central", "United States", 0.22),
    ]),
    ("APAC", "Asia-Pacific", "Asia Pacific", 0.280, [
        ("ANZ", "Australia", 0.26),
        ("Japan", "Japan", 0.30),
        ("Southeast Asia", "Singapore", 0.26),
        ("Greater China", "China", 0.18),
    ]),
]

# category -> (list price low/high, typical qty, base unit-cost ratio)
CATEGORIES = {
    "Hardware":     ((350.0, 4200.0), (1, 18), 0.660),
    "Software":     ((60.0, 900.0), (5, 120), 0.300),
    "Services":     ((120.0, 650.0), (1, 45), 0.620),
    "Support & CS": ((250.0, 2400.0), (1, 12), 0.550),
}

CATEGORY_MIX = {"Hardware": 0.35, "Software": 0.30, "Services": 0.20, "Support & CS": 0.15}

CHANNELS = [("Direct", 0.40, 0.050), ("Partner", 0.35, 0.100), ("Online", 0.25, 0.030)]
SEGMENTS = [("Enterprise", 0.30), ("Mid-Market", 0.42), ("SMB", 0.28)]

# Region-wide cost pressure / relief (multiplicative on unit cost).
REGION_COST_ADJ = {"EU": 1.015, "US": 0.985, "APAC": 1.005}

# 2026-Q2 EU anomaly: the "why did European margins drop" storyline.
EU_Q2_COST_SHOCK = {           # category -> extra unit-cost multiplier
    "Hardware": 1.18,
    "Software": 1.01,
    "Services": 1.06,
    "Support & CS": 1.04,
}
EU_Q2_EXTRA_DISCOUNT = 0.040   # +4pp discounting across EU in 2026-Q2

# Slight US/APAC improvement so the drop is clearly EU-specific.
Q2_COST_RELIEF = {"US": 0.985, "APAC": 0.980, "EU": 1.000}

# Customers that stopped buying -> organic churn in customer_quarters.csv.
CHURN_AFTER = [(0, 0.05), (1, 0.045), (2, 0.045)]  # quarter idx -> fraction

COMPANY_PREFIX = [
    "Northwind", "Acme", "Globex", "Initech", "Umbra", "Stark", "Wayne", "Wonka",
    "Hooli", "Pied Piper", "Vandelay", "Slate", "Cyberdyne", "Tyrell", "Massive",
    "Oscorp", "Aperture", "Black Mesa", "Abstergo", "Soylent", "Cybertron",
    "Meridian", "Aurora", "Zenith", "Halcyon", "Kestrel", "Lumen", "Vertex",
]
COMPANY_SUFFIX = [
    "Industries", "Systems", "Group", "Labs", "Logistics", "Retail", "Energy",
    "Financial", "Health", "Media", "Manufacturing", "Holdings", "Networks",
    "Analytics", "Logistik GmbH", "SAS", "S.r.l.", "B.V.", "Pty Ltd", "Ltd",
]


def weighted(pairs):
    """pairs: [(value, weight), ...] -> weighted random choice."""
    values, weights = zip(*pairs)
    return random.choices(values, weights=weights, k=1)[0]


def rand_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randrange((end - start).days + 1))


def quarter_of(d: date) -> int:
    for idx, (q_start, q_end, _) in enumerate(QUARTERS):
        if q_start <= d <= q_end:
            return idx
    return -1


def build_customers(rng: random.Random) -> list[dict]:
    """Customers with market/segment assignment and a churn schedule."""
    # Decide churn stop-quarter per customer first (drives order eligibility).
    stop = []
    for idx in range(CUSTOMER_COUNT):
        stop_q = 3  # active for the whole window by default
        for q_idx, frac in CHURN_AFTER:
            if rng.random() < frac:
                stop_q = q_idx
                break
        stop.append(stop_q)

    customers = []
    used_names: set[str] = set()
    for i in range(CUSTOMER_COUNT):
        region = weighted([("EU", 0.42), ("US", 0.36), ("APAC", 0.22)])
        region_row = next(r for r in REGIONS if r[0] == region)
        market, country = weighted([((m[0], m[1]), m[2]) for m in region_row[4]])

        name = f"{rng.choice(COMPANY_PREFIX)} {rng.choice(COMPANY_SUFFIX)}"
        while name in used_names:
            name = f"{rng.choice(COMPANY_PREFIX)} {rng.choice(COMPANY_SUFFIX)} {i}"
        used_names.add(name)

        # signup: ~55% before the window, rest spread across the 4 quarters
        r = rng.random()
        if r < 0.55:
            signup = rand_date(date(2024, 1, 1), date(2025, 6, 30))
        else:
            q = min(int((r - 0.55) / 0.45 * 4), 3)
            signup = rand_date(QUARTERS[q][0], QUARTERS[q][1])

        cust = {
            "customer_id": f"C-{i + 1:04d}",
            "customer_name": name,
            "segment": weighted(SEGMENTS),
            "region_code": region,
            "market": market,
            "country": country,
            "signup_date": signup.isoformat(),
            "signup_q": quarter_of(signup),
            "stop_q": stop[i],
        }
        customers.append(cust)
    return customers


def build_orders(rng: random.Random, customers: list[dict]) -> list[dict]:
    """10k orders. Eligible customers: signed up, not yet churned, quarter in window."""
    # Region share of order volume; slight growth over time, EU heavy in EU Q2.
    region_weights_by_q = {
        0: [("EU", 0.40), ("US", 0.38), ("APAC", 0.22)],
        1: [("EU", 0.41), ("US", 0.37), ("APAC", 0.22)],
        2: [("EU", 0.42), ("US", 0.36), ("APAC", 0.22)],
        3: [("EU", 0.46), ("US", 0.34), ("APAC", 0.20)],
    }

    eligible: dict[tuple[int, str], list[dict]] = {}
    for q in range(4):
        for region in ("EU", "US", "APAC"):
            eligible[(q, region)] = [
                c for c in customers
                if c["region_code"] == region
                and c["signup_q"] <= q
                and c["stop_q"] >= q
            ]

    orders = []
    for n in range(ORDER_COUNT):
        q = weighted([(0, 0.24), (1, 0.25), (2, 0.25), (3, 0.26)])
        region = weighted(region_weights_by_q[q])
        pool = eligible[(q, region)] or customers
        cust = rng.choice(pool)
        q_start, q_end, _ = QUARTERS[q]
        order_date = rand_date(q_start, q_end)

        category = weighted([(c, CATEGORY_MIX[c]) for c in CATEGORIES])
        channel_name, base_discount = weighted(
            [((c[0], c[1]), c[2]) for c in CHANNELS])
        (price_lo, price_hi), qty_rng, base_cost_ratio = CATEGORIES[category]
        quantity = rng.randint(*qty_rng)
        unit_price = round(rng.uniform(price_lo, price_hi), 2)

        discount = base_discount + rng.uniform(-0.02, 0.03)
        if region == "EU" and q == 3:
            discount += EU_Q2_EXTRA_DISCOUNT          # margin-compressing promo push
        discount = max(0.0, min(discount, 0.35))

        cost_ratio = base_cost_ratio * REGION_COST_ADJ[region]
        if region == "EU" and q == 3:
            cost_ratio *= EU_Q2_COST_SHOCK[category]  # supply-chain cost spike
        if q == 3 and region in Q2_COST_RELIEF:
            cost_ratio *= Q2_COST_RELIEF[region]

        unit_cost = round(unit_price * cost_ratio * rng.uniform(0.97, 1.03), 2)
        order_amount = round(quantity * unit_price * (1.0 - discount), 2)
        cogs = round(quantity * unit_cost, 2)

        orders.append({
            "order_id": f"O-{n + 1:05d}",
            "order_date": order_date.isoformat(),
            "customer_id": cust["customer_id"],
            "region_code": region,
            "market": cust["market"],
            "category": category,
            "channel": channel_name,
            "quantity": quantity,
            "unit_price": f"{unit_price:.2f}",
            "discount_pct": f"{discount:.4f}",
            "order_amount": f"{order_amount:.2f}",
            "cogs": f"{cogs:.2f}",
        })

    orders.sort(key=lambda o: (o["order_date"], o["order_id"]))
    for i, o in enumerate(orders, start=1):
        o["order_id"] = f"O-{i:05d}"
    return orders


def build_customer_quarters(orders: list[dict], customers: list[dict]) -> list[dict]:
    """Retention facts: active_last_quarter / active_this_quarter / churned."""
    active: dict[tuple[str, int], bool] = {}
    for o in orders:
        q = quarter_of(date.fromisoformat(o["order_date"]))
        active[(o["customer_id"], q)] = True

    rows = []
    for c in customers:
        for q in range(4):
            prev = active.get((c["customer_id"], q - 1), False) if q > 0 else False
            cur = active.get((c["customer_id"], q), False)
            q_start, _, label = QUARTERS[q]
            rows.append({
                "customer_id": c["customer_id"],
                "quarter_start": q_start.isoformat(),
                "quarter_label": label,
                "active_last_quarter": int(prev),
                "active_this_quarter": int(cur),
                "churned": int(prev and not cur),
            })
    return rows


def write_csv(name: str, rows: list[dict], fieldnames: list[str]) -> None:
    path = HERE / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {path.name:26s} {len(rows):>6,} rows")


def report(customers: list[dict], orders: list[dict], cq: list[dict]) -> None:
    """Print the margin story so we can eyeball that the demo question is answerable."""
    print("\n== margin by region / quarter (governed definition) ==")
    print(f"{'region':6} {'quarter':9} {'revenue':>14} {'cogs':>14} {'margin':>9}")
    agg: dict[tuple[str, str], list[float]] = {}
    for o in orders:
        q = QUARTERS[quarter_of(date.fromisoformat(o["order_date"]))][2]
        a = agg.setdefault((o["region_code"], q), [0.0, 0.0])
        a[0] += float(o["order_amount"])
        a[1] += float(o["cogs"])
    for region in ("EU", "US", "APAC"):
        for _, _, q_label in QUARTERS:
            rev, cogs = agg[(region, q_label)]
            print(f"{region:6} {q_label:9} {rev:14,.0f} {cogs:14,.0f} {(rev - cogs) / rev:9.1%}")

    print("\n== EU top cost drivers: 2026-Q2 vs 2026-Q1 (cogs delta) ==")
    cat: dict[tuple[str, str], list[float]] = {}
    for o in orders:
        q = QUARTERS[quarter_of(date.fromisoformat(o["order_date"]))][2]
        if o["region_code"] != "EU":
            continue
        a = cat.setdefault((o["category"], q), [0.0, 0.0])
        a[0] += float(o["order_amount"])
        a[1] += float(o["cogs"])
    deltas = []
    for (category, q), (_rev, cogs) in cat.items():
        if q == "2026-Q2":
            prev_cogs = cat.get((category, "2026-Q1"), [0, 0])[1]
            deltas.append((category, cogs - prev_cogs, cogs, prev_cogs))
    for category, delta, cogs, prev in sorted(deltas, key=lambda d: -d[1]):
        pct = (cogs - prev) / prev if prev else 0
        print(f"  {category:15} {prev:12,.0f} -> {cogs:12,.0f}  ({pct:+.1%})")

    churned = sum(r["churned"] for r in cq if r["quarter_label"] == "2026-Q2")
    active_prev = sum(r["active_last_quarter"] for r in cq if r["quarter_label"] == "2026-Q2")
    print(f"\n== churn 2026-Q2: {churned} churned / {active_prev} active_last "
          f"= {churned / active_prev:.1%}")
    print(f"== totals: {len(orders):,} orders, {len(customers):,} customers, "
          f"{len(cq):,} customer-quarter rows")


def main() -> None:
    rng = random.Random(SEED)
    print("Generating MetricMind seed data (deterministic, seed=42)...")
    customers = build_customers(rng)
    orders = build_orders(rng, customers)
    cq = build_customer_quarters(orders, customers)
    regions = [
        {"region_code": code, "region_name": name, "continent": continent,
         "margin_target": f"{target:.3f}"}
        for code, name, continent, target, _ in REGIONS
    ]

    write_csv("regions.csv", regions,
              ["region_code", "region_name", "continent", "margin_target"])
    write_csv("customers.csv", customers[:0] or [
        {k: c[k] for k in ("customer_id", "customer_name", "segment", "region_code",
                           "market", "country", "signup_date")}
        for c in customers
    ], ["customer_id", "customer_name", "segment", "region_code", "market",
        "country", "signup_date"])
    write_csv("orders.csv", orders,
              ["order_id", "order_date", "customer_id", "region_code", "market",
               "category", "channel", "quantity", "unit_price", "discount_pct",
               "order_amount", "cogs"])
    write_csv("customer_quarters.csv", cq,
              ["customer_id", "quarter_start", "quarter_label",
               "active_last_quarter", "active_this_quarter", "churned"])

    report(customers, orders, cq)


if __name__ == "__main__":
    main()
