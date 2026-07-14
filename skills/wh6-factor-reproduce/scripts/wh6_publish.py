#!/usr/bin/env python3
"""Dry-run by default; safely publish one sealed WH6 feature generation.

Execution requires three simultaneous, exact authorizations: ``--execute``,
``--confirm-run-id``, and ``--confirm-ready-sha256``.  There is deliberately no
force option.  An old live generation is moved to a unique same-volume
quarantine and is never deleted by this program.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import wh6_common as common
import wh6_validate as validator


SHA256_RE = re.compile(r"[0-9a-f]{64}")
SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9._-]+")


class PublishFailure(RuntimeError):
    """A publish gate or rollback operation failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublishFailure(message)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_sealed_run(
    qdh_root: Path | str, run_root: Path | str
) -> tuple[Path, Path, Path, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    qdh, run, control, manifest = validator._validate_run_identity(qdh_root, run_root)
    ready_path = control / "READY"
    _require(ready_path.is_file(), "run is not sealed: READY is missing")
    ready = validator._strict_json(ready_path)
    _require(ready.get("schema_version") == validator.SCHEMA_VERSION, "unsupported READY schema")
    _require(ready.get("status") == "READY" and ready.get("full_scope") is True, "run is not full-scope READY")
    _require(ready.get("run_id") == manifest["run_id"], "READY/run identity mismatch")
    _require(tuple(ready.get("columns", ())) == validator.OUTPUT_COLUMNS, "READY column contract mismatch")
    _require(ready.get("run_manifest_sha256") == common.sha256_file(control / "run_manifest.json"), "run manifest changed after READY")
    _require(ready.get("build_complete_sha256") == common.sha256_file(control / "BUILD_COMPLETE"), "BUILD_COMPLETE changed after READY")
    _require(ready.get("validation_full_sha256") == common.sha256_file(control / "validation_full.json"), "full report changed after READY")
    _require(
        ready.get("validation_tool_sha256s") == validator._validation_tool_hashes(),
        "validation/publish tools changed after READY",
    )
    files_path = control / "files_manifest.jsonl"
    _require(ready.get("files_manifest_sha256") == common.sha256_file(files_path), "validated file manifest changed after READY")
    validator._verify_build_complete(control, manifest)
    validator._verify_bundle_hashes(manifest)
    records, totals = validator._verify_files_manifest(run / "stage" / "features", files_path)
    _require(totals == ready.get("stage"), "READY stage totals differ from sealed files")
    return qdh, run, control, manifest, ready, records


def _release_manifest(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, str]:
    rows = [
        {
            "relative_path": row["relative_path"],
            "bytes": int(row["bytes"]),
            "rows": int(row["rows"]),
            "feature_sha256": row["file_sha256"],
            "market_sha256": row["market_file_sha256"],
        }
        for row in records
    ]
    rows.sort(key=lambda row: row["relative_path"])
    _require(len({row["relative_path"] for row in rows}) == len(rows), "duplicate release path")
    text = _jsonl_text(rows)
    return rows, text, _sha256_text(text)


def _qdh_market_identity(qdh: Path) -> dict[str, str]:
    path = qdh / "meta" / "market_snapshot.json"
    _require(path.is_file(), "qdh market snapshot is missing")
    value = validator._strict_json(path)
    snapshot_id = value.get("snapshot_id")
    _require(isinstance(snapshot_id, str) and snapshot_id, "invalid qdh market snapshot id")
    semantic = value.get("semantic_sha256")
    if semantic is None:
        # qdh market snapshot schema v1 predates a top-level local semantic
        # field.  Its already-COMMITTED feature snapshot carries the canonical
        # compatibility identity that catalog/clients use; preserve it while
        # the market snapshot id and every market file remain unchanged.
        current_features = validator._strict_json(qdh / "meta" / "features_snapshot.json")
        alignment = current_features.get("market_alignment", {})
        _require(
            alignment.get("market_snapshot_id") == snapshot_id,
            "current feature/market snapshot identity mismatch",
        )
        semantic = alignment.get("market_semantic_sha256")
    _require(
        isinstance(semantic, str) and SHA256_RE.fullmatch(semantic) is not None,
        "invalid canonical qdh market semantic SHA256",
    )
    return {"snapshot_id": snapshot_id, "semantic_sha256": semantic}


def _release_snapshot(
    qdh: Path,
    ready: dict[str, Any],
    rows: list[dict[str, Any]],
    manifest_sha256: str,
) -> dict[str, Any]:
    paths = [row["relative_path"].split("/") for row in rows]
    symbols = sorted({parts[0] for parts in paths})
    sequences = {(parts[0], parts[1]) for parts in paths}
    timeframes = [tf for tf in common.TIMEFRAMES if any(parts[1] == tf for parts in paths)]
    scope = {
        "symbols": len(symbols),
        "timeframes": timeframes,
        "sequences": len(sequences),
        "partitions": len(rows),
        "rows": sum(row["rows"] for row in rows),
    }
    _require(scope == {key: ready["scope"][key] for key in scope}, "READY/release scope mismatch")
    market_identity = _qdh_market_identity(qdh)
    return {
        "schema_version": 2,
        "dataset": "features",
        "status": "COMMITTED",
        "release_id": f"sha256:{manifest_sha256}",
        "committed_at_utc": common.now_utc(),
        "root": "features",
        "scope": scope,
        "schema": {
            "key": "trade_time",
            "column_count": len(validator.OUTPUT_COLUMNS),
            "feature_count": len(validator.FEATURE_COLUMNS),
            "columns": list(validator.OUTPUT_COLUMNS),
            "feature_dtype": "float64",
            "trade_time_rule": "same_arrow_type_as_paired_market_partition",
            "nullable": True,
        },
        "manifest": {
            "path": "meta/features_manifest.jsonl",
            "sha256": manifest_sha256,
            "records": len(rows),
        },
        "market_alignment": {
            "market_snapshot_id": market_identity["snapshot_id"],
            "market_semantic_sha256": market_identity["semantic_sha256"],
            "partition_set": "equal",
            "rows": "equal_per_partition",
            "trade_time": "equal_per_partition",
        },
        "quality": {
            "infinite_values": 0,
            "pre_2020_rows": 0,
            "strict_trade_time": True,
        },
    }


def _preflight(
    qdh_root: Path | str,
    run_root: Path | str,
    workers: int,
    ch_url: str | None,
) -> dict[str, Any]:
    qdh, run, control, manifest, ready, records = _load_sealed_run(qdh_root, run_root)
    live = validator.verify_live(qdh, workers)
    _require(live["status"] == "PASS", "current live generation failed verification")
    rows, manifest_text, manifest_sha = _release_manifest(records)
    snapshot = _release_snapshot(qdh, ready, rows, manifest_sha)
    market_now = common.market_snapshot(qdh, workers=workers)
    _require(market_now["semantic_sha256"] == ready["market_semantic_sha256"], "market changed after validation/finalize")
    resolved_ch_url = validator._resolve_ch_url(manifest, ch_url)
    warmup_now = common.warmup_snapshot(
        resolved_ch_url, validator._manifest_sequences(manifest)
    )
    _require(
        warmup_now["semantic_sha256"] == ready["warmup_semantic_sha256"],
        "ClickHouse warmup changed after validation/finalize",
    )
    _require((qdh / "features").is_dir(), "live features directory is missing")
    _require((run / "stage" / "features").is_dir(), "staged features directory is missing")
    _require(qdh.anchor.lower() == run.anchor.lower(), "stage/live are not on the same volume")
    return {
        "qdh": qdh,
        "run": run,
        "control": control,
        "manifest": manifest,
        "ready": ready,
        "ready_sha256": common.sha256_file(control / "READY"),
        "records": records,
        "release_rows": rows,
        "release_manifest_text": manifest_text,
        "release_manifest_sha256": manifest_sha,
        "release_snapshot": snapshot,
        "old_live": live,
        "ch_url": resolved_ch_url,
    }


def _public_plan(state: dict[str, Any], quarantine_parent: Path) -> dict[str, Any]:
    return {
        "mode": "DRY_RUN",
        "status": "PASS",
        "run_id": state["manifest"]["run_id"],
        "ready_sha256": state["ready_sha256"],
        "old_release_id": state["old_live"]["release_id"],
        "new_release_id": state["release_snapshot"]["release_id"],
        "scope": state["release_snapshot"]["scope"],
        "same_volume": True,
        "publish_lock": str(state["qdh"].parent / f".{state['qdh'].name}.features-publish.lock"),
        "quarantine_parent": str(quarantine_parent),
        "steps": [
            "acquire exclusive publish lock",
            "repeat every READY/stage/live/market gate",
            "move live features to a unique quarantine",
            "move old data-only snapshot and manifest to that quarantine",
            "move stage features to live",
            "write the new data-only manifest",
            "write the COMMITTED data-only snapshot last",
            "verify every live partition; rollback on any exception",
        ],
        "mutated": False,
    }


def _overlaps(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _quarantine_parent(qdh: Path, run: Path, value: str | None) -> Path:
    parent = Path(value).resolve(strict=False) if value else qdh.parent / f"{qdh.name}-feature-generations"
    _require(parent.is_absolute(), "quarantine root must be absolute")
    _require(parent.anchor.lower() == qdh.anchor.lower(), "quarantine must be on the qdh volume")
    _require(not _overlaps(parent, qdh), "quarantine root must not overlap qdh")
    _require(not _overlaps(parent, run), "quarantine root must not overlap the run root")
    _require(
        not _overlaps(parent, common.SKILL_ROOT),
        "quarantine root must not overlap the read-only skill directory",
    )
    _require(parent != qdh and parent != qdh.parent, "unsafe quarantine root")
    return parent


@contextmanager
def _exclusive_lock(path: Path, run_id: str) -> Iterator[None]:
    payload = json.dumps(
        {"run_id": run_id, "pid": os.getpid(), "created_at_utc": common.now_utc()},
        ensure_ascii=False,
        sort_keys=True,
    ) + "\n"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise PublishFailure(f"publish lock already exists: {path}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            if path.is_file() and path.read_text(encoding="utf-8") == payload:
                path.unlink()
        except OSError:
            pass


def _unique_quarantine(parent: Path, run_id: str) -> Path:
    _require(SAFE_COMPONENT_RE.fullmatch(run_id) is not None, "run_id is unsafe as a path component")
    parent.mkdir(parents=True, exist_ok=True)
    stamp = common.now_utc().replace(":", "").replace("+", "_").replace("-", "")
    target = parent / f"{stamp}--replaced-by--{run_id}"
    target.mkdir(parents=False, exist_ok=False)
    (target / "meta").mkdir()
    return target


def _move_no_replace(source: Path, destination: Path) -> None:
    _require(source.exists(), f"move source missing: {source}")
    _require(not destination.exists(), f"move destination already exists: {destination}")
    source.rename(destination)


def _execute(
    initial: dict[str, Any],
    qdh_root: str,
    run_root: str,
    workers: int,
    quarantine_parent: Path,
    confirm_run_id: str | None,
    confirm_ready_sha256: str | None,
    ch_url: str | None,
) -> dict[str, Any]:
    _require(confirm_run_id == initial["manifest"]["run_id"], "--confirm-run-id is missing or does not match")
    _require(
        isinstance(confirm_ready_sha256, str)
        and SHA256_RE.fullmatch(confirm_ready_sha256)
        and confirm_ready_sha256 == initial["ready_sha256"],
        "--confirm-ready-sha256 is missing or does not match",
    )
    qdh = initial["qdh"]
    lock_path = qdh.parent / f".{qdh.name}.features-publish.lock"
    with _exclusive_lock(lock_path, confirm_run_id):
        # Eliminate the authorization/preflight TOCTOU window while locked.
        state = _preflight(qdh_root, run_root, workers, ch_url)
        _require(state["manifest"]["run_id"] == confirm_run_id, "run changed while acquiring lock")
        _require(state["ready_sha256"] == confirm_ready_sha256, "READY changed while acquiring lock")
        qdh = state["qdh"]
        run = state["run"]
        control = state["control"]
        stage = run / "stage" / "features"
        live = qdh / "features"
        meta = qdh / "meta"
        live_manifest = meta / "features_manifest.jsonl"
        live_snapshot = meta / "features_snapshot.json"
        _require(live_manifest.is_file() and live_snapshot.is_file(), "old live metadata is incomplete")
        quarantine = _unique_quarantine(quarantine_parent, confirm_run_id)
        old_live = quarantine / "features"
        old_manifest = quarantine / "meta" / "features_manifest.jsonl"
        old_snapshot = quarantine / "meta" / "features_snapshot.json"
        failed_meta = quarantine / "failed_new_meta"
        moved_old_live = False
        moved_old_manifest = False
        moved_old_snapshot = False
        moved_stage = False
        wrote_new_manifest = False
        wrote_new_snapshot = False
        try:
            _move_no_replace(live, old_live)
            moved_old_live = True
            _move_no_replace(live_snapshot, old_snapshot)
            moved_old_snapshot = True
            _move_no_replace(live_manifest, old_manifest)
            moved_old_manifest = True
            _move_no_replace(stage, live)
            moved_stage = True
            common.atomic_write_text(live_manifest, state["release_manifest_text"])
            wrote_new_manifest = True
            _require(common.sha256_file(live_manifest) == state["release_manifest_sha256"], "new manifest write mismatch")
            # This is intentionally the final write inside qdh.
            common.atomic_write_json(live_snapshot, state["release_snapshot"])
            wrote_new_snapshot = True
            live_report = validator.verify_live(qdh, workers)
            _require(live_report["status"] == "PASS", "post-publish live verification failed")
            committed = {
                "schema_version": 1,
                "status": "COMMITTED",
                "run_id": confirm_run_id,
                "committed_at_utc": common.now_utc(),
                "ready_sha256": confirm_ready_sha256,
                "release_id": state["release_snapshot"]["release_id"],
                "snapshot_sha256": common.sha256_file(live_snapshot),
                "manifest_sha256": common.sha256_file(live_manifest),
                "quarantine": str(quarantine),
                "old_release_id": state["old_live"]["release_id"],
                "scope": state["release_snapshot"]["scope"],
                "publish_tool_sha256": common.sha256_file(Path(__file__).resolve()),
            }
            common.atomic_write_json(control / "COMMITTED", committed)
            return {**committed, "live_verification": live_report}
        except Exception as exc:
            rollback_errors: list[str] = []
            partials = (
                live_snapshot.with_name(live_snapshot.name + ".partial"),
                live_manifest.with_name(live_manifest.name + ".partial"),
            )

            def attempt(label: str, action: Any) -> None:
                try:
                    action()
                except Exception as rollback_exc:
                    rollback_errors.append(f"{label}: {rollback_exc}")

            for partial in partials:
                if partial.exists():
                    attempt(
                        f"quarantine partial {partial.name}",
                        lambda partial=partial: (
                            failed_meta.mkdir(exist_ok=True),
                            _move_no_replace(partial, failed_meta / partial.name),
                        ),
                    )
            if wrote_new_snapshot and live_snapshot.exists():
                attempt(
                    "quarantine new snapshot",
                    lambda: (
                        failed_meta.mkdir(exist_ok=True),
                        _move_no_replace(live_snapshot, failed_meta / "features_snapshot.json"),
                    ),
                )
            if wrote_new_manifest and live_manifest.exists():
                attempt(
                    "quarantine new manifest",
                    lambda: (
                        failed_meta.mkdir(exist_ok=True),
                        _move_no_replace(live_manifest, failed_meta / "features_manifest.jsonl"),
                    ),
                )
            if moved_stage and live.exists():
                attempt(
                    "return new generation to staging",
                    lambda: (
                        stage.parent.mkdir(parents=True, exist_ok=True),
                        _move_no_replace(live, stage),
                    ),
                )
            if moved_old_live and old_live.exists():
                attempt("restore old live generation", lambda: _move_no_replace(old_live, live))
            if moved_old_manifest and old_manifest.exists():
                attempt("restore old manifest", lambda: _move_no_replace(old_manifest, live_manifest))
            if moved_old_snapshot and old_snapshot.exists():
                attempt("restore old snapshot", lambda: _move_no_replace(old_snapshot, live_snapshot))
            try:
                restored = validator.verify_live(qdh, workers)
                if restored["status"] != "PASS":
                    rollback_errors.append("restored live generation did not verify")
            except Exception as verify_exc:
                rollback_errors.append(f"restored live verification failed: {verify_exc}")
            message = f"publish failed and rollback was attempted: {exc}"
            if rollback_errors:
                message += f"; ROLLBACK ERRORS: {rollback_errors}"
            raise PublishFailure(message) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdh-root", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--ch-url")
    parser.add_argument("--quarantine-root")
    parser.add_argument("--execute", action="store_true", help="perform the cutover; absent means read-only dry-run")
    parser.add_argument("--confirm-run-id")
    parser.add_argument("--confirm-ready-sha256")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        common.require_exact_runtime()
        state = _preflight(args.qdh_root, args.run_root, args.workers, args.ch_url)
        quarantine = _quarantine_parent(state["qdh"], state["run"], args.quarantine_root)
        plan = _public_plan(state, quarantine)
        if not args.execute:
            _require(args.confirm_run_id is None and args.confirm_ready_sha256 is None, "confirmation flags are accepted only with --execute")
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0
        result = _execute(
            state,
            args.qdh_root,
            args.run_root,
            args.workers,
            quarantine,
            args.confirm_run_id,
            args.confirm_ready_sha256,
            args.ch_url,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
