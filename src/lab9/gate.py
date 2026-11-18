"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    problems: list[str] = []

    ev_fail = pr.get("evaluator_failures")
    if not isinstance(ev_fail, list) or ev_fail:
        problems.append(f"evaluator_failures non-empty or invalid: {ev_fail!r}")

    pr_metrics = pr.get("metrics")
    if not isinstance(pr_metrics, dict):
        problems.append("pr['metrics'] is missing or not a dict")
        pr_metrics = {}
    for k, v in pr_metrics.items():
        if v is None:
            problems.append(f"metric {k} is None")
        elif isinstance(v, bool) or not isinstance(v, (int, float)):
            problems.append(f"metric {k} is non-numeric: {v!r}")
        elif math.isnan(v) or math.isinf(v):
            problems.append(f"metric {k} is {v}")
    for m in spec.get("metrics") or []:
        mid = m["id"]
        if mid not in pr_metrics or pr_metrics.get(mid) is None:
            problems.append(f"spec metric {mid} missing from pr['metrics']")

    pr_man = pr.get("manifest") or {}
    base_man = base.get("manifest") or {}
    pr_rows = pr.get("rows")
    base_rows = base.get("rows") or []
    if not isinstance(pr_rows, list):
        problems.append("pr['rows'] is missing or not a list")
        return problems

    pr_items = pr_man.get("items")
    pr_seeds = pr_man.get("seeds")
    if not isinstance(pr_items, int) or not isinstance(pr_seeds, list):
        problems.append("manifest items/seeds malformed")
    else:
        if len(set(pr_seeds)) != len(pr_seeds):
            problems.append("duplicate seeds in manifest")
        if pr_items != base_man.get("items"):
            problems.append(f"manifest items {pr_items} != baseline {base_man.get('items')}")
        if pr_seeds != base_man.get("seeds"):
            problems.append(f"manifest seeds {pr_seeds} != baseline {base_man.get('seeds')}")
        if "seeds" in spec and list(pr_seeds) != list(spec["seeds"]):
            problems.append(f"manifest seeds {pr_seeds} != spec seeds {spec['seeds']}")
        expected_rows = pr_items * len(pr_seeds)
        if len(pr_rows) != expected_rows:
            problems.append(f"row count {len(pr_rows)} != manifest items*seeds ({expected_rows})")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows if isinstance(r, dict)]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows if isinstance(r, dict)]
    if len(pr_pairs) != len(pr_rows):
        problems.append("malformed row entry in pr['rows']")
    if len(set(pr_pairs)) != len(pr_pairs):
        problems.append("duplicate (item_id, seed) rows in PR report")
    if set(pr_pairs) != set(base_pairs):
        problems.append("PR (item_id, seed) set differs from baseline")

    base_by_pair = {(r.get("item_id"), r.get("seed")): r for r in base_rows if isinstance(r, dict)}
    for r in pr_rows:
        if not isinstance(r, dict):
            continue
        pair = (r.get("item_id"), r.get("seed"))
        br = base_by_pair.get(pair)
        if br is not None and sorted(r.get("slices") or []) != sorted(br.get("slices") or []):
            problems.append(f"slice tags modified on {pair}: {r.get('slices')} != {br.get('slices')}")
            break

    graded_ids = [
        m["id"] for m in (spec.get("metrics") or [])
        if m["id"] in GRADERS
        and (not base_rows or m["id"] in base_rows[0] or any(isinstance(r, dict) and m["id"] in r for r in pr_rows))
    ]
    row_metric_broken = False
    for r in pr_rows:
        if not isinstance(r, dict):
            row_metric_broken = True
            break
        for mid in graded_ids:
            val = r.get(mid)
            if not isinstance(val, bool):
                problems.append(f"row ({r.get('item_id')}, {r.get('seed')}) metric {mid} is {val!r} (expected bool)")
                row_metric_broken = True
                break
        if row_metric_broken:
            break

    if not row_metric_broken and pr_rows:
        for m in spec.get("metrics") or []:
            mid = m["id"]
            pv = pr_metrics.get(mid)
            if mid in graded_ids and isinstance(pv, (int, float)) and not isinstance(pv, bool) and not math.isnan(pv):
                vals = [bool(r[mid]) for r in pr_rows]
                is_safety = mid in ("secret_leak", "approval_bypass") or m.get("kind") == "safety"
                exp_val = sum(vals) if is_safety else round(sum(vals) / len(vals), 4)
                if abs(float(pv) - float(exp_val)) > 1e-3:
                    problems.append(f"metric {mid}={pv} disagrees with rows ({exp_val})")
        if "pass_rate" in graded_ids:
            by_item: dict[str, list[bool]] = {}
            for r in pr_rows:
                by_item.setdefault(str(r.get("item_id")), []).append(bool(r["pass_rate"]))
            for k in spec.get("pass_k") or []:
                for prefix, fn in (("pass_at", stats.pass_at_k), ("pass_hat", stats.pass_hat_k)):
                    mk = f"{prefix}_{k}"
                    pv = pr_metrics.get(mk)
                    if (isinstance(pv, (int, float)) and not isinstance(pv, bool) and not math.isnan(pv)
                            and by_item and min(len(v) for v in by_item.values()) >= k):
                        exp_k = round(sum(fn(len(v), sum(v), k) for v in by_item.values()) / len(by_item), 4)
                        if abs(float(pv) - exp_k) > 1e-3:
                            problems.append(f"metric {mk}={pv} disagrees with rows ({exp_k})")

    same_eval_set = (
        base_spec is not None
        and (spec.get("eval_set_version") == base_spec.get("eval_set_version")
             or (pr_man.get("eval_set_sha") and pr_man.get("eval_set_sha") == base_man.get("eval_set_sha")))
    )
    if same_eval_set and base_spec is not None:
        spec_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
        for bm in base_spec.get("metrics") or []:
            mid = bm["id"]
            if mid not in spec_metrics:
                problems.append(f"ratchet: metric {mid} removed from spec")
                continue
            sm = spec_metrics[mid]
            if bm.get("blocking") and not sm.get("blocking"):
                problems.append(f"ratchet: metric {mid} changed from blocking to non-blocking")
            bth = bm.get("threshold") or {}
            sth = sm.get("threshold") or {}
            if "min" in bth and ("min" not in sth or sth["min"] < bth["min"] - 1e-12):
                problems.append(f"ratchet: metric {mid} min loosened ({sth.get('min')} < {bth['min']})")
            if "max" in bth and ("max" not in sth or sth["max"] > bth["max"] + 1e-12):
                problems.append(f"ratchet: metric {mid} max loosened ({sth.get('max')} > {bth['max']})")
            if "max_increase" in bth and ("max_increase" not in sth or sth["max_increase"] > bth["max_increase"] + 1e-12):
                problems.append(f"ratchet: metric {mid} max_increase loosened")
            if bth.get("no_significant_drop") and not sth.get("no_significant_drop"):
                problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

        spec_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
        for bsl in base_spec.get("slices") or []:
            skey = (bsl["name"], bsl["metric"])
            if skey not in spec_slices:
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} removed from spec")
                continue
            ssl = spec_slices[skey]
            if bsl.get("blocking") and not ssl.get("blocking"):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} changed from blocking to non-blocking")
            bth = bsl.get("threshold") or bsl
            sth = ssl.get("threshold") or ssl
            if "min" in bth and ("min" not in sth or sth["min"] < bth["min"] - 1e-12):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} min loosened")
            if "max" in bth and ("max" not in sth or sth["max"] > bth["max"] + 1e-12):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} max loosened")
            if bth.get("no_significant_drop") and not sth.get("no_significant_drop"):
                problems.append(f"ratchet: slice {skey[0]}/{skey[1]} dropped no_significant_drop")

        if "seeds" in base_spec and "seeds" in spec and list(spec["seeds"]) != list(base_spec["seeds"]):
            problems.append("ratchet: spec seeds modified")
        base_bs = base_spec.get("bootstrap") or {}
        spec_bs = spec.get("bootstrap") or {}
        if base_bs and spec_bs and spec_bs.get("confidence", 0.95) > base_bs.get("confidence", 0.95) + 1e-12:
            problems.append("ratchet: bootstrap confidence raised to widen CI")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap") or {}
    for s in spec.get("slices") or []:
        name, mid = s["name"], s["metric"]
        sid = f"slice:{name}/{mid}"
        th = s.get("threshold") or s
        a = per_item(pr, mid, slice_name=name)
        b = per_item(base, mid, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        else:
            if "max" in th and val > th["max"]:
                verdict = "fail"
            elif "min" in th and val < th["min"]:
                verdict = "fail"
            if th.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th_disp = {k: th[k] for k in ("min", "max", "no_significant_drop") if k in th}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th_disp):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
