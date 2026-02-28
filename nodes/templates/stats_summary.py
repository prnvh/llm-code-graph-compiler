import pandas as pd

def stats_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns descriptive statistics.
    Node: StatsSummary
    """
    summary = df.describe(include="all")
    print("[StatsSummary] Generated summary statistics")
    return summary