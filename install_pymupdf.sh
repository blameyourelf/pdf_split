#!/bin/bash

# Color codes for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Installing newer PyMuPDF version...${NC}"

# Ensure pip is up to date
pip install --upgrade pip

# Try to install the newer version of PyMuPDF (1.22.3 is the latest stable)
echo -e "${YELLOW}Installing PyMuPDF 1.22.3...${NC}"
pip install --no-cache-dir pymupdf==1.22.3

# Verify installation
if python -c "import fitz; print(f'PyMuPDF {fitz.__version__} installed successfully!')" 2>/dev/null; then
    echo -e "${GREEN}PyMuPDF installation successful!${NC}"
else
    echo -e "${RED}PyMuPDF installation failed.${NC}"
    echo -e "${YELLOW}Trying fallback version...${NC}"
    
    # Try a different recent version
    pip install --no-cache-dir pymupdf==1.21.1
    
    if python -c "import fitz; print(f'PyMuPDF {fitz.__version__} installed successfully!')" 2>/dev/null; then
        echo -e "${GREEN}PyMuPDF installation successful with fallback version!${NC}"
    else
        echo -e "${RED}All PyMuPDF installation attempts failed.${NC}"
        echo -e "${YELLOW}Please see MACOS_TROUBLESHOOTING.md for other options.${NC}"
    fi
fi
