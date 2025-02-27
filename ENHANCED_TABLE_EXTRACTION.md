# Enhanced Table Extraction for PDFs

This application now includes enhanced table extraction for PDF files using PyMuPDF. This feature significantly improves the quality of tables extracted from PDF documents, preserving their structure in the Markdown output.

## Features

- **Automatic Table Detection**: PyMuPDF automatically identifies tables in PDF documents, even when they lack explicit grid lines.
- **Proper Markdown Tables**: Tables are converted to proper Markdown format with column alignment.
- **Text Flow Preservation**: Text before, between, and after tables is properly preserved in the correct sequence.
- **Page Segmentation**: Each page is clearly marked in the output for better organization.
- **Fallback Mechanism**: If PyMuPDF is not available or encounters an error, the system automatically falls back to standard MarkItDown processing.

## Installation

To enable enhanced table extraction, you need to install PyMuPDF:

1. Run the included `install_pymupdf.bat` script, or
2. Manually install using pip:
   ```
   pip install pymupdf>=1.22.0
   ```

## Requirements

- Python 3.10 or higher
- MarkItDown (already installed with the application)
- PyMuPDF 1.22.0 or higher

## Usage

Once PyMuPDF is installed, the enhanced table extraction will be automatically used when processing PDF files. No additional configuration is required.

When you use the "Convert Files to MD" or "Convert Folder to MD" buttons to process PDF files, the system will:

1. Check if PyMuPDF is available
2. If available, use PyMuPDF for enhanced table extraction
3. If not available, fall back to standard MarkItDown processing

## How It Works

The enhanced table extraction process:

1. Opens the PDF using PyMuPDF
2. For each page:
   - Detects tables using PyMuPDF's table detection algorithm
   - Extracts text before, between, and after tables
   - Converts tables to Markdown format
   - Combines everything in the correct sequence
3. Adds metadata about the PDF (filename, file size, page count, etc.)
4. Returns the combined Markdown content

## Limitations

- Very complex tables with merged cells may not be perfectly represented in Markdown format (as Markdown tables don't support cell spanning)
- Scanned PDFs without OCR may not have detectable tables
- Very small tables or tables with unusual formatting may not be detected

## Troubleshooting

If you encounter issues with the enhanced table extraction:

1. Make sure PyMuPDF is properly installed
2. Check the console output for error messages
3. If PyMuPDF fails, the system will automatically fall back to standard MarkItDown processing
4. For very complex PDFs, you may need to manually edit the resulting Markdown

## Credits

The enhanced table extraction feature is based on PyMuPDF (also known as fitz), a powerful PDF processing library. For more information, visit the [PyMuPDF GitHub repository](https://github.com/pymupdf/PyMuPDF). 