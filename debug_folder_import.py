import os
import sys
import asyncio
import traceback
from pathlib import Path

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

from src.api.markitdown_client import markitdown_client
from src.config import config

async def debug_folder_import():
    """Debug folder import functionality with MarkItDown"""
    print("Starting folder import debug with MarkItDown")
    
    # Use the specific folder path
    folder_path = r"A:\TESTING"
    
    print(f"Testing folder: {folder_path}")
    print(f"Folder exists: {os.path.exists(folder_path)}")
    
    if not os.path.exists(folder_path):
        print(f"Error: Folder {folder_path} does not exist")
        print("Trying alternative path format...")
        
        # Try alternative path format
        folder_path = r"A:/TESTING"
        print(f"Alternative path: {folder_path}")
        print(f"Folder exists: {os.path.exists(folder_path)}")
        
        if not os.path.exists(folder_path):
            print("Error: Folder still not found with alternative path format")
            return
    
    try:
        # Print debug info
        print("\nDebug Information:")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Folder absolute path: {os.path.abspath(folder_path)}")
        
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
        print(f"Document conversion method: {config.document_conversion_method}")
        
        # Find all supported files in the folder
        supported_extensions = [
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', 
            '.jpg', '.jpeg', '.png', '.html', '.htm', '.txt', '.csv', 
            '.json', '.xml', '.wav', '.mp3', '.zip'
        ]
        
        files_to_process = []
        
        print(f"\nSearching for files with extensions: {supported_extensions}")
        
        # Scan for files
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in supported_extensions:
                    full_path = os.path.join(root, file)
                    files_to_process.append(full_path)
                    print(f"Found file: {full_path}")
        
        print(f"Total files found: {len(files_to_process)}")
        
        if not files_to_process:
            print("No supported files found")
            return
        
        # Process each file
        processed_count = 0
        error_count = 0
        
        for filename in files_to_process:
            try:
                # Show progress
                file_basename = os.path.basename(filename)
                print(f"\nProcessing file {processed_count+1}/{len(files_to_process)}: {file_basename}")
                
                # Get file extension
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Process the file with MarkItDown
                print(f"Calling markitdown_client.process_document for {filename}")
                result = await markitdown_client.process_document(filename, max_pages)
                print(f"Process complete, got result with content length: {len(result['content'])}")
                
                # Print metadata
                if "metadata" in result:
                    print("Metadata:")
                    for key, value in result["metadata"].items():
                        print(f"  {key}: {value}")
                
                # Save the result to a file
                output_file = os.path.splitext(os.path.basename(filename))[0] + "_converted.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result["content"])
                
                print(f"Content saved to {output_file}")
                
                processed_count += 1
                print(f"Successfully processed file {processed_count}/{len(files_to_process)}")
                
            except Exception as e:
                error_count += 1
                print(f"Error processing {filename}: {str(e)}")
                traceback.print_exc()
                continue
        
        # Show final status
        print(f"\nProcessing complete: {processed_count} files processed, {error_count} errors")
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    # Run the debug test
    asyncio.run(debug_folder_import())
    
    print("\nDebug complete. Press Enter to exit...")
    input() 