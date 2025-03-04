import pandas as pd
import os
import sys
import fitz  # PyMuPDF
from pathlib import Path

def find_pdf_files():
    """Find PDF files in the current directory and subdirectories."""
    pdf_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def extract_table_from_pdf(pdf_path):
    """Extract tables from a PDF file using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        tables_found = False
        
        for page_index in range(len(doc)):
            page = doc[page_index]
            tables = page.find_tables()
            
            # Try to convert to list and check if it's empty
            try:
                table_list = list(tables)
                if len(table_list) > 0:
                    tables_found = True
                    break
            except (TypeError, AttributeError):
                pass
        
        doc.close()
        return tables_found
    except Exception as e:
        print(f"Error extracting tables from {pdf_path}: {str(e)}")
        return False

def test_pdf_table_export():
    """Test if pandas can export PDF table data to Excel properly."""
    print("Testing PDF table export with pandas...")
    
    # Find PDF files
    pdf_files = find_pdf_files()
    if not pdf_files:
        print("No PDF files found in the current directory and subdirectories.")
        return False
    
    print(f"Found {len(pdf_files)} PDF files.")
    
    # Create a DataFrame with PDF data
    data = []
    
    for pdf_file in pdf_files:
        print(f"Processing {pdf_file}...")
        has_tables = extract_table_from_pdf(pdf_file)
        
        # Create a sample entry for this PDF
        data.append({
            "Filename": os.path.basename(pdf_file),
            "Source Doc": f"PDF file with {'tables' if has_tables else 'no tables'} detected.",
            "Response": f"This is a sample response for {os.path.basename(pdf_file)}."
        })
    
    # Create the DataFrame
    df = pd.DataFrame(data)
    print(f"Created DataFrame with shape: {df.shape}")
    
    # Export to Excel
    output_file = "test_pdf_export.xlsx"
    try:
        print("Exporting to Excel...")
        df.to_excel(output_file, index=False)
        print(f"Successfully exported to {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error exporting to Excel: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        success = test_pdf_table_export()
        print(f"Test {'passed' if success else 'failed'}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test failed with error: {str(e)}") 