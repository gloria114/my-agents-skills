# Execution contract

## Formula composition

The sibling skills are the formula authorities:

1. `wh6-factor-reproduce`: 198 columns.
2. `indicator-py-factor-reproduce`: 59 columns; its five WH6 dependencies come from the same WH6 result computed for this sequence.
3. `excel-factor-reproduce`: 66 columns.
4. `tv-factor-reproduce`: 142 columns.

The canonical output is 466 columns. Its compact-JSON column-order SHA256 is
`75f719fc1d2d4312a66a96de994afe1293da02fa1f96d6d54fc838229c8e4d88`.

All feature columns are float64. Formula NaN is represented as Arrow null. A valid value may never be Inf. `trade_time` must be bit-for-bit identical to its paired market partition, including Arrow timestamp type and timezone.

The sealed numerical runtime is Python 3.10.20, NumPy 2.2.6, pandas 2.3.3 and PyArrow 23.0.1. Every command verifies this fingerprint before formula execution. Source identity includes the locked sibling artifacts and the orchestration sources loaded from the executing agent's five-skill bundle.

## Sequence semantics

The compute unit is a complete symbol/timeframe sequence, never an isolated year. Input order is:

1. all available CH rows with `trade_date < 2020-01-01`, read by `SELECT FINAL`;
2. every qdh market row from 2020 onward in strict `trade_time` order.

The formulas run once on that continuous frame. Warmup rows are then removed. Live rows are sliced back into exactly the paths present in the current market snapshot.

## Validation

Structure validation proves exact path set, file hashes, market pairing, 466-column order, dtype, timestamp equality, row counts, no valid Inf, no pre-2020 output and strict time order.

Full validation independently reloads market and CH warmup, reruns all four formula families, and compares every non-null float64 value by its uint64 bits plus an exact null mask.

READY is allowed only for the complete current market scope. It seals source files, market and warmup identities, the files manifest, full-validation evidence and final structure evidence.

## Scope changes

This profile intentionally locks the present 62 JQ symbols, nine timeframes, `contract_code = symbol + JQ`, and the current ClickHouse table map inherited from `wh6_common.py`. New year partitions and added rows are dynamic. Adding/removing symbols, changing timeframes or changing CH table mappings is a contract revision, not a routine data refresh.
