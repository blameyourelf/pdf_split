# macOS Troubleshooting Guide

## PyMuPDF Installation Issues

If you're having trouble installing PyMuPDF on macOS, try these steps:

### 1. Install Required Dependencies

```bash
brew install freetype
brew install mupdf
```

### 2. Install PyMuPDF with Direct Options

```bash
pip install --no-cache-dir PyMuPDF==1.18.0
```

### 3. Alternative Installation

If the above doesn't work, try:

```bash
CFLAGS="-I/usr/local/include -I/usr/local/include/freetype2" LDFLAGS="-L/usr/local/lib" pip install --no-cache-dir PyMuPDF==1.18.0
```

## Database Initialization Issues

If you see errors like `AttributeError: 'NoneType' object has no attribute 'Model'`, it means there's an issue with the database initialization.

1. Make sure your `.env` file is properly formatted
2. Try running the setup script: `./setup_macos.sh`
3. Check that you have write permissions to the `instance` directory

## Google Drive API Issues

If you encounter Google Drive API errors:

1. Make sure you have valid credentials in your `.env` file
2. Try running the auth setup: `python auth_drive.py`
3. Delete the token file and re-authenticate: `rm /tmp/pdf_cache/token.pickle token.pickle`

## Loading Environment Variables

If Python-dotenv reports parsing errors:

1. Check your `.env` file for syntax errors
2. Make sure there are no trailing spaces after values
3. Use the provided `.env` template from the setup script
