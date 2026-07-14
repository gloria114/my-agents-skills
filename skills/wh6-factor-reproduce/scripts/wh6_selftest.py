#!/usr/bin/env python3
"""Static and deterministic self-test for the locked WH6 reproduce skill."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import wh6_common as common


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ACCEPTANCE = ROOT / "assets" / "acceptance"

EXPECTED_HASHES = {
    "wh6_candidate.py": "849c460a50864e05744211abe3e269b2e7e957312ee92ed2c432fbef4f89514e",
    "wh6_primitives.py": "9313b87f57138b9775ad502f8970d91bd81439e02f8056242561d2a822e39061",
    "wh6_formulas_v2.py": "e71c1d3be8c43c0c5e1ec0ac9fc204b471d07e527292b37571c08bc489439d8a",
}
FULL_REPORT = ACCEPTANCE / "full-558-v2.json"
FULL_REPORT_SHA256 = "02f091791c8d8568fdc6012f77cc5ed227634912c711be4d7e72899528d9ba93"
REPORTS = (
    FULL_REPORT,
    ACCEPTANCE / "synthetic_v2_report.json",
    ACCEPTANCE / "single_im5m_v2_report.json",
    ACCEPTANCE / "single_rb1day_v2_report.json",
    ACCEPTANCE / "single_sa1day_v2_report.json",
)
PAIR_ZERO_FIELDS = (
    "null_mask_mismatches",
    "bitwise_mismatches",
    "numeric_mismatches",
    "signed_zero_mismatches",
    "differing_column_count",
    "max_abs_diff",
    "max_rel_diff",
)
EXPECTED_FIELD_CONTRACT = {
    "OPEN/O": "open",
    "HIGH/H": "high",
    "LOW/L": "low",
    "CLOSE/C/SETTLE": "close",
    "VOL/CJLVOL": "volume",
    "CCL": "open_interest",
}
FORMULA_NAME_RE = re.compile(r"formula_(\d{3})_")
FORBIDDEN_CORE_MODULES = {
    "json",
    "pathlib",
    "requests",
    "importlib",
    "qdh",
    "wh6_formula_engine",
}
FORBIDDEN_CTX_DISPATCH = {"binary", "resolve", "unary"}


class SelfTestError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SelfTestError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SelfTestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing acceptance report: {path.name}")
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle, object_pairs_hook=reject_duplicate_keys)
    require(isinstance(value, dict), f"report is not a JSON object: {path.name}")
    return value


def verify_hashes() -> dict[str, str]:
    actual: dict[str, str] = {}
    for name, expected in EXPECTED_HASHES.items():
        path = SCRIPTS / name
        require(path.is_file(), f"missing runtime source: {name}")
        digest = sha256_file(path)
        require(digest == expected, f"runtime source hash mismatch: {name}: {digest}")
        actual[name] = digest
    report_hash = sha256_file(FULL_REPORT)
    require(report_hash == FULL_REPORT_SHA256, f"full report hash mismatch: {report_hash}")
    actual[FULL_REPORT.name] = report_hash
    return actual


def verify_reports() -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for path in REPORTS:
        report = load_json(path)
        result = report.get("result")
        require(isinstance(result, dict) and result.get("status") == "PASS", f"report not PASS: {path.name}")
        pairs = result.get("pairs")
        require(isinstance(pairs, dict) and pairs, f"report has no comparison pairs: {path.name}")
        for label, pair in pairs.items():
            require(isinstance(pair, dict) and pair.get("status") == "PASS", f"pair not PASS: {path.name}:{label}")
            for field in PAIR_ZERO_FIELDS:
                require(pair.get(field) == 0, f"nonzero {field}: {path.name}:{label}")
            require(pair.get("structural_failures") == [], f"structural failure: {path.name}:{label}")
        bundle = (((report.get("metadata") or {}).get("candidate") or {}).get("bundle_sha256s"))
        require(bundle == EXPECTED_HASHES, f"candidate bundle identity mismatch: {path.name}")
        summaries[path.name] = {"status": "PASS", "pairs": sorted(pairs)}

    full = load_json(FULL_REPORT)["result"]
    require(full.get("full_scope") is True, "full report is not full scope")
    require(full.get("selected_sequences") == 558, "full report sequence count mismatch")
    require(full.get("selected_partitions") == 3555, "full report partition count mismatch")
    require((full.get("sequences") or {}).get("warmup_rows") == 6_564_151, "full report warmup rows mismatch")
    require((full.get("sequences") or {}).get("live_rows") == 14_680_651, "full report live rows mismatch")
    return summaries


def assignment_node(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                if node.value is None:
                    break
                return node.value
    raise SelfTestError(f"missing top-level assignment: {name}")


def literal_assignment(tree: ast.Module, name: str) -> Any:
    try:
        return ast.literal_eval(assignment_node(tree, name))
    except (TypeError, ValueError) as exc:
        raise SelfTestError(f"assignment is not a static literal: {name}") from exc


def subscript_string(target: ast.AST, base_name: str) -> str | None:
    if not isinstance(target, ast.Subscript):
        return None
    if not isinstance(target.value, ast.Name) or target.value.id != base_name:
        return None
    if isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str):
        return target.slice.value
    return None


def function_outputs(function: ast.FunctionDef) -> tuple[str, ...]:
    outputs: list[str] = []
    returns_outputs = False
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                value = subscript_string(target, "outputs")
                if value is not None:
                    outputs.append(value)
        elif isinstance(node, ast.AnnAssign):
            value = subscript_string(node.target, "outputs")
            if value is not None:
                outputs.append(value)
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id == "outputs":
            returns_outputs = True
    require(returns_outputs, f"formula does not return explicit outputs mapping: {function.name}")
    require(outputs, f"formula has no explicit output: {function.name}")
    require(len(outputs) == len(set(outputs)), f"formula assigns duplicate output: {function.name}")
    require(all(name.startswith("wh6_") for name in outputs), f"non-wh6 output: {function.name}")
    return tuple(outputs)


def verify_forbidden_runtime_ast(path: Path, tree: ast.Module) -> None:
    forbidden_calls = {"eval", "exec", "compile", "open", "__import__"}
    forbidden_attrs = {"open", "read_text", "read_bytes", "write_text", "write_bytes"}

    def forbidden_module(module: str) -> bool:
        return any(
            module == name
            or module.startswith(f"{name}.")
            or module.endswith(f".{name}")
            for name in FORBIDDEN_CORE_MODULES
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(not forbidden_module(alias.name), f"forbidden core module {alias.name} in {path.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            require(not forbidden_module(module), f"forbidden core module {module} in {path.name}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, f"forbidden call {node.func.id} in {path.name}")
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attrs, f"forbidden file I/O {node.func.attr} in {path.name}")


def verify_formula_ast() -> dict[str, Any]:
    formula_path = SCRIPTS / "wh6_formulas_v2.py"
    candidate_path = SCRIPTS / "wh6_candidate.py"
    primitives_path = SCRIPTS / "wh6_primitives.py"
    formula_tree = ast.parse(formula_path.read_text(encoding="utf-8"), filename=str(formula_path))
    candidate_tree = ast.parse(candidate_path.read_text(encoding="utf-8"), filename=str(candidate_path))
    primitives_tree = ast.parse(primitives_path.read_text(encoding="utf-8"), filename=str(primitives_path))
    for path, tree in ((formula_path, formula_tree), (candidate_path, candidate_tree), (primitives_path, primitives_tree)):
        verify_forbidden_runtime_ast(path, tree)

    column_order = tuple(literal_assignment(formula_tree, "COLUMN_ORDER"))
    require(len(column_order) == 198 and len(set(column_order)) == 198, "COLUMN_ORDER is not 198 unique columns")
    require(all(name.startswith("wh6_") for name in column_order), "COLUMN_ORDER contains non-wh6 name")

    functions = {
        node.name: node
        for node in formula_tree.body
        if isinstance(node, ast.FunctionDef) and FORMULA_NAME_RE.match(node.name)
    }
    require(len(functions) == 97, f"formula function count mismatch: {len(functions)}")
    indices = sorted(int(FORMULA_NAME_RE.match(name).group(1)) for name in functions)
    require(indices == list(range(97)), "formula function numbering is not contiguous 000..096")

    groups_node = assignment_node(formula_tree, "FORMULA_GROUPS")
    require(isinstance(groups_node, (ast.Tuple, ast.List)), "FORMULA_GROUPS is not a static sequence")
    group_names = tuple(element.id if isinstance(element, ast.Name) else "" for element in groups_node.elts)
    require(len(group_names) == 97 and set(group_names) == set(functions), "FORMULA_GROUPS identity mismatch")

    metadata = tuple(literal_assignment(formula_tree, "FORMULA_GROUP_METADATA"))
    require(len(metadata) == 97, "FORMULA_GROUP_METADATA count mismatch")
    require(tuple(row[0] for row in metadata) == group_names, "FORMULA_GROUP_METADATA order mismatch")

    explicit: list[str] = []
    for group_name, row in zip(group_names, metadata, strict=True):
        outputs = function_outputs(functions[group_name])
        require(set(outputs) == set(row[2]), f"metadata/output mismatch: {group_name}")
        explicit.extend(outputs)
    require(len(explicit) == 198, f"explicit output assignment count mismatch: {len(explicit)}")
    require(len(set(explicit)) == 198, "explicit outputs are not unique")
    require(set(explicit) == set(column_order), "explicit outputs differ from COLUMN_ORDER")

    native_binops = sum(isinstance(node, ast.BinOp) for node in ast.walk(formula_tree))
    native_compares = sum(isinstance(node, ast.Compare) for node in ast.walk(formula_tree))
    require(native_binops > 0, "formula source contains no native ast.BinOp")
    require(native_compares > 0, "formula source contains no native ast.Compare")
    ctx_dispatch = {name: 0 for name in sorted(FORBIDDEN_CTX_DISPATCH)}
    for tree in (formula_tree, candidate_tree, primitives_tree):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "ctx"
                and node.func.attr in FORBIDDEN_CTX_DISPATCH
            ):
                ctx_dispatch[node.func.attr] += 1
    require(not any(ctx_dispatch.values()), f"forbidden ctx dispatch calls: {ctx_dispatch}")
    return {
        "formula_functions": 97,
        "explicit_outputs": 198,
        "column_order": 198,
        "native_binops": native_binops,
        "native_compares": native_compares,
        "ctx_dispatch_calls": ctx_dispatch,
        "forbidden_core_modules": sorted(FORBIDDEN_CORE_MODULES),
    }


def synthetic_frame(rows: int = 800) -> pd.DataFrame:
    x = np.arange(rows, dtype=np.float64)
    close = 100.0 + 0.02 * x + np.sin(x / 9.0)
    open_ = close + np.where((x.astype(np.int64) % 2) == 0, -0.15, 0.12)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 0.8,
            "low": np.minimum(open_, close) - 0.9,
            "close": close,
            "volume": 1000.0 + (x % 37.0) * 13.0,
            "open_interest": 5000.0 + x * 2.0,
        },
        dtype="float64",
    )


def verify_runtime() -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPTS))
    try:
        candidate = importlib.import_module("wh6_candidate")
        engine = candidate.load_engine()
    finally:
        if sys.path and sys.path[0] == str(SCRIPTS):
            sys.path.pop(0)
    capability = engine.capability_report()
    require(capability.get("status") == "READY", "candidate capability is not READY")
    require(capability.get("formula_source_format") == "native-python-v2", "formula source format mismatch")
    require(capability.get("runtime_formula_file_reads") is False, "candidate declares runtime formula reads")
    require(capability.get("formula_groups") == 97, "candidate capability formula count mismatch")
    require(capability.get("output_columns") == 198, "candidate capability output count mismatch")
    require(capability.get("field_contract") == EXPECTED_FIELD_CONTRACT, "candidate field contract mismatch")

    frame = synthetic_frame()
    first = engine.compute(frame.copy(deep=True))
    second = engine.compute(frame.copy(deep=True))
    require(tuple(first.columns) == tuple(engine.columns), "runtime column order mismatch")
    require(first.shape == (800, 198), f"runtime output shape mismatch: {first.shape}")
    require(all(dtype == np.dtype("float64") for dtype in first.dtypes), "runtime output dtype mismatch")
    a = first.to_numpy(dtype=np.float64, copy=True)
    b = second.to_numpy(dtype=np.float64, copy=True)
    null_a = np.isnan(a)
    null_b = np.isnan(b)
    require(np.array_equal(null_a, null_b), "deterministic rerun null-mask mismatch")
    require(
        np.array_equal(
            np.ascontiguousarray(a[~null_a]).view(np.uint64),
            np.ascontiguousarray(b[~null_b]).view(np.uint64),
        ),
        "deterministic rerun bitwise mismatch",
    )
    require(not np.isinf(a).any(), "runtime output contains infinity")

    direct = {
        "wh6_OPEN_OPEN": frame["open"],
        "wh6_BAR_BAR": frame["open"],
        "wh6_HIGH_HIGH": frame["high"],
        "wh6_LOW_LOW": frame["low"],
        "wh6_CLOSE_CLOSE": frame["close"],
        "wh6_SP_SP": frame["close"],
        "wh6_CJL_CJL": frame["volume"],
        "wh6_CCL_CCL": frame["open_interest"],
    }
    for output, source in direct.items():
        require(first[output].equals(source.astype("float64")), f"field binding output mismatch: {output}")
    return {
        "capability": {"formula_groups": 97, "output_columns": 198, "runtime_formula_file_reads": False},
        "synthetic_rows": 800,
        "deterministic_bitwise": True,
        "infinite_values": 0,
    }


def main() -> int:
    try:
        result = {
            "status": "PASS",
            "runtime_identity": common.require_exact_runtime(),
            "hashes": verify_hashes(),
            "reports": verify_reports(),
            "ast": verify_formula_ast(),
            "runtime": verify_runtime(),
        }
    except Exception as exc:
        result = {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
