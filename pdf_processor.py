# ... existing imports ...

@lru_cache(maxsize=32)
def process_ward_pdf(pdf_path):
    """Process a ward PDF and extract patient data with robust error handling."""
    print(f"Processing PDF: {pdf_path}")
    patient_data = {}
    try:
        # Check if the input is a dictionary (Google Drive file info)
        if isinstance(pdf_path, dict) and 'file_id' in pdf_path:
            # Get the local path from the drive manager
            from app import drive_manager
            local_path = drive_manager.get_local_path(pdf_path['file_id'], pdf_path['filename'])
            if not local_path or not os.path.exists(local_path):
                print(f"Failed to get local file for Google Drive file {pdf_path['filename']}")
                return {}
            pdf_path = local_path
            print(f"Using local file from Google Drive: {pdf_path}")
        
        # Verify the file exists
        if not os.path.exists(pdf_path):
            print(f"PDF file does not exist: {pdf_path}")
            return {}
            
        # Get file size for debugging
        file_size = os.path.getsize(pdf_path)
        print(f"PDF file size: {file_size / 1024:.2f} KB")
        
        # Open the PDF file
        pdf = fitz.open(pdf_path)
        print(f"PDF opened successfully with {len(pdf)} pages")
        
        # Extract bookmarks
        toc = pdf.get_toc()
        if not toc:
            print(f"No bookmarks found in {pdf_path}")
            
        # Process each bookmark
        for item in toc:
            level, title, page = item
            if level == 0:  # Only process top-level bookmarks
                try:
                    # Extract patient ID from title
                    match = re.search(r'\((\d+)\)', title)
                    if match:
                        patient_id = match.group(1)
                        # Extract name from title
                        name_match = re.match(r'Patient: (.*) \(', title)
                        name = name_match.group(1) if name_match else "Unknown"
                        
                        # Store basic patient info
                        patient_data[patient_id] = {
                            "name": name,
                            "page": page - 1  # Zero-indexed pages
                        }
                except Exception as e:
                    print(f"Error processing bookmark {title}: {str(e)}")
                    continue
        
        print(f"Extracted {len(patient_data)} patients from {pdf_path}")
        return patient_data
        
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

# ... existing code ...
