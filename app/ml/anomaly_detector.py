"""
Anomaly Detection Engine.

Combines two complementary approaches:

1. **Multivariate Isolation Forest** — finds rows that are jointly unusual
   across all metrics. This catches subtle combinations (e.g. moderate
   utilization + moderate errors + moderate discards) that no single
   threshold would flag.

2. **Univariate Z-score on metric distribution** — flags individual
   metrics that are statistically far above the population mean.

The two methods are unioned. Static threshold rules supplement them so
the system has sane behavior on tiny datasets where Isolation Forest is
unreliable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.core import MLEngineException, Settings, get_logger
from app.models import Anomaly, AnomalyType, InterfaceMetric, Severity

logger = get_logger(__name__)

_FEATURE_COLUMNS = [
    "in_utilization_percent",
    "out_utilization_percent",
    "in_errors_1h",
    "out_errors_1h",
    "in_discards_1h",
    "out_discards_1h",
]

_MIN_ROWS_FOR_ML = 5
_Z_SCORE_THRESHOLD = 2.5
_ASYMMETRY_THRESHOLD = 30.0  # percent points


class AnomalyDetectionEngine:
    """Detect anomalies in a batch of interface metrics."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(
        self, metrics: list[InterfaceMetric]
    ) -> dict[str, list[Anomaly]]:
        """
        Return a mapping of `interface_id -> list[Anomaly]`.

        Empty lists are included for clean interfaces so callers can
        rely on the key being present.
        """
        if not metrics:
            return {}

        try:
            df = self._build_dataframe(metrics)
            results: dict[str, list[Anomaly]] = {m.interface_id: [] for m in metrics}

            self._apply_threshold_rules(df, results)
            self._apply_asymmetry_rule(df, results)

            if len(df) >= _MIN_ROWS_FOR_ML:
                self._apply_zscore_detection(df, results)
                self._apply_isolation_forest(df, results)
            else:
                logger.info(
                    "skipping_ml_anomaly_detection",
                    reason="insufficient_rows",
                    row_count=len(df),
                    min_required=_MIN_ROWS_FOR_ML,
                )

            return results
        except Exception as exc:
            logger.exception("anomaly_detection_failed", error=str(exc))
            raise MLEngineException(
                "Anomaly detection failed",
                details={"underlying": str(exc)},
            ) from exc

    # ---------------- helpers ----------------

    def _build_dataframe(self, metrics: list[InterfaceMetric]) -> pd.DataFrame:
        rows = [
            {
                "interface_id": m.interface_id,
                **{col: getattr(m, col) for col in _FEATURE_COLUMNS},
            }
            for m in metrics
        ]
        return pd.DataFrame(rows)

    def _apply_threshold_rules(
        self, df: pd.DataFrame, results: dict[str, list[Anomaly]]
    ) -> None:
        """Hard rules — apply regardless of dataset size."""
        for _, row in df.iterrows():
            iid = row["interface_id"]

            max_util = max(row["in_utilization_percent"], row["out_utilization_percent"])
            if max_util >= self.settings.util_critical_threshold:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.UTILIZATION_HIGH,
                        severity=Severity.HIGH,
                        description=(
                            f"Utilization at {max_util:.1f}% exceeds critical "
                            f"threshold ({self.settings.util_critical_threshold}%)"
                        ),
                        metric_value=round(max_util, 2),
                    )
                )
            elif max_util >= self.settings.util_warning_threshold:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.UTILIZATION_HIGH,
                        severity=Severity.MEDIUM,
                        description=(
                            f"Utilization at {max_util:.1f}% above warning "
                            f"threshold ({self.settings.util_warning_threshold}%)"
                        ),
                        metric_value=round(max_util, 2),
                    )
                )

            total_errors = int(row["in_errors_1h"] + row["out_errors_1h"])
            if total_errors >= self.settings.error_critical_threshold:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.ERROR_SPIKE,
                        severity=Severity.HIGH,
                        description=f"{total_errors} interface errors in last hour",
                        metric_value=total_errors,
                    )
                )
            elif total_errors >= self.settings.error_warning_threshold:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.ERROR_SPIKE,
                        severity=Severity.MEDIUM,
                        description=f"{total_errors} interface errors in last hour",
                        metric_value=total_errors,
                    )
                )

            total_discards = int(row["in_discards_1h"] + row["out_discards_1h"])
            if total_discards >= self.settings.discard_critical_threshold:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.DISCARD_SPIKE,
                        severity=Severity.HIGH,
                        description=(
                            f"{total_discards} discards in last hour — "
                            "indicates buffer exhaustion or congestion"
                        ),
                        metric_value=total_discards,
                    )
                )
            elif total_discards >= self.settings.discard_warning_threshold:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.DISCARD_SPIKE,
                        severity=Severity.MEDIUM,
                        description=f"{total_discards} discards in last hour",
                        metric_value=total_discards,
                    )
                )

    def _apply_asymmetry_rule(
        self, df: pd.DataFrame, results: dict[str, list[Anomaly]]
    ) -> None:
        """Flag asymmetric in/out utilization — often a sign of misconfiguration."""
        for _, row in df.iterrows():
            iid = row["interface_id"]
            diff = abs(row["in_utilization_percent"] - row["out_utilization_percent"])
            min_util = min(row["in_utilization_percent"], row["out_utilization_percent"])
            # Only flag when at least one side has meaningful traffic
            if diff >= _ASYMMETRY_THRESHOLD and min_util >= 5.0:
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.UTILIZATION_ASYMMETRIC,
                        severity=Severity.LOW,
                        description=(
                            f"Asymmetric in/out utilization "
                            f"(in={row['in_utilization_percent']:.1f}%, "
                            f"out={row['out_utilization_percent']:.1f}%)"
                        ),
                        metric_value=round(diff, 2),
                    )
                )

    def _apply_zscore_detection(
        self, df: pd.DataFrame, results: dict[str, list[Anomaly]]
    ) -> None:
        """Flag rows whose metrics are >Z-score standard deviations from mean."""
        for col in _FEATURE_COLUMNS:
            std = df[col].std()
            if std == 0 or np.isnan(std):
                continue
            mean = df[col].mean()
            z_scores = (df[col] - mean) / std
            outliers = df[z_scores.abs() > _Z_SCORE_THRESHOLD]
            for _, row in outliers.iterrows():
                iid = row["interface_id"]
                # Avoid duplicate-flagging metrics already caught by thresholds
                already_flagged = {a.type for a in results[iid]}
                if "error" in col and AnomalyType.ERROR_SPIKE in already_flagged:
                    continue
                if "discard" in col and AnomalyType.DISCARD_SPIKE in already_flagged:
                    continue
                if "utilization" in col and AnomalyType.UTILIZATION_HIGH in already_flagged:
                    continue
                results[iid].append(
                    Anomaly(
                        type=AnomalyType.MULTIVARIATE_OUTLIER,
                        severity=Severity.LOW,
                        description=(
                            f"Statistical outlier on {col} "
                            f"(value={row[col]:.2f}, mean={mean:.2f})"
                        ),
                        metric_value=round(float(row[col]), 2),
                        baseline_value=round(float(mean), 2),
                    )
                )

    def _apply_isolation_forest(
        self, df: pd.DataFrame, results: dict[str, list[Anomaly]]
    ) -> None:
        """Multivariate Isolation Forest on the feature matrix."""
        x = df[_FEATURE_COLUMNS].values
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x)

        model = IsolationForest(
            contamination=self.settings.anomaly_contamination,
            random_state=self.settings.anomaly_random_state,
            n_estimators=100,
        )
        predictions = model.fit_predict(x_scaled)
        scores = model.score_samples(x_scaled)

        for idx, (pred, score) in enumerate(zip(predictions, scores)):
            if pred != -1:
                continue
            iid = df.iloc[idx]["interface_id"]
            # Skip if already caught by stronger rules
            if any(a.severity in (Severity.HIGH, Severity.CRITICAL) for a in results[iid]):
                continue
            severity = Severity.MEDIUM if score < -0.6 else Severity.LOW
            results[iid].append(
                Anomaly(
                    type=AnomalyType.MULTIVARIATE_OUTLIER,
                    severity=severity,
                    description=(
                        "Multivariate anomaly across utilization/errors/discards "
                        f"(isolation score={score:.3f})"
                    ),
                    metric_value=round(float(score), 4),
                )
            )
