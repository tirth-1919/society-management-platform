import sqlite3
from pathlib import Path

SOURCE = Path("instance/society_saas_recovery_source.db")
OUTPUT = Path("instance/society_saas_recovered.db")

print(f"Source: {SOURCE}")
print(f"Output: {OUTPUT}")

if not SOURCE.exists():
    raise SystemExit("Source database does not exist.")

if OUTPUT.exists():
    OUTPUT.unlink()

src = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
src.row_factory = sqlite3.Row

dst = sqlite3.connect(OUTPUT)

try:
    print("\n[1] Reading SQLite schema...")

    tables = src.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    print(f"Tables found: {len(tables)}")

    for row in tables:
        print(f"  - {row['name']}")

    print("\n[2] Recreating tables...")

    for row in tables:
        if not row["sql"]:
            continue

        try:
            dst.execute(row["sql"])
            print(f"  CREATED: {row['name']}")
        except Exception as exc:
            print(f"  FAILED CREATE {row['name']}: {exc}")

    dst.commit()

    print("\n[3] Copying table data...")

    for row in tables:
        table = row["name"]

        try:
            columns = [
                r[1]
                for r in src.execute(
                    f'PRAGMA table_info("{table}")'
                ).fetchall()
            ]

            if not columns:
                print(f"  SKIP: {table} (no columns)")
                continue

            column_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join("?" for _ in columns)

            query = f'SELECT {column_list} FROM "{table}"'

            copied = 0

            try:
                cursor = src.execute(query)

                for record in cursor:
                    values = [record[c] for c in columns]

                    try:
                        dst.execute(
                            f'INSERT INTO "{table}" ({column_list}) '
                            f'VALUES ({placeholders})',
                            values,
                        )
                        copied += 1
                    except Exception as exc:
                        print(
                            f"    SKIP ROW in {table}: {exc}"
                        )

                dst.commit()

                print(f"  RECOVERED: {table} ({copied} rows)")

            except sqlite3.DatabaseError as exc:
                print(f"  CORRUPTED TABLE: {table}")
                print(f"    {exc}")

        except Exception as exc:
            print(f"  FAILED: {table}: {exc}")

    print("\n[4] Checking recovered database...")

    result = dst.execute("PRAGMA integrity_check").fetchone()
    print("Integrity check:", result)

finally:
    src.close()
    dst.close()

print("\nRecovery process finished.")
print(f"Recovered database: {OUTPUT}")