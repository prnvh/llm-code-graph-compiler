import pandas as pd

def null_handler(df: pd.DataFrame, strategy: str, value=None) -> pd.DataFrame:
    """
    Handles null values.
    strategy: 'drop' or 'fill'
    Node: NullHandler
    """
    if strategy == "drop":
        result = df.dropna()
        print("[NullHandler] Dropped null rows")
    elif strategy == "fill":
        result = df.fillna(value)
        print(f"[NullHandler] Filled nulls with {value}")
    else:
        raise ValueError("strategy must be 'drop' or 'fill'")
    return result