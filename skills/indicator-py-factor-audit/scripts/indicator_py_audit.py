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
CONTRACT_PATH = SKILL_ROOT / "references" / "indicator-py-locked-59-contract.json"
EXCLUDED_FILENAMES = {
    "all_symbols_all_periods_summary.csv",
    "liquidity_screen.csv",
}


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        contract = json.load(handle)
    expected_count = int(contract["column_count"])
    actual_count = len(contract["columns"])
    if actual_count != expected_count:
        raise ValueError(
            f"合同列数不一致：column_count={expected_count}, columns={actual_count}"
        )
    return contract


def expected_indicator_columns(contract: dict[str, Any]) -> list[str]:
    return [item["name"] for item in contract["columns"]]


def unique_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


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
    if name.endswith("_indicator_audit.csv"):
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
    expected = expected_indicator_columns(contract)
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


def value_required_columns(contract: dict[str, Any]) -> list[str]:
    expected = expected_indicator_columns(contract)
    dependencies: list[str] = []
    for item in contract["columns"]:
        dependencies.extend(item.get("dependencies", []))
    return unique_preserve_order(dependencies + expected)


def numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def safe_zscore(series: pd.Series, window: int, ddof: int = 1) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std(ddof=ddof)
    result = (series - mean) / std
    return result.mask(std.abs() < 1e-10, 0.0)


def compute_expected(df: pd.DataFrame) -> dict[str, pd.Series]:
    close = numeric(df, "close")
    high = numeric(df, "high")
    low = numeric(df, "low")
    volume = numeric(df, "volume")
    open_interest = numeric(df, "open_interest")

    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma40 = close.rolling(40).mean()
    ma60 = close.rolling(60).mean()
    ma120 = close.rolling(120).mean()

    ret_1 = close.pct_change()
    vol5 = ret_1.rolling(5).std()
    vol10 = ret_1.rolling(10).std()
    vol20 = ret_1.rolling(20).std()

    prev_high_20 = high.rolling(20).max().shift(1)
    prev_low_20 = low.rolling(20).min().shift(1)
    high_20 = high.rolling(20).max()
    low_20 = low.rolling(20).min()
    high_60 = high.rolling(60).max()
    low_60 = low.rolling(60).min()

    tr = pd.Series(
        np.maximum.reduce(
            [
                (high - low).to_numpy(dtype=float),
                (high - close.shift(1)).abs().to_numpy(dtype=float),
                (low - close.shift(1)).abs().to_numpy(dtype=float),
            ]
        ),
        index=df.index,
    )

    wh6_macd = numeric(df, "wh6_MACD_MACD")
    wh6_rsi2 = numeric(df, "wh6_RSI_RSI2")
    wh6_atr = numeric(df, "wh6_ATR_ATR")
    wh6_zscore = numeric(df, "wh6_Z_SCORE_Z_SCORE")
    wh6_bbw = numeric(df, "wh6_u_8b96f436_BBW")

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    return {
        "indicator_py_ret_1": close.pct_change(1),
        "indicator_py_ret_3": close.pct_change(3),
        "indicator_py_ret_5": close.pct_change(5),
        "indicator_py_ret_10": close.pct_change(10),
        "indicator_py_ret_20": close.pct_change(20),
        "indicator_py_momentum_5": close - close.shift(5),
        "indicator_py_momentum_10": close - close.shift(10),
        "indicator_py_momentum_20": close - close.shift(20),
        "indicator_py_ma5_slope": ma5.pct_change(),
        "indicator_py_close_to_ma5": (close - ma5) / ma5,
        "indicator_py_ma10_slope": ma10.pct_change(),
        "indicator_py_close_to_ma10": (close - ma10) / ma10,
        "indicator_py_ma20_slope": ma20.pct_change(),
        "indicator_py_close_to_ma20": (close - ma20) / ma20,
        "indicator_py_ma40_slope": ma40.pct_change(),
        "indicator_py_close_to_ma40": (close - ma40) / ma40,
        "indicator_py_ma60_slope": ma60.pct_change(),
        "indicator_py_close_to_ma60": (close - ma60) / ma60,
        "indicator_py_ma120_slope": ma120.pct_change(),
        "indicator_py_close_to_ma120": (close - ma120) / ma120,
        "indicator_py_ma5_ma10_gap": (ma5 - ma10) / ma10,
        "indicator_py_ma5_ma20_gap": (ma5 - ma20) / ma20,
        "indicator_py_ma10_ma20_gap": (ma10 - ma20) / ma20,
        "indicator_py_ma20_ma40_gap": (ma20 - ma40) / ma40,
        "indicator_py_ma20_ma60_gap": (ma20 - ma60) / ma60,
        "indicator_py_ma40_ma120_gap": (ma40 - ma120) / ma120,
        "indicator_py_macd_hist_diff": (wh6_macd / 2.0).diff(),
        "indicator_py_ppo": (ema12 - ema26) / ema26,
        "indicator_py_rsi_diff": wh6_rsi2.diff(),
        "indicator_py_rsi_zscore_20": safe_zscore(wh6_rsi2, 20, ddof=0),
        "indicator_py_hl_pct": (high - low) / close,
        "indicator_py_tr_ratio": tr / close,
        "indicator_py_atr_norm": wh6_atr / close,
        "indicator_py_volatility_5": vol5,
        "indicator_py_volatility_10": vol10,
        "indicator_py_volatility_20": vol20,
        "indicator_py_vol_ratio_5_20": vol5 / vol20,
        "indicator_py_break_high_20": (close > prev_high_20).astype("int64"),
        "indicator_py_break_low_20": (close < prev_low_20).astype("int64"),
        "indicator_py_dist_prev_high_20": (close - prev_high_20) / prev_high_20,
        "indicator_py_dist_prev_low_20": (close - prev_low_20) / prev_low_20,
        "indicator_py_pos_in_range_20": (close - low_20) / (high_20 - low_20),
        "indicator_py_pos_in_range_60": (close - low_60) / (high_60 - low_60),
        "indicator_py_close_pos": (close - low) / (high - low),
        "indicator_py_boll_pct_b": 0.5 + wh6_zscore / 4.0,
        "indicator_py_boll_width": wh6_bbw,
        "indicator_py_zscore_close_20": wh6_zscore,
        "indicator_py_zscore_volume_20": safe_zscore(volume, 20, ddof=0),
        "indicator_py_close_rank_60": close.rolling(60).rank(pct=True),
        "indicator_py_volume_rank_60": volume.rolling(60).rank(pct=True),
        "indicator_py_vol_ratio_5": volume / volume.rolling(5).mean(),
        "indicator_py_vol_ratio_20": volume / volume.rolling(20).mean(),
        "indicator_py_volume_diff": volume.diff(),
        "indicator_py_oi_diff": open_interest.diff(),
        "indicator_py_oi_ratio_5": open_interest / open_interest.rolling(5).mean(),
        "indicator_py_price_up_vol_up": (
            (close > close.shift(1)) & (volume > volume.shift(1))
        ).astype("int64"),
        "indicator_py_price_down_vol_up": (
            (close < close.shift(1)) & (volume > volume.shift(1))
        ).astype("int64"),
        "indicator_py_price_up_oi_up": (
            (close > close.shift(1)) & (open_interest > open_interest.shift(1))
        ).astype("int64"),
        "indicator_py_price_down_oi_up": (
            (close < close.shift(1)) & (open_interest > open_interest.shift(1))
        ).astype("int64"),
    }


