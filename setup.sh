#!/bin/bash
# Setup script for PDF Split application

echo "==== PDF Split Application Setup ===="
echo

# Check Python version
python_version=$(python --version 2>&1)
if [[ $python_version != *"Python 3"* ]]; then
  echo "Error: Python 3 is required. Found: $python_version"
  echo "Please install Python 3.8 or higher."
  exit 1
fi

echo "✓ Python version: $python_version"

# Create virtual environment
echo
echo "Creating virtual environment..."
python -m venv venv
source venv/bin/activate

# Install dependencies
echo
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f .env ]; then
  echo
  echo "Creating .env file (you'll need to fill in your credentials)..."
  cat > .env << EOL
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000
GOOGLE_DRIVE_FOLDER_ID=your-drive-folder-id
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(16))")
PDF_DIRECTORY=./pdf_files
EOL
  echo "✓ Created .env file"
else
  echo
  echo "✓ .env file already exists"
fi

# Create PDF directory
echo
echo "Creating PDF directory..."
mkdir -p pdf_files
echo "✓ Created pdf_files directory"

# Create instance directory for database
echo
echo "Creating instance directory for database..."
mkdir -p instance
echo "✓ Created instance directory"

# Initialize database
echo
echo "Initializing database..."
python -c "from app import app, db; app.app_context().push(); db.create_all(); db.create_all(bind=['audit'])"
echo "✓ Database initialized"

echo
echo "==== Setup Complete ===="
echo
echo "Next steps:"
echo "1. Edit the .env file with your Google API credentials"
echo "2. Run 'python auth_drive.py' to authenticate with Google Drive"
echo "3. Start the application with 'python app.py'"
echo
echo "For more information, see README.md"
echo
