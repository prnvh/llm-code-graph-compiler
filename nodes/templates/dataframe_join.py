import pandas as pd

def dataframe_join(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    on: str,
    how: str = "inner"
) -> pd.DataFrame:
    """
    Joins two DataFrames.
    Node: DataFrameJoin
    """

    joined = pd.merge(left_df, right_df, on=on, how=how)

    print(f"[DataFrameJoin] Joined on {on} with {how}")
    return joined