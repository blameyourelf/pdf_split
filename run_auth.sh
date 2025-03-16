#!/bin/bash

# Make sure environment variables are loaded
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
else
    echo "Warning: .env file not found. Make sure environment variables are set."
fi

echo "Running Google Drive authentication..."
python auth_drive.py
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "Authentication completed successfully!"
    echo "You can now proceed to run the application with Google Drive integration."
else
    echo "Authentication failed with exit code $exit_code"
    echo "Please check the error messages above and fix any issues before continuing."
fi

exit $exit_code
