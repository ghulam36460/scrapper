#!/bin/bash

# Google Maps Lead Scraper - Run Script
# This script starts the web scraping application

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Google Maps Lead Scraper${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating it now...${NC}"
    python3 -m venv .venv
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment!${NC}"
        echo -e "${RED}Please install python3-venv: sudo apt install python3-venv${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Virtual environment created successfully!${NC}"
    echo ""
    
    # Activate and install dependencies
    source .venv/bin/activate
    
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip
    
    # Install from requirements.txt if it exists, otherwise install manually
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        echo -e "${YELLOW}Installing from requirements.txt...${NC}"
        pip install -r "$SCRIPT_DIR/requirements.txt"
    else
        echo -e "${YELLOW}requirements.txt not found, installing packages manually...${NC}"
        pip install flask playwright requests beautifulsoup4 lxml selectolax httpx orjson
    fi
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install dependencies!${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Dependencies installed successfully!${NC}"
    echo ""
    
    echo -e "${YELLOW}Installing Playwright browsers (this may take a while)...${NC}"
    python -m playwright install chromium
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install Playwright browsers!${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Playwright browsers installed successfully!${NC}"
    echo ""
else
    # Activate existing virtual environment
    source .venv/bin/activate
    
    # Check if Playwright browsers are installed
    if [ ! -d "$HOME/.cache/ms-playwright/chromium"* ] && [ ! -d "$HOME/.cache/ms-playwright/chromium_headless_shell"* ]; then
        echo -e "${YELLOW}Playwright browsers not found. Installing...${NC}"
        python -m playwright install chromium
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install Playwright browsers!${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}Playwright browsers installed successfully!${NC}"
        echo ""
    fi
fi

# Navigate to backend directory
cd backend

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo -e "${RED}Error: app.py not found in backend directory!${NC}"
    exit 1
fi

# Run the application
echo -e "${GREEN}Starting the application...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""
echo -e "${GREEN}Open your browser and go to:${NC}"
echo -e "${GREEN}http://127.0.0.1:5000${NC}"
echo ""
echo -e "${GREEN}==================================${NC}"
echo ""

python app.py
