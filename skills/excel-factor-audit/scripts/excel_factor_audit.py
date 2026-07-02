#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    print(
        json.dumps(
            {
                "status": "ERROR",
                "message": f"缺少运行依赖：{exc.name}。请在有 pandas/numpy 的 Python 环境中运行。",
            },
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )
    raise SystemExit(2)


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


SKILL_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = SKILL_ROOT / "references" / "excel-locked-66-contract.json"
EXCLUDED_FILENAMES = {
    "all_symbols_all_periods_summary.csv",
    "liquidity_screen.csv",
}


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    if len(contract["columns"]) != int(contract["column_count"]):
        raise ValueError("合同 column_count 与 columns 长度不一致。")
    return contract


def expected_excel_columns(contract: dict[str, Any]) -> list[str]:
    return list(contract["columns"])


def read_csv_header(path: Path) -> list[str]:
    try:
        return pd.read_csv(path, nrows=0).columns.tolist()
    except UnicodeDecodeError:
        return pd.read_csv(path, nrows=0, encoding="gb18030").columns.tolist()


def read_columns(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_header(path)
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq

            return pq.ParquetFile(path).schema.names
        except Exception:
            return pd.read_parquet(path).columns.tolist()
    raise ValueError(f"不支持的文件格式：{path}")


def read_frame(path: Path, usecols: list[str]) -> pd.DataFrame:
    suffix = path.suffix.lower()
    wanted = set(usecols)
    if suffix == ".csv":
        try:
            return pd.read_csv(path, usecols=lambda column: column in wanted)
        except UnicodeDecodeError:
            return pd.read_csv(
                path,
                usecols=lambda column: column in wanted,
                encoding="gb18030",
            )
    if suffix == ".parquet":
        return pd.read_parquet(path, columns=usecols)
    raise ValueError(f"不支持的文件格式：{path}")


def is_candidate_data_file(path: Path) -> bool:
    name = path.name
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".parquet"}:
        return False
    if name in EXCLUDED_FILENAMES:
        return False
    if name.endswith("_indicator_audit.csv") or name.endswith("_null_summary.csv"):
        return False
    return True


def discover_files(path: Path, limit: int | None) -> list[Path]:
    if path.is_file():
        return [path] if is_candidate_data_file(path) else []
    if not path.is_dir():
        raise FileNotFoundError(path)
    files = [
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and is_candidate_data_file(candidate)
    ]
    files.sort(key=lambda item: str(item).lower())
    if limit is not None:
        files = files[:limit]
    return files


def schema_check(columns: list[str], contract: dict[str, Any]) -> dict[str, Any]:
    prefix = contract["column_prefix"]
    expected = expected_excel_columns(contract)
    observed = [column for column in columns if column.startswith(prefix)]
    missing = [column for column in expected if column not in observed]
    extra = [column for column in observed if column not in expected]
    order_matches = observed == expected
    status = "PASS" if not missing and not extra and order_matches else "FAIL"
    return {
        "status": status,
        "expected_count": len(expected),
        "observed_count": len(observed),
        "missing": missing,
        "extra": extra,
        "order_matches": order_matches,
    }


def numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def clean_series(series: pd.Series) -> pd.Series:
    return pd.Series(series).replace([np.inf, -np.inf], np.nan)


def ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema_plain(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def ema_masked(series: pd.Series, span: int) -> pd.Series:
    result = series.ewm(span=span, adjust=False).mean().copy()
    valid = np.flatnonzero(pd.notna(series).to_numpy())
    if len(valid):
        result.iloc[: valid[0] + span - 1] = np.nan
    return result


def smooth_sma(series: pd.Series, window: int, weight: int = 1) -> pd.Series:
    arr = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    prev = np.nan
    for idx, value in enumerate(arr):
        if np.isnan(value):
            out[idx] = prev
            continue
        prev = value if np.isnan(prev) else (weight * value + (window - weight) * prev) / window
        out[idx] = prev
    return pd.Series(out, index=series.index)


def wma(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1, dtype=float)
    return series.rolling(window).apply(
        lambda values: float(np.dot(values, weights) / weights.sum()),
        raw=True,
    )


def rolling_sum(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).sum()


def highest(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).max()


def lowest(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).min()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    values = np.vstack(
        [
            (high - low).to_numpy(dtype=float),
            (high - close.shift(1)).abs().to_numpy(dtype=float),
            (low - close.shift(1)).abs().to_numpy(dtype=float),
        ]
    )
    return pd.Series(np.nanmax(values, axis=0), index=close.index)


def compute_expected(df: pd.DataFrame, ema_mode: str) -> dict[str, pd.Series]:
    ema = ema_masked if ema_mode == "masked" else ema_plain

    open_ = numeric(df, "open").astype(float)
    high = numeric(df, "high").astype(float)
    low = numeric(df, "low").astype(float)
    close = numeric(df, "close").astype(float)
    volume = numeric(df, "volume").astype(float)

    expected: dict[str, pd.Series] = {}

    ema20 = ema(close, 20)
    expected["excel_ER_bull_power_20"] = high - ema20
    expected["excel_ER_bear_power_20"] = low - ema20

    close_ma40 = ma(close, 40)
    dev = close - close_ma40
    dev_pos = dev.where(dev > 0, 0.0)
    dev_neg = (-dev).where(dev < 0, 0.0)
    sum_pos = rolling_sum(dev_pos, 21)
    sum_neg = rolling_sum(dev_neg, 21)
    tii = 100 * sum_pos / (sum_pos + sum_neg)
    expected["excel_TII_40_21"] = tii
    expected["excel_TII_signal_9"] = ema(tii, 9)

    ema9 = ema(close, 9)
    ema26 = ema(close, 26)
    expected["excel_PO_9_26"] = (ema9 - ema26) / ema26 * 100

    expected["excel_MADisplaced_20_10"] = ma(close, 20).shift(10)

    price_100 = (close - close.shift(100)) / close.shift(100)
    expected["excel_POS_100"] = (price_100 - lowest(price_100, 100)) / (
        highest(price_100, 100) - lowest(price_100, 100)
    )

    expected["excel_PAC_upper_20"] = smooth_sma(high, 20, 1)
    expected["excel_PAC_lower_20"] = smooth_sma(low, 20, 1)

    dema20 = 2 * ema(close, 20) - ema(ema(close, 20), 20)
    dema100 = 2 * ema(close, 100) - ema(ema(close, 100), 100)
    expected["excel_ZLMACD_20_100"] = dema20 - dema100

    expected["excel_TMA_20"] = ma(ma(close, 20), 20)

    typ = (close + high + low) / 3.0
    expected["excel_TYP"] = typ
    expected["excel_TYPMA1_10"] = ema(typ, 10)
    expected["excel_TYPMA2_30"] = ema(typ, 30)

    expected["excel_VMA_20"] = ma((high + low + open_ + close) / 4.0, 20)
    expected["excel_WMA_20"] = wma(close, 20)
    expected["excel_HMA_high_20"] = ma(high, 20)

    emap13 = ema(close, 13)
    expected["excel_SROC_13_21"] = (emap13 - emap13.shift(21)) / emap13.shift(21)

    expected["excel_EXPMA_12"] = ema(close, 12)
    expected["excel_EXPMA_50"] = ema(close, 50)

    dc_upper = highest(high, 20)
    dc_lower = lowest(low, 20)
    expected["excel_DC_upper_20"] = dc_upper
    expected["excel_DC_lower_20"] = dc_lower
    expected["excel_DC_middle_20"] = (dc_upper + dc_lower) / 2.0

    vi = (close - close.shift(10)).abs() / rolling_sum(
        (close - close.shift(1)).abs(),
        10,
    )
    expected["excel_VIDYA_10"] = vi * close + (1 - vi) * close.shift(1)
    expected["excel_Qstick_20"] = ma(close - open_, 20)

    tr = true_range(high, low, close)
    atr20 = ma(tr, 20)
    middle20 = ma(close, 20)
    for multiplier, label in [(1.618, "1_618"), (2.618, "2_618"), (4.236, "4_236")]:
        expected[f"excel_FB_upper_{label}"] = middle20 + multiplier * atr20
        expected[f"excel_FB_lower_{label}"] = middle20 - multiplier * atr20

    expected["excel_DEMA_60"] = 2 * ema(close, 60) - ema(ema(close, 60), 60)

    apz_vol = ema(ema(high - low, 10), 10)
    apz_base = ema(ema(close, 20), 20)
    expected["excel_APZ_upper_10_20"] = apz_base + 2 * apz_vol
    expected["excel_APZ_lower_10_20"] = apz_base - 2 * apz_vol

    atr14 = ma(true_range(high, low, close), 14)
    kc_middle = ema(close, 20)
    expected["excel_KC_upper_14_20"] = kc_middle + 2 * atr14
    expected["excel_KC_lower_14_20"] = kc_middle - 2 * atr14

    expected["excel_BOP_20"] = ma((close - open_) / (high - low), 20)

    env_mid = ma(close, 25)
    expected["excel_ENV_upper_25_5pct"] = env_mid * 1.05
    expected["excel_ENV_lower_25_5pct"] = env_mid * 0.95

    diff = close - close.shift(1)
    up = diff.where(diff > 0, 0.0)
    up[pd.isna(diff)] = np.nan
    rsi = smooth_sma(up, 40, 1) / smooth_sma(diff.abs(), 40, 1) * 100
    expected["excel_RSIH_40_120"] = rsi - ema(rsi, 120)

    expected["excel_HLMA_high_20"] = ma(high, 20)
    expected["excel_HLMA_low_20"] = ma(low, 20)

    triple_ema = ema(ema(ema(close, 20), 20), 20)
    expected["excel_TRIX_20"] = (triple_ema - triple_ema.shift(1)) / triple_ema.shift(1)

    wc = (high + low + 2 * close) / 4.0
    expected["excel_WC_ema20"] = ema(wc, 20)
    expected["excel_WC_ema40"] = ema(wc, 40)

    demax = (high - high.shift(1)).where((high - high.shift(1)) > 0, 0.0)
    demin = (low.shift(1) - low).where((low.shift(1) - low) > 0, 0.0)
    expected["excel_Demarker_20"] = ma(demax, 20) / (ma(demax, 20) + ma(demin, 20))

    momentum = close - close.shift(1)
    expected["excel_TSI_25_13"] = (
        ema(ema(momentum, 25), 13) / ema(ema(momentum.abs(), 25), 13) * 100
    )

    inc = (close - open_).where(close > open_, 0.0)
    dec = (open_ - close).where(open_ > close, 0.0)
    expected["excel_IMI_14"] = rolling_sum(inc, 14) / (
        rolling_sum(inc, 14) + rolling_sum(dec, 14)
    )

    su = rolling_sum(pd.Series(np.maximum(diff, 0.0), index=df.index), 20)
    sd = rolling_sum(pd.Series(np.maximum(-diff, 0.0), index=df.index), 20)
    expected["excel_CMO_20"] = (su - sd) / (su + sd) * 100

    osc = close - ma(close, 40)
    expected["excel_OSC_40"] = osc
    expected["excel_OSCMA_20"] = ma(osc, 20)

    clv = (2 * close - low - high) / (high - low)
    expected["excel_CLV"] = clv
    expected["excel_CLVMA_60"] = ma(clv, 60)

    for window in (20, 40):
        ema1 = ema(close, window)
        ema2 = ema(ema1, window)
        ema3 = ema(ema2, window)
        expected[f"excel_TEMA_{window}"] = 3 * ema1 - 3 * ema2 + ema3

    expected["excel_PVO_12_26"] = (ema(volume, 12) - ema(volume, 26)) / ema(volume, 26)

    for window in (6, 12, 24):
        expected[f"excel_BIASVOL_{window}"] = (volume - ma(volume, window)) / ma(
            volume,
            window,
        )

    macdvol = ema(volume, 20) - ema(volume, 40)
    expected["excel_MACDVOL_20_40"] = macdvol
    expected["excel_MACDVOL_signal_10"] = ma(macdvol, 10)
    expected["excel_ROCVOL_80"] = clean_series((volume - volume.shift(80)) / volume.shift(80))
    expected["excel_VWAP_20"] = rolling_sum(volume * typ, 20) / rolling_sum(volume, 20)
    expected["excel_FI_13"] = ema((close - close.shift(1)) * volume, 13)
    expected["excel_MAAMT_40"] = ma(close * volume, 40)
    emap_volume20 = ema(volume, 20)
    expected["excel_SROCVOL_20_10"] = (
        emap_volume20 - emap_volume20.shift(10)
    ) / emap_volume20.shift(10)

    return {key: clean_series(value) for key, value in expected.items()}


def compare_series(
    actual: pd.Series,
    expected: pd.Series,
    skip: int,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    actual_values = clean_series(pd.to_numeric(actual, errors="coerce")).to_numpy(dtype=float)[skip:]
    expected_values = clean_series(pd.to_numeric(expected, errors="coerce")).to_numpy(dtype=float)[skip:]
    close_mask = np.isclose(
        actual_values,
        expected_values,
        rtol=rel_tol,
        atol=abs_tol,
        equal_nan=True,
    )
    bad_mask = ~close_mask
    finite_mask = np.isfinite(actual_values) & np.isfinite(expected_values)
    finite_count = int(finite_mask.sum())
    bad_count = int(bad_mask.sum())
    max_abs_diff = None
    if finite_count:
        max_abs_diff = float(
            np.nanmax(np.abs(actual_values[finite_mask] - expected_values[finite_mask]))
        )
    first_bad_index = None
    if bad_count:
        first_bad_index = int(np.flatnonzero(bad_mask)[0] + skip)
    return {
        "status": "PASS" if bad_count == 0 else "FAIL",
        "rows_compared": int(len(actual_values)),
        "finite_pairs": finite_count,
        "bad_count": bad_count,
        "max_abs_diff": max_abs_diff,
        "first_bad_index": first_bad_index,
    }


def choose_comparison(
    actual: pd.Series,
    plain_expected: pd.Series,
    masked_expected: pd.Series,
    strategy: str,
    skip: int,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    plain = compare_series(
        actual,
        plain_expected,
        skip=skip,
        abs_tol=abs_tol,
        rel_tol=rel_tol,
    )
    masked = compare_series(
        actual,
        masked_expected,
        skip=0,
        abs_tol=abs_tol,
        rel_tol=rel_tol,
    )

    if strategy == "plain-warmup":
        plain["strategy"] = "plain-warmup"
        return plain
    if strategy == "masked-full":
        masked["strategy"] = "masked-full"
        return masked

    if plain["status"] == "PASS":
        plain["strategy"] = "plain-warmup"
        return plain
    if masked["status"] == "PASS":
        masked["strategy"] = "masked-full"
        return masked

    chosen = plain if plain["bad_count"] <= masked["bad_count"] else masked
    chosen = dict(chosen)
    chosen["strategy"] = "plain-warmup" if chosen is plain else "masked-full"
    chosen["plain_warmup"] = plain
    chosen["masked_full"] = masked
    return chosen


def value_required_columns(contract: dict[str, Any]) -> list[str]:
    return list(contract["required_base_columns"]) + expected_excel_columns(contract)


def value_check(
    df: pd.DataFrame,
    contract: dict[str, Any],
    strategy: str,
    warmup: int,
    tail_rows: int,
    abs_tol: float,
    rel_tol: float,
    include_columns: bool,
) -> dict[str, Any]:
    columns = expected_excel_columns(contract)
    plain_expected = compute_expected(df, ema_mode="plain")
    masked_expected = compute_expected(df, ema_mode="masked")
    skip = min(max(0, warmup), max(0, len(df) - max(1, tail_rows)))

    results = []
    for column in columns:
        comparison = choose_comparison(
            df[column],
            plain_expected[column],
            masked_expected[column],
            strategy=strategy,
            skip=skip,
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        )
        comparison["column"] = column
        results.append(comparison)

    failed = [item for item in results if item["status"] != "PASS"]
    payload: dict[str, Any] = {
        "status": "PASS" if not failed else "FAIL",
        "checked_columns": len(results),
        "warmup_skip": skip,
        "failed_columns": [
            {
                "column": item["column"],
                "strategy": item["strategy"],
                "bad_count": item["bad_count"],
                "max_abs_diff": item["max_abs_diff"],
                "first_bad_index": item["first_bad_index"],
            }
            for item in failed
        ],
    }
    if include_columns:
        payload["columns"] = results
    return payload


def check_file(
    path: Path,
    contract: dict[str, Any],
    mode: str,
    strategy: str,
    warmup: int,
    tail_rows: int,
    abs_tol: float,
    rel_tol: float,
    include_columns: bool,
) -> dict[str, Any]:
    columns = read_columns(path)
    schema = schema_check(columns, contract)
    result: dict[str, Any] = {
        "path": str(path),
        "format": path.suffix.lower().lstrip("."),
        "schema": schema,
    }

    if mode == "schema":
        result["status"] = schema["status"]
        return result

    required = value_required_columns(contract)
    missing_inputs = [column for column in required if column not in columns]
    if missing_inputs:
        result["status"] = "FAIL" if schema["status"] == "FAIL" else "SKIP_VALUES"
        result["value_check"] = {
            "status": "SKIP_VALUES",
            "missing_inputs": missing_inputs,
        }
        return result

    df = read_frame(path, required)
    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    result["row_count"] = int(len(df))
    values = value_check(
        df,
        contract,
        strategy=strategy,
        warmup=warmup,
        tail_rows=tail_rows,
        abs_tol=abs_tol,
        rel_tol=rel_tol,
        include_columns=include_columns,
    )
    result["value_check"] = values
    result["status"] = (
        "PASS"
        if schema["status"] == "PASS" and values["status"] == "PASS"
        else "FAIL"
    )
    return result


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    pass_count = sum(1 for item in results if item["status"] == "PASS")
    skip_count = sum(1 for item in results if item["status"] == "SKIP_VALUES")
    fail_count = sum(1 for item in results if item["status"] == "FAIL")
    if fail_count:
        status = "FAIL"
    elif skip_count:
        status = "SKIP_VALUES"
    else:
        status = "PASS"
    return {
        "status": status,
        "files_total": total,
        "files_passed": pass_count,
        "files_skipped_values": skip_count,
        "files_failed": fail_count,
    }


def command_summary(_args: argparse.Namespace) -> int:
    contract = load_contract()
    emit(
        {
            "status": "PASS",
            "contract_name": contract["contract_name"],
            "version": contract["version"],
            "column_prefix": contract["column_prefix"],
            "column_count": contract["column_count"],
            "source_workbook_name": contract["source_workbook_name"],
            "source_sheet": contract["source_sheet"],
            "required_base_columns": contract["required_base_columns"],
            "columns": expected_excel_columns(contract),
        }
    )
    return 0


def command_check_data(args: argparse.Namespace) -> int:
    contract = load_contract()
    target = Path(args.data).expanduser()
    files = discover_files(target, limit=args.limit)
    if not files:
        emit(
            {
                "status": "ERROR",
                "message": "未找到可审计的 CSV/Parquet 数据文件。",
                "data": str(target),
            }
        )
        return 2

    results = [
        check_file(
            path,
            contract=contract,
            mode=args.mode,
            strategy=args.strategy,
            warmup=args.warmup,
            tail_rows=args.tail_rows,
            abs_tol=args.abs_tol,
            rel_tol=args.rel_tol,
            include_columns=args.include_columns,
        )
        for path in files
    ]
    summary = summarize_results(results)
    emit(
        {
            **summary,
            "contract_name": contract["contract_name"],
            "contract_version": contract["version"],
            "mode": args.mode,
            "strategy": args.strategy,
            "data": str(target),
            "results": results,
        }
    )
    return 0 if summary["status"] in {"PASS", "SKIP_VALUES"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读核验 locked 66 个 excel_ 因子合同。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="输出 locked 66 合同摘要。")
    summary.set_defaults(func=command_summary)

    check = subparsers.add_parser("check-data", help="核验 CSV/Parquet 数据。")
    check.add_argument("--data", required=True, help="CSV/Parquet 文件或目录。")
    check.add_argument(
        "--mode",
        choices=["schema", "values"],
        default="values",
        help="schema 只核验列；values 同时核验列和值。",
    )
    check.add_argument(
        "--strategy",
        choices=["auto", "plain-warmup", "masked-full"],
        default="auto",
        help="数值比较策略。auto 会同时兼容 hidden warmup 和短历史起点初始化。",
    )
    check.add_argument("--limit", type=int, default=None, help="目录模式下最多检查文件数。")
    check.add_argument("--warmup", type=int, default=2000, help="plain-warmup 比较跳过行数。")
    check.add_argument("--tail-rows", type=int, default=100, help="至少保留比较的尾部行数。")
    check.add_argument("--abs-tol", type=float, default=1e-6, help="数值比较绝对容差。")
    check.add_argument("--rel-tol", type=float, default=1e-9, help="数值比较相对容差。")
    check.add_argument(
        "--include-columns",
        action="store_true",
        help="输出每个 excel_ 列的逐列比较明细。",
    )
    check.set_defaults(func=command_check_data)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
