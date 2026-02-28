import pandas as pd

def data_filter(df: pd.DataFrame, condition: str) -> pd.DataFrame:
    """
    Filters rows using pandas query syntax.
    Example condition: "age > 30 and salary < 50000"
    Node: DataFilter
    """
    filtered = df.query(condition)
    print(f"[DataFilter] Applied condition: {condition}")
    return filtered