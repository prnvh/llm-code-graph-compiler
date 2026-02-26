import os
from flask import request, abort

def auth_middleware(app, api_key_env_var: str):
    """
    Adds API key authentication to Flask app.
    Node: AuthMiddleware
    """
    API_KEY = os.getenv(api_key_env_var)

    @app.before_request
    def check_auth():
        if request.headers.get("x-api-key") != API_KEY:
            abort(401)

    print("[AuthMiddleware] Authentication enabled")
    return app