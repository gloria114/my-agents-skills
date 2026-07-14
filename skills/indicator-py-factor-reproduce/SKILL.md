---
name: indicator-py-factor-reproduce
description: 用锁定的纯 Python 核心，从一段完整连续的 warmup+live（或已确认 CH 无更早历史的 cold-start）OHLCV+open_interest Parquet 安全复现、验证并外部 staging 59 个 indicator_py_ 因子。用于 selftest、输入连续性核验、trade_time+59 复算、warmup 后切片验证、公式审阅或为统一 qdh features orchestrator 准备独立候选；默认只读，不直接发布当前 466 列生产 features。
---

# Indicator PY Factor Reproduce

## Scope

Use this skill only for the locked 59 `indicator_py_` columns. The runtime is self-contained: it vendors the accepted Indicator-PY core and the locked WH6 engine needed to derive the five upstream WH6 columns from raw `open/high/low/close/volume/open_interest`.

Do not use this skill to add indicators, reinterpret parameters, merge the full feature palette, or publish directly into qdh. The standalone output contract is exactly `trade_time + 59 indicator_py_ columns`. Current production features are `trade_time + 465`, for 466 columns total; only the `qdh-features-reproduce` orchestrator may merge all four families and publish production features.

The skill directory is read-only. Never place input, output, temporary files, logs, or orchestration control files beneath it.

## Location, runtime, and multi-agent contract

Resolve `<skill-root>` from the directory containing the currently loaded `SKILL.md`. Do not infer it from a user home, agent name, agent-specific configuration directory, or the current working directory. Replace every angle-bracket placeholder below with an absolute value:

- `<python>`: one controlled interpreter with exactly Python 3.10.20, NumPy 2.2.6, pandas 2.3.3, and PyArrow 23.0.1.
- `<skill-root>`: the absolute path of this skill package.
- `<input>`: one complete continuous warmup+live Parquet sequence.
- `<run-root>`: the unique external orchestration run assigned to the current agent.
- `<output>`: a new absolute staging Parquet path owned by this agent, normally beneath `<run-root>`.
- `<qdh-root>`: the absolute qdh root used only for the write boundary check.
- `<ch-url>`: the read-only ClickHouse endpoint used by the caller or orchestrator to establish warmup/cold-start evidence; it is not a standalone CLI argument.
- `<live-start>`: the ISO-8601 live boundary.

Every agent must receive a unique `<output>`. Exactly one agent owns an output path from dry-run through execute; agents must not race, share, overwrite, or reuse it. Use the same `<python>` for summary, selftest, dry-run, and execute. cc-switch distribution must preserve locked files byte-for-byte, including line endings.

## Required reading

Before computing or changing behavior, read:

1. `references/reproduction-contract.md` for input, warmup, output, determinism, runtime, and writer boundaries.
2. `references/indicator-py-locked-59-contract.json` for machine-readable column order and dependencies.
3. `references/indicator-py-formulas.md` when formula-level review is requested.
4. `references/indicator-py-audit-policy.md` when comparing this reproduction scope with audit scope.

Treat `assets/acceptance/indicator_migration.json` as immutable provenance evidence, not as a runtime data source. The CLI never resolves or opens paths recorded inside that evidence.

## Safe workflow

### 1. Run read-only checks

```text
<python> -B -X utf8 "<skill-root>/scripts/indicator_py_reproduce.py" summary
<python> -B -X utf8 "<skill-root>/scripts/indicator_py_reproduce.py" selftest
```

Stop if either command fails. `selftest` verifies the exact runtime, locked source hashes, migration-core byte equivalence, five required WH6 dependencies, 59-column order and `float64` schema, infinity normalization, repeat-run bit determinism, compute-full-then-slice warmup behavior, explicit cold-start handling, and the pre-2020 output guard.

### 2. Supply one complete continuous sequence

The input must be one Parquet file containing one symbol/timeframe sequence with strictly increasing, unique, non-null `trade_time` and these numeric columns:

`open`, `high`, `low`, `close`, `volume`, `open_interest`.

Rows before `<live-start>` are transient warmup. They participate in all recursive and rolling calculations but are never written. Do not concatenate unrelated contracts, symbols, or timeframes. `<live-start>` cannot be earlier than `2020-01-01`.

If and only if upstream ClickHouse inspection proves that this exact symbol/timeframe sequence has no earlier rows, a file that begins at or after `<live-start>` is a legitimate cold start. The CLI fails closed by default; add `--allow-cold-start` only to record that explicit upstream confirmation.

### 3. Preflight a staging build

The build command is dry-run by default and never writes without `--execute`:

```text
<python> -B -X utf8 "<skill-root>/scripts/indicator_py_reproduce.py" build --input "<input>" --output "<output>" --qdh-root "<qdh-root>" --live-start "<live-start>"
```

Review the JSON plan. `<output>` must be absolute, outside `<qdh-root>` and `<skill-root>`, different from `<input>`, and absent before execution. For a confirmed CH zero-history sequence, append `--allow-cold-start` to both dry-run and execute commands.

### 4. Write only explicit external staging

Repeat the identical command with `--execute`. The CLI writes a random sibling temporary file, rereads and validates it, then uses an atomic hard-link no-clobber commit. It refuses an existing or concurrently created output.

```text
<python> -B -X utf8 "<skill-root>/scripts/indicator_py_reproduce.py" build --input "<input>" --output "<output>" --qdh-root "<qdh-root>" --live-start "<live-start>" --execute
```

## Unified writer boundary

This skill does not own the qdh wide-feature writer. Never point `<output>` at qdh `features/`, never merge into an existing feature Parquet, and never perform an atomic directory switch. The `qdh-features-reproduce` orchestrator alone owns cross-family joins by `trade_time`, partition preservation, 466-column schema order, full acceptance, publication, and rollback.

## Implementation locks

- `scripts/factor_indicator.py` is a byte-identical accepted core.
- `scripts/vendor/wh6_candidate.py`, `wh6_formulas_v2.py`, and `wh6_primitives.py` are byte-identical vendored WH6 sources.
- `scripts/indicator_py_reproduce.py` checks every locked source SHA-256 before compute or write.
- Runtime calculation does not read the audit skill, qdh metadata, another skill package, or any path recorded in acceptance evidence.
- Computing all 198 WH6 columns internally and selecting only the locked five dependencies is intentional; the persisted artifact contains no WH6 columns.

If any locked hash, order, dependency, semantic contract, or exact runtime must change, stop and require renewed acceptance.
