# GPT Batch Processor

A high-performance system for processing large datasets through GPT models (OpenAI and Anthropic) with SQLite storage and a PyQt6-based GUI interface.

## Features

- Process large batches of documents through OpenAI and Anthropic APIs
- Import from Excel files or folders (supports .txt and .md files)
- Intelligent rate limiting and token management
- Persistent configuration storage
- Progress tracking and error handling
- Export results to Excel

## Requirements

- Python 3.8 or higher
- Windows 10/11 (64-bit)
- 8GB RAM minimum (16GB recommended)
- Internet connection for API access

## Installation

1. Clone this repository:
   ```bash
   git clone [repository-url]
   cd sqlgpt
   ```

2. Run the application:
   ```bash
   run.bat
   ```

The script will automatically:
- Create a virtual environment
- Install required dependencies
- Start the application

## Configuration

1. Click the "Configure" button in the application
2. Enter your API keys:
   - OpenAI API key for GPT-4 models
   - Anthropic API key for Claude models
3. Select your preferred model
4. Adjust settings:
   - System prompt
   - Batch size
   - Token limits
   - Reasoning effort (for OpenAI models)

## Usage

1. Import Data:
   - Click "Import Excel" to load data from an Excel file
   - Click "Import Folder" to load .txt and .md files from a folder
   
2. Process Documents:
   - Review imported documents in the table
   - Click "Process Batch" to start processing
   - Monitor progress in the status bar
   
3. Export Results:
   - Click "Export Excel" to save results
   - Results include filename, source document, and API response

## Development

To run tests:
```bash
run_tests.bat
```

## Rate Limits

### OpenAI Models
- GPT-4 Turbo: 500 RPM, 150K TPM
- GPT-4: 500 RPM, 150K TPM
- GPT-3.5 Turbo: 3500 RPM, 180K TPM

### Anthropic Models
- Claude-3: 4000 RPM, 200K input TPM, 80K output TPM

## Error Handling

- API errors are logged and displayed
- Failed requests are marked in the database
- Processing can be stopped and resumed
- Rate limits are automatically respected

## Performance

The system is optimized for:
- Parallel API requests
- Efficient token usage
- Memory management
- Database performance

## Support

For issues or questions, please open a GitHub issue. 