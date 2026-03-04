import sqlite3

def sqlite_reader(db_path: str):
    """
    Opens a pre-existing .db file from disk and returns a DB handle. 
    Input is a FilePath. Only use this to read a database that exists before the 
    pipeline starts 
    Node: SQLiteReader
    """

    conn = sqlite3.connect(db_path)
    print(f"[SQLiteReader] Connected to {db_path}")
    return conn