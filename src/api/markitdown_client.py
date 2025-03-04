import os
import asyncio
import tempfile
import json
import mimetypes
import PyPDF2
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

class MarkItDownClient:
    """Client for local document conversion using MarkItDown."""
    
    def __init__(self):
        """Initialize the MarkItDown client."""
        self.markitdown = None
        self.pymupdf_available = False
        
    def initialize(self):
        """Initialize the MarkItDown library (lazy loading to avoid import overhead)."""
        if self.markitdown is None:
            try:
                from markitdown import MarkItDown
                self.markitdown = MarkItDown()
                
                # Check if PyMuPDF is available for enhanced table extraction
                try:
                    import fitz  # PyMuPDF
                    self.pymupdf_available = True
                    print("PyMuPDF is available for enhanced table extraction")
                except ImportError:
                    self.pymupdf_available = False
                    print("PyMuPDF is not available. Tables in PDFs may not be properly formatted.")
                    print("To enable enhanced table extraction, install PyMuPDF: pip install pymupdf")
                
                return True
            except ImportError:
                raise ImportError(
                    "MarkItDown is not installed. Please install it with: pip install markitdown"
                )
        return True
    
    def get_markdown_path(self, file_path: str) -> str:
        """Get the path for the markdown file corresponding to the source file.
        
        Args:
            file_path: Path to the source document
            
        Returns:
            Path to the corresponding markdown file
        """
        # Get the directory and base name of the file
        dir_path = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create the markdown file path
        return os.path.join(dir_path, f"{base_name}.md")
    
    def check_markdown_exists(self, file_path: str) -> bool:
        """Check if a markdown file already exists for the given source file.
        
        Args:
            file_path: Path to the source document
            
        Returns:
            True if a corresponding markdown file exists, False otherwise
        """
        markdown_path = self.get_markdown_path(file_path)
        return os.path.exists(markdown_path)
    
    def is_markdown_current(self, file_path: str) -> bool:
        """Check if the existing markdown file is newer than the source file.
        
        Args:
            file_path: Path to the source document
            
        Returns:
            True if the markdown file is newer than the source file, False otherwise
        """
        if not self.check_markdown_exists(file_path):
            return False
            
        markdown_path = self.get_markdown_path(file_path)
        
        # Get the modification times
        source_mtime = os.path.getmtime(file_path)
        markdown_mtime = os.path.getmtime(markdown_path)
        
        # Check if the markdown file is newer
        return markdown_mtime > source_mtime
    
    async def read_existing_markdown(self, file_path: str) -> Dict[str, Any]:
        """Read an existing markdown file.
        
        Args:
            file_path: Path to the source document
            
        Returns:
            Dictionary containing the job_id, content, and metadata
        """
        markdown_path = self.get_markdown_path(file_path)
        
        try:
            # Read the markdown file
            with open(markdown_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create a unique job ID (using the file path hash)
            job_id = f"local-{hash(file_path)}"
            
            # Extract metadata from the file
            metadata = {
                "filename": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path),
                "file_type": mimetypes.guess_type(file_path)[0] or "unknown",
                "conversion_method": "markitdown-cached",
                "markdown_path": markdown_path,
                "cached": True
            }
            
            # For PDFs, add page count to metadata
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.pdf':
                try:
                    with open(file_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        metadata["page_count"] = len(pdf_reader.pages)
                except Exception:
                    pass
            
            print(f"Using cached markdown file: {markdown_path}")
            
            return {
                "job_id": job_id,
                "content": content,
                "metadata": metadata
            }
        except Exception as e:
            print(f"Error reading markdown file {markdown_path}: {str(e)}")
            raise
    
    async def process_document(self, file_path: str, max_pages: int = 0, force_regenerate: bool = False) -> Dict[str, Any]:
        """Process a document through MarkItDown.
        
        Args:
            file_path: Path to the document to process
            max_pages: Maximum number of pages to process (0 means all pages)
            force_regenerate: Force regeneration of markdown file even if it exists
            
        Returns:
            Dictionary containing the job_id, content, and metadata
        """
        try:
            # Check if a markdown file already exists and is current
            if not force_regenerate and self.is_markdown_current(file_path):
                return await self.read_existing_markdown(file_path)
            
            # Initialize MarkItDown if not already initialized
            self.initialize()
            
            # Get file extension
            file_ext = os.path.splitext(file_path)[1].lower()
            upload_path = file_path
            temp_file = None
            
            # Check if this is a PDF and we have PyMuPDF available for enhanced table extraction
            if file_ext == '.pdf' and self.pymupdf_available:
                try:
                    # Import the table extractor
                    from .pdf_table_extractor import pdf_to_markdown_with_tables
                    
                    # If max_pages is set, extract only those pages
                    if max_pages > 0:
                        # Create a temporary file for the extracted page(s)
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                        temp_file.close()
                        
                        # Extract the specified number of pages
                        from .pdf_table_extractor import extract_pages_from_pdf
                        extract_pages_from_pdf(file_path, temp_file.name, max_pages)
                        
                        # Use the temporary file for processing
                        result = pdf_to_markdown_with_tables(temp_file.name, max_pages=0)  # Already extracted
                    else:
                        # Process the full PDF
                        result = pdf_to_markdown_with_tables(file_path, max_pages)
                    
                    # Clean up temporary file if created
                    if temp_file and os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                    
                    # Create a unique job ID (using the file path hash)
                    job_id = f"local-{hash(file_path)}"
                    
                    # Update metadata with the original file path
                    result["metadata"]["original_file"] = file_path
                    
                    # Save the markdown file
                    markdown_path = self.get_markdown_path(file_path)
                    with open(markdown_path, 'w', encoding='utf-8') as f:
                        f.write(result["content"])
                    
                    # Update metadata with markdown path
                    result["metadata"]["markdown_path"] = markdown_path
                    result["metadata"]["cached"] = False
                    
                    print(f"Saved markdown file: {markdown_path}")
                    
                    # Return the result
                    return {
                        "job_id": job_id,
                        "content": result["content"],
                        "metadata": result["metadata"]
                    }
                    
                except ImportError:
                    # PyMuPDF table extraction failed, fall back to standard MarkItDown
                    print("Enhanced table extraction failed, falling back to standard MarkItDown")
                    self.pymupdf_available = False
                except Exception as e:
                    # Log the error and fall back to standard MarkItDown
                    print(f"Enhanced table extraction error: {str(e)}")
                    print("Falling back to standard MarkItDown")
                    self.pymupdf_available = False
            
            # Standard MarkItDown processing for non-PDF files or if PyMuPDF is not available
            # Only extract pages for PDFs when max_pages is set
            if file_ext == '.pdf' and max_pages > 0:
                # Create a temporary file for the extracted page(s)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                temp_file.close()
                
                # Extract the specified number of pages
                try:
                    with open(file_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        pdf_writer = PyPDF2.PdfWriter()
                        
                        # Get the number of pages to extract (limited by the actual PDF length)
                        num_pages = min(max_pages, len(pdf_reader.pages))
                        
                        # Add pages to the new PDF
                        for page_num in range(num_pages):
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                        
                        # Save the new PDF to the temporary file
                        with open(temp_file.name, 'wb') as output_file:
                            pdf_writer.write(output_file)
                    
                    # Use the temporary file for processing
                    upload_path = temp_file.name
                except Exception as e:
                    # If extraction fails, fall back to the original file
                    if temp_file and os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                    raise Exception(f"Failed to extract pages from PDF: {str(e)}")
            
            # Process the file using MarkItDown
            # Run in a separate thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.markitdown.convert(upload_path)
            )
            
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            
            # Create a unique job ID (using the file path hash)
            job_id = f"local-{hash(file_path)}"
            
            # Extract metadata from the file
            metadata = {
                "filename": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path),
                "file_type": mimetypes.guess_type(file_path)[0] or "unknown",
                "conversion_method": "markitdown-local",
                "cached": False
            }
            
            # For PDFs, add page count to metadata
            if file_ext == '.pdf':
                try:
                    with open(file_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        metadata["page_count"] = len(pdf_reader.pages)
                        if max_pages > 0:
                            metadata["pages_processed"] = min(max_pages, len(pdf_reader.pages))
                except Exception:
                    pass
            
            # Save the markdown file
            markdown_path = self.get_markdown_path(file_path)
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(result.text_content)
            
            # Update metadata with markdown path
            metadata["markdown_path"] = markdown_path
            
            print(f"Saved markdown file: {markdown_path}")
            
            return {
                "job_id": job_id,
                "content": result.text_content,
                "metadata": metadata
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"Error in process_document: {str(e)}")
    
    async def process_documents(self, file_paths: List[str], max_pages: int = 0, force_regenerate: bool = False) -> List[Dict[str, Any]]:
        """Process multiple documents in parallel.
        
        Args:
            file_paths: List of paths to documents to process
            max_pages: Maximum number of pages to process per document (0 means all pages)
            force_regenerate: Force regeneration of markdown files even if they exist
            
        Returns:
            List of dictionaries containing the job_id, content, and metadata for each document
        """
        tasks = [self.process_document(file_path, max_pages, force_regenerate) for file_path in file_paths]
        return await asyncio.gather(*tasks)

# Global client instance
markitdown_client = MarkItDownClient() 