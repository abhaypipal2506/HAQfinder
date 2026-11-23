"""Command line interface for the ingestion pipeline.

Usage (run from the project root):
    python -m app.ingest.cli seed
    python -m app.ingest.cli import data/ingest/<name>.json
    python -m app.ingest.cli links
    python -m app.ingest.cli status
"""

import argparse
import json
import sys
from pathlib import Path

from . import db
from .pipeline import run_import
from .seed import seed_database
from .validate_link import check_link

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGEST_DIR = PROJECT_ROOT / "data" / "ingest"
LINK_FIELDS = ("official_information_url", "source_url")


def _print_report(report: dict) -> None:
    print(f"source_id: {report['source_id']}")
    print(f"accepted: {report['accepted']}")
    print(f"rejected: {report['rejected']}")
    print(f"committed: {report['committed']}")
    print(f"duplicates: {len(report['duplicates'])}")
    print(f"warnings: {len(report['warnings'])}")
    if report["error"]:
        print(f"error: {report['error']}")
    for item in report["rejected_details"]:
        print(f"  rejected index={item['index']} scheme_id={item['scheme_id']}: "
              + "; ".join(item["errors"]))
    for dup in report["duplicates"]:
        print(f"  duplicate: {dup['a']} / {dup['b']} ({dup['reason']})")
    for warning in report["warnings"]:
        print(f"  warning: {warning}")
    changes = report["changes"]
    if report["committed"]:
        print(f"  added: {len(changes['added'])}, removed (not deleted): "
              f"{len(changes['removed'])}, changed: {len(changes['changed'])}")


def cmd_seed(args) -> int:
    report = seed_database()
    _print_report(report)
    return 0 if report["committed"] else 1


def cmd_import(args) -> int:
    path = Path(args.path).resolve()
    try:
        path.relative_to(INGEST_DIR.resolve())
    except ValueError:
        print(f"error: path must be inside {INGEST_DIR.relative_to(PROJECT_ROOT)}")
        return 2

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"error: could not read JSON: {exc}")
        return 2

    if isinstance(data, dict):
        schemes = data.get("schemes")
        source_id = data.get("source_id", path.stem)
        if not isinstance(schemes, list):
            print('error: JSON object must contain a "schemes" array')
            return 2
    elif isinstance(data, list):
        schemes = data
        source_id = path.stem
    else:
        print("error: JSON must be an object with a schemes array, or a list")
        return 2

    if not isinstance(source_id, str) or not source_id.strip():
        print("error: source_id must be a non-empty string")
        return 2

    report = run_import(schemes, source_id)
    _print_report(report)
    return 0 if report["committed"] else 1


def cmd_links(args) -> int:
    counts = {}
    seen = set()
    for rec in db.list_live_schemes():
        for field in LINK_FIELDS:
            url = rec.get(field)
            if not isinstance(url, str) or not url or url in seen:
                continue
            seen.add(url)
            verdict = check_link(url)["verdict"]
            counts[verdict] = counts.get(verdict, 0) + 1
            print(f"{verdict}\t{url}")
    print("summary:")
    if not counts:
        print("  no URLs to check")
    for verdict in sorted(counts):
        print(f"  {verdict}: {counts[verdict]}")
    return 0


def cmd_status(args) -> int:
    print(f"live schemes: {len(db.list_live_schemes())}")
    rows = db.recent_sync_log(10)
    if not rows:
        print("no sync log entries")
    for row in rows:
        print(f"{row['ran_at']}\t{row['source_id']}\t{row['status']}\t"
              f"accepted={row['accepted']}\trejected={row['rejected']}\t{row['message']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingest.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="load data/schemes.json through the import pipeline")
    p_import = sub.add_parser("import", help="import a JSON file from data/ingest/")
    p_import.add_argument("path")
    sub.add_parser("links", help="check official URLs of live schemes (network)")
    sub.add_parser("status", help="show live scheme count and recent sync log")
    args = parser.parse_args(argv)

    handlers = {
        "seed": cmd_seed,
        "import": cmd_import,
        "links": cmd_links,
        "status": cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
