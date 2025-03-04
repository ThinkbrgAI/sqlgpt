#!/usr/bin/env python
"""
Automated Enhanced Table Extraction Test Script

This script automatically tests the enhanced table extraction functionality using PyMuPDF.
It doesn't require manual input and will use the test_table.pdf file created earlier.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

def check_pymupdf():
    """Check if PyMuPDF is installed."""
    try:
        import fitz
        print("✅ PyMuPDF is installed")
        return True
    except ImportError:
        print("❌ PyMuPDF is not installed")
        print("Please install it with: pip install pymupdf>=1.22.0")
        return False

async def test_enhanced_table_extraction():
    """Test enhanced table extraction with PyMuPDF."""
    if not check_pymupdf():
        return
    
    # Import the table extractor
    try:
        from src.api.pdf_table_extractor import pdf_to_markdown_with_tables
    except ImportError:
        print("❌ Could not import pdf_table_extractor module")
        return
    
    # Use the test PDF file we created
    pdf_path = "test_table.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} does not exist")
        return
    
    print(f"Testing enhanced table extraction on {pdf_path}")
    
    try:
        # Process the PDF
        print("Processing PDF...")
        result = pdf_to_markdown_with_tables(pdf_path)
        
        # Print results
        print("\nExtraction successful!")
        print(f"Content length: {len(result['content'])} characters")
        print("\nMetadata:")
        for key, value in result["metadata"].items():
            print(f"  {key}: {value}")
        
        # Print a sample of the content
        print("\nContent sample (first 1000 characters):")
        print(result["content"][:1000])
        
        # Save the result to a file
        output_file = os.path.splitext(os.path.basename(pdf_path))[0] + "_enhanced_tables.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["content"])
        
        print(f"\nFull content saved to {output_file}")
        
        # Now try to export to Excel
        print("\nTesting Excel export...")
        import pandas as pd
        
        # Create a DataFrame with the extracted data
        data = [
            {
                "Filename": os.path.basename(pdf_path),
                "Source Doc": result["content"],
                "Response": "This is a test response."
            }
        ]
        
        df = pd.DataFrame(data)
        print(f"Created DataFrame with shape: {df.shape}")
        
        # Export to Excel
        excel_file = os.path.splitext(os.path.basename(pdf_path))[0] + "_export.xlsx"
        print(f"Exporting to {excel_file}...")
        df.to_excel(excel_file, index=False)
        
        print(f"Successfully exported to {excel_file}")
        print(f"File size: {os.path.getsize(excel_file)} bytes")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during extraction or export: {str(e)}")

async def test_markitdown_with_enhanced_tables():
    """Test MarkItDown with enhanced table extraction."""
    if not check_pymupdf():
        return
    
    # Import the MarkItDown client
    try:
        from src.api.markitdown_client import markitdown_client
    except ImportError:
        print("❌ Could not import markitdown_client module")
        return
    
    # Use the test PDF file we created
    pdf_path = "test_table.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} does not exist")
        return
    
    print(f"Testing MarkItDown with enhanced table extraction on {pdf_path}")
    
    try:
        # Initialize MarkItDown
        print("Initializing MarkItDown client...")
        markitdown_client.initialize()
        print("MarkItDown client initialized successfully")
        
        # Process the PDF
        print("Processing PDF...")
        result = await markitdown_client.process_document(pdf_path)
        
        # Print results
        print("\nConversion successful!")
        print(f"Content length: {len(result['content'])} characters")
        print("\nMetadata:")
        for key, value in result["metadata"].items():
            print(f"  {key}: {value}")
        
        # Print a sample of the content
        print("\nContent sample (first 1000 characters):")
        print(result["content"][:1000])
        
        # Save the result to a file
        output_file = os.path.splitext(os.path.basename(pdf_path))[0] + "_markitdown_enhanced.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["content"])
        
        print(f"\nFull content saved to {output_file}")
        
        # Now try to export to Excel
        print("\nTesting Excel export...")
        import pandas as pd
        
        # Create a DataFrame with the extracted data
        data = [
            {
                "Filename": os.path.basename(pdf_path),
                "Source Doc": result["content"],
                "Response": "This is a test response."
            }
        ]
        
        df = pd.DataFrame(data)
        print(f"Created DataFrame with shape: {df.shape}")
        
        # Export to Excel
        excel_file = os.path.splitext(os.path.basename(pdf_path))[0] + "_markitdown_export.xlsx"
        print(f"Exporting to {excel_file}...")
        df.to_excel(excel_file, index=False)
        
        print(f"Successfully exported to {excel_file}")
        print(f"File size: {os.path.getsize(excel_file)} bytes")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during conversion or export: {str(e)}")

def main():
    """Main function."""
    print("Automated Enhanced Table Extraction Test Script")
    print("==============================================\n")
    
    print("This script will automatically test the enhanced table extraction functionality using PyMuPDF.\n")
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 10):
        print("❌ Python 3.10 or higher is required for PyMuPDF")
        return
    else:
        print("✅ Python version is compatible")
    
    # Run both tests
    print("\nRunning Test 1: PyMuPDF table extraction directly")
    asyncio.run(test_enhanced_table_extraction())
    
    print("\n" + "="*50 + "\n")
    
    print("Running Test 2: MarkItDown with enhanced table extraction")
    asyncio.run(test_markitdown_with_enhanced_tables())

if __name__ == "__main__":
    main()
    print("\nTests completed. Press Enter to exit...")
    input() 