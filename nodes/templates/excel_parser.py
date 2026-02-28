import pandas as pd

def excel_parser(file_path: str) -> pd.DataFrame:
    """
    Reads Excel file into DataFrame.
    Node: ExcelParser
    """
    df = pd.read_excel(file_path)
    print(f"[ExcelParser] Loaded {len(df)} rows from {file_path}")
    return df