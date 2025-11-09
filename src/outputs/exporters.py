from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from xml.etree.ElementTree import Element, SubElement, ElementTree

def flatten_comments(comments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flatten nested comment tree into a list of rows suitable for tabular exports.

    The 'replies' field is removed and a 'depth' field is added to preserve hierarchy.
    """
    rows: List[Dict[str, Any]] = []

    def _walk(items: Iterable[Dict[str, Any]], depth: int) -> None:
        for item in items:
            base = dict(item)
            replies = base.pop("replies", []) or []
            base["depth"] = depth
            rows.append(base)
            if replies:
                _walk(replies, depth + 1)

    _walk(comments, depth=0)
    return rows

def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def export_json(
    comments: List[Dict[str, Any]],
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    _ensure_parent_dir(path)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(comments, f, ensure_ascii=False, indent=2)
        logger.info("Exported JSON to %s", path)
    except OSError as exc:
        logger.error("Failed to write JSON file %s: %s", path, exc)

def export_jsonl(
    comments: List[Dict[str, Any]],
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    _ensure_parent_dir(path)
    rows = flatten_comments(comments)
    try:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("Exported JSONL to %s", path)
    except OSError as exc:
        logger.error("Failed to write JSONL file %s: %s", path, exc)

def export_csv(
    comments: List[Dict[str, Any]],
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    _ensure_parent_dir(path)
    rows = flatten_comments(comments)
    if not rows:
        logger.warning("No data to export to CSV at %s", path)
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        logger.info("Exported CSV to %s", path)
    except OSError as exc:
        logger.error("Failed to write CSV file %s: %s", path, exc)

def export_xml(
    comments: List[Dict[str, Any]],
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    _ensure_parent_dir(path)
    rows = flatten_comments(comments)

    root = Element("comments")
    for row in rows:
        comment_el = SubElement(root, "comment")
        for key, value in row.items():
            if value is None:
                text = ""
            else:
                text = str(value)
            field_el = SubElement(comment_el, key)
            field_el.text = text

    tree = ElementTree(root)
    try:
        tree.write(path, encoding="utf-8", xml_declaration=True)
        logger.info("Exported XML to %s", path)
    except OSError as exc:
        logger.error("Failed to write XML file %s: %s", path, exc)

def export_html(
    comments: List[Dict[str, Any]],
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    _ensure_parent_dir(path)
    rows = flatten_comments(comments)

    if not rows:
        html = "<html><head><meta charset='utf-8'><title>Reddit Comments</title></head><body><p>No comments available.</p></body></html>"
    else:
        columns = sorted({key for row in rows for key in row.keys()})
        header_cells = "".join(f"<th>{col}</th>" for col in columns)
        body_rows = []
        for row in rows:
            cells = []
            for col in columns:
                value = row.get(col, "")
                cells.append(f"<td>{value}</td>")
            body_rows.append(f"<tr>{''.join(cells)}</tr>")
        table_html = f"<table border='1'><thead><tr>{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
        html = (
            "<html><head><meta charset='utf-8'>"
            "<title>Reddit Comments</title></head><body>"
            "<h1>Reddit Comments Export</h1>"
            f"{table_html}"
            "</body></html>"
        )

    try:
        with path.open("w", encoding="utf-8") as f:
            f.write(html)
        logger.info("Exported HTML to %s", path)
    except OSError as exc:
        logger.error("Failed to write HTML file %s: %s", path, exc)

def export_excel(
    comments: List[Dict[str, Any]],
    path: Path,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    _ensure_parent_dir(path)
    rows = flatten_comments(comments)
    if not rows:
        logger.warning("No data to export to Excel at %s", path)
        return

    try:
        df = pd.DataFrame(rows)
        df.to_excel(path, index=False)
        logger.info("Exported Excel to %s", path)
    except Exception as exc:  # pandas/openpyxl can raise various exceptions
        logger.error("Failed to write Excel file %s: %s", path, exc)