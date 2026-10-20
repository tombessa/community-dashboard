import argparse
import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_date(value):
    """Parse a calendar date in YYYY-MM-DD format."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use a valid date in YYYY-MM-DD format."
        ) from error


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize GitHub repository data into SQLite."
    )

    parser.add_argument(
        "--repository",
        default="scanapi/scanapi",
        help="GitHub repository in owner/name format.",
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        required=True,
        help="First update date to include, in UTC (YYYY-MM-DD).",
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
        default=None,
        help=(
            "Last update date to include, in UTC (YYYY-MM-DD). "
            "Defaults to the current instant."
        ),
    )


    args = parser.parse_args()

    execution_time = datetime.now(timezone.utc)

    start_at = datetime.combine(
        args.start_date,
        time.min,
        tzinfo=timezone.utc,
    )

    if args.end_date is not None:
        if args.end_date < args.start_date:
            parser.error("--end-date must not precede --start-date.")

        if args.end_date == date.max:
            parser.error("--end-date is too large.")

        # Use the next midnight as an exclusive upper bound.
        end_before = datetime.combine(
            args.end_date + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

        # Do not extend the query beyond the current instant.
        end_before = min(end_before, execution_time)
    else:
        end_before = execution_time

    if start_at >= end_before:
        parser.error("--start-date must precede the current instant.")

    os.chdir(PROJECT_ROOT)

    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Append execution logs to a daily log file.
    log_file = logs_dir / f"sync_{datetime.now():%Y-%m-%d}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    try:
        # Import after configuring the working directory and logging.
        from src.job.github_async import synchronize_repository

        logging.info(
            "Starting synchronization: repository=%s, start=%s, end_exclusive=%s",
            args.repository,
            start_at.isoformat(),
            end_before.isoformat(),
        )

        total = synchronize_repository(
            repo_name=args.repository,
            start_at=start_at,
            end_before=end_before,
        )

        logging.info(
            "Synchronization completed: repository=%s, items=%s",
            args.repository,
            total,
        )

        # Report successful execution to the task scheduler.
        return 0

    except Exception:
        # Record the traceback and report failure to the task scheduler.
        logging.exception(
            "Synchronization failed: %s",
            args.repository,
        )
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
