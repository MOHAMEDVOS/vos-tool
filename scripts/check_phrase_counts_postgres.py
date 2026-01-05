import os

from lib.database import DatabaseManager


def _print_counts(db: DatabaseManager) -> None:
    tables = [
        "repository_phrases",
        "rebuttal_phrases",
        "pending_phrases",
        "phrase_blacklist",
    ]

    print("\nPer-table counts:")
    for t in tables:
        try:
            r = db.execute_query(f"SELECT COUNT(*) AS c FROM {t}", fetchone=True)
            c = r.get("c") if isinstance(r, dict) else r[0]
            print(f"{t}: {c}")
        except Exception as e:
            print(f"{t}: ERROR ({e})")

    try:
        u = db.execute_query(
            "SELECT COUNT(*) AS total_unique FROM (SELECT DISTINCT category, phrase FROM repository_phrases) x",
            fetchone=True,
        )
        total_unique = u.get("total_unique") if isinstance(u, dict) else u[0]
        print("repository_phrases unique(category+phrase):", total_unique)
    except Exception as e:
        print("repository_phrases unique(category+phrase): ERROR (" + str(e) + ")")


def _print_connection_info(db: DatabaseManager) -> None:
    try:
        info = db.execute_query(
            "SELECT current_database() AS db, current_user AS usr, current_schema() AS schema, "
            "inet_server_addr() AS server_ip, inet_server_port() AS server_port, "
            "current_setting('search_path') AS search_path, version() AS ver",
            fetchone=True,
        )
        print("CONN:", info)
    except Exception as e:
        print("CONN: ERROR (" + str(e) + ")")


def _print_table_locations(db: DatabaseManager) -> None:
    try:
        rows = db.execute_query(
            """
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE tablename IN ('repository_phrases','rebuttal_phrases','pending_phrases','phrase_blacklist')
            ORDER BY tablename, schemaname
            """
        )
        print("\nTable locations (pg_tables):")
        for r in rows:
            print(r)
    except Exception as e:
        print("\nTable locations (pg_tables): ERROR (" + str(e) + ")")


def _print_pg_stat_top(db: DatabaseManager) -> None:
    try:
        top = db.execute_query(
            """
            SELECT schemaname, relname, n_live_tup
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
            LIMIT 30
            """
        )
        print("\nTop tables by rows (pg_stat_user_tables):")
        for r in top:
            print(r)
    except Exception as e:
        print("\nTop tables by rows (pg_stat_user_tables): ERROR (" + str(e) + ")")


def main() -> None:
    os.environ.setdefault("DB_TYPE", "postgresql")
    db = DatabaseManager()
    _print_connection_info(db)
    _print_table_locations(db)
    _print_counts(db)
    _print_pg_stat_top(db)


if __name__ == "__main__":
    main()
