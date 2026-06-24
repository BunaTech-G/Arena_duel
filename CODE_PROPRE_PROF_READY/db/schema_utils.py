from __future__ import annotations


def get_database_name(cursor) -> str:
    cursor.execute("SELECT DATABASE()")
    row = cursor.fetchone()
    return str(row[0]) if row and row[0] else ""


def relation_exists(
    cursor,
    relation_name: str,
    relation_type: str | None = None,
) -> bool:
    schema_name = get_database_name(cursor)
    if not schema_name:
        return False

    query = """
        SELECT 1
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
        """
    params = [schema_name, relation_name]

    if relation_type:
        query += " AND TABLE_TYPE = ?"
        params.append(relation_type)

    cursor.execute(query, tuple(params))
    return cursor.fetchone() is not None


def table_exists(cursor, table_name: str) -> bool:
    return relation_exists(cursor, table_name, "BASE TABLE")


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    schema_name = get_database_name(cursor)
    if not schema_name:
        return False

    cursor.execute(
        """
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
          AND COLUMN_NAME = ?
        """,
        (schema_name, table_name, column_name),
    )
    return cursor.fetchone() is not None
