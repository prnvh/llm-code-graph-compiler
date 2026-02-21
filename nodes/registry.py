from pydantic import BaseModel
from nodes.types import NodeType

class Node(BaseModel):
    name: str
    description: str
    input_type: NodeType
    output_type: NodeType
    template_path: str
    required_params: list[str]  # e.g. ["file_path"], ["route", "port"]

NODE_REGISTRY = {
    "CSVParser": Node(
        name="CSVParser",
        description="Reads a CSV file from disk and returns a DataFrame",
        input_type=NodeType.FILE_PATH,
        output_type=NodeType.DATA_FRAME,
        template_path="nodes/templates/csv_parser.py",
        required_params=["file_path"]
    ),
    "SchemaValidator": Node(
        name="SchemaValidator",
        description="Validates DataFrame columns and types against expected schema",
        input_type=NodeType.DATA_FRAME,
        output_type=NodeType.DATA_FRAME,
        template_path="nodes/templates/schema_validator.py",
        required_params=[]
    ),
    "DataTransformer": Node(
        name="DataTransformer",
        description="Applies transformations to a DataFrame (rename, filter, cast)",
        input_type=NodeType.DATA_FRAME,
        output_type=NodeType.DATA_FRAME,
        template_path="nodes/templates/data_transformer.py",
        required_params=[]
    ),
    "SQLiteConnector": Node(
        name="SQLiteConnector",
        description="Stores a DataFrame into a SQLite database table",
        input_type=NodeType.DATA_FRAME,
        output_type=NodeType.DB_HANDLE,
        template_path="nodes/templates/sqlite_connector.py",
        required_params=["db_path", "table_name"]
    ),
    "QueryEngine": Node(
        name="QueryEngine",
        description="Runs SQL queries against a DBHandle and returns a DataFrame",
        input_type=NodeType.DB_HANDLE,
        output_type=NodeType.DATA_FRAME,
        template_path="nodes/templates/query_engine.py",
        required_params=["query"]
    ),
    "Aggregator": Node(
        name="Aggregator",
        description="Aggregates a DataFrame — group by, sum, count, mean",
        input_type=NodeType.DATA_FRAME,
        output_type=NodeType.DATA_FRAME,
        template_path="nodes/templates/aggregator.py",
        required_params=["group_by", "agg_func"]
    ),
    "RESTEndpoint": Node(
        name="RESTEndpoint",
        description="Exposes a DBHandle as a REST API endpoint using Flask",
        input_type=NodeType.DB_HANDLE,
        output_type=NodeType.HTTP_RESPONSE,
        template_path="nodes/templates/rest_endpoint.py",
        required_params=["route", "port"]
    ),
    "AuthMiddleware": Node(
        name="AuthMiddleware",
        description="Adds API key authentication to an HTTP endpoint",
        input_type=NodeType.HTTP_RESPONSE,
        output_type=NodeType.HTTP_RESPONSE,
        template_path="nodes/templates/auth_middleware.py",
        required_params=["api_key_env_var"]
    ),
    "ErrorHandler": Node(
        name="ErrorHandler",
        description="Wraps any output in a try/except with structured error logging",
        input_type=NodeType.ANY,
        output_type=NodeType.HTTP_RESPONSE,
        template_path="nodes/templates/error_handler.py",
        required_params=[]
    ),
}