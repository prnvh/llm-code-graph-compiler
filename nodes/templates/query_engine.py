import pandas as pd
import sqlite3

def query_engine(conn: sqlite3.Connection, query: str) -> pd.DataFrame:
    """
    Executes SQL query on DBHandle.
    Node: QueryEngine
    """
    df = pd.read_sql_query(query, conn)
    print("[QueryEngine] Query executed")
    return df