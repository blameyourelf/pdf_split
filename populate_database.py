#!/usr/bin/env python3
"""
Script to populate the database with PDF data during deployment.
This should be run once during deployment to initialize the database.
"""

import os
import argparse
from pdf_to_db import process_google_drive_pdfs, process_local_pdfs

def main():
    parser = argparse.ArgumentParser(description='Populate database with PDF data')
    parser.add_argument('--db-path', default='instance/patient_data.db', 
                        help='Path to SQLite database')
    parser.add_argument('--pdf-directory', default=os.environ.get('PDF_DIRECTORY', '.'),
                        help='Directory containing PDF files')
    parser.add_argument('--google-drive', action='store_true', 
                        help='Process PDFs from Google Drive')
    parser.add_argument('--folder-id', default=os.environ.get('GOOGLE_DRIVE_FOLDER_ID', ''),
                        help='Google Drive folder ID')
    
    args = parser.parse_args()
    
    print(f"Database will be populated at: {args.db_path}")
    
    if args.google_drive:
        print(f"Processing PDFs from Google Drive folder: {args.folder_id}")
        process_google_drive_pdfs(args.folder_id)
    else:
        print(f"Processing PDFs from local directory: {args.pdf_directory}")
        process_local_pdfs(args.pdf_directory)
        
    print("Database population completed")

if __name__ == "__main__":
    main()
