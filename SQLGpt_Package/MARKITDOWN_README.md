# MarkItDown Integration

This application now supports local document conversion using [MarkItDown](https://github.com/microsoft/markitdown), a utility for converting various files to Markdown.

## Features

- **Local Processing**: Convert documents locally without sending data to external services
- **Multiple File Formats**: Support for a wide range of file formats:
  - PDF
  - PowerPoint (PPTX, PPT)
  - Word (DOCX, DOC)
  - Excel (XLSX, XLS)
  - Images (JPG, JPEG, PNG)
  - HTML
  - Text-based formats (CSV, JSON, XML)
  - Audio (WAV, MP3)
  - ZIP files
- **Page Limiting**: Option to process only the first N pages of PDF documents
- **Metadata Extraction**: Automatically extracts and displays metadata from documents

## Installation

To use the MarkItDown integration, you need to install the MarkItDown package:

1. Run the included `install_markitdown.bat` script, or
2. Manually install using pip:
   ```
   pip install markitdown>=0.0.2
   ```

## Requirements

- Python 3.10 or higher
- All dependencies will be installed automatically with the MarkItDown package

## Usage

1. Open the application
2. Go to Configuration
3. In the "Document Conversion" tab, select "MarkItDown (Local)" as the conversion method
4. Set the maximum number of pages to process (0 means all pages)
5. Click "Save"
6. Use the "Convert Files to MD" or "Convert Folder to MD" buttons to process documents

## Comparison with LlamaParse

| Feature | MarkItDown | LlamaParse |
|---------|-----------|------------|
| Processing Location | Local (on your machine) | Cloud-based |
| Cost | Free | Pay per page |
| Speed | Fast | Varies by mode |
| File Format Support | Wide range | Limited |
| Quality | Good for most documents | Premium quality available |
| API Key Required | No | Yes |
| Internet Connection | Not required | Required |

## Troubleshooting

If you encounter issues with the MarkItDown integration:

1. Make sure you have Python 3.10 or higher installed
2. Try reinstalling MarkItDown using the provided script
3. Check the console output for error messages
4. For PDF page extraction issues, make sure PyPDF2 is properly installed

## Credits

MarkItDown is developed by Microsoft. For more information, visit the [MarkItDown GitHub repository](https://github.com/microsoft/markitdown). 