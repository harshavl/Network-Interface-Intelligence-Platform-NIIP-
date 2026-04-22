"""Tests for CSV ingestion."""

from __future__ import annotations

import io

import pytest

from app.core import DataIngestionException
from app.utils import CSVLoader


def test_load_basic_csv(sample_csv_content):
    metrics = CSVLoader.load_from_string(sample_csv_content)
    assert len(metrics) == 3
    assert metrics[0].device_name == "rtr-01"
    assert metrics[0].interface_name == "Gi0/1"


def test_load_handles_aliased_columns():
    """Headers with spaces, mixed case, and 'last 1 hour' phrasing should normalize."""
    content = (
        "Device Name, Interface Name, Interface Description, "
        "In UtilizationPercent, Out Utilization Percent, "
        "In Errors last 1 hour, Out Errors last 1 hour, "
        "In Discards last 1 hour, Out Discards last 1 hour\n"
        "rtr-01,Gi0/1,desc,10,12,0,0,0,0\n"
    )
    metrics = CSVLoader.load_from_string(content)
    assert len(metrics) == 1
    assert metrics[0].in_utilization_percent == 10.0


def test_load_rejects_missing_columns():
    bad = "device_name,interface_name\nrtr-01,Gi0/1\n"
    with pytest.raises(DataIngestionException) as exc_info:
        CSVLoader.load_from_string(bad)
    assert "missing" in exc_info.value.message.lower()


def test_load_rejects_empty_file():
    with pytest.raises(DataIngestionException):
        CSVLoader.load_from_string("")


def test_load_clips_invalid_utilization():
    content = (
        "device_name,interface_name,interface_description,"
        "in_utilization_percent,out_utilization_percent,"
        "in_errors_1h,out_errors_1h,in_discards_1h,out_discards_1h\n"
        "rtr-01,Gi0/1,desc,150.0,-5.0,0,0,0,0\n"
    )
    metrics = CSVLoader.load_from_string(content)
    assert metrics[0].in_utilization_percent == 100.0
    assert metrics[0].out_utilization_percent == 0.0


def test_load_handles_missing_description():
    """Description column is optional."""
    content = (
        "device_name,interface_name,"
        "in_utilization_percent,out_utilization_percent,"
        "in_errors_1h,out_errors_1h,in_discards_1h,out_discards_1h\n"
        "rtr-01,Gi0/1,10.0,12.0,0,0,0,0\n"
    )
    metrics = CSVLoader.load_from_string(content)
    assert metrics[0].interface_description == ""


def test_load_from_filelike(sample_csv_content):
    f = io.StringIO(sample_csv_content)
    metrics = CSVLoader.load(f)
    assert len(metrics) == 3
