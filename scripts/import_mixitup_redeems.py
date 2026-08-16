import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

REDEEM_COLUMNS = {"First": "first", "Second": "second", "Comets": "daily"}


@dataclass(frozen=True)
class ImportedRedeemTotal:
    user_id: str
    username: str
    redeem_type: str
    claim_count: int


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Mix It Up First, Second, and Comet totals into RatsBoomBot.")
    parser.add_argument("user_data_path", type=Path, help="Mix It Up tab-separated export containing First and Second columns.")
    parser.add_argument("daily_data_path", type=Path, help="Mix It Up tab-separated export containing the Comets column.")
    parser.add_argument("--broadcaster-id", required=True, help="Permanent Twitch user ID of the broadcaster receiving the totals.")
    parser.add_argument("--database", type=Path, default=Path(".data/tokens.db"), help="RatsBoomBot SQLite database path. Default: .data/tokens.db")
    parser.add_argument("--apply", action="store_true", help="Replace the existing totals. Without this flag, only a preview is shown.")
    return parser.parse_args()


def require_headers(fieldnames: list[str] | None, required: set[str], export_path: Path) -> None:
    available = set(fieldnames or [])
    missing = sorted(required - available)

    if missing:
        raise ValueError(f"{export_path}: missing required column(s): {', '.join(missing)}")


def parse_claim_count(raw_value: str | None, column: str, row_number: int, export_path: Path) -> int:
    value = str(raw_value or "").strip()

    try:
        claim_count = int(value)
    except ValueError as exception:
        raise ValueError(f"{export_path}, row {row_number}: {column} must be a whole number, received {value!r}.") from exception

    if claim_count < 0:
        raise ValueError(f"{export_path}, row {row_number}: {column} cannot be negative.")

    return claim_count


def load_export(export_path: Path, columns: tuple[str, ...]) -> list[ImportedRedeemTotal]:
    try:
        export_file = export_path.open(encoding="utf-8-sig", newline="")
    except OSError as exception:
        raise ValueError(f"Could not read export file {export_path}: {exception}") from exception

    totals: dict[tuple[str, str], ImportedRedeemTotal] = {}

    with export_file:
        reader = csv.DictReader(export_file, delimiter="\t")
        require_headers(reader.fieldnames, {"Platform", "PlatformID", "Username", *columns}, export_path)

        for row_number, row in enumerate(reader, start=2):
            if str(row.get("Platform", "")).strip().casefold() != "twitch":
                continue

            user_id = str(row.get("PlatformID", "")).strip()
            username = str(row.get("Username", "")).strip()

            if not user_id:
                raise ValueError(f"{export_path}, row {row_number}: PlatformID is required.")

            if not user_id.isdigit():
                raise ValueError(f"{export_path}, row {row_number}: PlatformID must be a Twitch numeric user ID.")

            if not username:
                raise ValueError(f"{export_path}, row {row_number}: Username is required.")

            for column in columns:
                claim_count = parse_claim_count(row.get(column), column, row_number, export_path)

                if claim_count == 0:
                    continue

                redeem_type = REDEEM_COLUMNS[column]
                key = (redeem_type, user_id)

                if key in totals:
                    raise ValueError(f"{export_path}, row {row_number}: duplicate Twitch user ID {user_id} for {column}.")

                totals[key] = ImportedRedeemTotal(user_id=user_id, username=username, redeem_type=redeem_type, claim_count=claim_count)

    return list(totals.values())


def load_totals(user_data_path: Path, daily_data_path: Path) -> list[ImportedRedeemTotal]:
    user_totals = load_export(user_data_path, ("First", "Second"))
    daily_totals = load_export(daily_data_path, ("Comets",))
    totals = user_totals + daily_totals

    if not totals:
        raise ValueError("No non-zero Twitch redeem totals were found in either Mix It Up export.")

    return totals


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
    VALUES (?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)
    """

    values = [(broadcaster_id, total.user_id, total.username, total.redeem_type, total.claim_count) for total in totals]
    redeem_types = tuple(REDEEM_COLUMNS.values())
    placeholders = ", ".join("?" for _ in redeem_types)

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
            raise ValueError("The imported_redeem_totals table is missing. Deploy and start the updated bot once before importing.")

        connection.execute("BEGIN IMMEDIATE")
        parameters = (broadcaster_id, *redeem_types)
        connection.execute(f"DELETE FROM redeem_claims WHERE broadcaster_id = ? AND redeem_type IN ({placeholders})", parameters)
        connection.execute(f"DELETE FROM imported_redeem_totals WHERE broadcaster_id = ? AND redeem_type IN ({placeholders})", parameters)
        connection.executemany(query, values)


def summarize_totals(totals: list[ImportedRedeemTotal]) -> dict[str, tuple[int, int]]:
    return {
        redeem_type: (
            sum(1 for total in totals if total.redeem_type == redeem_type),
            sum(total.claim_count for total in totals if total.redeem_type == redeem_type)
        )
        for redeem_type in REDEEM_COLUMNS.values()
    }


def main() -> None:
    arguments = parse_arguments()

    try:
        totals = load_totals(arguments.user_data_path, arguments.daily_data_path)
        summary = summarize_totals(totals)

        print(f"Broadcaster ID: {arguments.broadcaster_id}")
        print(f"Database: {arguments.database}")

        for redeem_type in ("first", "second", "daily"):
            users, claims = summary[redeem_type]
            print(f"{redeem_type.title()}: {users} users with {claims} total historical claims.")

        if not arguments.apply:
            print("Preview only. Run again with --apply to replace the existing First, Second, and daily totals.")
            return

        import_totals(arguments.database, str(arguments.broadcaster_id), totals)

    except ValueError as exception:
        raise SystemExit(f"Import failed: {exception}") from exception

    print(f"Imported {len(totals)} non-zero user totals successfully.")


if __name__ == "__main__":
    main()
