"""
CSV ingestion utility.

LogicMonitor exports vary in column casing and spacing across versions
and customer configurations. This module normalizes column names to a
canonical schema and produces validated `InterfaceMetric` instances.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import IO, Union

import pandas as pd

from app.core import DataIngestionException, get_logger
from app.models import InterfaceMetric

logger = get_logger(__name__)

# Map normalized column names → canonical names
_COLUMN_ALIASES: dict[str, str] = {
    # device
    "device": "device_name",
    "devicename": "device_name",
    "device_name": "device_name",
    "host": "device_name",
    "hostname": "device_name",
    # interface
    "interface": "interface_name",
    "interfacename": "interface_name",
    "interface_name": "interface_name",
    "ifname": "interface_name",
    # description
    "description": "interface_description",
    "interfacedescription": "interface_description",
    "interface_description": "interface_description",
    "ifdescr": "interface_description",
    # utilization
    "inutilizationpercent": "in_utilization_percent",
    "in_utilization_percent": "in_utilization_percent",
    "inutilization": "in_utilization_percent",
    "inputilization": "in_utilization_percent",
    "oututilizationpercent": "out_utilization_percent",
    "out_utilization_percent": "out_utilization_percent",
    "oututilization": "out_utilization_percent",
    "outputilization": "out_utilization_percent",
    # errors
    "inerrorslast1hour": "in_errors_1h",
    "in_errors_last_1_hour": "in_errors_1h",
    "in_errors_1h": "in_errors_1h",
    "inerrors": "in_errors_1h",
    "outerrorslast1hour": "out_errors_1h",
    "out_errors_last_1_hour": "out_errors_1h",
    "out_errors_1h": "out_errors_1h",
    "outerrors": "out_errors_1h",
    # discards
    "indiscardslast1hour": "in_discards_1h",
    "in_discards_last_1_hour": "in_discards_1h",
    "in_discards_1h": "in_discards_1h",
    "indiscards": "in_discards_1h",
    "outdiscardslast1hour": "out_discards_1h",
    "out_discards_last_1_hour": "out_discards_1h",
    "out_discards_1h": "out_discards_1h",
    "outdiscards": "out_discards_1h",
}

_REQUIRED_COLUMNS = {
    "device_name",
    "interface_name",
    "in_utilization_percent",
    "out_utilization_percent",
    "in_errors_1h",
    "out_errors_1h",
    "in_discards_1h",
    "out_discards_1h",
}


class CSVLoader:
    """Load and normalize LogicMonitor-style CSV files."""

    @staticmethod
    def load(source: Union[str, Path, IO]) -> list[InterfaceMetric]:
        """
        Load metrics from a file path or file-like object.

        Raises `DataIngestionException` on schema or parse failure.
        """
        try:
            if isinstance(source, (str, Path)):
                df = pd.read_csv(source, skipinitialspace=True)
            else:
                df = pd.read_csv(source, skipinitialspace=True)
        except pd.errors.EmptyDataError as exc:
            raise DataIngestionException("CSV file is empty") from exc
        except pd.errors.ParserError as exc:
            raise DataIngestionException(
                "Failed to parse CSV file",
                details={"underlying": str(exc)},
            ) from exc
        except UnicodeDecodeError as exc:
            raise DataIngestionException(
                "CSV file is not valid UTF-8 — please re-export as UTF-8",
                details={"underlying": str(exc)},
            ) from exc

        df = CSVLoader._normalize_columns(df)
        CSVLoader._validate_columns(df)

        # Description is optional — fill if missing
        if "interface_description" not in df.columns:
            df["interface_description"] = ""

        df = CSVLoader._coerce_types(df)

        metrics: list[InterfaceMetric] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                metrics.append(
                    InterfaceMetric(
                        device_name=str(row["device_name"]).strip(),
                        interface_name=str(row["interface_name"]).strip(),
                        interface_description=str(row.get("interface_description", "")).strip(),
                        in_utilization_percent=float(row["in_utilization_percent"]),
                        out_utilization_percent=float(row["out_utilization_percent"]),
                        in_errors_1h=int(row["in_errors_1h"]),
                        out_errors_1h=int(row["out_errors_1h"]),
                        in_discards_1h=int(row["in_discards_1h"]),
                        out_discards_1h=int(row["out_discards_1h"]),
                    )
                )
            except (ValueError, TypeError) as exc:
                errors.append(f"Row {idx + 2}: {exc}")  # +2 = header + 1-based

        if errors and not metrics:
            raise DataIngestionException(
                "Every CSV row failed validation",
                details={"errors": errors[:10]},
            )

        if errors:
            logger.warning(
                "csv_partial_load",
                loaded=len(metrics),
                failed=len(errors),
                first_errors=errors[:5],
            )

        logger.info("csv_loaded", row_count=len(metrics), failed_rows=len(errors))
        return metrics

    @staticmethod
    def load_from_string(content: str) -> list[InterfaceMetric]:
        """Convenience for loading from in-memory CSV text."""
        return CSVLoader.load(io.StringIO(content))

    # ---------------- helpers ----------------

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Strip, lower-case, and resolve aliases to canonical names."""
        rename_map: dict[str, str] = {}
        for col in df.columns:
            normalized = re.sub(r"[\s_\-%]+", "", str(col).strip().lower())
            normalized = normalized.replace("(", "").replace(")", "")
            if normalized in _COLUMN_ALIASES:
                rename_map[col] = _COLUMN_ALIASES[normalized]
        return df.rename(columns=rename_map)

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        missing = _REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise DataIngestionException(
                "CSV is missing required columns",
                details={
                    "missing": sorted(missing),
                    "found": sorted(df.columns.tolist()),
                },
            )

    @staticmethod
    def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
        """Force numeric columns; coerce errors to NaN, then fill with 0."""
        numeric_cols = [
            "in_utilization_percent",
            "out_utilization_percent",
            "in_errors_1h",
            "out_errors_1h",
            "in_discards_1h",
            "out_discards_1h",
        ]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Clip utilization to valid 0-100
        df["in_utilization_percent"] = df["in_utilization_percent"].clip(0, 100)
        df["out_utilization_percent"] = df["out_utilization_percent"].clip(0, 100)
        return df
