"""Deterministic sample data for the pipeline report POC. Same seed, same files."""
import csv, random, datetime as dt
from pathlib import Path

random.seed(20261018)
OUT = Path(__file__).parent / "data"
weeks = [dt.date(2026, 10, 18) - dt.timedelta(weeks=11 - i) for i in range(12)]

REGIONS = [("North", 1_100_000), ("South", 900_000), ("East", 1_200_000), ("West", 800_000)]
STAGES = [("Discovery", 1), ("Qualified", 2), ("Proposal", 3), ("Negotiation", 4), ("Commit", 5)]
ACCOUNTS = ["Halvorsen Freight", "Brightwater Labs", "Kestrel Systems", "Marlow & Finch", "Northgate Health",
            "Ostrava Metals", "Pinecrest Foods", "Quillon Software", "Redfern Logistics", "Solano Energy",
            "Tamsin Retail", "Umber Analytics"]
OWNERS = ["A. Rivera", "J. Okafor", "M. Chen", "S. Patel", "T. Novak", "L. Haddad"]

# Slipped deals this week (close date pushed out)
slipped = []
for i, acct in enumerate(random.sample(ACCOUNTS, 7)):
    region = random.choice(REGIONS)[0]
    stage = random.choice(STAGES[2:])[0]
    amount = random.randrange(40, 260) * 1000
    was = dt.date(2026, 10, random.randint(20, 31))
    now = was + dt.timedelta(days=random.choice([14, 21, 30, 45, 60]))
    slipped.append(dict(deal_id=f"OPP-{4100 + i * 7}", account=acct, owner=random.choice(OWNERS), region=region,
                        stage=stage, amount=amount, close_was=was.isoformat(), close_now=now.isoformat()))
slipped_amount = sum(d["amount"] for d in slipped)

# Weekly history: Q3 target through Sep, Q4 target from Oct
rows, pipe = [], 3_150_000
for i, w in enumerate(weeks):
    target = 3_600_000 if w.month < 10 else 4_000_000
    new = random.randrange(180, 420) * 1000
    pipe = pipe + new - random.randrange(120, 330) * 1000
    win = round(0.205 + 0.03 * random.random() + (0.01 if i > 7 else 0), 3)
    rows.append(dict(week=w.isoformat(), pipeline=pipe, target=target, win_rate=win, new_pipeline=new,
                     slipped_amount=random.randrange(150, 520) * 1000, forecast=int(round(pipe * random.uniform(0.29, 0.34), -3))))
rows[-1]["slipped_amount"] = slipped_amount          # keep the table and the history consistent
latest = rows[-1]["pipeline"]

# Current-week breakdowns that sum to the latest pipeline and target
def split(total, weights):
    parts = [int(round(total * w / sum(weights), -3)) for w in weights]
    parts[-1] += total - sum(parts)
    return parts
region_pipe = split(latest, [1.05, 0.78, 1.18, 0.82])
stage_amt = split(latest, [0.31, 0.24, 0.2, 0.15, 0.1])
stage_deals = [58, 41, 27, 16, 9]

def write(name, fields, data):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(data)

write("sample_weekly.csv", list(rows[0]), rows)
write("sample_regions.csv", ["region", "pipeline", "target"],
      [dict(region=r, pipeline=p, target=t) for (r, t), p in zip(REGIONS, region_pipe)])
write("sample_stages.csv", ["stage", "stage_order", "deals", "amount"],
      [dict(stage=s, stage_order=o, deals=d, amount=a) for (s, o), d, a in zip(STAGES, stage_deals, stage_amt)])
write("sample_slipped.csv", list(slipped[0]), sorted(slipped, key=lambda d: -d["amount"]))
print("latest pipeline", latest, "target", rows[-1]["target"], "slipped", slipped_amount, len(slipped))
