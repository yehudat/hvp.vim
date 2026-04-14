#!/usr/bin/env python3
"""Generate a structured markdown page from a Synopsys HVP verification plan.

Usage:
    python3 hvp_to_markdown.py --file <path-to-hvp>
    python3 hvp_to_markdown.py --json <path-to-json>
    python3 hvp_to_markdown.py --file <path-to-hvp> --output <path-to-md>

Reads an HVP file directly (or pre-parsed JSON from parse_hvp.py via --json)
and generates a Confluence-ready markdown page.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Loader -- import parse_hvp from same directory
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent


def _load_parse_hvp():
    spec = importlib.util.spec_from_file_location(
        "parse_hvp", SCRIPT_DIR / "parse_hvp.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_data(args) -> dict:
    if args.json:
        return json.loads(Path(args.json).read_text(encoding="utf-8"))
    parse_hvp = _load_parse_hvp()
    return parse_hvp.parse_file(args.file)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_document_info(data: dict, args) -> str:
    meta = data["metadata"]
    title = args.title or meta.get("title", meta.get("plan_name", "Verification Plan"))
    owner = args.owner or "<owner's name>"
    version = args.version or "0.0.1"

    return f"""## Document Information

| Field | Value |
|---|---|
| **Document Title** | {title} |
| **Project** | <project> |
| **Block / DUT** | {plan_name} |
| **Specification Ref** | RS: TBD |
| **Version** | {version} |
| **Status** | Active Development |
| **Owner** | {owner} |"""


def render_revision_history(args) -> str:
    version = args.version or "0.1.0"
    today = date.today().strftime("%B %Y")
    return f"""## Revision History

| Version | Author | Date | Description |
|---|---|---|---|
| {version} | {plan_name} | {today} | Initial HVP publication |"""


def render_overview(data: dict) -> str:
    meta = data["metadata"]
    stats = data["stats"]
    plan_name = meta.get("plan_name", "verification_plan")
    compliance = meta.get("compliance", "")

    req_summary = ", ".join(
        f"{count} {prefix}" for prefix, count in sorted(stats["req_counts"].items())
    )
    if not req_summary:
        req_summary = "none"

    return f"""## Overview

This Hierarchical Verification Plan (HVP) defines the verification strategy for the \
`{plan_name}` block. The plan is structured in accordance with Synopsys HVP architectural \
hierarchy, mapping requirements to verification features, test cases, and coverage \
points. The HVP is machine-parseable by Synopsys Verdi for plan tracking and metric \
aggregation.

