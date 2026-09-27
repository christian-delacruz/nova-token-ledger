import pytest
from ledger_report import call_cost, summarize

MODEL = "claude-haiku-4-5-20251001"
PRICES = {MODEL: (1.0, 5.0)}


def rec(purpose, inp, out, user="", ts="2026-09-27T21:00:00+00:00", bot="telegram"):
    return {"ts": ts, "bot": bot, "purpose": purpose, "tier": "", "model": MODEL,
            "input_tokens": inp, "output_tokens": out, "user": user}


def test_cost_uses_per_million_prices():
    # 1M input at $1 plus 200k output at $5 = $2.00
    assert call_cost(rec("classify", 1_000_000, 200_000), PRICES) == pytest.approx(2.0)


def test_unpriced_model_fails_loudly():
    r = rec("classify", 10, 1)
    r["model"] = "some-new-model"
    with pytest.raises(ValueError):
        call_cost(r, PRICES)


def test_first_real_nova_message():
    # Measured 2026-09-27: classify 164/7 tokens, answer 276/190 tokens
    s = summarize([rec("classify", 164, 7), rec("answer_free", 276, 190, user="u1")], PRICES)
    assert s["messages"] == 1
    assert s["total_cost"] == pytest.approx(0.001425)
    assert s["classifier_share"] == pytest.approx(0.000199 / 0.001425)


def test_cost_per_learner_counts_distinct_users():
    records = [rec("classify", 100, 5), rec("answer_free", 200, 100, user="u1"),
               rec("classify", 100, 5), rec("answer_free", 200, 100, user="u1"),
               rec("classify", 100, 5), rec("answer_free", 200, 100, user="u2")]
    s = summarize(records, PRICES)
    assert s["cost_per_learner"]["2026-09"] == pytest.approx(s["total_cost"] / 2)


def test_upsells_are_acquisition_cost():
    s = summarize([rec("upsell_avanzado", 300, 100, user="u1")], PRICES)
    assert s["acquisition_cost"] == pytest.approx(s["total_cost"])
