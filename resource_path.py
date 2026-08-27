# Helper function for Pyinstaller when calling any external non-Python file types.
import sys, os
def resource_path(name):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(__file__), name)

# Retrieve API key from environment variables
# Load variables from .env into environment
env_path = resource_path(".env")