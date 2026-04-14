#!/usr/bin/env python3
"""Parse a Synopsys HVP verification plan into structured JSON.

Usage:
    python3 parse_hvp.py --file <path-to-hvp>
    python3 parse_hvp.py --file <path-to-hvp> --output <path-to-json>

Outputs JSON to stdout (or --output file) with keys:
    metadata, metrics, attributes, annotations, features, overrides,
    filters, stats
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def concat_multiline_string(lines: list[str], start: int) -> tuple[str, int]:
    """Join consecutive quoted-string continuation lines.

    Given a line like:  description = "part one"
    followed by:                       "part two";
    returns ("part one part two", ending_line_index).
    """
    parts: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i].strip()
        # Extract all quoted segments on this line
        for m in re.finditer(r'"([^"]*)"', line):
            parts.append(m.group(1))
        if line.rstrip().endswith(";"):
            break
        i += 1
    return " ".join(parts), i


# ---------------------------------------------------------------------------
# Header metadata
# ---------------------------------------------------------------------------

def parse_header_comments(lines: list[str]) -> dict:
    """Extract metadata from the // comment block at the top of the file."""
    meta: dict = {
        "plan_name": "",
        "title": "",
        "pldrs_source": "",
        "hvp_lrm": "",
        "methodology_ref": "",
        "compliance": "",
        "req_id_convention": {},
        "regression_tiers": {},
    }

    in_header = True
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("//"):
            if stripped.startswith("plan "):
                m = re.match(r"plan\s+(\w+)\s*;", stripped)
                if m:
                    meta["plan_name"] = m.group(1)
            if in_header and stripped and not stripped.startswith("//"):
                in_header = False
            if not in_header:
                continue

        text = stripped.lstrip("/ ").strip()
        if not text:
            continue

        # Key-value pairs in header
        kv = re.match(r"^([A-Za-z_ ]+):\s+(.+)$", text)
        if kv:
            key = kv.group(1).strip().lower().replace(" ", "_")
            val = kv.group(2).strip()
            if key == "pldrs_source":
                meta["pldrs_source"] = val
            elif key == "hvp_lrm":
                meta["hvp_lrm"] = val
            elif key == "methodology":
                meta["methodology_ref"] = val
            elif key == "compliance":
                meta["compliance"] = val

        # Title from first non-empty comment line (the === decorated one)
        title_m = re.match(r"^([A-Z][\w\s\-–]+)$", text)
        if title_m and not meta["title"] and "===" not in text:
            meta["title"] = title_m.group(1).strip()

        # Requirement ID convention:  PREFIX-NNN -- description
        req_m = re.match(r"^(\w+-\w+-NNN)\s+--\s+(.+)$", text)
        if req_m:
            prefix = re.sub(r"-NNN$", "", req_m.group(1))
            meta["req_id_convention"][prefix] = req_m.group(2).strip()

        # Regression tiers:  tier_name  -- description
        reg_m = re.match(r"^(l\d+_\w+)\s+--\s+(.+)$", text)
        if reg_m:
            meta["regression_tiers"][reg_m.group(1)] = reg_m.group(2).strip()

    return meta


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def parse_metrics(lines: list[str]) -> list[dict]:
    """Parse `metric <type> <name>; ... endmetric` blocks."""
    metrics: list[dict] = []
    i = 0
    while i < len(lines):
        m = re.match(r"\s*metric\s+(\w+)\s+(\w+)\s*;", lines[i])
        if m:
            metric = {"name": m.group(2), "type": m.group(1), "goal": "", "aggregator": ""}
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("endmetric"):
                line = lines[i].strip()
                g = re.match(r"goal\s*=\s*\((.+)\)\s*;", line)
                if g:
                    metric["goal"] = g.group(1).strip()
                a = re.match(r"aggregator\s*=\s*(\w+)\s*;", line)
                if a:
                    metric["aggregator"] = a.group(1)
                i += 1
            metrics.append(metric)
        i += 1
    return metrics


# ---------------------------------------------------------------------------
# Attributes and Annotations
# ---------------------------------------------------------------------------

