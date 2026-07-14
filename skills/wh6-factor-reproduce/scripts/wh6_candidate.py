"""File-independent pure-Python WH6 198-column candidate engine."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from wh6_formulas_v2 import (
    COLUMN_ORDER,
    FORMULA_GROUP_METADATA,
    FORMULA_GROUPS,
    FORMULA_SOURCE_FORMAT,
    SOURCE_FORMULA_MAP_SHA256,
)
from wh6_primitives import FormulaContext, WH6EvaluationError


class PurePythonWH6Engine:
    """Execute the 97 Python formula groups in their locked order."""

    columns = COLUMN_ORDER

    def capability_report(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "implementation": "pure_python_explicit_formulas",
            "formula_source_format": FORMULA_SOURCE_FORMAT,
            "runtime_formula_file_reads": False,
            "formula_groups": len(FORMULA_GROUPS),
            "output_columns": len(self.columns),
            "source_formula_map_sha256": SOURCE_FORMULA_MAP_SHA256,
            "field_contract": {
                "OPEN/O": "open",
                "HIGH/H": "high",
                "LOW/L": "low",
                "CLOSE/C/SETTLE": "close",
                "VOL/CJLVOL": "volume",
                "CCL": "open_interest",
            },
        }

    def compute(self, frame: pd.DataFrame) -> pd.DataFrame:
        required = ("open", "high", "low", "close", "volume", "open_interest")
        missing = [name for name in required if name not in frame.columns]
        if missing:
            raise WH6EvaluationError(f"missing input columns: {missing}")
        if not frame.index.is_unique:
            raise WH6EvaluationError("input index must be unique")

        source = {
            name: pd.to_numeric(frame[name], errors="raise").astype("float64")
            for name in required
        }
        fields = {
            "OPEN": source["open"],
            "O": source["open"],
            "HIGH": source["high"],
            "H": source["high"],
            "LOW": source["low"],
            "L": source["low"],
            "CLOSE": source["close"],
            "C": source["close"],
            "SETTLE": source["close"],
            "VOL": source["volume"],
            "VOLUME": source["volume"],
            "CCL": source["open_interest"],
            "OPEN_INTEREST": source["open_interest"],
        }

        values: dict[str, pd.Series] = {}
        with np.errstate(all="ignore"):
            for formula, (_name, label, expected_columns) in zip(
                FORMULA_GROUPS, FORMULA_GROUP_METADATA, strict=True
            ):
                context = FormulaContext(label, fields, frame.index)
                group_values = formula(context)
                if tuple(group_values) != expected_columns:
                    raise WH6EvaluationError(
                        f"{label}: output binding mismatch: "
                        f"expected={expected_columns}, actual={tuple(group_values)}"
                    )
                for column, value in group_values.items():
                    if column in values:
                        raise WH6EvaluationError(f"duplicate output {column}")
                    series = context.series(value, dtype="float64")
                    values[column] = series.mask(~np.isfinite(series), np.nan)

        missing_outputs = [column for column in self.columns if column not in values]
        extra_outputs = sorted(set(values) - set(self.columns))
        if missing_outputs or extra_outputs:
            raise WH6EvaluationError(
                f"output contract violation: missing={missing_outputs}, extra={extra_outputs}"
            )
        return pd.DataFrame(
            {column: values[column] for column in self.columns}, index=frame.index
        )


def load_engine(_ignored_formula_map: Any = None) -> PurePythonWH6Engine:
    """Return the file-independent engine; the optional argument is ignored."""

    return PurePythonWH6Engine()
