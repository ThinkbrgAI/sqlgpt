import os
import sys
import asyncio
from pathlib import Path

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

from src.api.markitdown_client import markitdown_client
from src.config import config

async def test_pdf_conversion():
    """Test PDF conversion with MarkItDown"""
    print("Starting PDF conversion test with MarkItDown")
    
    # Ask for a PDF file path
    pdf_path = input("Enter the full path to a PDF file to test: ")
    
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} does not exist")
        return
    
    if not pdf_path.lower().endswith('.pdf'):
        print(f"Error: File {pdf_path} is not a PDF file")
        return
    
    print(f"Testing conversion of {pdf_path}")
    
    try:
        # Initialize MarkItDown
        print("Initializing MarkItDown client...")
        markitdown_client.initialize()
        print("MarkItDown client initialized successfully")
        
        # Set max pages from config
        max_pages = config.markitdown_max_pages
        print(f"Using max_pages setting: {max_pages}")
        
        # Process the PDF
        print("Processing PDF...")
        result = await markitdown_client.process_document(pdf_path, max_pages)
        
        # Print results
        print("\nConversion successful!")
        print(f"Content length: {len(result['content'])} characters")
        print("\nMetadata:")
        for key, value in result["metadata"].items():
            print(f"  {key}: {value}")
        
        # Print a sample of the content
        print("\nContent sample (first 500 characters):")
        print(result["content"][:500])
        
        # Save the result to a file
        output_file = os.path.splitext(os.path.basename(pdf_path))[0] + "_converted.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["content"])
        
        print(f"\nFull content saved to {output_file}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during conversion: {str(e)}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_pdf_conversion())
    
    print("\nTest complete. Press Enter to exit...")
    input() 