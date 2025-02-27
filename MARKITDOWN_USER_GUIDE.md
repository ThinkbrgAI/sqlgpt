# MarkItDown User Guide

This guide will help you get started with the MarkItDown integration for local document conversion.

## Installation

### Prerequisites
- Python 3.10 or higher installed on your system
- Basic familiarity with the application

### Installing MarkItDown

**Option 1: Using the Installation Script (Recommended)**

1. Locate the `install_markitdown.bat` file in your application folder
2. Double-click the file to run it
3. A command prompt window will open and show the installation progress
4. Wait for the "MarkItDown has been successfully installed!" message
5. Press any key to close the window

**Option 2: Manual Installation**

1. Open a command prompt or PowerShell window
2. Run the following command:
   ```
   pip install markitdown>=0.0.2
   ```
3. Wait for the installation to complete

## Configuration

1. Open the application
2. Click on the "Configuration" button in the toolbar
3. Go to the "Document Conversion" tab
4. Select "MarkItDown (Local)" as the conversion method
5. Set the maximum number of pages to process (0 means all pages)
6. Click "Save" to apply your settings

## Converting Documents

### Converting Individual Files

1. Click on the "Convert Files to MD" button in the toolbar
2. In the file selection dialog, navigate to the files you want to convert
3. Select one or more files (you can use Ctrl+click to select multiple files)
4. Click "Open" to start the conversion process
5. A progress dialog will show the conversion status
6. Once complete, the converted documents will appear in the main table

### Converting a Folder

1. Click on the "Convert Folder to MD" button in the toolbar
2. In the folder selection dialog, navigate to the folder containing your documents
3. Click "Select Folder" to start the conversion process
4. A progress dialog will show the conversion status
5. Once complete, the converted documents will appear in the main table

## Supported File Types

MarkItDown supports a wide range of file formats:

- **Documents**: PDF, DOCX, DOC, RTF, TXT
- **Presentations**: PPTX, PPT
- **Spreadsheets**: XLSX, XLS, CSV
- **Images**: JPG, JPEG, PNG, GIF, BMP, TIFF
- **Web**: HTML, XML, JSON
- **Audio**: WAV, MP3 (metadata and transcription)
- **Archives**: ZIP (will extract and process contents)

## Viewing Results

1. After conversion, your documents will appear in the main table
2. Click on any row to view the converted Markdown content in the preview pane
3. The metadata column will show information about the document, such as:
   - Filename
   - File size
   - File type
   - Page count (for PDFs)
   - Conversion method

## Troubleshooting

### Common Issues

**MarkItDown Not Installed**
- Error message: "MarkItDown is not installed. Please install it with: pip install markitdown"
- Solution: Run the installation script or manually install using pip

**PDF Page Extraction Issues**
- Error message: "Failed to extract pages from PDF"
- Solution: Make sure PyPDF2 is properly installed (`pip install PyPDF2>=3.0.0`)

**Python Version Issues**
- Error message: "Python is not installed or not in PATH"
- Solution: Install Python 3.10 or higher and make sure it's added to your PATH

### Getting Help

If you encounter issues not covered in this guide:
1. Check the console output for specific error messages
2. Try reinstalling MarkItDown using the provided script
3. Verify that all dependencies are correctly installed
4. Restart the application and try again

## Tips and Best Practices

1. **For Large Documents**: Set a reasonable page limit to improve processing speed
2. **For Complex PDFs**: If the conversion quality is not satisfactory, try using LlamaParse instead
3. **For Batch Processing**: Use the folder conversion option for better efficiency
4. **For Privacy-Sensitive Documents**: MarkItDown processes everything locally, making it ideal for confidential information

## Comparing MarkItDown and LlamaParse

| Use Case | Recommended Option |
|----------|-------------------|
| Quick conversion of simple documents | MarkItDown |
| Processing confidential information | MarkItDown |
| Offline work | MarkItDown |
| Complex document layouts | LlamaParse |
| Tables with complex formatting | LlamaParse |
| Highest quality conversion | LlamaParse Premium |
| Large batch processing on a budget | MarkItDown | 