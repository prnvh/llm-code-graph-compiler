from enum import Enum

class NodeType(str, Enum):
    FILE_PATH = "FilePath"
    DATA_FRAME = "DataFrame"
    DB_HANDLE = "DBHandle"
    HTTP_RESPONSE = "HTTPResponse"
    ANY = "Any"