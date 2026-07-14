"""Shared, fail-closed helpers for the WH6 reproduction pipeline.

This module contains no formula definitions.  The only executable formula
source is the three-file native-Python core beside this file.  All functions
here either inspect immutable inputs or write beneath an explicitly validated
staging run root.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import stat
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
import requests


TIMEFRAMES = ("5m", "10m", "15m", "20m", "30m", "60m", "120m", "240m", "1day")
PERIODS = {
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "20m": 20,
    "30m": 30,
    "60m": 60,
    "120m": 120,
    "240m": 240,
    "1day": 1440,
}
TABLES = {
    timeframe: (
        "default.futures_market_data_1day_tq"
        if timeframe == "1day"
        else f"default.futures_market_data_{timeframe[:-1]}min_tq"
    )
    for timeframe in TIMEFRAMES
}
MARKET_COLUMNS = (
    "symbol",
    "period",
    "trade_time",
    "trade_date",
    "contract_code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
)
ENGINE_INPUT_COLUMNS = ("open", "high", "low", "close", "volume", "open_interest")
WARMUP_COLUMNS = ("trade_time",) + ENGINE_INPUT_COLUMNS
START_DATE = "2020-01-01"
TZ = "Asia/Shanghai"
EXPECTED_SYMBOLS = 62
EXPECTED_SEQUENCES = EXPECTED_SYMBOLS * len(TIMEFRAMES)
CORE_FILES = ("wh6_candidate.py", "wh6_formulas_v2.py", "wh6_primitives.py")
RUNTIME_FILES = ("wh6_common.py", "wh6_reproduce.py")
EXPECTED_RUNTIME = {
    "python": "3.10.20",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "23.0.1",
}
SKILL_ROOT = Path(__file__).resolve().parents[1]

_thread_local = threading.local()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_exact_runtime() -> dict[str, str]:
    observed = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
    }
    if observed != EXPECTED_RUNTIME:
        raise RuntimeError(
            "runtime version mismatch: "
            f"expected={EXPECTED_RUNTIME}, observed={observed}"
        )
    return observed


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path | str) -> str:
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def atomic_write_text(path: Path | str, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def atomic_write_json(path: Path | str, value: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def write_jsonl(path: Path | str, rows: Iterable[dict[str, Any]]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    atomic_write_text(path, text)


def read_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def schema_signature(schema: pa.Schema) -> str:
    fields = [(field.name, str(field.type), field.nullable) for field in schema]
    return canonical_json_sha256(fields)


def normalize_ch_url(ch_url: str) -> str:
    parsed = urlsplit(ch_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("ClickHouse URL must be an absolute http(s) URL")
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def redact_ch_url(ch_url: str) -> str:
    parsed = urlsplit(normalize_ch_url(ch_url))
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    # Never persist URL userinfo or query parameters: ClickHouse deployments
    # commonly carry ``user``/``password`` in the query string.
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def ensure_qdh_run_roots(
    qdh_root: Path | str,
    run_root: Path | str,
    *,
    require_run: bool = False,
) -> tuple[Path, Path]:
    raw_qdh = Path(qdh_root)
    raw_run = Path(run_root)
    if not raw_qdh.is_absolute() or not raw_run.is_absolute():
        raise RuntimeError("qdh root and run root must both be absolute paths")
    _reject_reparse_chain(raw_qdh, "qdh root")
    _reject_reparse_chain(raw_run, "run root")
    qdh = raw_qdh.resolve(strict=True)
    run = raw_run.resolve(strict=False)
    if not (qdh / "market").is_dir():
        raise RuntimeError(f"qdh market not found: {qdh / 'market'}")
    if qdh.anchor.lower() != run.anchor.lower():
        raise RuntimeError("run root and qdh root must be on the same volume")
    if run == qdh:
        raise RuntimeError("run root cannot equal qdh root")
    try:
        run.relative_to(SKILL_ROOT)
    except ValueError:
        pass
    else:
        raise RuntimeError("run root must be outside the read-only skill directory")
    try:
        SKILL_ROOT.relative_to(run)
    except ValueError:
        pass
    else:
        raise RuntimeError("run root cannot be an ancestor of the skill directory")
    try:
        run.relative_to(qdh)
    except ValueError:
        pass
    else:
        raise RuntimeError("run root must be outside qdh")
    try:
        qdh.relative_to(run)
    except ValueError:
        pass
    else:
        raise RuntimeError("run root cannot be an ancestor of qdh")
    if require_run and not run.is_dir():
        raise RuntimeError(f"run root does not exist: {run}")
    if run.exists():
        _reject_reparse_chain(run / "stage" / "features", "stage features")
    return qdh, run


def _reject_reparse_chain(path: Path, label: str) -> None:
    """Reject symlink/reparse traversal before any recursive staging cleanup."""

    current = path
    while True:
        if current.exists():
            attributes = getattr(os.lstat(current), "st_file_attributes", 0)
            if current.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise RuntimeError(f"{label} traverses a symlink/reparse point: {current}")
        parent = current.parent
        if parent == current:
            break
        current = parent


def _timestamp_ns(values: pa.ChunkedArray | pa.Array) -> np.ndarray:
    value_type = values.type
    if not pa.types.is_timestamp(value_type):
        raise RuntimeError(f"trade_time must be timestamp, got {value_type}")
    if value_type.tz != TZ:
        raise RuntimeError(f"trade_time timezone must be {TZ}, got {value_type.tz}")
    raw = np.asarray(pc.cast(values, pa.int64()), dtype=np.int64)
    multiplier = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}[
        value_type.unit
    ]
    return raw * multiplier


def _unique_values(column: pa.ChunkedArray) -> list[Any]:
    return pc.unique(column).to_pylist()


def _validate_market_schema(schema: pa.Schema, relative_path: str) -> None:
    if tuple(schema.names) != MARKET_COLUMNS:
        raise RuntimeError(
            f"{relative_path}: expected 11 ordered market columns, got {schema.names}"
        )
    expected = {
        "period": pa.int64(),
        "trade_date": pa.date32(),
        "open": pa.float64(),
        "high": pa.float64(),
        "low": pa.float64(),
        "close": pa.float64(),
        "volume": pa.int64(),
        "open_interest": pa.int64(),
    }
    for name in ("symbol", "contract_code"):
        if not (pa.types.is_string(schema.field(name).type) or pa.types.is_large_string(schema.field(name).type)):
            raise RuntimeError(f"{relative_path}: {name} must be string")
    timestamp_type = schema.field("trade_time").type
    if not pa.types.is_timestamp(timestamp_type) or timestamp_type.tz != TZ:
        raise RuntimeError(f"{relative_path}: invalid trade_time type {timestamp_type}")
    for name, expected_type in expected.items():
        if schema.field(name).type != expected_type:
            raise RuntimeError(
                f"{relative_path}: {name} type {schema.field(name).type} != {expected_type}"
            )


def _scan_market_partition(qdh: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(qdh / "market").as_posix()
    parts = Path(relative).parts
    if len(parts) != 4 or parts[-1] != "data.parquet":
        raise RuntimeError(f"invalid market partition path: {relative}")
    symbol, timeframe, year_text, _ = parts
    if timeframe not in TIMEFRAMES:
        raise RuntimeError(f"{relative}: unsupported timeframe")
    try:
        year = int(year_text)
    except ValueError as exc:
        raise RuntimeError(f"{relative}: year is not numeric") from exc
    if year < 2020:
        raise RuntimeError(f"{relative}: live market contains pre-2020 output")

    parquet_schema = pq.read_schema(path)
    _validate_market_schema(parquet_schema, relative)
    table = pq.read_table(path, columns=list(MARKET_COLUMNS)).combine_chunks()
    if table.num_rows <= 0:
        raise RuntimeError(f"{relative}: empty partition")
    nulls = sum(column.null_count for column in table.columns)
    if nulls:
        raise RuntimeError(f"{relative}: market contains {nulls} null values")
    if _unique_values(table["symbol"]) != [symbol]:
        raise RuntimeError(f"{relative}: symbol value/path mismatch")
    if _unique_values(table["period"]) != [PERIODS[timeframe]]:
        raise RuntimeError(f"{relative}: period value/path mismatch")
    codes = _unique_values(table["contract_code"])
    expected_code = symbol + "JQ"
    if codes != [expected_code]:
        raise RuntimeError(
            f"{relative}: contract_code must be exactly {expected_code}, got {codes}"
        )
    years = np.asarray(pc.year(table["trade_date"]), dtype=np.int64)
    if not np.all(years == year):
        raise RuntimeError(f"{relative}: trade_date/year partition mismatch")
    times = _timestamp_ns(table["trade_time"])
    if len(times) > 1 and np.any(times[1:] <= times[:-1]):
        raise RuntimeError(f"{relative}: trade_time is not strictly increasing")
    for name in ("open", "high", "low", "close"):
        values = np.asarray(table[name], dtype=np.float64)
        if not np.isfinite(values).all():
            raise RuntimeError(f"{relative}: {name} contains non-finite values")

    min_date = pc.min(table["trade_date"]).as_py().isoformat()
    max_date = pc.max(table["trade_date"]).as_py().isoformat()
    return {
        "relative_path": relative,
        "symbol": symbol,
        "contract_code": expected_code,
        "timeframe": timeframe,
        "period": PERIODS[timeframe],
        "year": year,
        "rows": table.num_rows,
        "bytes": path.stat().st_size,
        "file_sha256": sha256_file(path),
        "schema_sha256": schema_signature(parquet_schema),
        "min_trade_date": min_date,
        "max_trade_date": max_date,
        "min_trade_time_epoch_ns": int(times[0]),
        "max_trade_time_epoch_ns": int(times[-1]),
    }


def market_snapshot(qdh_root: Path | str, workers: int = 4) -> dict[str, Any]:
    """Fully inspect and hash the current qdh market without writing anything."""

    qdh = Path(qdh_root).resolve(strict=True)
    market = qdh / "market"
    if not market.is_dir():
        raise RuntimeError(f"market not found: {market}")
    symbols = sorted(path.name for path in market.iterdir() if path.is_dir())
    if len(symbols) != EXPECTED_SYMBOLS:
        raise RuntimeError(f"expected {EXPECTED_SYMBOLS} symbols, found {len(symbols)}")

    all_files = sorted(path for path in market.rglob("*") if path.is_file())
    parquet_files = [path for path in all_files if path.name == "data.parquet"]
    extras = [path.relative_to(market).as_posix() for path in all_files if path.name != "data.parquet"]
    if extras:
        raise RuntimeError(f"unexpected files below market: {extras[:20]}")
    for symbol in symbols:
        actual_timeframes = sorted(
            path.name for path in (market / symbol).iterdir() if path.is_dir()
        )
        if set(actual_timeframes) != set(TIMEFRAMES):
            raise RuntimeError(
                f"{symbol}: timeframe set mismatch; actual={actual_timeframes}"
            )
        for timeframe in TIMEFRAMES:
            partition_files = sorted((market / symbol / timeframe).glob("*/data.parquet"))
            if not partition_files:
                raise RuntimeError(f"{symbol}/{timeframe}: no partitions")

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 8))) as pool:
        futures = {pool.submit(_scan_market_partition, qdh, path): path for path in parquet_files}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                failures.append(f"{futures[future]}: {exc}")
    if failures:
        raise RuntimeError("market validation failed:\n" + "\n".join(sorted(failures)[:100]))
    rows.sort(
        key=lambda row: (
            row["symbol"],
            TIMEFRAMES.index(row["timeframe"]),
            row["year"],
        )
    )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["symbol"], row["timeframe"]), []).append(row)
    if len(grouped) != EXPECTED_SEQUENCES:
        raise RuntimeError(
            f"expected {EXPECTED_SEQUENCES} symbol/timeframe sequences, found {len(grouped)}"
        )
    sequences: list[dict[str, Any]] = []
    for (symbol, timeframe), partitions in sorted(
        grouped.items(), key=lambda item: (item[0][0], TIMEFRAMES.index(item[0][1]))
    ):
        previous: int | None = None
        for partition in partitions:
            current = partition["min_trade_time_epoch_ns"]
            if previous is not None and current <= previous:
                raise RuntimeError(f"{symbol}/{timeframe}: cross-year trade_time overlap")
            previous = partition["max_trade_time_epoch_ns"]
        sequences.append(
            {
                "symbol": symbol,
                "contract_code": partitions[0]["contract_code"],
                "timeframe": timeframe,
                "period": PERIODS[timeframe],
                "partitions": len(partitions),
                "rows": sum(row["rows"] for row in partitions),
                "min_trade_date": partitions[0]["min_trade_date"],
                "max_trade_date": partitions[-1]["max_trade_date"],
                "min_trade_time_epoch_ns": partitions[0]["min_trade_time_epoch_ns"],
                "max_trade_time_epoch_ns": partitions[-1]["max_trade_time_epoch_ns"],
                "partition_paths": [row["relative_path"] for row in partitions],
            }
        )
    global_min = min(row["min_trade_date"] for row in sequences)
    if not global_min.startswith("2020-"):
        raise RuntimeError(f"market must begin in 2020, found {global_min}")
    cutoffs = {row["max_trade_date"] for row in sequences}
    if len(cutoffs) != 1:
        raise RuntimeError(f"558 sequences do not share one cutoff: {sorted(cutoffs)}")

    stable = {
        "schema_version": 1,
        "root": str(market),
        "symbols": symbols,
        "timeframes": list(TIMEFRAMES),
        "sequences": sequences,
        "partitions": rows,
        "counts": {
            "symbols": len(symbols),
            "timeframes": len(TIMEFRAMES),
            "sequences": len(sequences),
            "partitions": len(rows),
            "rows": sum(row["rows"] for row in rows),
            "bytes": sum(row["bytes"] for row in rows),
        },
        "start_trade_date": global_min,
        "cutoff_trade_date": next(iter(cutoffs)),
    }
    return {
        "created_at": now_utc(),
        **stable,
        "semantic_sha256": canonical_json_sha256(stable),
    }


def _session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def ch_post(
    ch_url: str,
    query: str,
    *,
    arrow: bool = False,
    timeout: int = 600,
) -> str | pa.Table:
    response = _session().post(
        normalize_ch_url(ch_url),
        params={"readonly": "2", "max_threads": "2"},
        data=query.encode("utf-8"),
        timeout=(10, timeout),
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"ClickHouse HTTP {response.status_code}: {response.text[:2000]}"
        )
    if arrow:
        return ipc.open_stream(io.BytesIO(response.content)).read_all()
    return response.text


def ch_json_rows(ch_url: str, query: str) -> list[dict[str, Any]]:
    payload = ch_post(ch_url, query.rstrip().rstrip(";") + "\nFORMAT JSONEachRow")
    assert isinstance(payload, str)
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


def qstr(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def clickhouse_preflight(ch_url: str) -> dict[str, Any]:
    rows = ch_json_rows(
        ch_url,
        "SELECT toInt64(getSetting('readonly')) AS readonly, version() AS version, "
        "currentDatabase() AS current_database",
    )
    if len(rows) != 1 or int(rows[0]["readonly"]) != 2:
        raise RuntimeError(f"ClickHouse readonly=2 was not enforced: {rows}")
    table_names = [TABLES[timeframe].split(".", 1)[1] for timeframe in TIMEFRAMES]
    schemas: dict[str, list[dict[str, Any]]] = {}
    required = {"contract_code", "trade_time", "trade_date", *ENGINE_INPUT_COLUMNS}
    for timeframe, table in TABLES.items():
        columns = ch_json_rows(
            ch_url,
            "SELECT name,type,position FROM system.columns "
            f"WHERE database='default' AND table={qstr(table.split('.', 1)[1])} "
            "ORDER BY position",
        )
        names = {row["name"] for row in columns}
        if not required.issubset(names):
            raise RuntimeError(f"{table}: missing columns {sorted(required - names)}")
        schemas[timeframe] = columns
    mutations = ch_json_rows(
        ch_url,
        "SELECT table,mutation_id,command FROM system.mutations "
        "WHERE database='default' AND is_done=0 AND table IN "
        f"({','.join(qstr(name) for name in table_names)}) ORDER BY table,mutation_id",
    )
    if mutations:
        raise RuntimeError(f"unfinished ClickHouse mutations: {mutations}")
    stable = {
        "readonly": 2,
        "read_mode": "SELECT FINAL",
        "boundary": f"trade_date < {START_DATE}",
        "server": rows[0],
        "table_schemas": schemas,
    }
    return {**stable, "semantic_sha256": canonical_json_sha256(stable)}


def _sequence_triplets(sequences: Sequence[dict[str, Any]]) -> list[tuple[str, str, str]]:
    triplets = {
        (str(row["symbol"]), str(row["contract_code"]), str(row["timeframe"]))
        for row in sequences
    }
    for symbol, code, timeframe in triplets:
        if timeframe not in TIMEFRAMES or code != symbol + "JQ":
            raise RuntimeError(f"invalid sequence identity: {symbol}/{code}/{timeframe}")
    return sorted(triplets, key=lambda value: (TIMEFRAMES.index(value[2]), value[0]))


def warmup_snapshot(ch_url: str, sequences: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Hash all requested pre-2020 CH rows using read-only ``FINAL`` aggregates."""

    connection = clickhouse_preflight(ch_url)
    triplets = _sequence_triplets(sequences)
    by_timeframe: dict[str, list[tuple[str, str, str]]] = {}
    for item in triplets:
        by_timeframe.setdefault(item[2], []).append(item)
    aggregate_rows: list[dict[str, Any]] = []
    for timeframe in TIMEFRAMES:
        items = by_timeframe.get(timeframe, [])
        if not items:
            continue
        expected = {code: symbol for symbol, code, _ in items}
        code_list = ",".join(qstr(code) for code in sorted(expected))
        query_rows = ch_json_rows(
            ch_url,
            f"""
            SELECT
                contract_code,
                count() AS rows,
                toString(min(trade_time)) AS min_trade_time,
                toString(max(trade_time)) AS max_trade_time,
                sum(cityHash64(contract_code,trade_time,open,high,low,close,volume,open_interest)) AS hash_sum,
                groupBitXor(cityHash64(contract_code,trade_time,open,high,low,close,volume,open_interest)) AS hash_xor
            FROM {TABLES[timeframe]} FINAL
            WHERE trade_date < {qstr(START_DATE)} AND contract_code IN ({code_list})
            GROUP BY contract_code
            ORDER BY contract_code
            """,
        )
        found: set[str] = set()
        for row in query_rows:
            code = str(row["contract_code"])
            if code not in expected:
                raise RuntimeError(f"unexpected CH warmup contract: {code}")
            found.add(code)
            aggregate_rows.append(
                {
                    "symbol": expected[code],
                    "contract_code": code,
                    "timeframe": timeframe,
                    "rows": int(row["rows"]),
                    "min_trade_time": row["min_trade_time"],
                    "max_trade_time": row["max_trade_time"],
                    "hash_sum": str(row["hash_sum"]),
                    "hash_xor": str(row["hash_xor"]),
                }
            )
        for code in sorted(set(expected) - found):
            aggregate_rows.append(
                {
                    "symbol": expected[code],
                    "contract_code": code,
                    "timeframe": timeframe,
                    "rows": 0,
                    "min_trade_time": None,
                    "max_trade_time": None,
                    "hash_sum": "0",
                    "hash_xor": "0",
                }
            )
    aggregate_rows.sort(
        key=lambda row: (row["symbol"], TIMEFRAMES.index(row["timeframe"]))
    )
    stable = {
        "schema_version": 1,
        "read_mode": "SELECT FINAL",
        "readonly": 2,
        "boundary": f"trade_date < {START_DATE}",
        "connection_semantic_sha256": connection["semantic_sha256"],
        "sequences": aggregate_rows,
        "counts": {
            "sequences": len(aggregate_rows),
            "rows": sum(row["rows"] for row in aggregate_rows),
            "with_rows": sum(row["rows"] > 0 for row in aggregate_rows),
            "cold_start": sum(row["rows"] == 0 for row in aggregate_rows),
        },
    }
    return {
        "created_at": now_utc(),
        "connection": connection,
        **stable,
        "semantic_sha256": canonical_json_sha256(stable),
    }