def compare_series(
    actual: pd.Series,
    expected: pd.Series,
    warmup: int,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    total = len(actual)
    skip = min(max(0, warmup), max(0, total // 4))
    actual_values = pd.to_numeric(actual, errors="coerce").to_numpy(dtype=float)[skip:]
    expected_values = pd.to_numeric(expected, errors="coerce").to_numpy(dtype=float)[skip:]

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
    compared_count = int(len(actual_values))
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
        "rows_total": total,
        "rows_compared": compared_count,
        "finite_pairs": finite_count,
        "bad_count": bad_count,
        "max_abs_diff": max_abs_diff,
        "first_bad_index": first_bad_index,
    }


def value_check(
    df: pd.DataFrame,
    contract: dict[str, Any],
    warmup: int,
    abs_tol: float,
    rel_tol: float,
    include_columns: bool,
) -> dict[str, Any]:
    expected_map = compute_expected(df)
    results = []
    for column in expected_indicator_columns(contract):
        comparison = compare_series(
            df[column],
            expected_map[column],
            warmup=warmup,
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        )
        comparison["column"] = column
        results.append(comparison)

    failed = [item for item in results if item["status"] != "PASS"]
    payload: dict[str, Any] = {
        "status": "PASS" if not failed else "FAIL",
        "checked_columns": len(results),
        "failed_columns": [
            {
                "column": item["column"],
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
    warmup: int,
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
    result["row_count"] = int(len(df))
    values = value_check(
        df,
        contract,
        warmup=warmup,
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
            "required_base_columns": contract["required_base_columns"],
            "required_wh6_columns": contract["required_wh6_columns"],
            "columns": expected_indicator_columns(contract),
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
            warmup=args.warmup,
            abs_tol=args.abs_tol,
            rel_tol=args.rel_tol,
            include_columns=args.include_columns,
        )
        for path in files
    ]
    summary = summarize_results(results)
    payload = {
        **summary,
        "contract_name": contract["contract_name"],
        "contract_version": contract["version"],
        "mode": args.mode,
        "data": str(target),
        "results": results,
    }
    emit(payload)
    return 0 if summary["status"] in {"PASS", "SKIP_VALUES"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读核验 locked 59 个 indicator_py_ 因子合同。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="输出 locked 59 合同摘要。")
    summary.set_defaults(func=command_summary)

    check = subparsers.add_parser("check-data", help="核验 CSV/Parquet 数据。")
    check.add_argument("--data", required=True, help="CSV/Parquet 文件或目录。")
    check.add_argument(
        "--mode",
        choices=["schema", "values"],
        default="values",
        help="schema 只核验列；values 同时核验列和值。",
    )
    check.add_argument("--limit", type=int, default=None, help="目录模式下最多检查文件数。")
    check.add_argument("--warmup", type=int, default=500, help="数值比较跳过的前置行数。")
    check.add_argument("--abs-tol", type=float, default=1e-3, help="数值比较绝对容差。")
    check.add_argument("--rel-tol", type=float, default=1e-9, help="数值比较相对容差。")
    check.add_argument(
        "--include-columns",
        action="store_true",
        help="输出每个 indicator_py_ 列的逐列比较明细。",
    )
    check.set_defaults(func=command_check_data)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
