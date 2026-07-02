#!/usr/bin/env python
"""锁定版 WH6 198 列合同的只读审计工具。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "references" / "wh6-locked-198-contract.json"


def load_contract(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_tag(text: str, tag: str) -> str:
    match = re.search(fr"<{tag}>\s*(.*?)\s*</{tag}>", text, flags=re.S | re.I)
    return match.group(1).strip() if match else ""


def read_xtrd(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    text = data.decode("gb18030", errors="replace").replace("\x00", "")
    return {
        "file_sha256": sha_bytes(data),
        "param_text": extract_tag(text, "PARAM"),
        "code_text": extract_tag(text, "CODE"),
    }


def contract_columns(contract: dict[str, Any]) -> list[str]:
    return [entry["column"] for entry in contract["entries"]]


def wh6_columns(header: list[str]) -> list[str]:
    return [col for col in header if col.startswith("wh6_")]


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def iter_csv_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = []
    for csv_path in path.rglob("*.csv"):
        name = csv_path.name
        if name.endswith("_indicator_audit.csv"):
            continue
        if name in {"all_symbols_all_periods_summary.csv", "liquidity_screen.csv"}:
            continue
        files.append(csv_path)
    return sorted(files)


def cmd_summary(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    evidence = contract.get("source_evidence", {})
    print(f"contract: {contract['contract_name']}")
    print(f"schema_version: {contract['schema_version']}")
    print(f"locked_wh6_columns: {contract['wh6_column_count']}")
    print(f"base_columns: {', '.join(contract['base_columns'])}")
    print(f"explicit_named_outputs: {evidence.get('explicit_named_count')}")
    print(f"anonymous_or_sanitized_outputs: {evidence.get('anonymous_or_sanitized_count')}")
    print(f"xtrd_files_seen_in_source_evidence: {evidence.get('xtrd_file_count_seen')}")
    return 0


def cmd_check_xtrd(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    xtrd_root = args.xtrd_root
    failures: list[str] = []
    seen_paths: set[str] = set()

    for entry in contract["entries"]:
        rel = entry["xtrd_relative_path"]
        if rel in seen_paths:
            continue
        seen_paths.add(rel)
        path = xtrd_root / Path(rel)
        if not path.exists():
            failures.append(f"missing_xtrd: {rel}")
            continue
        actual = read_xtrd(path)
        if actual["file_sha256"] != entry["xtrd_file_sha256"]:
            failures.append(f"file_sha256_changed: {rel}")
        if sha_text(actual["param_text"]) != entry["param_sha256"]:
            failures.append(f"param_sha256_changed: {rel}")
        if sha_text(actual["code_text"]) != entry["code_sha256"]:
            failures.append(f"code_sha256_changed: {rel}")

    print(f"checked_xtrd_files: {len(seen_paths)}")
    if failures:
        print(f"failures: {len(failures)}")
        for item in failures[: args.show]:
            print(item)
        return 1
    print("status: PASS")
    return 0


def require_pandas():
    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit("数值锚点检查需要 pandas 和 numpy") from exc
    return pd, np


def compute_anchors(df):
    pd, np = require_pandas()

    def ma(s, n):
        return s.rolling(int(n), min_periods=int(n)).mean()

    def rolling_sum(s, n):
        return s.cumsum() if int(n) == 0 else s.rolling(int(n), min_periods=int(n)).sum()

    def hhv(s, n):
        return s.rolling(int(n), min_periods=int(n)).max()

    def llv(s, n):
        return s.rolling(int(n), min_periods=int(n)).min()

    def ref(s, n):
        return s.shift(int(n))

    def ema(s, n):
        return s.ewm(alpha=2 / (float(n) + 1), adjust=False).mean()

    def sma(s, n, m):
        alpha = float(m) / float(n)
        out = []
        prev = np.nan
        for value in pd.Series(s).astype(float).to_numpy():
            if np.isnan(value):
                out.append(prev if not np.isnan(prev) else np.nan)
            elif np.isnan(prev):
                prev = value
                out.append(prev)
            else:
                prev = alpha * value + (1 - alpha) * prev
                out.append(prev)
        return pd.Series(out, index=pd.Series(s).index)

    def std(s, n):
        return s.rolling(int(n), min_periods=int(n)).std(ddof=0)

    def avedev(s, n):
        return s.rolling(int(n), min_periods=int(n)).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )

    def ifelse(cond, a, b):
        if not hasattr(a, "index"):
            a = pd.Series(a, index=cond.index)
        if not hasattr(b, "index"):
            b = pd.Series(b, index=cond.index)
        return pd.Series(np.where(cond, a, b), index=cond.index)

    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    out = {}

    out["wh6_OPEN_OPEN"] = open_
    out["wh6_HIGH_HIGH"] = high
    out["wh6_LOW_LOW"] = low
    out["wh6_CLOSE_CLOSE"] = close
    out["wh6_BAR_BAR"] = open_
    out["wh6_MA_MA1"] = ma(close, 10)
    out["wh6_EMA_MA1"] = ema(close, 20)
    out["wh6_SMA_SMA"] = sma(close, 6, 2)
    ema60 = ema(close, 60)
    out["wh6_DEMA_DEMA"] = 2 * ema60 - ema(ema60, 60)

    diff = ema(close, 12) - ema(close, 26)
    dea = ema(diff, 9)
    out["wh6_MACD_DIFF"] = diff
    out["wh6_MACD_DEA"] = dea
    out["wh6_MACD_MACD"] = 2 * (diff - dea)

    rsv = (close - llv(low, 9)) / (hhv(high, 9) - llv(low, 9)) * 100
    k = sma(rsv, 3, 1)
    d = sma(k, 3, 1)
    out["wh6_KDJ_K"] = k
    out["wh6_KDJ_D"] = d
    out["wh6_KDJ_J"] = 3 * k - 2 * d

    rsv_kd = (close - llv(low, 17)) / (hhv(high, 17) - llv(low, 17)) * 100
    kd_k = sma(rsv_kd, 6, 1)
    kd_d = sma(kd_k, 6, 1)
    out["wh6_KD_K"] = kd_k
    out["wh6_KD_D"] = kd_d

    lc = ref(close, 1)
    out["wh6_RSI_RSI1"] = sma(np.maximum(close - lc, 0), 8, 1) / sma((close - lc).abs(), 8, 1) * 100
    out["wh6_RSI_RSI2"] = sma(np.maximum(close - lc, 0), 14, 1) / sma((close - lc).abs(), 14, 1) * 100

    tr = np.maximum(np.maximum(high - low, (ref(close, 1) - high).abs()), (ref(close, 1) - low).abs())
    out["wh6_ATR_TR"] = tr
    out["wh6_ATR_ATR"] = ma(tr, 14)
    out["wh6_BIAS_BIAS1"] = (close - ma(close, 6)) / ma(close, 6) * 100
    out["wh6_BIAS_BIAS2"] = (close - ma(close, 12)) / ma(close, 12) * 100
    out["wh6_BIAS_BIAS3"] = (close - ma(close, 20)) / ma(close, 20) * 100

    roc = (close - ref(close, 24)) / ref(close, 24) * 100
    out["wh6_ROC_ROC"] = roc
    out["wh6_ROC_ROCMA"] = ma(roc, 20)

    mid = ma(close, 26)
    sigma = std(close, 26)
    out["wh6_BOLL_MID"] = mid
    out["wh6_BOLL_TOP"] = mid + 1.5 * sigma
    out["wh6_BOLL_BOTTOM"] = mid - 1.5 * sigma

    typ = (close + high + low) / 3
    out["wh6_CCI_CCI"] = (typ - ma(typ, 100)) / avedev(typ, 100) / 0.015

    tr_sum = rolling_sum(np.maximum(np.maximum(high - low, (high - ref(close, 1)).abs()), (low - ref(close, 1)).abs()), 14)
    hd = high - ref(high, 1)
    ld = ref(low, 1) - low
    dmp = rolling_sum(ifelse((hd > 0) & (hd > ld), hd, 0), 14)
    dmm = rolling_sum(ifelse((ld > 0) & (ld > hd), ld, 0), 14)
    pdi = dmp * 100 / tr_sum
    mdi = dmm * 100 / tr_sum
    adx = ma((mdi - pdi).abs() / (mdi + pdi) * 100, 6)
    out["wh6_DMI_PDI"] = pdi
    out["wh6_DMI_MDI"] = mdi
    out["wh6_DMI_ADX"] = adx
    out["wh6_DMI_ADXR"] = (adx + ref(adx, 6)) / 2

    signed_volume = ifelse(close > ref(close, 1), volume, ifelse(close < ref(close, 1), -volume, 0))
    out["wh6_OBV_OBV_increment"] = signed_volume
    out["wh6_VWMA_VWMA3"] = rolling_sum(close * volume, 50) / rolling_sum(volume, 50)
    out["wh6_Z_SCORE_Z_SCORE"] = (close - ma(close, 20)) / std(close, 20)

    dtm = ifelse(open_ <= ref(open_, 1), 0, np.maximum(high - open_, open_ - ref(open_, 1)))
    dbm = ifelse(open_ >= ref(open_, 1), 0, np.maximum(open_ - low, ref(open_, 1) - open_))
    stm = rolling_sum(dtm, 23)
    sbm = rolling_sum(dbm, 23)
    adtm = ifelse(stm > sbm, (stm - sbm) / stm, ifelse(stm == sbm, 0, (stm - sbm) / sbm))
    out["wh6_ADTM_ADTM"] = adtm
    out["wh6_ADTM_ADTMMA"] = ma(adtm, 8)
    return out


def compare_series(actual, expected, skip: int, abs_tol: float, rel_tol: float) -> dict[str, Any]:
    pd, np = require_pandas()
    a = pd.to_numeric(actual, errors="coerce").iloc[skip:]
    b = pd.Series(expected).iloc[skip:]
    mask = np.isfinite(a.to_numpy()) & np.isfinite(b.to_numpy())
    if not mask.any():
        return {"n": 0, "bad": 0, "max_abs": None, "p99_abs": None}
    diff = (a[mask] - b[mask]).abs()
    rel = diff / np.maximum(1.0, np.abs(a[mask].to_numpy()))
    bad = ((diff > abs_tol) & (rel > rel_tol)).sum()
    return {
        "n": int(mask.sum()),
        "bad": int(bad),
        "max_abs": float(diff.max()),
        "p99_abs": float(np.nanpercentile(diff, 99)),
        "max_rel": float(rel.max()),
        "p99_rel": float(np.nanpercentile(rel, 99)),
    }


def numeric_anchor_failures(csv_path: Path, abs_tol: float, rel_tol: float) -> list[str]:
    pd, _ = require_pandas()
    df = pd.read_csv(csv_path)
    required = {"open", "high", "low", "close", "volume"}
    missing = sorted(required - set(df.columns))
    if missing:
        return [f"numeric_anchor_missing_base_columns: {csv_path}: {missing}"]
    anchors = compute_anchors(df)
    skip = min(500, max(0, len(df) // 4))
    failures: list[str] = []
    for col, expected in anchors.items():
        if col == "wh6_OBV_OBV_increment":
            if "wh6_OBV_OBV" not in df.columns:
                continue
            actual_increment = pd.to_numeric(df["wh6_OBV_OBV"], errors="coerce").diff()
            result = compare_series(actual_increment, expected, skip + 1, abs_tol, rel_tol)
            label = col
        else:
            if col not in df.columns:
                continue
            result = compare_series(df[col], expected, skip, abs_tol, rel_tol)
            label = col
        if result["bad"]:
            failures.append(
                f"numeric_anchor_mismatch: {csv_path}: {label}: bad={result['bad']} "
                f"n={result['n']} max_abs={result['max_abs']} p99_abs={result['p99_abs']}"
            )
    return failures


def cmd_check_csv(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    locked = contract_columns(contract)
    locked_set = set(locked)
    base = contract["base_columns"]
    files = iter_csv_files(args.csv)
    if args.limit:
        files = files[: args.limit]
    if not files:
        print("failures: 1")
        print(f"no_csv_files: {args.csv}")
        return 1

    failures: list[str] = []
    for csv_path in files:
        header = read_header(csv_path)
        if header[: len(base)] != base:
            failures.append(f"base_column_order_mismatch: {csv_path}")
        current_wh6 = wh6_columns(header)
        missing = sorted(locked_set - set(current_wh6))
        extra = sorted(set(current_wh6) - locked_set)
        if missing:
            failures.append(f"missing_locked_wh6_columns: {csv_path}: {missing[:10]} count={len(missing)}")
        if extra:
            failures.append(f"extra_wh6_columns: {csv_path}: {extra[:10]} count={len(extra)}")
        ordered = [col for col in header if col in locked_set]
        if ordered != locked:
            failures.append(f"locked_wh6_order_mismatch: {csv_path}")
        if args.numeric_anchors:
            failures.extend(numeric_anchor_failures(csv_path, args.abs_tol, args.rel_tol))

    print(f"checked_csv_files: {len(files)}")
    if failures:
        print(f"failures: {len(failures)}")
        for item in failures[: args.show]:
            print(item)
        return 1
    print("status: PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT, help="锁定合同 JSON 路径")
    parser.add_argument("--show", type=int, default=30, help="失败项最多显示数量")
    sub = parser.add_subparsers(dest="command", required=True)

    summary = sub.add_parser("summary", help="显示内置合同摘要")
    summary.set_defaults(func=cmd_summary)

    check_xtrd = sub.add_parser("check-xtrd", help="核实 .XTRD 公式文件是否与 locked 合同 hash 吻合")
    check_xtrd.add_argument("--xtrd-root", type=Path, required=True, help="WH6 公式根目录")
    check_xtrd.set_defaults(func=cmd_check_xtrd)

    check_csv = sub.add_parser("check-csv", help="核实 CSV 是否包含 locked 198 个 WH6 列")
    check_csv.add_argument("--csv", type=Path, required=True, help="CSV 文件或 CSV 文件夹")
    check_csv.add_argument("--limit", type=int, default=0, help="当输入为文件夹时，限制检查的 CSV 文件数量")
    check_csv.add_argument("--numeric-anchors", action="store_true", help="运行已实现公式族的数值锚点检查")
    check_csv.add_argument("--abs-tol", type=float, default=1e-4, help="数值锚点绝对误差容差")
    check_csv.add_argument("--rel-tol", type=float, default=1e-6, help="数值锚点相对误差容差")
    check_csv.set_defaults(func=cmd_check_csv)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
