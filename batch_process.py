#!/usr/bin/env python
"""
Batch PDF Processing Script

This script automatically processes multiple PDF files in a directory without requiring user input.
It uses the MarkItDown client with enhanced table extraction to convert PDFs to markdown.
"""

import os
import sys
import asyncio
import argparse
import traceback
import gc
import json
import time
from pathlib import Path
from datetime import datetime

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

async def process_file(file_path, output_dir=None, retry_count=0, max_retries=3):
    """Process a single file using MarkItDown with enhanced table extraction."""
    try:
        # Import the MarkItDown client
        from src.api.markitdown_client import markitdown_client
        
        print(f"Processing: {file_path}")
        
        # Initialize MarkItDown
        markitdown_client.initialize()
        
        # Process the document
        result = await markitdown_client.process_document(file_path)
        
        # Create output filename
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{base_name}.md")
        else:
            output_file = f"{base_name}.md"
        
        # Save the result
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["content"])
        
        print(f"✅ Successfully processed: {file_path}")
        print(f"   Output saved to: {output_file}")
        print(f"   Content length: {len(result['content'])} characters")
        
        # Force garbage collection to free memory
        gc.collect()
        
        return True
    except Exception as e:
        print(f"❌ Error processing {file_path}: {str(e)}")
        traceback.print_exc()
        
        # Try to retry a few times for transient errors
        if retry_count < max_retries:
            print(f"Retrying ({retry_count + 1}/{max_retries})...")
            # Wait a bit before retrying
            await asyncio.sleep(2)
            return await process_file(file_path, output_dir, retry_count + 1, max_retries)
        
        return False

async def batch_process(input_dir, output_dir=None, file_extensions=None, recursive=False, resume_file=None, 
                        max_retries=3, delay=1.0, gc_interval=5):
    """Process all files in a directory."""
    if file_extensions is None:
        file_extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']
    
    # Find all files with the specified extensions
    files_to_process = []
    
    if recursive:
        for root, _, files in os.walk(input_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in file_extensions):
                    files_to_process.append(os.path.join(root, file))
    else:
        for file in os.listdir(input_dir):
            if any(file.lower().endswith(ext) for ext in file_extensions):
                files_to_process.append(os.path.join(input_dir, file))
    
    if not files_to_process:
        print(f"No files with extensions {file_extensions} found in {input_dir}")
        return
    
    print(f"Found {len(files_to_process)} files to process")
    
    # Check if we should resume from a previous run
    processed_files = set()
    if resume_file and os.path.exists(resume_file):
        try:
            with open(resume_file, 'r') as f:
                resume_data = json.load(f)
                processed_files = set(resume_data.get('processed_files', []))
                print(f"Resuming from previous run. {len(processed_files)} files already processed.")
        except Exception as e:
            print(f"Error loading resume file: {str(e)}")
    
    # Create a progress tracking file
    progress_file = resume_file or "batch_progress.json"
    
    # Process files one by one to avoid memory issues
    successful = 0
    failed = 0
    skipped = 0
    
    for i, file_path in enumerate(files_to_process):
        # Skip already processed files if resuming
        if file_path in processed_files:
            print(f"Skipping already processed file: {file_path}")
            skipped += 1
            continue
        
        print(f"Processing file {i+1}/{len(files_to_process)}: {file_path}")
        
        if await process_file(file_path, output_dir, max_retries=max_retries):
            successful += 1
            # Add to processed files and save progress
            processed_files.add(file_path)
            try:
                with open(progress_file, 'w') as f:
                    json.dump({
                        'processed_files': list(processed_files),
                        'last_update': datetime.now().isoformat()
                    }, f)
            except Exception as e:
                print(f"Warning: Could not save progress: {str(e)}")
        else:
            failed += 1
        
        # Add a small delay between files to allow system to stabilize
        await asyncio.sleep(delay)
        
        # Force garbage collection periodically
        if i % gc_interval == 0:
            print("Running garbage collection...")
            gc.collect()
    
    print("\nBatch processing complete!")
    print(f"Successfully processed: {successful} files")
    print(f"Failed to process: {failed} files")
    print(f"Skipped (already processed): {skipped} files")

def main():
    """Main function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Batch process PDF files to markdown",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("input_dir", help="Directory containing files to process")
    parser.add_argument("--output-dir", "-o", help="Directory to save output files (default: same as input)")
    parser.add_argument("--recursive", "-r", action="store_true", help="Process subdirectories recursively")
    parser.add_argument("--extensions", "-e", nargs="+", default=['.pdf'], 
                        help="File extensions to process (default: .pdf)")
    parser.add_argument("--resume", action="store_true", help="Resume from previous run")
    parser.add_argument("--resume-file", help="Custom file to track progress for resuming")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retry attempts for failed files")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between processing files")
    parser.add_argument("--gc-interval", type=int, default=5, help="Run garbage collection after processing this many files")
    
    args = parser.parse_args()
    
    # Check if PyMuPDF is installed
    if not check_pymupdf():
        print("PyMuPDF is required for enhanced table extraction")
        return
    
    # Check if input directory exists
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        return
    
    # Determine resume file
    resume_file = None
    if args.resume or args.resume_file:
        resume_file = args.resume_file or f"batch_progress_{Path(args.input_dir).name}.json"
    
    # Print start time
    start_time = datetime.now()
    print(f"Starting batch processing at {start_time.strftime('%H:%M:%S')}")
    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir or 'Same as input'}")
    print(f"Processing extensions: {args.extensions}")
    print(f"Recursive mode: {'Enabled' if args.recursive else 'Disabled'}")
    print(f"Resume mode: {'Enabled' if resume_file else 'Disabled'}")
    if resume_file:
        print(f"Resume file: {resume_file}")
    print(f"Max retries: {args.max_retries}")
    print(f"Delay between files: {args.delay} seconds")
    print(f"Garbage collection interval: Every {args.gc_interval} files")
    print("-" * 50)
    
    # Run the batch processing
    asyncio.run(batch_process(
        args.input_dir, 
        args.output_dir, 
        args.extensions, 
        args.recursive,
        resume_file,
        args.max_retries,
        args.delay,
        args.gc_interval
    ))
    
    # Print end time and duration
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"Finished at {end_time.strftime('%H:%M:%S')}")
    print(f"Total duration: {duration}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
    finally:
        print("\nBatch processing script completed") 