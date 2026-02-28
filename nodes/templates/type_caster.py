import pandas as pd

def type_caster(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    Casts column types.
    Example mapping: {"age": "int", "salary": "float"}
    Node: TypeCaster
    """
    casted = df.astype(mapping)
    print(f"[TypeCaster] Cast columns: {mapping}")
    return casted