def _parse_decl(keyword: str, lines: list[str]) -> list[dict]:
    """Parse `attribute|annotation <type> <name> = <default>;` lines.

    Handles enum types that may span two lines:
        attribute enum {a, b, c}
            name = default;
    """
    decls: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith(keyword + " "):
            i += 1
            continue

        rest = line[len(keyword) + 1:]
        # Check for enum type
        enum_m = re.match(r"enum\s*\{([^}]+)\}\s*(.*)", rest)
        if enum_m:
            enum_vals = [v.strip() for v in enum_m.group(1).split(",")]
            remainder = enum_m.group(2).strip()
            # Name and default might be on the next line
            if not remainder or "=" not in remainder:
                i += 1
                if i < len(lines):
                    remainder = lines[i].strip()
            nm = re.match(r"(\w+)\s*=\s*(\w+)\s*;?", remainder)
            if nm:
                decls.append({
                    "name": nm.group(1),
                    "type": "enum",
                    "enum_values": enum_vals,
                    "default": nm.group(2),
                })
        else:
            # Simple type: string, real, integer, percent
            sm = re.match(r"(\w+)\s+(\w+)\s*=\s*(.+?)\s*;", rest)
            if sm:
                default = sm.group(3).strip().strip('"')
                decls.append({
                    "name": sm.group(2),
                    "type": sm.group(1),
                    "enum_values": None,
                    "default": default,
                })
        i += 1
    return decls


def parse_attributes(lines: list[str]) -> list[dict]:
    return _parse_decl("attribute", lines)


def parse_annotations(lines: list[str]) -> list[dict]:
    return _parse_decl("annotation", lines)


# ---------------------------------------------------------------------------
# Features (recursive)
# ---------------------------------------------------------------------------

def parse_features(lines: list[str]) -> list[dict]:
    """Parse the feature hierarchy inside a plan block.

    Returns a list of top-level feature nodes. Each node:
    {
        "name": str,
        "attributes": {key: value},
        "annotations": {key: value},
        "measures": [{"metric_type": str, "name": str, "source": str}],
        "children": [<nested feature nodes>],
    }
    """
    root_children: list[dict] = []
    stack: list[dict] = []  # stack of feature nodes being built

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # Feature open
        fm = re.match(r"feature\s+(\w+)\s*;", stripped)
        if fm:
            node: dict = {
                "name": fm.group(1),
                "attributes": {},
                "annotations": {},
                "measures": [],
                "children": [],
            }
            stack.append(node)
            i += 1
            continue

        # Feature close
        if stripped.startswith("endfeature"):
            if stack:
                closed = stack.pop()
                if stack:
                    stack[-1]["children"].append(closed)
                else:
                    root_children.append(closed)
            i += 1
            continue

        # Inside a feature -- parse attributes, annotations, measures
        if stack:
            current = stack[-1]

            # Measure block
            mm = re.match(r"measure\s+(\w+)\s+(\w+)\s*;", stripped)
            if mm:
                measure = {"metric_type": mm.group(1), "name": mm.group(2), "source": ""}
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("endmeasure"):
                    src_line = lines[i].strip()
                    if "source" in src_line:
                        source_str, i = concat_multiline_string(lines, i)
                        measure["source"] = source_str
                    i += 1
                current["measures"].append(measure)
                i += 1
                continue

            # Inline attribute assignments (key = value;)
            attr_m = re.match(r"(\w+)\s*=\s*(.+?)\s*;", stripped)
            if attr_m and not stripped.startswith("//"):
                key = attr_m.group(1)
                val = attr_m.group(2).strip().strip('"')
                # Known annotation names
                if key in ("description", "weight", "pass_criteria", "fail_criteria"):
                    if '"' in lines[i]:
                        val, i = concat_multiline_string(lines, i)
                    current["annotations"][key] = val
                else:
                    current["attributes"][key] = val
                i += 1
                continue

        i += 1

    return root_children


# ---------------------------------------------------------------------------
# Overrides and Filters (outside plan block)
# ---------------------------------------------------------------------------

