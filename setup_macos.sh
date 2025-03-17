#!/bin/bash

# Color codes for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up PDF Split application on macOS${NC}"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 not found. Please install Python 3.${NC}"
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Update basic tools
echo -e "${YELLOW}Updating pip, setuptools, and wheel...${NC}"
pip install --upgrade pip setuptools wheel

# Install base requirements
echo -e "${YELLOW}Installing base requirements...${NC}"
pip install -r requirements.txt

# Install PyMuPDF separately with special handling for macOS
echo -e "${YELLOW}Installing PyMuPDF (may take a few minutes)...${NC}"
pip install --no-cache-dir PyMuPDF==1.18.0

# Set up proper .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << EOL
# Google API credentials for local development
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth2callback
GOOGLE_DRIVE_FOLDER_ID=your-drive-folder-id

# Application settings
PDF_DIRECTORY=./pdf_files
SECRET_KEY=your-secret-key-for-local-development
SESSION_COOKIE_SECURE=False
EOL
    echo -e "${GREEN}.env file created. Please update it with your credentials.${NC}"
fi

# Create required directories
mkdir -p pdf_files
mkdir -p instance

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python -c "from app import app, db; app.app_context().push(); db.create_all(); db.create_all(bind=['audit'])" || {
    echo -e "${RED}Database initialization failed. This will be attempted again when you run the app.${NC}"
}

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${GREEN}Run the application with: ./run_local.sh${NC}"
chmod +x run_local.sh
