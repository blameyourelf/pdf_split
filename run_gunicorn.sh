#!/bin/bash

# Set environment variables - default to current directory for PDFs
export PDF_DIRECTORY="."

# Check if PDF files exist
echo "Checking for PDF files in the current directory..."
PDF_COUNT=$(ls -1 ward_*_records.pdf 2>/dev/null | wc -l)
echo "Found $PDF_COUNT PDF files"

if [ "$PDF_COUNT" -eq 0 ]; then
    echo "Warning: No PDF files found in the current directory."
    echo "Please make sure ward_*_records.pdf files are present."
fi

# Run the app with Gunicorn
echo "Starting application with Gunicorn..."
gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app
