import pandas as pd

def data_transformer(df: pd.DataFrame, operations: dict | None = None) -> pd.DataFrame:
    """
    Applies transformations to a DataFrame.
    Node: DataTransformer
    """
    if operations:
        if "rename" in operations:
            df = df.rename(columns=operations["rename"])
        if "filter" in operations:
            df = df.query(operations["filter"])
        if "cast" in operations:
            for col, dtype in operations["cast"].items():
                df[col] = df[col].astype(dtype)

    print("[DataTransformer] Transformations applied")
    return df