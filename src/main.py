import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from extractors.reddit_parser import fetch_comments_for_post
from outputs.exporters import (
    export_csv,
    export_excel,
    export_html,
    export_json,
    export_jsonl,
    export_xml,
)

LOGGER_NAME = "reddit_comments_scraper"

def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logging.getLogger(LOGGER_NAME).warning(
            "Config file %s not found. Falling back to CLI args only.", path
        )
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logging.getLogger(LOGGER_NAME).error(
            "Failed to parse config JSON at %s: %s", path, exc
        )
        return {}

def normalize_formats(formats: Optional[List[str]]) -> List[str]:
    if not formats:
        return ["json"]
    normalized = []
    for fmt in formats:
        if not fmt:
            continue
        token = fmt.strip().lower()
        if token in {"xlsx", "excel"}:
            token = "xlsx"
        normalized.append(token)
    # Ensure uniqueness while preserving order
    seen = set()
    result: List[str] = []
    for fmt in normalized:
        if fmt not in seen:
            seen.add(fmt)
            result.append(fmt)
    return result or ["json"]

def resolve_proxies(raw: Any) -> Optional[Dict[str, str]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        proxies: Dict[str, str] = {}
        for k, v in raw.items():
            if v:
                proxies[str(k)] = str(v)
        return proxies or None
    return None

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    logger = logging.getLogger(LOGGER_NAME)

    parser = argparse.ArgumentParser(
        description="Reddit Comments Scraper - extract complete comment threads."
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="url",
        help="Reddit post URL to scrape (e.g., https://www.reddit.com/r/.../comments/...).",
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_path",
        default="data/inputs.sample.json",
        help="Path to JSON configuration file (default: data/inputs.sample.json).",
    )
    parser.add_argument(
        "-m",
        "--max-items",
        dest="max_items",
        type=int,
        help="Maximum number of comments to collect (including nested replies).",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        dest="out_dir",
        help="Output directory for exported files (default from config or ./data).",
    )
    parser.add_argument(
        "-f",
        "--formats",
        nargs="+",
        dest="formats",
        help="Export formats, space-separated. Options: json jsonl csv xml html xlsx.",
    )
    args = parser.parse_args()

    config_path = Path(args.config_path)
    config = load_config(config_path)

    url = args.url or config.get("url")
    if not url:
        parser.error(
            "No Reddit URL provided. Use --url or specify 'url' in the config JSON."
        )

    max_items = args.max_items if args.max_items is not None else config.get("maxItems")
    out_dir = args.out_dir or config.get("output_dir") or "data"
    formats = normalize_formats(args.formats or config.get("formats"))
    proxies = resolve_proxies(config.get("proxies"))

    logger.info("Starting scrape for URL: %s", url)
    if max_items:
        logger.info("Max items limit: %d", max_items)
    if proxies:
        logger.info("Using proxies for HTTP requests.")

    comments = fetch_comments_for_post(
        url=url,
        max_items=max_items,
        proxies=proxies,
        timeout=15,
        logger=logger,
    )

    if not comments:
        logger.warning("No comments were retrieved from the target URL.")
    else:
        logger.info("Retrieved %d top-level comment(s).", len(comments))

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_filename = "reddit_comments"

    logger.info("Exporting results to directory: %s", output_dir)

    if "json" in formats:
        export_json(comments, output_dir / f"{base_filename}.json", logger=logger)

    if "jsonl" in formats:
        export_jsonl(comments, output_dir / f"{base_filename}.jsonl", logger=logger)

    if "csv" in formats:
        export_csv(comments, output_dir / f"{base_filename}.csv", logger=logger)

    if "xml" in formats:
        export_xml(comments, output_dir / f"{base_filename}.xml", logger=logger)

    if "html" in formats:
        export_html(comments, output_dir / f"{base_filename}.html", logger=logger)

    if "xlsx" in formats:
        export_excel(comments, output_dir / f"{base_filename}.xlsx", logger=logger)

    logger.info("Scraping and export complete.")

if __name__ == "__main__":
    main()