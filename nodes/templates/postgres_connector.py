from sqlalchemy import create_engine

def postgres_connector(df, connection_string: str, table_name: str):
    """
    Stores DataFrame in PostgreSQL.
    Node: PostgresConnector
    """
    engine = create_engine(connection_string)
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"[PostgresConnector] Stored table {table_name}")
    return engine