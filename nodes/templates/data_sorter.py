import pandas as pd

def data_sorter(df: pd.DataFrame, by: str, ascending: bool = True) -> pd.DataFrame:
    """
    Sorts DataFrame by column.
    Node: DataSorter
    """
    sorted_df = df.sort_values(by=by, ascending=ascending)
    print(f"[DataSorter] Sorted by {by}, ascending={ascending}")
    return sorted_df