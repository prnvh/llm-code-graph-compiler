import pandas as pd

def data_deduplicator(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes duplicate rows.
    Node: DataDeduplicator
    """
    deduped = df.drop_duplicates()
    print("[DataDeduplicator] Removed duplicate rows")
    return deduped