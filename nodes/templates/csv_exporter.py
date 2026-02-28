import pandas as pd

def csv_exporter(df: pd.DataFrame, output_path: str) -> str:
    """
    Exports DataFrame to CSV.
    Node: CSVExporter
    """
    df.to_csv(output_path, index=False)
    print(f"[CSVExporter] Exported to {output_path}")
    return output_path