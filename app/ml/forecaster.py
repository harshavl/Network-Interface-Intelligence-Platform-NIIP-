"""
Forecasting Engine.

In a single-snapshot scenario (one CSV row per interface), the engine
estimates capacity timing using a population-aware heuristic:

  - If utilization is already over the critical threshold → ALREADY_BREACHED
  - Else, estimate days-until-80% from a baseline growth rate

When the system is later extended to ingest historical time series, the
`forecast_series` method does proper Holt-Winters exponential smoothing
on per-interface history. Both code paths are exposed so the API can
evolve without breaking callers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

from app.core import MLEngineException, Settings, get_logger
from app.models import Forecast, InterfaceMetric

logger = get_logger(__name__)

_TARGET_UTILIZATION = 80.0
_DEFAULT_GROWTH_PCT_PER_MONTH = 5.0  # conservative baseline growth assumption
_MAX_FORECAST_DAYS = 365


class ForecastingEngine:
    """Forecast capacity timing for interfaces."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ---------------- single-snapshot mode ----------------

    def forecast_snapshot(
        self, metric: InterfaceMetric
    ) -> Optional[Forecast]:
        """
        Forecast based on a single snapshot reading.

        Returns `None` for interfaces with negligible utilization where
        forecasting would be meaningless.
        """
        try:
            current = metric.max_utilization

            if current < 5.0:
                return None  # idle interface, forecasting not informative

            if current >= self.settings.util_critical_threshold:
                return Forecast(
                    predicted_80pct_breach="ALREADY_BREACHED",
                    days_until_capacity=0,
                    trend="critical",
                    confidence=0.95,
                    method="snapshot_threshold",
                )

            if current >= _TARGET_UTILIZATION:
                return Forecast(
                    predicted_80pct_breach="ALREADY_BREACHED",
                    days_until_capacity=0,
                    trend="critical",
                    confidence=0.90,
                    method="snapshot_threshold",
                )

            # Linear projection at baseline growth rate
            headroom = _TARGET_UTILIZATION - current
            growth_per_day = _DEFAULT_GROWTH_PCT_PER_MONTH / 30.0
            days = int(headroom / growth_per_day)
            days = min(days, _MAX_FORECAST_DAYS)

            breach_date = datetime.now(timezone.utc) + timedelta(days=days)

            if days <= 7:
                trend = "critical"
            elif days <= 30:
                trend = "increasing"
            elif days <= 90:
                trend = "stable"
            else:
                trend = "stable"

            # Confidence is intentionally low for snapshot-based forecasts
            return Forecast(
                predicted_80pct_breach=breach_date.date().isoformat(),
                days_until_capacity=days,
                trend=trend,
                confidence=0.45,
                method="snapshot_linear_projection",
            )
        except Exception as exc:
            logger.exception("snapshot_forecast_failed", error=str(exc))
            raise MLEngineException(
                "Snapshot forecast failed",
                details={"underlying": str(exc), "interface": metric.interface_id},
            ) from exc

    # ---------------- time-series mode ----------------

    def forecast_series(
        self,
        history: pd.Series,
        forecast_days: int = 30,
    ) -> Optional[Forecast]:
        """
        Forecast from a historical time series of utilization values.

        `history` must be a pandas Series indexed by datetime, with
        values in percent (0–100). At least 14 observations recommended.
        """
        try:
            if history is None or len(history) < 7:
                logger.info("series_forecast_skipped", reason="insufficient_history")
                return None

            history = history.dropna().sort_index()
            if len(history) < 7:
                return None

            # Lazy-import statsmodels to keep cold-start cheap
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            try:
                model = ExponentialSmoothing(
                    history.values,
                    trend="add",
                    seasonal=None,
                    initialization_method="estimated",
                )
                fit = model.fit(optimized=True)
                forecast_values = fit.forecast(forecast_days)
            except Exception as fit_err:
                logger.warning("holtwinters_fit_failed", error=str(fit_err))
                # Fallback: simple linear regression on time
                forecast_values = self._linear_fallback(history, forecast_days)

            # Find first day forecast crosses the target
            breach_idx = None
            for i, v in enumerate(forecast_values):
                if v >= _TARGET_UTILIZATION:
                    breach_idx = i
                    break

            current = float(history.iloc[-1])
            if breach_idx is None:
                # Won't breach in the forecast window
                return Forecast(
                    predicted_80pct_breach=None,
                    days_until_capacity=None,
                    trend=self._compute_trend(history),
                    confidence=0.7,
                    method="holt_winters",
                )

            breach_date = (datetime.now(timezone.utc) + timedelta(days=breach_idx)).date()
            return Forecast(
                predicted_80pct_breach=breach_date.isoformat(),
                days_until_capacity=breach_idx,
                trend=self._compute_trend(history),
                confidence=0.75,
                method="holt_winters",
            )
        except Exception as exc:
            logger.exception("series_forecast_failed", error=str(exc))
            raise MLEngineException(
                "Series forecast failed",
                details={"underlying": str(exc)},
            ) from exc

    # ---------------- helpers ----------------

    @staticmethod
    def _linear_fallback(history: pd.Series, forecast_days: int) -> np.ndarray:
        x = np.arange(len(history))
        y = history.values
        slope, intercept = np.polyfit(x, y, 1)
        future_x = np.arange(len(history), len(history) + forecast_days)
        return slope * future_x + intercept

    @staticmethod
    def _compute_trend(history: pd.Series) -> str:
        if len(history) < 2:
            return "stable"
        x = np.arange(len(history))
        slope, _ = np.polyfit(x, history.values, 1)
        if slope > 0.5:
            return "increasing"
        elif slope < -0.5:
            return "decreasing"
        return "stable"
