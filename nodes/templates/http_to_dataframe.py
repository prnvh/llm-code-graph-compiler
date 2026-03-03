import pandas as pd
import json

def http_to_dataframe(response) -> pd.DataFrame:
    """
    Converts an HTTP JSON response into a DataFrame.
    Node: HTTPToDataFrame
    """

    data = response.json()
    df = pd.DataFrame(data)

    print("[HTTPToDataFrame] Converted response to DataFrame")
    return df