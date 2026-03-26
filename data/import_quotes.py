import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.forecast_support import QuoteHistoryImporter


def main():
    parser = argparse.ArgumentParser(description="Import real quote history CSV into SQLite.")
    parser.add_argument("csv_path")
    parser.add_argument("--source")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    importer = QuoteHistoryImporter(db_path=args.db_path) if args.db_path else QuoteHistoryImporter()
    result = importer.import_csv(args.csv_path, source_override=args.source)
    print("Quote import complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
