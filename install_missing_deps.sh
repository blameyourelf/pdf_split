#!/bin/bash

# Color codes for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Installing missing dependencies...${NC}"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
  echo -e "${RED}Not running in a virtual environment.${NC}"
  echo -e "${YELLOW}It's recommended to use a virtual environment.${NC}"
  read -p "Continue installation globally? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Installation cancelled. You can create a virtual environment with:${NC}"
    echo "python -m venv venv"
    echo "source venv/bin/activate  # On macOS/Linux"
    echo "venv\\Scripts\\activate  # On Windows"
    exit 1
  fi
else
  echo -e "${GREEN}Installing in virtual environment: $VIRTUAL_ENV${NC}"
fi

# Install PyMuPDF
echo -e "${YELLOW}Installing PyMuPDF...${NC}"
pip install PyMuPDF

# Install other dependencies
echo -e "${YELLOW}Checking for other missing dependencies...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}Installation complete!${NC}"
echo -e "${GREEN}You can now run the application with ./run_local.sh${NC}"
