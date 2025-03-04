#!/usr/bin/env python
"""
Enhanced Table Extraction Test Script

This script tests the enhanced table extraction functionality using PyMuPDF.
It processes a PDF file and shows the extracted tables in Markdown format.
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
    
    # Ask for a PDF file path
    pdf_path = input("Enter the full path to a PDF file with tables to test: ")
    
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} does not exist")
        return
    
    if not pdf_path.lower().endswith('.pdf'):
        print(f"Error: File {pdf_path} is not a PDF file")
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
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during extraction: {str(e)}")

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
    
    # Ask for a PDF file path
    pdf_path = input("Enter the full path to a PDF file with tables to test: ")
    
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} does not exist")
        return
    
    if not pdf_path.lower().endswith('.pdf'):
        print(f"Error: File {pdf_path} is not a PDF file")
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
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during conversion: {str(e)}")

def main():
    """Main function."""
    print("Enhanced Table Extraction Test Script")
    print("====================================\n")
    
    print("This script will test the enhanced table extraction functionality using PyMuPDF.\n")
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 10):
        print("❌ Python 3.10 or higher is required for PyMuPDF")
        return
    else:
        print("✅ Python version is compatible")
    
    # Ask which test to run
    print("\nSelect a test to run:")
    print("1. Test PyMuPDF table extraction directly")
    print("2. Test MarkItDown with enhanced table extraction")
    
    choice = input("Enter your choice (1 or 2): ")
    
    if choice == "1":
        asyncio.run(test_enhanced_table_extraction())
    elif choice == "2":
        asyncio.run(test_markitdown_with_enhanced_tables())
    else:
        print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main()
    print("\nPress Enter to exit...")
    input() 