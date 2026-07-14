#!/usr/bin/env python3
"""Self-contained acceptance tests for tv-factor-reproduce."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import factor_tv
import tv_factor_reproduce as reproduce
import tv_selftest


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
ACCEPTANCE = SKILL_ROOT / "references" / "tv-acceptance.json"
CORE_SELFTEST = HERE / "tv_selftest.py"
EXPECTED_ACCEPTANCE_SHA256 = "ac2e5138a5218005e830c720931b77b74619d6ca744118b4d02ca3f35047b42d"
EXPECTED_CORE_LOCK_SHA256 = "6ada73284dfc3621a45aef9ce3e8a77c74bdfa54c3a72b9ffe4221668c72e6f4"


class SkillSelfTestFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SkillSelfTestFailure(message)


def require_close(actual: float, expected: float, label: str) -> None:
    require(
        bool(np.isclose(actual, expected, rtol=1e-12, atol=1e-10, equal_nan=True)),
        f"recurrence drift in {label}: actual={actual!r}, expected={expected!r}",
    )


def bitwise_frame_equal(actual: pd.DataFrame, expected: pd.DataFrame, label: str) -> None:
    require(tuple(actual.columns) == tuple(expected.columns), f"column mismatch: {label}")
    a = actual.to_numpy(dtype=np.float64, copy=False)
    b = expected.to_numpy(dtype=np.float64, copy=False)
    require(np.array_equal(np.isnan(a), np.isnan(b)), f"null-mask mismatch: {label}")
    valid = np.isfinite(a) & np.isfinite(b)
    require(
        np.array_equal(
            np.ascontiguousarray(a[valid]).view(np.uint64),
            np.ascontiguousarray(b[valid]).view(np.uint64),
        ),
        f"float64 bit mismatch: {label}",
    )


def verify_acceptance() -> dict[str, Any]:
    locked = reproduce.verify_locked_core()
    acceptance_sha = reproduce.sha256_file(ACCEPTANCE)
    lock_sha = reproduce.sha256_file(reproduce.CORE_LOCK_PATH)
    require(
        acceptance_sha == EXPECTED_ACCEPTANCE_SHA256,
        f"TV acceptance SHA drift: {acceptance_sha}",
    )
    require(lock_sha == EXPECTED_CORE_LOCK_SHA256, f"TV core-lock SHA drift: {lock_sha}")
    acceptance = reproduce.strict_json(ACCEPTANCE)
    lock = reproduce.strict_json(reproduce.CORE_LOCK_PATH)
    require(acceptance["status"] == "PASS", "TV acceptance status is not PASS")
    require(
        acceptance["acceptance_scope"] == "tv_locked_142_reproduction_core",
        "TV acceptance scope differs",
    )
    require(
        acceptance["implementation"]["sha256"] == locked["core_sha256"],
        "TV implementation SHA differs",
    )
    require(acceptance["contract"]["column_count"] == 142, "TV column count differs")
    require(
        acceptance["contract"]["column_order_sha256"] == locked["column_order_sha256"],
        "TV column order differs",
    )
    require(
        acceptance["contract"]["sha256"] == lock["contract_sha256"],
        "TV contract SHA differs",
    )
    require(
        acceptance["formula_policies"]["ema"]
        == {"span": "period", "adjust": False, "min_periods": "period"},
        "TV EMA policy differs",
    )
    require(
        acceptance["formula_policies"]["rma"]
        == {"alpha": "1/period", "adjust": False, "min_periods": 0},
        "TV RMA policy differs",
    )
    require(
        acceptance["formula_policies"]["mfi"]
        == {
            "division": "direct",
            "positive_only": 100.0,
            "negative_only": 0.0,
            "zero_over_zero": "null",
        },
        "TV MFI policy differs",
    )
    selftest_sha = reproduce.sha256_file(CORE_SELFTEST)
    require(selftest_sha == lock["selftest_sha256"], f"TV selftest SHA drift: {selftest_sha}")
    require(
        selftest_sha == acceptance["verification"]["selftest_sha256"],
        "TV acceptance selftest SHA differs",
    )
    return {
        **locked,
        "acceptance_status": acceptance["status"],
        "acceptance_sha256": acceptance_sha,
        "core_lock_sha256": lock_sha,
        "selftest_sha256": selftest_sha,
        "runtime_external_source_dependency": False,
    }


def verify_cumulative_recurrence() -> dict[str, Any]:
    frame = tv_selftest.synthetic_frame(600)
    result = factor_tv.compute(frame)
    close = frame["close"].to_numpy(dtype=np.float64)
    high = frame["high"].to_numpy(dtype=np.float64)
    low = frame["low"].to_numpy(dtype=np.float64)
    volume = frame["volume"].to_numpy(dtype=np.float64)

    anchors = {
        "tv_obv": 0.0,
        "tv_adl": 0.0,
        "tv_pvt": 0.0,
        "tv_pvi": 1000.0,
        "tv_nvi": 1000.0,
    }
    for name, expected in anchors.items():
        require(result[name].iloc[0] == expected, f"anchor drift: {name}")

    for i in range(1, len(frame)):
        change_sign = np.sign(close[i] - close[i - 1])
        require_close(
            result["tv_obv"].iloc[i],
            result["tv_obv"].iloc[i - 1] + change_sign * volume[i],
            f"tv_obv@{i}",
        )

        denominator = high[i] - low[i]
        clv = 0.0 if denominator == 0.0 else ((close[i] - low[i]) - (high[i] - close[i])) / denominator
        require_close(
            result["tv_adl"].iloc[i],
            result["tv_adl"].iloc[i - 1] + clv * volume[i],
            f"tv_adl@{i}",
        )

        ret = (close[i] - close[i - 1]) / close[i - 1]
        require_close(
            result["tv_pvt"].iloc[i],
            result["tv_pvt"].iloc[i - 1] + volume[i] * ret,
            f"tv_pvt@{i}",
        )
        expected_pvi = (
            result["tv_pvi"].iloc[i - 1] * (1.0 + ret)
            if volume[i] > volume[i - 1]
            else result["tv_pvi"].iloc[i - 1]
        )
        expected_nvi = (
            result["tv_nvi"].iloc[i - 1] * (1.0 + ret)
            if volume[i] < volume[i - 1]
            else result["tv_nvi"].iloc[i - 1]
        )
        require_close(result["tv_pvi"].iloc[i], expected_pvi, f"tv_pvi@{i}")
        require_close(result["tv_nvi"].iloc[i], expected_nvi, f"tv_nvi@{i}")

    alpha = 2.0 / 21.0
    require(result["tv_obv_ema_20"].iloc[:19].isna().all(), "OBV EMA emitted before 20 observations")
    ema_state = result["tv_obv"].iloc[0]
    for i in range(1, 20):
        ema_state = result["tv_obv"].iloc[i] * alpha + ema_state * (1.0 - alpha)
    require_close(result["tv_obv_ema_20"].iloc[19], ema_state, "tv_obv_ema_20@19")
    for i in range(20, len(frame)):
        expected_obv_ema = (
            result["tv_obv"].iloc[i] * alpha
            + result["tv_obv_ema_20"].iloc[i - 1] * (1.0 - alpha)
        )
        require_close(result["tv_obv_ema_20"].iloc[i], expected_obv_ema, f"tv_obv_ema_20@{i}")

    return {
        "rows": len(frame),
        "anchors": anchors,
        "obv": "PASS",
        "obv_ema_20": "PASS",
        "adl": "PASS",
        "pvt": "PASS",
        "pvi": "PASS",
        "nvi": "PASS",
    }


def verify_psar_causal_bootstrap() -> dict[str, Any]:
    frame = tv_selftest.synthetic_frame(80)
    baseline = factor_tv.compute(frame)
    mutated = frame.copy(deep=True)
    mutated.loc[1:, "open"] += 10000.0
    mutated.loc[1:, "high"] += 10000.0
    mutated.loc[1:, "low"] -= 5000.0
    mutated.loc[1:, "close"] -= 2500.0
    changed = factor_tv.compute(mutated)
    for name in ("tv_psar_002_02", "tv_psar_dir"):
        left = np.asarray([baseline[name].iloc[0]], dtype=np.float64)
        right = np.asarray([changed[name].iloc[0]], dtype=np.float64)
        require(np.array_equal(left.view(np.uint64), right.view(np.uint64)), f"PSAR inspected future data: {name}")
    one_row = factor_tv.compute(frame.iloc[:1].copy())
    require(
        baseline["tv_psar_002_02"].iloc[0] == one_row["tv_psar_002_02"].iloc[0],
        "PSAR one-row bootstrap drift",
    )
    return {"future_rows_cannot_change_row0": True, "one_row_bootstrap": True}


def verify_warmup_slice() -> dict[str, Any]:
    rows = 600
    warmup_rows = 300
    frame = tv_selftest.synthetic_frame(rows)
    times = pd.date_range("2019-01-01", periods=rows, freq="5min", tz="Asia/Shanghai")
    combined = frame.copy()
    combined.insert(0, "trade_time", times)
    output, metadata = reproduce.compute_live_output(combined, times[warmup_rows])

    full = factor_tv.compute(frame)
    expected = full.iloc[warmup_rows:].reset_index(drop=True)
    bitwise_frame_equal(output.loc[:, list(factor_tv.COLUMN_ORDER)], expected, "warmup live slice")
    require(len(output) == rows - warmup_rows, "warmup rows leaked into output")
    require(output["trade_time"].iloc[0] == times[warmup_rows], "first live trade_time drift")
    require(metadata["warmup_rows"] == warmup_rows, "reported warmup count drift")

    restarted = factor_tv.compute(frame.iloc[warmup_rows:].reset_index(drop=True))
    anchor_sensitive = ("tv_obv", "tv_adl", "tv_pvt", "tv_pvi", "tv_nvi")
    for name in anchor_sensitive:
        require(
            expected[name].iloc[0] != restarted[name].iloc[0],
            f"warmup anchor test is not discriminating: {name}",
        )
    return {
        "input_rows": rows,
        "warmup_rows": warmup_rows,
        "live_rows": len(output),
        "bitwise_slice": True,
        "anchor_sensitive_columns": list(anchor_sensitive),
    }


def verify_cold_start_gate() -> dict[str, Any]:
    rows = 180
    frame = tv_selftest.synthetic_frame(rows)
    times = pd.date_range("2020-01-01", periods=rows, freq="5min", tz="Asia/Shanghai")
    combined = frame.copy()
    combined.insert(0, "trade_time", times)

    try:
        reproduce.compute_live_output(combined, times[0])
    except reproduce.ReproduceError as exc:
        require("--allow-cold-start" in str(exc), "cold-start rejection lacks explicit recovery gate")
    else:
        raise AssertionError("zero-warmup sequence passed without explicit cold-start acknowledgement")

    output, metadata = reproduce.compute_live_output(
        combined,
        times[0],
        allow_cold_start=True,
    )
    expected = factor_tv.compute(frame)
    bitwise_frame_equal(output.loc[:, list(factor_tv.COLUMN_ORDER)], expected, "cold-start output")
    require(metadata["warmup_rows"] == 0, "cold-start warmup count drift")
    require(metadata["cold_start"] is True, "cold-start metadata drift")
    require(output["trade_time"].min() >= times[0], "pre-live row leaked from cold-start output")
    return {
        "default_fail_closed": True,
        "explicit_acknowledgement": True,
        "rows": len(output),
        "pre_live_rows": 0,
        "bitwise_full_sequence": True,
    }


def verify_output_path_guards() -> dict[str, Any]:
    source = reproduce.CORE_PATH
    protected_output = reproduce.SKILL_ROOT / "references" / "__must_not_write.parquet"
    try:
        reproduce.assert_output_safe(source, protected_output, reproduce.SKILL_ROOT)
    except reproduce.ReproduceError as exc:
        require("protected root" in str(exc), "explicit qdh-root rejection reason drifted")
    else:
        raise AssertionError("explicit protected root accepted an in-root output")

    absent_parent = reproduce.SKILL_ROOT / "__absent_staging_parent__" / "candidate.parquet"
    require(not absent_parent.parent.exists(), "selftest sentinel parent unexpectedly exists")
    try:
        reproduce.assert_output_safe(source, absent_parent, reproduce.SKILL_ROOT)
    except reproduce.ReproduceError as exc:
        require("output parent must already exist" in str(exc), "missing-parent rejection reason drifted")
    else:
        raise AssertionError("CLI accepted an absent output parent")
    return {
        "explicit_protected_root": True,
        "explicit_qdh_root_required": True,
        "missing_parent_rejected": True,
        "writes": False,
    }


def run_selftest() -> dict[str, Any]:
    acceptance = verify_acceptance()
    core = {
        "static": tv_selftest.verify_static_contract(),
        "runtime": tv_selftest.verify_runtime(),
        "ema_and_mfi_policies": tv_selftest.verify_ema_and_mfi_policies(),
        "boundaries": tv_selftest.verify_flat_and_zero_boundaries(),
    }
    recurrence = verify_cumulative_recurrence()
    psar = verify_psar_causal_bootstrap()
    warmup = verify_warmup_slice()
    cold_start = verify_cold_start_gate()
    output_guards = verify_output_path_guards()
    return {
        "status": "PASS",
        "acceptance": acceptance,
        "core_selftest": core,
        "cumulative_recurrence": recurrence,
        "psar_causal_bootstrap": psar,
        "warmup_slice": warmup,
        "cold_start_gate": cold_start,
        "output_path_guards": output_guards,
        "default_writes": False,
        "unified_writer_boundary": "PASS",
    }


def main() -> int:
    try:
        payload = run_selftest()
    except Exception as exc:
        payload = {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
