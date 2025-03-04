import os
import sys
import asyncio
import traceback
from pathlib import Path

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

from src.api.markitdown_client import markitdown_client
from src.config import config

async def debug_pdf_conversion():
    """Debug PDF conversion with MarkItDown"""
    print("Starting PDF conversion debug with MarkItDown")
    
    # Use the specific file path
    pdf_path = r"A:\TESTING\xPages from 2021108.12 INV. 01 - SEPTEMBER.pdf"
    
    print(f"Testing file: {pdf_path}")
    print(f"File exists: {os.path.exists(pdf_path)}")
    
    if not os.path.exists(pdf_path):
        print(f"Error: File {pdf_path} does not exist")
        print("Trying alternative path format...")
        
        # Try alternative path format
        pdf_path = r"A:/TESTING/xPages from 2021108.12 INV. 01 - SEPTEMBER.pdf"
        print(f"Alternative path: {pdf_path}")
        print(f"File exists: {os.path.exists(pdf_path)}")
        
        if not os.path.exists(pdf_path):
            print("Error: File still not found with alternative path format")
            return
    
    try:
        # Print debug info
        print("\nDebug Information:")
        print(f"Current working directory: {os.getcwd()}")
        print(f"File absolute path: {os.path.abspath(pdf_path)}")
        print(f"File size: {os.path.getsize(pdf_path)} bytes")
        
        # Initialize MarkItDown with detailed error reporting
        print("\nInitializing MarkItDown client...")
        try:
            markitdown_client.initialize()
            print("MarkItDown client initialized successfully")
        except Exception as e:
            print(f"Error initializing MarkItDown: {str(e)}")
            traceback.print_exc()
            return
        
        # Set max pages from config
        max_pages = config.markitdown_max_pages
        print(f"Using max_pages setting: {max_pages}")
        
        # Process the PDF with detailed error reporting
        print("\nProcessing PDF...")
        try:
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
            print(f"Error during PDF processing: {str(e)}")
            traceback.print_exc()
            
            # Check if it's a file access issue
            print("\nChecking file access...")
            try:
                with open(pdf_path, 'rb') as f:
                    print("File can be opened for reading")
                    # Read a small chunk to verify
                    chunk = f.read(1024)
                    print(f"Successfully read {len(chunk)} bytes from file")
            except Exception as e:
                print(f"Error accessing file: {str(e)}")
                traceback.print_exc()
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    # Run the debug test
    asyncio.run(debug_pdf_conversion())
    
    print("\nDebug complete. Press Enter to exit...")
    input() 