**Plan summary**: {stats['total_features']} features, {stats['total_measures']} measures, \
{req_summary} requirements."""


def render_metrics_table(data: dict) -> str:
    rows = ["## Plan Metrics", "",
            "| Metric | Type | Goal | Aggregator |",
            "|---|---|---|---|"]
    for m in data["metrics"]:
        rows.append(
            f"| **{m['name']}** | {m['type']} | {m['goal']} | {m['aggregator']} |"
        )
    return "\n".join(rows)


def render_milestone_overrides(data: dict) -> str:
    overrides = data["overrides"]
    if not overrides:
        return ""

    # Collect all metric names across overrides
    metric_names: list[str] = []
    for ov in overrides:
        for rule in ov["rules"]:
            # expression like "fcov >= 50%"
            parts = rule["expression"].split()
            if parts:
                name = parts[0]
                if name not in metric_names:
                    metric_names.append(name)

    header = "| Milestone | " + " | ".join(metric_names) + " |"
    sep = "|---" * (len(metric_names) + 1) + "|"
    rows = [header, sep]

    for ov in overrides:
        # Build a lookup: metric_name -> threshold
        thresholds: dict[str, str] = {}
        for rule in ov["rules"]:
            parts = rule["expression"].split()
            if len(parts) >= 3:
                thresholds[parts[0]] = " ".join(parts[1:])

        cells = [thresholds.get(mn, "--") for mn in metric_names]
        rows.append(f"| **{ov['name']}** | " + " | ".join(cells) + " |")

    return "### Milestone Overrides\n\n" + "\n".join(rows)


def render_attributes_table(data: dict) -> str:
    rows = ["## Plan Attributes", "",
            "| Attribute | Type | Default | Values |",
            "|---|---|---|---|"]
    for a in data["attributes"]:
        vals = ", ".join(a["enum_values"]) if a.get("enum_values") else "--"
        rows.append(f"| **{a['name']}** | {a['type']} | {a['default']} | {vals} |")
    return "\n".join(rows)


def render_regression_tiers(data: dict) -> str:
    tiers = data["metadata"].get("regression_tiers", {})
    if not tiers:
        return ""
    rows = ["## Regression Tiers", "",
            "| Tier | Description |",
            "|---|---|"]
    for tier, desc in tiers.items():
        rows.append(f"| **{tier}** | {desc} |")
    return "\n".join(rows)


def render_requirement_summary(data: dict) -> str:
    stats = data["stats"]
    convention = data["metadata"].get("req_id_convention", {})
    rows = ["## Requirement Summary", "",
            "| Prefix | Count | Description |",
            "|---|---|---|"]
    for prefix, count in sorted(stats["req_counts"].items()):
        desc = convention.get(prefix, "")
        rows.append(f"| **{prefix}** | {count} | {desc} |")
    return "\n".join(rows)


def render_feature_hierarchy(data: dict) -> str:
    """Render top-level features as a summary table."""
    features = data["features"]
    if not features:
        return ""

    rows = ["## Plan Hierarchy", "",
            "| Feature | Sub-features | Measures | Priority | Regression |",
            "|---|---|---|---|---|"]

    for f in features:
        n_children = len(f["children"])
        n_measures = sum(
            len(c.get("measures", [])) for c in _flatten(f)
        )
        priority = f["attributes"].get("priority", "--")
        regression = f["attributes"].get("regression", "--")
        rows.append(
            f"| **{f['name']}** | {n_children} | {n_measures} "
            f"| {priority} | {regression} |"
        )

    return "\n".join(rows)


def _flatten(feature: dict) -> list[dict]:
    """Yield all descendants of a feature (including itself)."""
    result = [feature]
    for child in feature.get("children", []):
        result.extend(_flatten(child))
    return result


def render_filters(data: dict) -> str:
    filters = data["filters"]
    if not filters:
        return ""
    rows = ["## Regression Filters", "",
            "| Filter | Conditions |",
            "|---|---|"]
    for f in filters:
        conds = "; ".join(f["conditions"])
        rows.append(f"| **{f['name']}** | {conds} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_page(data: dict, args) -> str:
    sections = [
        render_document_info(data, args),
        render_revision_history(args),
        render_overview(data),
        render_metrics_table(data),
        render_milestone_overrides(data),
        render_attributes_table(data),
        render_regression_tiers(data),
        render_requirement_summary(data),
        render_feature_hierarchy(data),
        render_filters(data),
    ]
    # Drop empty sections
    return "\n\n".join(s for s in sections if s)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate markdown from a Synopsys HVP verification plan.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to the .hvp file (parses directly)")
    group.add_argument("--json", help="Path to pre-parsed JSON from parse_hvp.py")
    parser.add_argument("--output", help="Write markdown to file instead of stdout")
    parser.add_argument("--title", help="Override document title")
    parser.add_argument("--owner", help="Override owner field")
    parser.add_argument("--version", default="0.e.0", help="Document version (default 0.0.0)")
    args = parser.parse_args()

    if args.file and not Path(args.file).is_file():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    data = load_data(args)
    md = assemble_page(data, args)

    if args.output:
        Path(args.output).write_text(md + "\n", encoding="utf-8")
    else:
        print(md)


if __name__ == "__main__":
    main()
