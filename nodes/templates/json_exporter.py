import pandas as pd  
  
def json_exporter(df: pd.DataFrame, output_path: str) -> str:  
    """  
    Exports DataFrame to JSON.  
    Node: JSONExporter  
    """  
    df.to_json(output_path, orient="records")  
    print(f"[JSONExporter] Exported to {output_path}")  
    return output_path