def parse_overrides(lines: list[str]) -> list[dict]:
    """Parse `override <name>; ... endoverride` blocks."""
    overrides: list[dict] = []
    i = 0
    while i < len(lines):
        om = re.match(r"\s*override\s+(\w+)\s*;", lines[i])
        if om:
            override = {"name": om.group(1), "rules": []}
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("endoverride"):
                rule_line = lines[i].strip()
                if rule_line and not rule_line.startswith("//"):
                    # path.metric = metric >= threshold;
                    rm = re.match(
                        r"([\w.*]+)\s*=\s*(.+?)\s*;",
                        rule_line,
                    )
                    if rm:
                        override["rules"].append({
                            "path": rm.group(1),
                            "expression": rm.group(2).strip(),
                        })
                i += 1
            overrides.append(override)
        i += 1
    return overrides


def parse_filters(lines: list[str]) -> list[dict]:
    """Parse `filter <name>; ... endfilter` blocks."""
    filters: list[dict] = []
    i = 0
    while i < len(lines):
        fm = re.match(r"\s*filter\s+(\w+)\s*;", lines[i])
        if fm:
            filt = {"name": fm.group(1), "conditions": []}
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("endfilter"):
                cond_line = lines[i].strip()
                if cond_line and not cond_line.startswith("//"):
                    filt["conditions"].append(cond_line.rstrip(";"))
                i += 1
            filters.append(filt)
        i += 1
    return filters


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _walk_features(features: list[dict]) -> tuple[int, int, dict[str, int], dict[str, int]]:
    """Recursively walk feature tree, counting features, measures, req IDs."""
    total_features = 0
    total_measures = 0
    req_counts: dict[str, int] = defaultdict(int)
    measure_counts: dict[str, int] = defaultdict(int)

    for f in features:
        total_features += 1
        total_measures += len(f["measures"])
        for m in f["measures"]:
            measure_counts[m["metric_type"]] += 1
        req_id = f["attributes"].get("req_id", "")
        if req_id:
            # Extract prefix from first two dash-separated segments:
            #   SCH-REQ-001     -> SCH-REQ
            #   SCH-NOTE-024-S1 -> SCH-NOTE
            parts = req_id.split("-")
            if len(parts) >= 3:
                prefix = f"{parts[0]}-{parts[1]}"
                req_counts[prefix] += 1
        # Recurse
        cf, cm, cr, cmc = _walk_features(f["children"])
        total_features += cf
        total_measures += cm
        for k, v in cr.items():
            req_counts[k] += v
        for k, v in cmc.items():
            measure_counts[k] += v

    return total_features, total_measures, dict(req_counts), dict(measure_counts)


def compute_stats(features: list[dict]) -> dict:
    total_features, total_measures, req_counts, measure_counts = _walk_features(features)
    return {
        "total_features": total_features,
        "total_measures": total_measures,
        "req_counts": req_counts,
        "measure_counts": measure_counts,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(path: str) -> dict:
    """Parse an HVP file and return the full structured dict."""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()

    metadata = parse_header_comments(lines)
    metrics = parse_metrics(lines)
    attributes = parse_attributes(lines)
    annotations = parse_annotations(lines)
    features = parse_features(lines)
    overrides = parse_overrides(lines)
    filters = parse_filters(lines)
    stats = compute_stats(features)

    return {
        "metadata": metadata,
        "metrics": metrics,
        "attributes": attributes,
        "annotations": annotations,
        "features": features,
        "overrides": overrides,
        "filters": filters,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a Synopsys HVP verification plan into structured JSON.",
    )
    parser.add_argument("--file", required=True, help="Path to the .hvp file")
    parser.add_argument("--output", help="Write JSON to file instead of stdout")
    parser.add_argument("--indent", type=int, default=2, help="JSON indent (default 2)")
    args = parser.parse_args()

    if not Path(args.file).is_file():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    result = parse_file(args.file)
    json_str = json.dumps(result, indent=args.indent, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(json_str + "\n", encoding="utf-8")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
