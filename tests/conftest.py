"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import create_app
from app.core import Settings, get_settings
from app.models import InterfaceMetric


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture()
def app(settings):
    app = create_app(settings)
    app.config["TESTING"] = True
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def healthy_metric() -> InterfaceMetric:
    return InterfaceMetric(
        device_name="test-rtr-01",
        interface_name="Gi0/1",
        interface_description="Test healthy interface",
        in_utilization_percent=10.0,
        out_utilization_percent=12.0,
        in_errors_1h=0,
        out_errors_1h=0,
        in_discards_1h=0,
        out_discards_1h=0,
    )


@pytest.fixture()
def congested_metric() -> InterfaceMetric:
    return InterfaceMetric(
        device_name="test-rtr-01",
        interface_name="Gi0/2",
        interface_description="Test congested interface",
        in_utilization_percent=92.0,
        out_utilization_percent=89.5,
        in_errors_1h=0,
        out_errors_1h=0,
        in_discards_1h=400,
        out_discards_1h=350,
    )


@pytest.fixture()
def physical_layer_issue_metric() -> InterfaceMetric:
    return InterfaceMetric(
        device_name="test-rtr-01",
        interface_name="Gi0/3",
        interface_description="Bad SFP",
        in_utilization_percent=8.0,
        out_utilization_percent=7.0,
        in_errors_1h=200,
        out_errors_1h=10,
        in_discards_1h=0,
        out_discards_1h=0,
    )


@pytest.fixture()
def sample_csv_content() -> str:
    return (
        "device_name,interface_name,interface_description,"
        "in_utilization_percent,out_utilization_percent,"
        "in_errors_1h,out_errors_1h,in_discards_1h,out_discards_1h\n"
        "rtr-01,Gi0/1,Healthy,10.0,12.0,0,0,0,0\n"
        "rtr-01,Gi0/2,Congested,92.0,89.0,0,0,400,350\n"
        "rtr-01,Gi0/3,BadSFP,8.0,7.0,200,10,0,0\n"
    )
