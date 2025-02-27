"""
Enhanced PDF to Markdown converter with table support.
Uses PyMuPDF (fitz) to detect and extract tables as Markdown.
"""

import fitz  # PyMuPDF
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

def pdf_to_markdown_with_tables(pdf_path: str, max_pages: int = 0) -> Dict[str, Any]:
    """
    Convert a PDF to Markdown, preserving detected tables via PyMuPDF.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to process (0 means all pages)
        
    Returns:
        Dictionary containing the content and metadata
    """
    doc = fitz.open(pdf_path)
    markdown_output = []
    
    # Get the number of pages to process
    total_pages = len(doc)
    pages_to_process = total_pages if max_pages <= 0 else min(max_pages, total_pages)
    
    for page_index in range(pages_to_process):
        page = doc[page_index]
        
        # Add page header
        markdown_output.append(f"\n## Page {page_index + 1}\n")

        # Detect tables on the page
        tables = page.find_tables()
        
        # Convert TableFinder object to a list of tables
        table_list = []
        try:
            # Try to convert to list and check if it's empty
            table_list = list(tables)
            has_tables = len(table_list) > 0
        except (TypeError, AttributeError):
            # If conversion fails, assume no tables
            has_tables = False
        
        if not has_tables:
            # No tables found, just extract the full page text as Markdown
            page_text = page.get_text("text").strip()
            markdown_output.append(page_text + "\n")
        else:
            # If tables exist, we gather text *before* the first table,
            # between tables, and after the last table.
            # We'll use the table bounding boxes to segment the text.

            last_y = 0.0
            page_height = page.rect.height
            
            # sort tables by vertical position top->bottom
            table_list.sort(key=lambda t: t.bbox[1])

            for table_idx, table in enumerate(table_list):
                table_top = table.bbox[1]
                table_bottom = table.bbox[3]

                # 1) Text from last_y to current table top
                if table_top > last_y:
                    text_above = page.get_textbox(
                        fitz.Rect(0, last_y, page.rect.width, table_top)
                    ).strip()
                    if text_above:
                        markdown_output.append(text_above + "\n\n")

                # 2) The table itself in Markdown
                md_table = table.to_markdown()
                # Optional cleanup or spacing:
                markdown_output.append(md_table.strip() + "\n\n")

                last_y = table_bottom

            # 3) After the last table, capture any remaining text
            if last_y < page_height:
                text_below = page.get_textbox(
                    fitz.Rect(0, last_y, page.rect.width, page_height)
                ).strip()
                if text_below:
                    markdown_output.append(text_below + "\n")

    # Extract metadata
    metadata = {
        "filename": os.path.basename(pdf_path),
        "file_size": os.path.getsize(pdf_path),
        "file_type": "application/pdf",
        "conversion_method": "pymupdf-tables",
        "page_count": total_pages,
        "pages_processed": pages_to_process
    }
    
    doc.close()
    
    return {
        "content": "\n".join(markdown_output),
        "metadata": metadata
    }

def extract_pages_from_pdf(input_path: str, output_path: str, max_pages: int) -> None:
    """
    Extract the first N pages from a PDF file.
    
    Args:
        input_path: Path to the input PDF file
        output_path: Path to save the extracted pages
        max_pages: Maximum number of pages to extract
    """
    doc = fitz.open(input_path)
    out_doc = fitz.open()
    
    # Get the number of pages to extract
    pages_to_extract = min(max_pages, len(doc))
    
    # Add pages to the new document
    for i in range(pages_to_extract):
        out_doc.insert_pdf(doc, from_page=i, to_page=i)
    
    # Save the new document
    out_doc.save(output_path)
    out_doc.close()
    doc.close() 