import sqlite3

def sqlite_reader(db_path: str):
    """
    Creates a SQLite DB handle without requiring a DataFrame input.
    Node: SQLiteReader
    """

    conn = sqlite3.connect(db_path)
    print(f"[SQLiteReader] Connected to {db_path}")
    return conn