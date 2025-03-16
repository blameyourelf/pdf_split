#!/usr/bin/env python3
import os
import sys

def check_pdfs(directory="."):
    """Check for PDF files in the specified directory"""
    print(f"Checking for PDF files in: {os.path.abspath(directory)}")
    
    if not os.path.exists(directory):
        print(f"Error: Directory {directory} does not exist")
        return False
        
    pdf_files = [f for f in os.listdir(directory) if f.startswith('ward_') and f.endswith('_records.pdf')]
    
    if not pdf_files:
        print("No ward PDF files found!")
        return False
    
    print(f"Found {len(pdf_files)} PDF files:")
    for i, pdf in enumerate(sorted(pdf_files)[:10]):
        print(f"  {i+1}. {pdf}")
    
    if len(pdf_files) > 10:
        print(f"  ... and {len(pdf_files) - 10} more")
    
    return True

if __name__ == "__main__":
    directory = "." if len(sys.argv) < 2 else sys.argv[1]
    success = check_pdfs(directory)
    sys.exit(0 if success else 1)
