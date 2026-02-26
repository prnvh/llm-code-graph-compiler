import sqlite3
import pandas as pd

def sqlite_connector(df: pd.DataFrame, db_path: str, table_name: str):
    """
    Stores DataFrame into SQLite and returns connection.
    Node: SQLiteConnector
    """
    conn = sqlite3.connect(db_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    print(f"[SQLiteConnector] Stored table '{table_name}' in {db_path}")
    return conn