# Indicator-PY 59 reproduction contract

## Locked scope

- Output: exactly `trade_time` followed by the 59 columns listed in `indicator-py-locked-59-contract.json`.
- Feature type: Arrow/Pandas `float64`; unavailable results are null/NaN.
- Runtime inputs: one continuous sequence containing `trade_time`, `open`, `high`, `low`, `close`, `volume`, and `open_interest`.
- Internal upstream calculation: the vendored locked WH6 engine computes 198 columns, after which only these five are passed to Indicator-PY:
  - `wh6_MACD_MACD`
  - `wh6_RSI_RSI2`
  - `wh6_ATR_ATR`
  - `wh6_Z_SCORE_Z_SCORE`
  - `wh6_u_8b96f436_BBW`
- Persistence: upstream market and WH6 columns are not written to the standalone output.

The vendored WH6 field contract maps `SETTLE` to `close`, identical to the accepted WH6 reproduction core. This skill does not discover or reconstruct a separate settlement series.

## Source locks

| File | SHA-256 |
|---|---|
| `scripts/factor_indicator.py` | `817b6531f19e33c5dea3307afca56314a8396f01034b03f53205e87ac49dc2d1` |
| `scripts/vendor/wh6_candidate.py` | `849c460a50864e05744211abe3e269b2e7e957312ee92ed2c432fbef4f89514e` |
| `scripts/vendor/wh6_formulas_v2.py` | `e71c1d3be8c43c0c5e1ec0ac9fc204b471d07e527292b37571c08bc489439d8a` |
| `scripts/vendor/wh6_primitives.py` | `9313b87f57138b9775ad502f8970d91bd81439e02f8056242561d2a822e39061` |
| `references/indicator-py-locked-59-contract.json` | `633bf61bf71e7ef8d75cea3e65621a69177ce20bd3d856f72ed9ea777d3e9097` |
| `references/indicator-py-formulas.md` | `69ef6c57d9e8063fb3671da382c43605e289bb6b870ae47e9f35796165672d39` |
| `references/indicator-py-audit-policy.md` | `67224613b8f62b4028b70353557368daa19348cb1fddfedf26ea71235ff43746` |
| `assets/acceptance/indicator_migration.json` | `2e9a280271b805a093276ff725734ed64d144ac6a64b9b6ef6f8bd7ef45dff58` |

`selftest` recomputes every hash. It also checks that the migration acceptance evidence names the same Indicator and WH6 hashes. Paths recorded inside that evidence are provenance only and are never opened.

## Exact runtime

Summary, selftest, dry-run, and execute must use one interpreter with these exact versions:

| Component | Version |
|---|---|
| Python | `3.10.20` |
| NumPy | `2.2.6` |
| pandas | `2.3.3` |
| PyArrow | `23.0.1` |

Any mismatch fails closed. Resolve the skill root from the loaded `SKILL.md` location; never infer it from an agent-specific configuration directory, a user home, agent type, or current working directory. Keep the skill directory read-only and preserve every locked file byte-for-byte during cc-switch distribution.

## Sequence and warmup semantics

The input must represent one symbol and one timeframe. `trade_time` must be an Arrow timestamp, non-null, unique, and strictly increasing. The CLI cannot infer whether exchange-session rows are semantically complete, so the caller must establish that the file is the complete intended sequence and does not mix contracts, symbols, or timeframes.

Compute the full file before slicing. `--live-start` cannot be earlier than `2020-01-01` and divides the file into:

- warmup: all rows where `trade_time < live_start`; used by rolling and recursive state, never persisted;
- live: all rows where `trade_time >= live_start`; persisted after the full computation.

The CLI rejects an input with zero warmup rows by default. Some ClickHouse sequences legitimately have no pre-2020 rows and therefore have a true cold start. Only after upstream inspection confirms zero earlier ClickHouse history for the exact symbol/timeframe may the caller add `--allow-cold-start`; this records the exception but does not synthesize state.

The CLI never computes only the live tail when warmup exists, never writes pre-live rows, and hard-rejects any output row earlier than `2020-01-01`, including when `--allow-cold-start` is present.

## Formula semantics

The detailed human-readable formulas are in `indicator-py-formulas.md`. The accepted core additionally locks these edge rules:

- return volatility uses rolling sample standard deviation (`ddof=1`);
- z-scores use rolling population standard deviation (`ddof=0`);
- exact constant windows reset their standard deviation to zero;
- a z-score denominator with absolute value below `1e-10` becomes exact zero;
- ordinary IEEE division is used, then all `+/-Inf` is normalized to NaN/null;
- rolling ranks are ascending percentage ranks with average ties;
- cold-start true range uses `high-low` when previous close is unavailable;
- PPO uses `adjust=False` recursive EMA with `min_periods=span`;
- six boolean/break columns are `float64` values `0.0/1.0` and carry no nulls;
- WH6 ATR is preferred, with only its unavailable cold-start prefix filled by the equivalent 14-row market true-range mean.

## Determinism and validation

`selftest` must pass before staging. It verifies:

1. every locked source hash;
2. byte equivalence between the skill Indicator core and migration acceptance hash;
3. 59 feature columns in locked order plus `trade_time` at output;
4. every feature is `float64` and no feature contains infinity;
5. two identical calculations are bit-for-bit identical, including null payloads;
6. full-sequence computation followed by warmup slicing is stable;
7. a cold live-only recomputation differs, proving the warmup guard is active;
8. zero warmup fails closed by default and succeeds only with explicit cold-start authorization;
9. output selection cannot contain pre-2020 rows;
10. the vendored engine still computes locked WH6 198 and supplies exactly the five selected dependencies.

## Write safety and ownership

- `summary` and `selftest` never write.
- `build` without `--execute` reads and computes but performs no filesystem mutation.
- `build --execute` requires an absolute output outside the existing `--qdh-root` and outside the skill directory.
- Existing outputs are never overwritten.
- Every agent receives a unique output path. Exactly one agent owns that path from dry-run through execute; agents must not concurrently target, share, or reuse it.
- A new parent staging directory may be created only after explicit `--execute`.
- The Parquet file is written to a random sibling temporary file, reread and validated, then committed with an atomic hard-link no-clobber operation. A concurrently created destination causes failure.

This is not the qdh wide-table writer. It must not write, merge, partition, publish, switch, or roll back qdh `features/`. Current production features are `trade_time + 465`, for 466 columns total. Only the `qdh-features-reproduce` orchestrator owns final partition layout, four-family joins by `trade_time`, full acceptance, publication, and rollback.

## Acceptance evidence boundaries

The copied migration evidence records a historical candidate acceptance, including 62 symbols, 557 sequences, 3,550 paired partitions, 13,825,291 paired rows, and documented oracle boundaries. It does not prove current qdh data coverage, current ClickHouse parity, or pre-2020 legacy oracle identity. Those remain upstream data/warmup acceptance responsibilities.
