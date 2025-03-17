import os
import sys
import tempfile

# Print startup diagnostic information
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"Temporary directory: {tempfile.gettempdir()}")
print(f"Environment variables: {', '.join(k for k in os.environ.keys() if 'GOOGLE_' in k)}")

try:
    from app import app
    print("Successfully imported app")
except Exception as e:
    print(f"Error importing app: {str(e)}")
    raise

# This is the WSGI application object that Gunicorn will use
application = app

if __name__ == "__main__":
    app.run()