def arrow_table_sha256(table: pa.Table) -> str:
    table = table.combine_chunks()
    output = io.BytesIO()
    with ipc.new_stream(output, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(output.getvalue()).hexdigest()


def load_warmup_sequence(
    ch_url: str,
    contract_code: str,
    timeframe: str,
) -> pa.Table:
    if timeframe not in TIMEFRAMES:
        raise RuntimeError(f"unsupported timeframe {timeframe}")
    query = f"""
        SELECT {','.join(WARMUP_COLUMNS)}
        FROM {TABLES[timeframe]} FINAL
        WHERE contract_code={qstr(contract_code)}
          AND trade_date < {qstr(START_DATE)}
        ORDER BY trade_time
        FORMAT ArrowStream
    """
    result = ch_post(ch_url, query, arrow=True)
    assert isinstance(result, pa.Table)
    result = result.combine_chunks()
    if tuple(result.column_names) != WARMUP_COLUMNS:
        raise RuntimeError(
            f"{contract_code}/{timeframe}: unexpected warmup columns {result.column_names}"
        )
    if sum(column.null_count for column in result.columns):
        raise RuntimeError(f"{contract_code}/{timeframe}: warmup contains nulls")
    if result.num_rows:
        # ClickHouse may expose DateTime without an explicit timezone.  Ordering
        # is checked on the native integer representation and the values are not
        # written to output.
        raw_time = np.asarray(pc.cast(result["trade_time"], pa.int64()), dtype=np.int64)
        if len(raw_time) > 1 and np.any(raw_time[1:] <= raw_time[:-1]):
            raise RuntimeError(f"{contract_code}/{timeframe}: warmup time is not strict")
        for name in ("open", "high", "low", "close"):
            if not np.isfinite(np.asarray(result[name], dtype=np.float64)).all():
                raise RuntimeError(f"{contract_code}/{timeframe}: warmup {name} non-finite")
    return result


def load_market_sequence(
    qdh_root: Path | str,
    symbol: str,
    timeframe: str,
) -> dict[str, Any]:
    qdh = Path(qdh_root).resolve(strict=True)
    files = sorted(
        (qdh / "market" / symbol / timeframe).glob("*/data.parquet"),
        key=lambda path: int(path.parent.name),
    )
    if not files:
        raise RuntimeError(f"missing market sequence {symbol}/{timeframe}")
    tables: list[pa.Table] = []
    partitions: list[dict[str, Any]] = []
    offset = 0
    for path in files:
        table = pq.read_table(path, columns=list(MARKET_COLUMNS)).combine_chunks()
        _validate_market_schema(table.schema, path.as_posix())
        tables.append(table)
        partitions.append(
            {
                "path": path,
                "relative_path": path.relative_to(qdh / "market").as_posix(),
                "year": int(path.parent.name),
                "rows": table.num_rows,
                "offset": offset,
                "market_file_sha256": sha256_file(path),
            }
        )
        offset += table.num_rows
    combined = pa.concat_tables(tables)
    times = _timestamp_ns(combined["trade_time"])
    if len(times) > 1 and np.any(times[1:] <= times[:-1]):
        raise RuntimeError(f"{symbol}/{timeframe}: market time is not strict")
    return {"table": combined, "tables": tables, "partitions": partitions}


def select_sequences(
    snapshot: dict[str, Any],
    symbols: Sequence[str] | None = None,
    timeframes: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    available_symbols = set(snapshot["symbols"])
    chosen_symbols = set(symbols or snapshot["symbols"])
    chosen_timeframes = set(timeframes or TIMEFRAMES)
    unknown_symbols = sorted(chosen_symbols - available_symbols)
    unknown_timeframes = sorted(chosen_timeframes - set(TIMEFRAMES))
    if unknown_symbols or unknown_timeframes:
        raise RuntimeError(
            f"invalid filters: symbols={unknown_symbols}, timeframes={unknown_timeframes}"
        )
    if not chosen_symbols or not chosen_timeframes:
        raise RuntimeError("filters cannot select an empty scope")
    rows = [
        row
        for row in snapshot["sequences"]
        if row["symbol"] in chosen_symbols and row["timeframe"] in chosen_timeframes
    ]
    rows.sort(key=lambda row: (row["symbol"], TIMEFRAMES.index(row["timeframe"])))
    expected = len(chosen_symbols) * len(chosen_timeframes)
    if len(rows) != expected:
        raise RuntimeError(f"selected sequence scope is incomplete: {len(rows)} != {expected}")
    return rows


def bundle_hashes(script_dir: Path | str) -> dict[str, Any]:
    root = Path(script_dir).resolve(strict=True)
    core = {name: sha256_file(root / name) for name in CORE_FILES}
    runtime = {name: sha256_file(root / name) for name in RUNTIME_FILES}
    return {
        "core": core,
        "core_semantic_sha256": canonical_json_sha256(core),
        "runtime": runtime,
        "runtime_semantic_sha256": canonical_json_sha256(runtime),
    }
