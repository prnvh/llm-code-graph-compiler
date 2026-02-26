import pandas as pd

def csv_parser(file_path: str) -> pd.DataFrame:
    """
    Reads a CSV file from disk and returns a DataFrame.
    Node: CSVParser
    """
    df = pd.read_csv(file_path)
    print(f"[CSVParser] Loaded {len(df)} rows from {file_path}")
    return df
