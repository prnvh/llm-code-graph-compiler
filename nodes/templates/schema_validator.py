import pandas as pd

def schema_validator(df: pd.DataFrame, schema: dict | None = None) -> pd.DataFrame:
    """
    Validates DataFrame schema.
    Node: SchemaValidator
    """
    if schema:
        for col, dtype in schema.items():
            if col not in df.columns:
                raise ValueError(f"[SchemaValidator] Missing column: {col}")
            if not pd.api.types.is_dtype_equal(df[col].dtype, dtype):
                print(f"[SchemaValidator] Warning: Column {col} dtype mismatch")

    print("[SchemaValidator] Schema validated")
    return df