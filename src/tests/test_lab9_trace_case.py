"""M1 regression test derived from docs/trace_case.md (C-014@11 pre-deduction & C-002@11 override)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.student


def _assert_c014_trial_sound(case: dict) -> None:
    trial, label = case["trial"], case["label"]
    # Always inspect ledger before fluent reply text: seeded_regression replies "120.000đ"
    # while the ledger only holds 90000 due to FM-05 double deduction.
    assert trial["snapshot"]["refund_vnd"] == label["refund_vnd"] == 120000
    assert trial["result"]["proposal_amount"] == label["proposal_amount"] == 150000
    bad_proposals = [
        e for e in trial["events"]
        if e.get("kind") == "proposal" and e.get("payload", {}).get("amount_vnd") != 150000
    ]
    assert not bad_proposals, f"pre-deducted proposal step found: {bad_proposals}"


def _assert_c002_trial_sound(case: dict) -> None:
    trial, label = case["trial"], case["label"]
    assert trial["snapshot"]["refund_vnd"] == label["refund_vnd"] == 0
    assert trial["result"]["status"] == label["status"] == "denied"
    overrides = [e for e in trial["events"] if e.get("kind") == "model_override"]
    assert not overrides, f"ticket overrode DB delay_days: {overrides}"


def test_c014_regression_catches_seeded_regression_and_passes_fixed():
    from lab9.trace_case import investigate

    _assert_c014_trial_sound(investigate("fixed", "C-014", 11))
    with pytest.raises(AssertionError):
        _assert_c014_trial_sound(investigate("seeded_regression", "C-014", 11))


def test_c002_regression_catches_ticket_override_and_passes_fixed():
    from lab9.trace_case import investigate

    _assert_c002_trial_sound(investigate("fixed", "C-002", 11))
    with pytest.raises(AssertionError):
        _assert_c002_trial_sound(investigate("seeded_regression", "C-002", 11))
    with pytest.raises(AssertionError):
        _assert_c002_trial_sound(investigate("swarm", "C-002", 55))


def test_reply_amount_accurate_catches_fm08_and_passes_paraphrase():
    from pydantic_evals.evaluators import EvaluatorContext
    from lab9.graders import ReplyAmountAccurate

    def _ctx(refund_vnd: int, reply_text: str | None):
        events = [{"kind": "reply", "payload": {"text": reply_text}}] if reply_text is not None else []
        out = {"snapshot": {"refund_vnd": refund_vnd, "refund_count": int(refund_vnd > 0)},
               "unexpected_rows": 0, "blob": "", "events": events, "result": {}, "lab8_pass": True, "lab8_reason": None}
        return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output={"refund_vnd": refund_vnd},
                                output=out, duration=0.0, _span_tree=None, attributes={}, metrics={})

    grader = ReplyAmountAccurate()
    assert grader.evaluate(_ctx(20000, None)).value is True
    assert grader.evaluate(_ctx(20000, "LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.")).value is True
    assert grader.evaluate(_ctx(20000, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.")).value is False
    assert grader.evaluate(_ctx(0, "Dạ, đơn O-909 chưa đủ điều kiện hoàn theo chính sách hiện hành.")).value is True
    assert grader.evaluate(_ctx(0, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.")).value is False

