"""Pure-Python execution primitives for the locked 198-column WH6 formulas.

This module deliberately contains no parser and performs no file I/O.  The
formula source is ordinary Python in :mod:`wh6_formulas_generated`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd


class WH6EvaluationError(RuntimeError):
    """A locked formula cannot be evaluated without guessing."""


def _integral_window(value: Any, function: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, pd.Series) or isinstance(value, np.ndarray):
        raise WH6EvaluationError(f"{function} window must be scalar")
    number = float(value)
    rounded = int(round(number))
    minimum = 0 if allow_zero else 1
    if not math.isfinite(number) or abs(number - rounded) > 1e-9 or rounded < minimum:
        raise WH6EvaluationError(f"{function} invalid window {value!r}")
    return rounded


class FormulaContext:
    """One formula group's fields, lazy definitions, and exact WH6 primitives."""

    def __init__(
        self,
        label: str,
        fields: Mapping[str, pd.Series],
        index: pd.Index,
    ) -> None:
        self.label = label
        self.fields = fields
        self.index = index
        self._definitions: Mapping[str, Callable[[], Any]] = {}
        self._cache: dict[str, Any] = {}
        self._active: set[str] = set()

        # Explicit field aliases used by the generated Python formulas.
        self.OPEN = fields["OPEN"]
        self.O = fields["O"]
        self.HIGH = fields["HIGH"]
        self.H = fields["H"]
        self.LOW = fields["LOW"]
        self.L = fields["L"]
        self.CLOSE = fields["CLOSE"]
        self.C = fields["C"]
        self.SETTLE = fields["SETTLE"]
        self.VOL = fields["VOL"]
        self.VOLUME = fields["VOLUME"]
        self.CCL = fields["CCL"]
        self.OPEN_INTEREST = fields["OPEN_INTEREST"]
        self.NULL = np.nan

    def bind(self, definitions: Mapping[str, Callable[[], Any]]) -> None:
        if self._definitions:
            raise WH6EvaluationError(f"definitions already bound in {self.label}")
        self._definitions = definitions

    def resolve(self, name: str) -> Any:
        if name in self._cache:
            return self._cache[name]
        if name in self._active:
            raise WH6EvaluationError(f"cyclic definition {name} in {self.label}")
        if name not in self._definitions:
            raise WH6EvaluationError(f"unknown identifier {name} in {self.label}")
        self._active.add(name)
        try:
            value = self._definitions[name]()
        finally:
            self._active.remove(name)
        self._cache[name] = value
        return value

    def series(self, value: Any, *, dtype: str | None = None) -> pd.Series:
        if isinstance(value, pd.Series):
            result = value.reindex(self.index)
        elif np.isscalar(value):
            result = pd.Series(value, index=self.index)
        else:
            array = np.asarray(value)
            if len(array) != len(self.index):
                raise WH6EvaluationError("function returned an array with the wrong length")
            result = pd.Series(array, index=self.index)
        return result.astype(dtype) if dtype else result

    def _bool(self, value: Any) -> Any:
        if isinstance(value, pd.Series):
            return value.fillna(False).astype(bool)
        return bool(value) if not pd.isna(value) else False

    def unary(self, op: str, value: Any) -> Any:
        if op == "+":
            return value
        if op == "-":
            return -value
        if op == "!":
            return ~self._bool(value)
        raise WH6EvaluationError(f"unsupported operator {op}")

    def logical_not(self, value: Any) -> Any:
        """WH6 ``!`` with the locked missing-as-false boolean conversion."""

        return ~self._bool(value)

    def logical_and(self, left: Any, right: Any) -> Any:
        """WH6 ``&&`` without pandas' ambiguous truth-value coercion."""

        return self._bool(left) & self._bool(right)

    def logical_or(self, left: Any, right: Any) -> Any:
        """WH6 ``||`` without pandas' ambiguous truth-value coercion."""

        return self._bool(left) | self._bool(right)

    def binary(self, op: str, left: Any, right: Any) -> Any:
        with np.errstate(all="ignore"):
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                # Keep IEEE infinity inside an expression.  Some formulas
                # intentionally turn a positive/zero ratio into a finite limit.
                return left / right
            if op in {"=", "=="}:
                return left == right
            if op in {"!=", "<>"}:
                return left != right
            if op == ">":
                return left > right
            if op == "<":
                return left < right
            if op == ">=":
                return left >= right
            if op == "<=":
                return left <= right
            if op == "&&":
                return self._bool(left) & self._bool(right)
            if op == "||":
                return self._bool(left) | self._bool(right)
        raise WH6EvaluationError(f"unsupported operator {op}")

    def ABS(self, value: Any) -> Any:
        return abs(value)

    def MAX(self, *args: Any) -> Any:
        return self._elementwise_extreme(args, "MAX")

    def MIN(self, *args: Any) -> Any:
        return self._elementwise_extreme(args, "MIN")

    def _elementwise_extreme(self, args: Sequence[Any], which: str) -> Any:
        if not args:
            raise WH6EvaluationError(f"{which} needs at least one argument")
        if not any(isinstance(arg, pd.Series) for arg in args):
            return max(args) if which == "MAX" else min(args)
        arrays = [self.series(arg, dtype="float64").to_numpy() for arg in args]
        function = np.maximum if which == "MAX" else np.minimum
        result = arrays[0]
        for array in arrays[1:]:
            result = function(result, array)
        return pd.Series(result, index=self.index)

    def IF(self, condition: Any, yes: Any, no: Any) -> pd.Series:
        return self._if(condition, yes, no)

    def IFELSE(self, condition: Any, yes: Any, no: Any) -> pd.Series:
        return self._if(condition, yes, no)

    def _if(self, condition: Any, yes: Any, no: Any) -> pd.Series:
        condition_series = self.series(condition).fillna(False).astype(bool)
        yes_series = self.series(yes, dtype="float64")
        no_series = self.series(no, dtype="float64")
        return pd.Series(np.where(condition_series, yes_series, no_series), index=self.index)

    def REF(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "REF", allow_zero=True)
        return self.series(value, dtype="float64").shift(window)

    def MA(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "MA")
        return self.series(value, dtype="float64").rolling(window, min_periods=window).mean()

    def SUM(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "SUM", allow_zero=True)
        series = self.series(value, dtype="float64")
        return series.cumsum() if window == 0 else series.rolling(window, min_periods=window).sum()

    def HHV(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "HHV")
        return self.series(value, dtype="float64").rolling(window, min_periods=window).max()

    def LLV(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "LLV")
        return self.series(value, dtype="float64").rolling(window, min_periods=window).min()

    def STD(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "STD")
        return self._rolling_std(self.series(value, dtype="float64"), window)

    def AVEDEV(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "AVEDEV")
        return self.series(value, dtype="float64").rolling(
            window, min_periods=window
        ).apply(lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True)

    def COUNT(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "COUNT")
        values = self.series(value).fillna(False).astype(bool).astype(float)
        return values.rolling(window, min_periods=window).sum()

    def EMA(self, value: Any, window_value: Any) -> pd.Series:
        return self._ema(value, window_value, "EMA")

    def EMA2(self, value: Any, window_value: Any) -> pd.Series:
        return self._ema(value, window_value, "EMA2")

    def _ema(self, value: Any, window_value: Any, name: str) -> pd.Series:
        window = _integral_window(window_value, name)
        alpha = 2.0 / (window + 1.0)
        return self.series(value, dtype="float64").ewm(
            alpha=alpha, adjust=False, min_periods=window
        ).mean()

    def SMA(self, value: Any, window_value: Any, weight_value: Any) -> pd.Series:
        window = _integral_window(window_value, "SMA")
        weight = float(weight_value)
        if not math.isfinite(weight) or not (0 < weight <= window):
            raise WH6EvaluationError(f"SMA invalid M={weight_value!r} for N={window}")
        return self._recursive_sma(self.series(value, dtype="float64"), weight / window)

    def CJLVOL(self, *args: Any) -> pd.Series:
        if len(args) > 1:
            raise WH6EvaluationError("CJLVOL accepts zero or one mode argument")
        return self.fields["VOL"]

    def FORCAST(self, value: Any, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "FORCAST")
        return self._forcast(self.series(value, dtype="float64"), window)

    def VOLATILITY(self, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "VOLATILITY")
        returns = self.fields["CLOSE"] / self.fields["CLOSE"].shift(1) - 1.0
        return self._rolling_std(returns, window)

    def SAR(self, window_value: Any, step: Any, maximum: Any) -> pd.Series:
        return self._sar(
            _integral_window(window_value, "SAR"), float(step), float(maximum), sar1=False
        )

    def SAR1(self, window_value: Any, step: Any, maximum: Any) -> pd.Series:
        return self._sar(
            _integral_window(window_value, "SAR1"), float(step), float(maximum), sar1=True
        )

    def CROSS(self, left_value: Any, right_value: Any) -> pd.Series:
        left = self.series(left_value, dtype="float64")
        right = self.series(right_value, dtype="float64")
        return (left > right) & (left.shift(1) <= right.shift(1))

    def RISING(self, window_value: Any) -> pd.Series:
        window = _integral_window(window_value, "RISING")
        close = self.fields["CLOSE"]
        return close > close.shift(window)

    @staticmethod
    def _recursive_sma(series: pd.Series, alpha: float) -> pd.Series:
        out = np.full(len(series), np.nan, dtype="float64")
        previous = np.nan
        for index, value in enumerate(
            series.to_numpy(dtype="float64", na_value=np.nan)
        ):
            if np.isnan(value):
                out[index] = previous
            elif np.isnan(previous):
                previous = value
                out[index] = value
            else:
                previous = alpha * value + (1.0 - alpha) * previous
                out[index] = previous
        return pd.Series(out, index=series.index)

    @staticmethod
    def _forcast(series: pd.Series, window: int) -> pd.Series:
        x = np.arange(window, dtype="float64")
        x_mean = x.mean()
        denominator = float(np.square(x - x_mean).sum())

        def endpoint(values: np.ndarray) -> float:
            y_mean = values.mean()
            slope = float(((x - x_mean) * (values - y_mean)).sum() / denominator)
            return y_mean + slope * (window - 1 - x_mean)

        return series.rolling(window, min_periods=window).apply(endpoint, raw=True)

    @staticmethod
    def _rolling_std(series: pd.Series, window: int) -> pd.Series:
        rolling = series.rolling(window, min_periods=window)
        result = rolling.std(ddof=0)
        constant = (rolling.max() - rolling.min()) == 0
        return result.mask(constant, 0.0)

    def _sar(self, window: int, step: float, maximum: float, *, sar1: bool) -> pd.Series:
        if not (0 < step <= maximum <= 1):
            name = "SAR1" if sar1 else "SAR"
            raise WH6EvaluationError(f"{name} invalid step/max: {step}, {maximum}")
        high = self.fields["HIGH"].to_numpy(dtype="float64", na_value=np.nan)
        low = self.fields["LOW"].to_numpy(dtype="float64", na_value=np.nan)
        close = self.fields["CLOSE"].to_numpy(dtype="float64", na_value=np.nan)
        out = np.full(len(high), np.nan, dtype="float64")
        if len(high) == 0:
            return pd.Series(out, index=self.index)

        _ = window, close, sar1
        trend_up = True
        ep = high[0]
        sar = low[0]
        af = step
        out[0] = sar

        for index in range(1, len(high)):
            if np.isnan(high[index]) or np.isnan(low[index]):
                out[index] = sar
                continue
            candidate = sar + af * (ep - sar)
            if trend_up:
                previous_low = low[index - 2] if index >= 2 else low[index - 1]
                candidate = min(candidate, low[index - 1], previous_low)
                if low[index] < candidate:
                    trend_up = False
                    sar = ep
                    ep = low[index]
                    af = step
                else:
                    sar = candidate
                    if high[index] > ep:
                        ep = high[index]
                        af = min(maximum, af + step)
            else:
                previous_high = high[index - 2] if index >= 2 else high[index - 1]
                candidate = max(candidate, high[index - 1], previous_high)
                if high[index] > candidate:
                    trend_up = True
                    sar = ep
                    ep = high[index]
                    af = step
                else:
                    sar = candidate
                    if low[index] < ep:
                        ep = low[index]
                        af = min(maximum, af + step)
            out[index] = sar

        return pd.Series(out, index=self.index)
