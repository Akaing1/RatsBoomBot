import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REDEEM_TYPE = "daily"


@dataclass(frozen=True)
class ImportedRedeemTotal:
    user_id: str
    username: str
    claim_count: int
    source_last_write: str | None


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Streamer.bot redeem totals into RatsBoomBot.")
    parser.add_argument("export_path", type=Path, help="Path to the Streamer.bot user-variable JSON export.")
    parser.add_argument("--broadcaster-id", required=True,
                        help="Permanent Twitch user ID of the broadcaster receiving the totals.")
    parser.add_argument("--variable", default="login",
                        help="Streamer.bot variable containing the redeem total. Default: login")
    parser.add_argument("--database", type=Path, default=Path(".data/tokens.db"),
                        help="RatsBoomBot SQLite database path. Default: .data/tokens.db")
    parser.add_argument("--apply", action="store_true",
                        help="Write the validated totals. Without this flag, only a preview is shown.")
    return parser.parse_args()


def require_text(item: dict[str, Any], field: str, row_number: int) -> str:
    value = str(item.get(field, "")).strip()

    if not value:
        raise ValueError(f"Row {row_number}: {field} is required.")

    return value


def load_export(export_path: Path, variable_name: str) -> list[ImportedRedeemTotal]:
    try:
        data = json.loads(export_path.read_text(encoding="utf-8-sig"))
    except OSError as exception:
        raise ValueError(f"Could not read export file: {exception}") from exception
    except json.JSONDecodeError as exception:
        raise ValueError(f"Export file is not valid JSON: {exception}") from exception

    if not isinstance(data, list):
        raise ValueError("The Streamer.bot export must contain a JSON list.")

    totals: dict[str, ImportedRedeemTotal] = {}

    for row_number, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Row {row_number}: expected a JSON object.")

        if str(item.get("VariableName", "")).strip() != variable_name:
            continue

        if str(item.get("UserType", "")).strip().lower() != "twitch":
            continue

        user_id = require_text(item, "UserId", row_number)
        username = require_text(item, "UserName", row_number)
        raw_value = require_text(item, "Value", row_number)

        try:
            claim_count = int(raw_value)
        except ValueError as exception:
            raise ValueError(
                f"Row {row_number}: Value must be a whole number, "
                f"received {raw_value!r}."
            ) from exception

        if claim_count < 0:
            raise ValueError(f"Row {row_number}: Value cannot be negative.")

        if user_id in totals:
            raise ValueError(
                f"Row {row_number}: duplicate Twitch user ID {user_id} "
                f"for variable {variable_name!r}."
            )

        source_last_write = str(item.get("LastWrite", "")).strip() or None

        totals[user_id] = ImportedRedeemTotal(
            user_id=user_id,
            username=username,
            claim_count=claim_count,
            source_last_write=source_last_write
        )

    if not totals:
        raise ValueError(
            f"No Twitch entries were found for Streamer.bot "
            f"variable {variable_name!r}."
        )

    return list(totals.values())


def import_totals(database_path: Path, broadcaster_id: str, totals: list[ImportedRedeemTotal]) -> None:
    if not database_path.is_file():
        raise ValueError(f"Database does not exist: {database_path}")

    query = """
    INSERT INTO imported_redeem_totals (
        broadcaster_id,
        user_id,
        username,
        redeem_type,
        claim_count,
        source_last_write,
        imported_at
    )
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """

    values = [
        (
            broadcaster_id,
            total.user_id,
            total.username,
            REDEEM_TYPE,
            total.claim_count,
            total.source_last_write
        )
        for total in totals
    ]

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'imported_redeem_totals'
            """
        ).fetchone()

        if table is None:
            raise ValueError(
                "The imported_redeem_totals table is missing. "
                "Deploy and start the updated bot once before importing."
            )

        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            """
            DELETE FROM redeem_claims
            WHERE broadcaster_id = ?
              AND redeem_type = ?
            """,
            (broadcaster_id, REDEEM_TYPE)
        )

        connection.execute(
            """
            DELETE FROM imported_redeem_totals
            WHERE broadcaster_id = ?
              AND redeem_type = ?
            """,
            (broadcaster_id, REDEEM_TYPE)
        )

        connection.executemany(query, values)


def main() -> None:
    arguments = parse_arguments()

    try:
        totals = load_export(arguments.export_path, arguments.variable)
        total_claims = sum(total.claim_count for total in totals)

        print(f"Validated {len(totals)} users with {total_claims} total historical claims.")
        print(f"Broadcaster ID: {arguments.broadcaster_id}")
        print(f"Variable: {arguments.variable}")
        print(f"Database: {arguments.database}")

        if not arguments.apply:
            print("Preview only. Run again with --apply to write these totals.")
            return

        import_totals(arguments.database, str(arguments.broadcaster_id), totals)

    except ValueError as exception:
        raise SystemExit(f"Import failed: {exception}") from exception

    print(f"Imported {len(totals)} users successfully.")


if __name__ == "__main__":
    main()
