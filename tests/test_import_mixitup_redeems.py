import sqlite3

from scripts.import_mixitup_redeems import import_totals, load_totals, summarize_totals


def write_export(path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")


def test_load_totals_maps_mixitup_columns_and_ignores_zero_rows(tmp_path) -> None:
    user_data = tmp_path / "users.txt"
    daily_data = tmp_path / "daily.txt"
    write_export(
        user_data,
        "UserID\tPlatform\tPlatformID\tUsername\tFirst\tSecond\n"
        "mix-1\tTwitch\t101\talice\t2\t0\n"
        "mix-2\tTwitch\t202\tbob\t0\t3\n"
        "mix-3\tYouTube\t303\tcarol\t9\t9\n"
    )
    write_export(
        daily_data,
        "UserID\tPlatform\tPlatformID\tUsername\tComets\n"
        "mix-1\tTwitch\t101\talice\t4\n"
        "mix-2\tTwitch\t202\tbob\t0\n"
    )

    totals = load_totals(user_data, daily_data)

    assert [(total.user_id, total.redeem_type, total.claim_count) for total in totals] == [
        ("101", "first", 2),
        ("202", "second", 3),
        ("101", "daily", 4)
    ]
    assert summarize_totals(totals) == {"first": (1, 2), "second": (1, 3), "daily": (1, 4)}


def test_import_totals_replaces_all_three_redeem_types(tmp_path) -> None:
    user_data = tmp_path / "users.txt"
    daily_data = tmp_path / "daily.txt"
    database = tmp_path / "tokens.db"
    write_export(user_data, "UserID\tPlatform\tPlatformID\tUsername\tFirst\tSecond\nrow\tTwitch\t101\talice\t2\t3\n")
    write_export(daily_data, "UserID\tPlatform\tPlatformID\tUsername\tComets\nrow\tTwitch\t101\talice\t4\n")

    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE redeem_claims (broadcaster_id TEXT, redeem_type TEXT)")
        connection.execute(
            """
            CREATE TABLE imported_redeem_totals (
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                redeem_type TEXT NOT NULL,
                claim_count INTEGER NOT NULL,
                source_last_write TEXT,
                imported_at TEXT NOT NULL,
                PRIMARY KEY (broadcaster_id, user_id, redeem_type)
            )
            """
        )
        connection.execute("INSERT INTO redeem_claims VALUES ('channel-1', 'first')")
        connection.execute("INSERT INTO imported_redeem_totals VALUES ('channel-1', 'old', 'old', 'daily', 99, NULL, CURRENT_TIMESTAMP)")

    totals = load_totals(user_data, daily_data)
    import_totals(database, "channel-1", totals)

    with sqlite3.connect(database) as connection:
        claims = connection.execute("SELECT * FROM redeem_claims").fetchall()
        imported = connection.execute(
            "SELECT user_id, redeem_type, claim_count FROM imported_redeem_totals ORDER BY redeem_type"
        ).fetchall()

    assert claims == []
    assert imported == [("101", "daily", 4), ("101", "first", 2), ("101", "second", 3)]
