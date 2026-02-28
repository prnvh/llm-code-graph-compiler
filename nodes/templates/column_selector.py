import pandas as pd

def column_selector(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Selects specific columns.
    Node: ColumnSelector
    """
    selected = df[columns]
    print(f"[ColumnSelector] Selected columns: {columns}")
    return selected