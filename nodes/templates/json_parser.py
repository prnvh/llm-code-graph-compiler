import json
import pandas as pd

def json_parser(file_path: str) -> pd.DataFrame:
    """
    Reads a JSON file and returns a DataFrame.
    Node: JSONParser
    """
    with open(file_path, "r") as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    print(f"[JSONParser] Loaded {len(df)} rows from {file_path}")
    return df