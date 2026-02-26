import traceback

def error_handler(func):
    """
    Wraps execution in try/except.
    Node: ErrorHandler
    """
    try:
        return func()
    except Exception as e:
        print("[ErrorHandler] Exception occurred:")
        traceback.print_exc()
        raise e