from flask import Flask, jsonify
import pandas as pd

def rest_endpoint(conn, route: str, port: int):
    """
    Exposes DBHandle as REST endpoint.
    Node: RESTEndpoint
    """
    app = Flask(__name__)

    @app.route(route)
    def handler():
        df = pd.read_sql_query("SELECT * FROM sqlite_master", conn)
        return jsonify(df.to_dict(orient="records"))

    print(f"[RESTEndpoint] Running on port {port}")
    app.run(port=port)