#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PDF Split application...${NC}"
echo "Checking dependencies..."
# Check if required packages are installed
python -c "import flask, flask_login, flask_sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: Required Python packages are missing."
    echo "Please run: pip install flask flask-login flask-sqlalchemy"
    exit 1
fi

# Create required directories
echo "Creating required directories..."
mkdir -p instance pdf_files logs
mkdir -p ./temp

# Load environment variables
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
fi

# Set default PDF directory if not set
export PDF_DIRECTORY=${PDF_DIRECTORY:-"./pdf_files"}
echo "Using PDF directory: $PDF_DIRECTORY"

# Initialize database
echo "Checking database..."
python init_db.py

if [ $? -ne 0 ]; then
    echo "Error: Database initialization failed"
    exit 1
fi

# Check for duplicate route definitions
echo "Checking for missing imports and duplicate routes..."
python fix_routes.py
if [ $? -ne 0 ]; then
    echo "Error: Route fixing script failed"
    exit 1
fi

# Start the application
echo -e "${GREEN}Starting Flask development server...${NC}"
export FLASK_APP=app.py
export FLASK_ENV=development
FLASK_DEBUG=1 FLASK_ENV=development python app.py