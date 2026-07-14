"""Confirmation-gated, features-only publisher for a sealed READY run.

The transaction never edits qdh metadata.  It renames the old live tree into
same-volume quarantine and renames the sealed candidate into place.  A journal
makes the two-rename transaction crash recoverable; consumers that bypass a
shared maintenance fence can still observe the brief rename window.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import msvcrt
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from skill_paths import activate_import_paths, source_hashes

activate_import_paths()
import wh6_common as common  # noqa: E402
from feature_build import require, require_market_profile  # noqa: E402
from feature_runtime import COLUMN_ORDER_SHA256, OUTPUT_COLUMNS, selftest as runtime_selftest  # noqa: E402


def tree_inventory(root: Path) -> list[dict[str, Any]]:
    require(root.is_dir(), f"tree missing: {root}")
    common._reject_reparse_chain(root, "feature tree")
    all_files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    extras = [path.relative_to(root).as_posix() for path in all_files if path.name != "data.parquet"]
    require(not extras, f"unexpected feature files: {extras[:20]}")
    rows = [{"relative_path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": common.sha256_file(path)} for path in all_files]
    require(bool(rows), f"empty feature tree: {root}")
    return rows


def candidate_inventory(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "relative_path": row["relative_path"],
            "bytes": row["bytes"],
            "sha256": row["feature_sha256"],
        }
        for row in files
    ]
    rows.sort(key=lambda row: row["relative_path"])
    return rows


def inventory_matches(root: Path, expected: list[dict[str, Any]]) -> bool:
    try:
        return tree_inventory(root) == expected
    except (RuntimeError, OSError):
        return False


def transaction_paths(run: Path) -> tuple[Path, Path]:
    """Derive transaction destinations; journal paths are never authoritative."""

    quarantine = run / "quarantine" / f"before-{run.name}" / "features"
    failed = run / "quarantine" / f"failed-{run.name}" / "features"
    for label, path in (("quarantine", quarantine), ("failed candidate", failed)):
        common._reject_reparse_chain(path, label)
        path.resolve(strict=False).relative_to(run.resolve(strict=True))
    return quarantine, failed


def checked_journal(run: Path) -> tuple[Path, dict[str, Any], Path, Path]:
    journal_path = run / "control" / "publish_journal.json"
    require(journal_path.is_file(), "publish journal missing")
    journal = common.read_json(journal_path)
    quarantine, failed = transaction_paths(run)
    require(journal.get("run_id") == run.name, "journal run id mismatch")
    require(journal.get("quarantine_features") == str(quarantine), "journal quarantine path mismatch")
    require(journal.get("failed_candidate") == str(failed), "journal failed-candidate path mismatch")
    return journal_path, journal, quarantine, failed


def _fixture_tree(root: Path, payload: bytes) -> None:
    path = root / "a" / "1day" / "2020" / "data.parquet"
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)


def transaction_selftest() -> dict[str, Any]:
    """Exercise recovery and forced rollback without touching a qdh workspace."""

    with tempfile.TemporaryDirectory(prefix="qdh-features-publisher-") as raw:
        base = Path(raw)
        # WindowsPath ordering case-folds names.  Inventory identity must use
        # the exact, case-sensitive relative path because symbol casing is
        # part of the qdh contract and READY uses the same canonical order.
        mixed = base / "case-mixed-symbols"
        _fixture_tree(mixed, b"lower")
        upper = mixed / "AP" / "1day" / "2020" / "data.parquet"
        upper.parent.mkdir(parents=True)
        upper.write_bytes(b"upper")
        actual = tree_inventory(mixed)
        files = [
            {
                "relative_path": row["relative_path"],
                "bytes": row["bytes"],
                "feature_sha256": row["sha256"],
            }
            for row in reversed(actual)
        ]
        expected = candidate_inventory(files)
        require(
            [row["relative_path"] for row in actual]
            == ["AP/1day/2020/data.parquet", "a/1day/2020/data.parquet"],
            "mixed-case inventory order is not canonical",
        )
        require(expected == actual and inventory_matches(mixed, expected), "mixed-case inventory identity failed")

        # Crash before the first rename: leave live and stage untouched.
        qdh = base / "case-prepared" / "qdh"; run = base / "case-prepared" / "run"
        _fixture_tree(qdh / "features", b"old"); _fixture_tree(run / "stage" / "features", b"new")
        (run / "control").mkdir(parents=True)
        old = tree_inventory(qdh / "features"); candidate = tree_inventory(run / "stage" / "features")
        quarantine, failed = transaction_paths(run)
        journal = {"status": "IN_PROGRESS", "phase": "PREPARED", "run_id": run.name, "quarantine_features": str(quarantine), "failed_candidate": str(failed), "old_live_files": old}
        common.atomic_write_json(run / "control" / "publish_journal.json", journal)
        result = recover_locked(qdh, run, candidate)
        require(result is not None and result["status"] == "ROLLED_BACK", "PREPARED recovery selftest failed")
        require(inventory_matches(qdh / "features", old) and inventory_matches(run / "stage" / "features", candidate), "PREPARED recovery changed a tree")

        # Crash after live->quarantine but before the phase journal update.
        qdh = base / "case-first-rename" / "qdh"; run = base / "case-first-rename" / "run"
        qdh.mkdir(parents=True)
        _fixture_tree(run / "stage" / "features", b"new")
        quarantine, failed = transaction_paths(run)
        _fixture_tree(quarantine, b"old"); (run / "control").mkdir(parents=True)
        old = tree_inventory(quarantine); candidate = tree_inventory(run / "stage" / "features")
        journal = {"status": "IN_PROGRESS", "phase": "PREPARED", "run_id": run.name, "quarantine_features": str(quarantine), "failed_candidate": str(failed), "old_live_files": old}
        common.atomic_write_json(run / "control" / "publish_journal.json", journal)
        result = recover_locked(qdh, run, candidate)
        require(result is not None and result["status"] == "ROLLED_BACK", "first-rename recovery selftest failed")
        require(inventory_matches(qdh / "features", old), "first-rename recovery did not restore live")

        # Candidate is live but a synchronous post-switch check failed: force old live back.
        qdh = base / "case-rollback" / "qdh"; run = base / "case-rollback" / "run"
        run.mkdir(parents=True)
        quarantine, failed = transaction_paths(run)
        _fixture_tree(qdh / "features", b"new"); _fixture_tree(quarantine, b"old")
        (run / "control").mkdir(parents=True)
        old = tree_inventory(quarantine); candidate = tree_inventory(qdh / "features")
        journal = {"status": "IN_PROGRESS", "phase": "CANDIDATE_LIVE", "run_id": run.name, "quarantine_features": str(quarantine), "failed_candidate": str(failed), "old_live_files": old}
        common.atomic_write_json(run / "control" / "publish_journal.json", journal)
        result = rollback_locked(qdh, run)
        require(result["status"] == "ROLLED_BACK" and inventory_matches(qdh / "features", old), "forced rollback selftest failed")
        require(inventory_matches(failed, candidate), "failed candidate was not retained")
    return {
        "status": "PASS",
        "write_scope": "temporary-directory-only",
        "mixed_case_inventory": True,
        "prepared_recovery": True,
        "first_rename_crash_recovery": True,
        "forced_rollback": True,
    }


@contextlib.contextmanager
def global_publish_lock(qdh: Path):
    path = qdh.parent / f".{qdh.name}.features-publish.lock"
    path.touch(exist_ok=True)
    with path.open("r+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"0"); handle.flush(); os.fsync(handle.fileno())
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError(f"another publisher holds {path}") from exc
        try:
            yield
        finally:
            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def load_and_verify_ready(
    qdh_root: str,
    run_root: str,
    ch_url: str,
    workers: int,
    *,
    allow_live_candidate: bool = False,
) -> tuple[Path, Path, dict[str, Any], str, list[dict[str, Any]]]:
    qdh, run = common.ensure_qdh_run_roots(qdh_root, run_root, require_run=True)
    control = run / "control"
    ready_path = control / "READY"
    require(ready_path.is_file(), "READY seal missing")
    ready_sha = common.sha256_file(ready_path)
    ready = common.read_json(ready_path)
    exact = {
        "schema_version", "status", "sealed_at_utc", "run_id", "release_mode", "meta_policy",
        "qdh_root", "stage_root", "scope", "columns", "market_semantic_sha256",
        "warmup_semantic_sha256", "source_semantic_sha256", "source_files",
        "manifest_sha256", "build_complete_sha256", "files_sha256", "files",
        "stage_tree_semantic_sha256", "validation_full_sha256",
        "validation_final_structure_sha256", "bitwise_recompute_match",
    }
    require(set(ready) == exact, f"READY field set changed: {sorted(set(ready) ^ exact)}")
    require(ready["status"] == "READY" and ready["schema_version"] == 1, "invalid READY status")
    require(ready["run_id"] == run.name and ready["qdh_root"] == str(qdh), "READY identity mismatch")
    require(ready["release_mode"] == "features-only" and ready["meta_policy"] == "unchanged", "publisher only accepts features-only READY")
    require(ready["columns"]["names"] == list(OUTPUT_COLUMNS), "READY columns changed")
    require(ready["columns"]["order_sha256"] == COLUMN_ORDER_SHA256, "READY column hash changed")
    require(ready["bitwise_recompute_match"] is True, "READY lacks bitwise validation")
    evidence = {
        "manifest.json": ready["manifest_sha256"],
        "build_complete.json": ready["build_complete_sha256"],
        "files.jsonl": ready["files_sha256"],
        "validation_full.json": ready["validation_full_sha256"],
        "validation_final_structure.json": ready["validation_final_structure_sha256"],
    }
    for name, expected in evidence.items():
        path = control / name
        require(path.is_file() and common.sha256_file(path) == expected, f"sealed evidence changed: {name}")
    current_sources = source_hashes()
    require(current_sources == ready["source_files"], "formula/orchestration source changed")
    require(common.canonical_json_sha256(current_sources) == ready["source_semantic_sha256"], "source semantic hash changed")
    runtime_selftest()
    files = ready["files"]
    require(common.canonical_json_sha256(files) == ready["stage_tree_semantic_sha256"], "READY file list changed")
    require(common.sha256_file(control / "files.jsonl") == ready["files_sha256"], "files evidence changed")
    stage = run / "stage" / "features"
    require(str(stage) == ready["stage_root"], "READY stage path mismatch")
    expected_candidate = candidate_inventory(files)
    candidate_ok = inventory_matches(stage, expected_candidate)
    if allow_live_candidate and not candidate_ok:
        candidate_ok = inventory_matches(qdh / "features", expected_candidate)
    require(candidate_ok, "neither stage nor permitted live tree matches READY")
    market = common.market_snapshot(qdh, workers=workers)
    require_market_profile(market)
    manifest = common.read_json(control / "manifest.json")
    warmup = common.warmup_snapshot(ch_url, manifest["selected_scope"]["sequences"])
    require(market["semantic_sha256"] == ready["market_semantic_sha256"], "market changed after READY")
    require(warmup["semantic_sha256"] == ready["warmup_semantic_sha256"], "warmup changed after READY")
    return qdh, run, ready, ready_sha, expected_candidate


def dry_run_plan(qdh: Path, run: Path, ready: dict[str, Any], ready_sha: str, expected_candidate: list[dict[str, Any]]) -> dict[str, Any]:
    live = qdh / "features"
    current = tree_inventory(live)
    return {
        "status": "DRY_RUN_PASS", "write_count": 0, "run_id": run.name,
        "ready_sha256": ready_sha, "release_mode": "features-only",
        "meta_will_change": False,
        "candidate": {"partitions": len(expected_candidate), "bytes": sum(row["bytes"] for row in expected_candidate), "semantic_sha256": common.canonical_json_sha256(expected_candidate)},
        "current_live": {"partitions": len(current), "bytes": sum(row["bytes"] for row in current), "semantic_sha256": common.canonical_json_sha256(current)},
        "atomicity": "same-volume crash-recoverable rename transaction; direct unlocked readers may observe the rename window",
        "execute_requires": ["--execute", f"--confirm-run-id {run.name}", f"--confirm-ready-sha256 {ready_sha}"],
    }


def recover_locked(qdh: Path, run: Path, expected_candidate: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw_journal = run / "control" / "publish_journal.json"
    if not raw_journal.is_file():
        return None
    journal_path, journal, quarantine, failed = checked_journal(run)
    if journal.get("status") != "IN_PROGRESS":
        return journal
    live = qdh / "features"
    phase = journal.get("phase")
    old_expected = journal["old_live_files"]
    if phase == "PREPARED":
        if inventory_matches(live, old_expected):
            pass
        elif not live.exists() and inventory_matches(quarantine, old_expected):
            os.replace(quarantine, live)
            require(inventory_matches(live, old_expected), "PREPARED recovery restored wrong live tree")
        else:
            raise RuntimeError("PREPARED recovery cannot prove either pre-rename or post-first-rename state")
        journal["status"] = "ROLLED_BACK"
        journal["recovered_at_utc"] = common.now_utc()
        common.atomic_write_json(journal_path, journal)
        return journal
    if phase in ("CANDIDATE_LIVE", "LIVE_VERIFIED") and inventory_matches(live, expected_candidate):
        journal["status"] = "COMMITTED"
        journal["recovered_at_utc"] = common.now_utc()
        common.atomic_write_json(journal_path, journal)
        return journal
    if live.exists():
        require(not failed.exists(), f"failed-candidate destination already exists: {failed}")
        failed.parent.mkdir(parents=True, exist_ok=True)
        os.replace(live, failed)
    require(quarantine.is_dir(), "cannot recover: old live quarantine is missing")
    os.replace(quarantine, live)
    require(inventory_matches(live, old_expected), "restored old live does not match journal")
    journal["status"] = "ROLLED_BACK"
    journal["recovered_at_utc"] = common.now_utc()
    common.atomic_write_json(journal_path, journal)
    return journal


def rollback_locked(qdh: Path, run: Path) -> dict[str, Any]:
    """Force rollback after a detected in-process validation failure."""

    journal_path, journal, quarantine, failed = checked_journal(run)
    require(journal.get("status") == "IN_PROGRESS", "rollback requires an in-progress journal")
    live = qdh / "features"
    if live.exists():
        require(not failed.exists(), f"failed-candidate destination already exists: {failed}")
        failed.parent.mkdir(parents=True, exist_ok=True)
        os.replace(live, failed)
    require(quarantine.is_dir(), "rollback quarantine is missing")
    os.replace(quarantine, live)
    require(inventory_matches(live, journal["old_live_files"]), "forced rollback restored the wrong live tree")
    journal["status"] = "ROLLED_BACK"
    journal["rolled_back_at_utc"] = common.now_utc()
    common.atomic_write_json(journal_path, journal)
    return journal


def execute_publish(
    qdh: Path,
    run: Path,
    ready: dict[str, Any],
    ready_sha: str,
    expected_candidate: list[dict[str, Any]],
    ch_url: str,
    workers: int,
) -> dict[str, Any]:
    live = qdh / "features"
    stage = run / "stage" / "features"
    control = run / "control"
    journal_path = control / "publish_journal.json"
    if journal_path.is_file():
        prior = recover_locked(qdh, run, expected_candidate)
        require(prior is not None and prior.get("status") != "IN_PROGRESS", "unresolved publish journal")
        require(prior.get("status") != "COMMITTED", "this READY run is already published")
    old = tree_inventory(live)
    quarantine, failed = transaction_paths(run)
    quarantine_root = quarantine.parent
    require(not quarantine_root.exists(), f"quarantine already exists: {quarantine_root}")
    quarantine_root.mkdir(parents=True)
    journal = {
        "schema_version": 1, "status": "IN_PROGRESS", "phase": "PREPARED",
        "started_at_utc": common.now_utc(), "run_id": run.name, "ready_sha256": ready_sha,
        "qdh_root": str(qdh), "stage_features": str(stage), "live_features": str(live),
        "quarantine_features": str(quarantine), "failed_candidate": str(failed),
        "old_live_files": old, "old_live_semantic_sha256": common.canonical_json_sha256(old),
        "candidate_semantic_sha256": common.canonical_json_sha256(expected_candidate),
        "meta_changed": False,
    }
    common.atomic_write_json(journal_path, journal)
    try:
        os.replace(live, quarantine)
        journal["phase"] = "OLD_QUARANTINED"; common.atomic_write_json(journal_path, journal)
        os.replace(stage, live)
        journal["phase"] = "CANDIDATE_LIVE"; common.atomic_write_json(journal_path, journal)
        require(inventory_matches(live, expected_candidate), "published live differs from READY")
        # Close the source-drift window after the directory switch.
        require(source_hashes() == ready["source_files"], "source changed during publish")
        market = common.market_snapshot(qdh, workers=workers)
        require_market_profile(market)
        manifest = common.read_json(control / "manifest.json")
        warmup = common.warmup_snapshot(ch_url, manifest["selected_scope"]["sequences"])
        require(market["semantic_sha256"] == ready["market_semantic_sha256"], "market changed during publish")
        require(warmup["semantic_sha256"] == ready["warmup_semantic_sha256"], "warmup changed during publish")
        journal["phase"] = "LIVE_VERIFIED"; journal["status"] = "COMMITTED"; journal["committed_at_utc"] = common.now_utc()
        common.atomic_write_json(journal_path, journal)
    except Exception:
        current = common.read_json(journal_path)
        if current.get("phase") == "PREPARED":
            recover_locked(qdh, run, expected_candidate)
        else:
            rollback_locked(qdh, run)
        raise
    receipt = {
        "status": "COMMITTED", "run_id": run.name, "ready_sha256": ready_sha,
        "committed_at_utc": journal["committed_at_utc"], "release_mode": "features-only",
        "meta_changed": False, "live_semantic_sha256": common.canonical_json_sha256(expected_candidate),
        "rollback_quarantine": str(quarantine),
    }
    common.atomic_write_json(control / "publish_receipt.json", receipt)
    return receipt


def command_publish(args: argparse.Namespace) -> int:
    qdh, run, ready, ready_sha, expected = load_and_verify_ready(args.qdh_root, args.run_root, args.ch_url, args.workers)
    if not args.execute:
        print(json.dumps(dry_run_plan(qdh, run, ready, ready_sha, expected), ensure_ascii=False, indent=2))
        return 0
    require(args.confirm_run_id == run.name, "--confirm-run-id mismatch")
    require(args.confirm_ready_sha256 == ready_sha, "--confirm-ready-sha256 mismatch")
    with global_publish_lock(qdh):
        # Re-run all expensive identity checks under the publish lock.
        qdh, run, ready, ready_sha, expected = load_and_verify_ready(args.qdh_root, args.run_root, args.ch_url, args.workers)
        require(args.confirm_run_id == run.name, "locked --confirm-run-id mismatch")
        require(args.confirm_ready_sha256 == ready_sha, "locked --confirm-ready-sha256 mismatch")
        result = execute_publish(qdh, run, ready, ready_sha, expected, args.ch_url, args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    qdh, run, ready, ready_sha, expected = load_and_verify_ready(
        args.qdh_root, args.run_root, args.ch_url, args.workers,
        allow_live_candidate=True,
    )
    # A published run no longer has stage; allow verification directly from READY.
    live = qdh / "features"
    require(inventory_matches(live, expected), "live features do not match READY")
    print(json.dumps({"status": "PASS", "run_id": run.name, "ready_sha256": ready_sha, "live_semantic_sha256": common.canonical_json_sha256(expected), "meta_checked": False}, ensure_ascii=False, indent=2))
    return 0


def command_recover(args: argparse.Namespace) -> int:
    qdh, run, ready, ready_sha, expected = load_and_verify_ready(
        args.qdh_root, args.run_root, args.ch_url, args.workers,
        allow_live_candidate=True,
    )
    require(args.confirm_run_id == run.name, "--confirm-run-id mismatch")
    require(args.confirm_ready_sha256 == ready_sha, "--confirm-ready-sha256 mismatch")
    with global_publish_lock(qdh):
        qdh, run, ready, ready_sha, expected = load_and_verify_ready(
            args.qdh_root, args.run_root, args.ch_url, args.workers,
            allow_live_candidate=True,
        )
        require(args.confirm_run_id == run.name, "locked --confirm-run-id mismatch")
        require(args.confirm_ready_sha256 == ready_sha, "locked --confirm-ready-sha256 mismatch")
        journal_path, journal, _, _ = checked_journal(run)
        require(journal.get("ready_sha256") == ready_sha, "journal READY authorization mismatch")
        result = recover_locked(qdh, run, expected)
    print(json.dumps(result or {"status": "NO_JOURNAL"}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("publish", "verify-live", "recover"):
        item = sub.add_parser(name)
        item.add_argument("--qdh-root", required=True); item.add_argument("--run-root", required=True); item.add_argument("--ch-url", required=True); item.add_argument("--workers", type=int, default=4)
        if name == "publish":
            item.add_argument("--execute", action="store_true"); item.add_argument("--confirm-run-id"); item.add_argument("--confirm-ready-sha256")
        if name == "recover":
            item.add_argument("--confirm-run-id", required=True); item.add_argument("--confirm-ready-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "publish":
        return command_publish(args)
    if args.command == "verify-live":
        return command_verify(args)
    return command_recover(args)


if __name__ == "__main__":
    raise SystemExit(main())
