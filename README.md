# SQLGpt - PDF Processing with Enhanced Table Extraction

A powerful application for processing PDF files and other documents, with enhanced table extraction capabilities.

## Features

- **Document Conversion**: Convert various file formats to Markdown
- **Enhanced Table Extraction**: Automatically detect and extract tables from PDFs
- **Batch Processing**: Process multiple files or entire folders at once
- **Metadata Extraction**: Extract and display metadata from documents
- **Export to Excel**: Export processed data to Excel for further analysis

## Installation

### Prerequisites

- **Python 3.10 or higher** - [Download Python](https://www.python.org/downloads/)
  - Make sure to check "Add Python to PATH" during installation

### Quick Installation (Recommended)

1. Run the `install_all.bat` script by double-clicking it
2. Wait for the installation to complete
3. Follow the on-screen instructions

### Manual Installation

If the quick installation doesn't work, you can install the components manually:

1. Install base requirements:
   ```
   pip install -r requirements.txt
   ```

2. Install MarkItDown:
   ```
   pip install markitdown>=0.0.2
   ```

3. Install PyMuPDF for enhanced table extraction:
   ```
   pip install pymupdf>=1.22.0
   ```

## Running the Application

1. Open a command prompt or PowerShell window in the application folder
2. Run the application:
   ```
   python run.py
   ```

## Using the Application

### Converting Files to Markdown

1. Click the "Convert Files to MD" button
2. Select one or more files to convert
3. The application will process the files and display the results in the table

### Converting a Folder to Markdown

1. Click the "Convert Folder to MD" button
2. Select a folder containing files to convert
3. The application will find all supported files in the folder and its subfolders
4. Confirm the processing when prompted
5. The application will process all files and display the results in the table

### Enhanced Table Extraction

The application automatically uses PyMuPDF for enhanced table extraction when processing PDF files. This provides better table formatting in the resulting Markdown.

### Exporting Results

1. After processing files, click the "Export Excel" button
2. Choose a location to save the Excel file
3. The application will export all data from the table to the Excel file

## Supported File Formats

- **PDF** - With enhanced table extraction
- **Word** - DOCX, DOC
- **PowerPoint** - PPTX, PPT
- **Excel** - XLSX, XLS
- **Images** - JPG, JPEG, PNG
- **Web** - HTML, HTM
- **Text** - TXT, CSV, JSON, XML
- **Audio** - WAV, MP3
- **Archives** - ZIP

## Troubleshooting

### Installation Issues

- Make sure Python 3.10 or higher is installed and in your PATH
- Try running the commands manually in a command prompt
- Check your internet connection

### Application Issues

- If the application crashes, check the console output for error messages
- Make sure all dependencies are installed correctly
- Try restarting the application

## Additional Documentation

- [ENHANCED_TABLE_EXTRACTION.md](ENHANCED_TABLE_EXTRACTION.md) - Details about the enhanced table extraction feature
- [MARKITDOWN_README.md](MARKITDOWN_README.md) - Information about the MarkItDown library
- [MARKITDOWN_USER_GUIDE.md](MARKITDOWN_USER_GUIDE.md) - Detailed guide for using MarkItDown

## Credits

- **MarkItDown** - For local document conversion
- **PyMuPDF** - For enhanced table extraction
- **PyQt6** - For the user interface
- **pandas** - For data handling and Excel export 