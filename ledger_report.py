"""Turn Nova's token ledger (one JSON record per Claude call) into unit economics."""
import csv
import json
import sys
from collections import defaultdict

ACQUISITION = {"upsell_intermedio", "upsell_avanzado"}


def load_prices(path="pricing.csv"):
    prices = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            prices[row["model"]] = (float(row["input_per_1m_usd"]), float(row["output_per_1m_usd"]))
    return prices


def load_ledger(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def call_cost(record, prices):
    model = record["model"]
    if model not in prices:
        raise ValueError(f"No price for model {model!r}; add it to pricing.csv")
    input_price, output_price = prices[model]
    return (record["input_tokens"] * input_price + record["output_tokens"] * output_price) / 1_000_000


def summarize(records, prices):
    s = {
        "calls": len(records),
        "messages": 0,
        "total_cost": 0.0,
        "acquisition_cost": 0.0,
        "by_purpose": defaultdict(float),
        "by_bot": defaultdict(float),
        "month_cost": defaultdict(float),
        "month_learners": defaultdict(set),
    }
    for r in records:
        cost = call_cost(r, prices)
        month = r["ts"][:7]
        s["total_cost"] += cost
        s["by_purpose"][r["purpose"]] += cost
        s["by_bot"][r["bot"]] += cost
        s["month_cost"][month] += cost
        if r["purpose"] == "classify":
            s["messages"] += 1
        if r["purpose"] in ACQUISITION:
            s["acquisition_cost"] += cost
        if r["user"]:
            s["month_learners"][month].add(r["user"])
    s["cost_per_message"] = s["total_cost"] / s["messages"] if s["messages"] else 0.0
    classify = s["by_purpose"].get("classify", 0.0)
    s["classifier_share"] = classify / s["total_cost"] if s["total_cost"] else 0.0
    s["cost_per_learner"] = {
        m: s["month_cost"][m] / len(s["month_learners"][m])
        for m in s["month_cost"] if s["month_learners"][m]
    }
    return s


def report(s):
    lines = [
        f"Claude calls:              {s['calls']}",
        f"Student messages:          {s['messages']}",
        f"Total cost:                ${s['total_cost']:.4f}",
        f"Cost per message:          ${s['cost_per_message']:.5f}",
        f"Classifier share of cost:  {s['classifier_share']:.0%}",
        f"Acquisition (upsell) cost: ${s['acquisition_cost']:.4f}",
        "",
        "Cost by purpose:",
    ]
    for purpose, cost in sorted(s["by_purpose"].items(), key=lambda x: -x[1]):
        lines.append(f"  {purpose:<20} ${cost:.4f}")
    lines += ["", "Cost per active learner, by month:"]
    for month, cost in sorted(s["cost_per_learner"].items()):
        n = len(s['month_learners'][month])
        lines.append(f"  {month}  ${cost:.4f}  ({n} learner{'s' if n != 1 else ''})")
    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_data/usage_sample.jsonl"
    print(report(summarize(load_ledger(path), load_prices())))
