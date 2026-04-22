"""
Command-line interface.

Usage:
    python -m app.cli analyze data/input/sample.csv
    python -m app.cli analyze data/input/sample.csv --format table
    python -m app.cli analyze data/input/sample.csv -o report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core import NIIPException, configure_logging, get_settings
from app.services import AnalysisService
from app.utils import CSVLoader, serialize_report


def _format_table(report_dict: dict) -> str:
    """Pretty-print a compact summary table."""
    lines = []
    s = report_dict["summary"]
    lines.append("=" * 78)
    lines.append("NIIP — Analysis Summary")
    lines.append("=" * 78)
    lines.append(f"Timestamp:           {report_dict['analysis_timestamp']}")
    lines.append(f"Total interfaces:    {s['total_interfaces']}")
    lines.append(f"  Healthy:           {s['healthy_count']}")
    lines.append(f"  Warning:           {s['warning_count']}")
    lines.append(f"  Critical:          {s['critical_count']}")
    lines.append(f"Anomalies detected:  {s['anomalies_detected']}")
    lines.append(f"Forecasts generated: {s['forecasts_generated']}")
    lines.append(f"Root causes found:   {s['root_causes_identified']}")
    lines.append(f"Avg health score:    {s['avg_health_score']}")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"{'Device':<22}{'Interface':<28}{'Score':>6}  {'Status':<10}{'Anomalies':>10}")
    lines.append("-" * 78)
    for iface in report_dict["interfaces"]:
        lines.append(
            f"{iface['device'][:21]:<22}"
            f"{iface['interface'][:27]:<28}"
            f"{iface['health_score']:>6}  "
            f"{iface['status']:<10}"
            f"{len(iface['anomalies']):>10}"
        )
    lines.append("-" * 78)
    return "\n".join(lines)


def cmd_analyze(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings)

    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        return 2

    try:
        metrics = CSVLoader.load(csv_path)
        service = AnalysisService(settings)
        report = service.analyze(metrics)
        report_dict = serialize_report(report)
    except NIIPException as exc:
        print(f"ERROR: {exc.message}", file=sys.stderr)
        if exc.details:
            print(json.dumps(exc.details, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: unexpected: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        output = json.dumps(report_dict, indent=2)
    else:
        output = _format_table(report_dict)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="niip",
        description="Network Interface Intelligence Platform CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Analyze a LogicMonitor CSV file")
    p_analyze.add_argument("input", help="Path to the input CSV file")
    p_analyze.add_argument(
        "-f",
        "--format",
        choices=("json", "table"),
        default="table",
        help="Output format (default: table)",
    )
    p_analyze.add_argument(
        "-o", "--output", help="Write output to file instead of stdout"
    )
    p_analyze.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
