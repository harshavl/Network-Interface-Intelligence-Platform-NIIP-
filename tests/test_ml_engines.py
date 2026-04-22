"""Unit tests for the four ML engines."""

from __future__ import annotations

from app.core import get_settings
from app.ml import (
    AnomalyDetectionEngine,
    ForecastingEngine,
    HealthScoringEngine,
    RootCauseEngine,
)
from app.models import AnomalyType, HealthStatus, Severity


def test_anomaly_engine_flags_high_utilization(congested_metric):
    engine = AnomalyDetectionEngine(get_settings())
    result = engine.detect([congested_metric])
    anomalies = result[congested_metric.interface_id]
    types = {a.type for a in anomalies}
    assert AnomalyType.UTILIZATION_HIGH in types
    assert AnomalyType.DISCARD_SPIKE in types


def test_anomaly_engine_clean_for_healthy(healthy_metric):
    engine = AnomalyDetectionEngine(get_settings())
    result = engine.detect([healthy_metric])
    assert result[healthy_metric.interface_id] == []


def test_anomaly_engine_handles_empty_input():
    engine = AnomalyDetectionEngine(get_settings())
    assert engine.detect([]) == {}


def test_forecast_already_breached(congested_metric):
    engine = ForecastingEngine(get_settings())
    forecast = engine.forecast_snapshot(congested_metric)
    assert forecast is not None
    assert forecast.predicted_80pct_breach == "ALREADY_BREACHED"
    assert forecast.days_until_capacity == 0
    assert forecast.trend == "critical"


def test_forecast_returns_none_for_idle(healthy_metric):
    """Idle interfaces (<5% util) should not be forecast."""
    engine = ForecastingEngine(get_settings())
    # healthy_metric has 10% which is >5, so use a different one
    from app.models import InterfaceMetric

    idle = InterfaceMetric(
        device_name="d", interface_name="i", interface_description="",
        in_utilization_percent=1.0, out_utilization_percent=1.0,
        in_errors_1h=0, out_errors_1h=0, in_discards_1h=0, out_discards_1h=0,
    )
    assert engine.forecast_snapshot(idle) is None


def test_forecast_projects_for_moderate_utilization():
    from app.models import InterfaceMetric

    engine = ForecastingEngine(get_settings())
    metric = InterfaceMetric(
        device_name="d", interface_name="i", interface_description="",
        in_utilization_percent=50.0, out_utilization_percent=45.0,
        in_errors_1h=0, out_errors_1h=0, in_discards_1h=0, out_discards_1h=0,
    )
    forecast = engine.forecast_snapshot(metric)
    assert forecast is not None
    assert forecast.days_until_capacity is not None
    assert forecast.days_until_capacity > 0
    assert forecast.predicted_80pct_breach != "ALREADY_BREACHED"


def test_root_cause_congestion(congested_metric):
    engine = RootCauseEngine(get_settings())
    anomaly_engine = AnomalyDetectionEngine(get_settings())
    anomalies = anomaly_engine.detect([congested_metric])[congested_metric.interface_id]
    suggestion = engine.suggest(congested_metric, anomalies)
    assert suggestion is not None
    assert "congestion" in suggestion.probable_cause.lower()
    assert suggestion.confidence >= 0.9
    assert len(suggestion.recommended_actions) >= 2


def test_root_cause_physical_layer(physical_layer_issue_metric):
    engine = RootCauseEngine(get_settings())
    anomaly_engine = AnomalyDetectionEngine(get_settings())
    anomalies = anomaly_engine.detect([physical_layer_issue_metric])[
        physical_layer_issue_metric.interface_id
    ]
    suggestion = engine.suggest(physical_layer_issue_metric, anomalies)
    assert suggestion is not None
    assert "physical" in suggestion.probable_cause.lower()


def test_root_cause_returns_none_for_no_anomalies(healthy_metric):
    engine = RootCauseEngine(get_settings())
    assert engine.suggest(healthy_metric, []) is None


def test_health_score_perfect_for_healthy(healthy_metric):
    engine = HealthScoringEngine(get_settings())
    score, status = engine.score(healthy_metric, [])
    assert score >= 90
    assert status == HealthStatus.HEALTHY


def test_health_score_low_for_critical(congested_metric):
    engine = HealthScoringEngine(get_settings())
    anomaly_engine = AnomalyDetectionEngine(get_settings())
    anomalies = anomaly_engine.detect([congested_metric])[congested_metric.interface_id]
    score, status = engine.score(congested_metric, anomalies)
    assert score < 50
    assert status == HealthStatus.CRITICAL


def test_health_score_bounded_0_to_100():
    """Score must always be in [0, 100]."""
    from app.models import InterfaceMetric, Anomaly

    engine = HealthScoringEngine(get_settings())
    extreme = InterfaceMetric(
        device_name="d", interface_name="i", interface_description="",
        in_utilization_percent=100.0, out_utilization_percent=100.0,
        in_errors_1h=99999, out_errors_1h=99999,
        in_discards_1h=99999, out_discards_1h=99999,
    )
    fake_anomalies = [
        Anomaly(
            type=AnomalyType.UTILIZATION_HIGH,
            severity=Severity.CRITICAL,
            description="x",
            metric_value=100,
        )
    ] * 10
    score, _ = engine.score(extreme, fake_anomalies)
    assert 0 <= score <= 100
