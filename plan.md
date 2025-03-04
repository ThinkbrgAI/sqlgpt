# Project Plan: High-Performance GPT API Processing System

## Overview
A high-performance asynchronous system for processing large datasets through GPT models (OpenAI and Anthropic) with SQLite storage and basic GUI interface. The system focuses on maximum throughput while maintaining data integrity and providing simple import/export capabilities.

## Hardware Specifications
- CPU: Intel i9-14900KF 3.20 GHz
- RAM: 192 GB
- GPU: Dual Nvidia A5000 (28GB) in bridge configuration
- OS: Windows 64-bit

## Project Goals
- [x] Define project requirements and scope
- [x] Set up project structure
- [x] Create initial implementation
- [x] Add tests
- [x] Review and refine

## Architecture Decisions
- GUI: PyQt6 (QT6)
  - Reason: Best multi-threading support
  - Separate UI thread from processing
  - Native support for large datasets
  - Modern grid widgets for data display
  
- Database Strategy:
  - Primary SQLite DB with WAL (Write-Ahead Logging)
  - Memory-mapped temporary tables for batch processing
  - Connection pooling with separate connections for:
    - UI reads
    - Batch writes
    - Transaction management
  
- Async Implementation:
  - asyncio for API calls
  - ThreadPoolExecutor for DB operations
  - QThread for UI responsiveness
  - Batch size: Dynamic based on memory usage (target: 2GB per batch)

## Core Features
- [x] Configuration GUI
  - [x] API key input
  - [x] Model selection (OpenAI/Anthropic)
  - [x] System prompt configuration
  - [x] Settings management
  - [x] Reasoning effort controls for OpenAI models
- [x] Database Management
  - [x] SQLite implementation
  - [x] Excel import/export
  - [x] Null-value preservation logic
  - [x] Auto-save functionality
  - [x] Create new blank database with custom name
  - [x] Enhanced database connection management for Windows
  - [x] Improved file operations with error handling
- [x] Asynchronous Processing
  - [x] 100 simultaneous API calls
  - [x] Rate limit management
  - [x] Response-to-row matching
  - [x] Progress tracking
- [x] Data Structure
  - [x] Source Doc column
  - [x] Response column
  - [x] Metadata columns (timestamp, token count, model used, etc.)

## API Integration Details
### OpenAI Reasoning Models
- Allowed Models ONLY:
  - o1 (advanced model)
    - Rate Limits:
      - 30,000,000 tokens per minute (TPM)
      - 1,000 requests per minute (RPM)
      - 10,000,000,000 tokens per day (TPD)
    - Best for: Complex tasks, cross-domain reasoning
  - o3-mini (faster model)
    - Rate Limits:
      - 150,000,000 tokens per minute (TPM)
      - 30,000 requests per minute (RPM)
    - Best for: Simpler tasks, high throughput

#### Default Settings
- Default Model: o1
- Reasoning Effort: High (REQUIRED)
- Available Reasoning Levels:
  - High: Best reasoning, more tokens
  - Medium: Balanced approach
  - Low: Faster, fewer tokens

#### Reasoning Model Features
- Internal chain of thought processing
- Excels in:
  - Complex problem solving
  - Coding tasks
  - Scientific reasoning
  - Multi-step planning

#### Implementation Example
```python
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="o3-mini",  # or "o1"
    reasoning_effort="high",  # REQUIRED: always set to "high"
    messages=[
        {
            "role": "user", 
            "content": prompt
        }
    ]
)
```

### Anthropic Claude 3
- Allowed Model ONLY:
  - claude-3-7-sonnet-20250219
  - Rate Limits:
    - 4,000 requests per minute
    - 200,000 input tokens per minute (excluding cache reads)
    - 80,000 output tokens per minute

Example Implementation:
```python
import anthropic

client = anthropic.Anthropic(
    # defaults to os.environ.get("ANTHROPIC_API_KEY")
    api_key="my_api_key",
)

message = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello, Claude"}
    ]
)
print(message.content)
```

## LlamaParse Integration
- [x] Add LlamaParse configuration options
  - Parse mode (balanced, fast, premium)
  - Continuous mode
  - Auto mode
  - Max pages
  - Language
  - Advanced options (OCR, diagonal text, columns, tables, layout)
- [x] Create LlamaParse API client
  - Async file upload
  - Job status polling
  - Result retrieval in Markdown format
  - Error handling and retries
- [x] Add PDF import functionality to main window
  - File selection dialog
  - Progress tracking
  - Display results in table
  - Show metadata
- [x] Optimize PDF processing
  - [x] Extract only required pages when max_pages is set
  - [x] Use temporary files for extracted pages
  - [x] Add retry logic for network issues
  - [x] Improve error handling and user feedback

## MarkItDown Integration
- [x] Add MarkItDown configuration options
  - Document conversion method selection (LlamaParse or MarkItDown)
  - Max pages setting
- [x] Create MarkItDown client
  - Async document processing
  - Support for multiple file formats
  - Metadata extraction
  - Error handling
- [x] Update UI to support both conversion methods
  - Tabbed configuration dialog
  - File type filters based on selected method
  - Progress tracking and status updates
- [x] Optimize PDF processing
  - [x] Extract only required pages when max_pages is set
  - [x] Use temporary files for extracted pages
  - [x] Add error handling and user feedback
- [x] Create documentation and support files
  - [x] Add MarkItDown to requirements.txt
  - [x] Create installation script (install_markitdown.bat)
  - [x] Create README documentation (MARKITDOWN_README.md)
  - [x] Create detailed user guide (MARKITDOWN_USER_GUIDE.md)
  - [x] Create test script and batch file for verification

## Enhanced Table Extraction
- [x] Implement PyMuPDF-based table extraction
  - [x] Create pdf_table_extractor.py module
  - [x] Add table detection and extraction logic
  - [x] Implement text flow preservation around tables
  - [x] Add fallback to standard MarkItDown when tables can't be extracted
- [x] Integrate with MarkItDown client
  - [x] Add PyMuPDF availability check
  - [x] Implement conditional use of enhanced table extraction
  - [x] Add error handling and fallback mechanisms
- [x] Fix table extraction issues
  - [x] Fix TableFinder object handling
  - [x] Implement robust table list conversion
  - [x] Add proper error handling for PyMuPDF-specific operations
- [x] Create documentation and support files
  - [x] Add PyMuPDF to requirements.txt
  - [x] Create installation script for PyMuPDF
  - [x] Create documentation (ENHANCED_TABLE_EXTRACTION.md)
  - [x] Create test script for enhanced table extraction

## Robustness Improvements
- [x] Create batch processing script for automated processing
  - [x] Support for processing multiple files without user interaction
  - [x] Command-line arguments for input/output directories
  - [x] Recursive directory processing
  - [x] Error handling and reporting
- [x] Enhance application stability
  - [x] Create robust version of main application
  - [x] Add global exception handling
  - [x] Implement graceful error recovery
  - [x] Add signal handling for clean termination
- [x] Create convenience batch files
  - [x] Batch processing launcher
  - [x] Robust application launcher
  - [x] User-friendly error messages
- [x] Enhanced batch processing reliability
  - [x] Add resume capability to continue from where processing stopped
  - [x] Implement retry mechanism for failed files
  - [x] Add memory management with garbage collection
  - [x] Progress tracking and reporting
  - [x] Create robust batch processing launcher

## Token-Efficient Processing
- [x] Add options to limit text sent to GPT models
  - [x] Create text truncation settings in configuration dialog
  - [x] Add first N characters/tokens option
  - [x] Add first N paragraphs option
  - [x] Add custom regex pattern matching for targeted extraction
- [ ] Implement smart extraction modes
  - [ ] Document date extraction mode
  - [ ] Entity extraction mode (names, addresses, etc.)
  - [ ] Key information extraction mode
- [x] Add text selection processing
  - [x] Allow manual selection of text portions for processing
  - [x] Add right-click context menu for processing selected text
  - [x] Implement highlighting for selected text
- [ ] Create document summarization option
  - [ ] Add pre-processing step to generate document summary
  - [ ] Allow processing of summary instead of full document
  - [ ] Implement caching of summaries for repeated processing
- [x] Add token usage estimation and cost preview
  - [x] Show estimated token count before processing
  - [x] Display approximate cost based on current API pricing
  - [x] Add cost calculation column to the results table
  - [x] Update configuration dialog to show pricing information
- [x] Fix cost display issues
  - [x] Ensure cost is properly calculated and stored in database
  - [x] Implement direct cost update in UI after processing
  - [x] Add threaded cost update mechanism to avoid UI freezing
  - [x] Add debug logging for cost calculation and display
  - [x] Ensure cost is displayed correctly after table refresh

## MarkItDown Optimization
- [x] Optimize document ingestion with MarkItDown
  - [x] Save markdown files alongside source files
  - [x] Import markdown files directly into database
  - [x] Add caching mechanism to avoid reprocessing
  - [x] Implement file change detection
- [x] Enhance batch processing for markdown files
  - [x] Update batch processor to use cached markdown files
  - [x] Add option to regenerate markdown files
  - [x] Improve progress tracking for two-stage processing
- [x] Update UI for optimized workflow
  - [x] Add indicators for cached markdown files
  - [x] Provide options to manage cached files
  - [x] Maintain backward compatibility
- [x] Add direct markdown import functionality
  - [x] Add "Import Markdown" button to UI
  - [x] Support single file and folder import
  - [x] Match filenames to update existing entries
  - [x] Handle large documents exceeding Excel limits

## Installation and Packaging
- [x] Create comprehensive installation script
  - [x] Check for Python and pip
  - [x] Install all required packages
  - [x] Install correct version of MarkItDown
  - [x] Install PyMuPDF for enhanced table extraction
  - [x] Verify installation with quick test
- [x] Create packaging script for easy sharing
  - [x] Package all necessary files
  - [x] Include documentation
  - [x] Include installation and run scripts
  - [x] Provide clear instructions for sharing
- [x] Create simple run script
  - [x] Easy startup for non-technical users
  - [x] Clear error messages
- [x] Update documentation
  - [x] Create comprehensive README
  - [x] Document installation process
  - [x] Document usage instructions
  - [x] Document troubleshooting steps

## Development Phases

### Phase 1: Quick Setup (20 minutes) ✅
- [x] Create project structure
- [x] Set up virtual environment
- [x] Install core dependencies:
  - [x] PyQt6
  - [x] aiosqlite
  - [x] pandas
  - [x] aiohttp
  - [x] openai
  - [x] anthropic
  - [x] python-dotenv

### Phase 2: Core Development (80 minutes) ✅
- [x] Database Implementation
  - [x] SQLite schema with WAL
  - [x] Basic connection manager
  - [x] Essential tables setup
- [x] Basic GUI
  - [x] Main window
  - [x] Configuration dialog
  - [x] Data grid view
- [x] API Integration
  - [x] Async client setup
  - [x] Basic error handling
  - [x] Response processing

### Phase 3: Final Integration (20 minutes) ✅
- [x] Connect all components
- [x] Basic error handling
- [x] Quick testing
- [x] Initial run with sample data

### Phase 4: Enhanced Features (40 minutes) ✅
- [x] Add MarkItDown integration
- [x] Add enhanced table extraction
- [x] Create installation and packaging scripts
- [x] Update documentation

## Project Structure
```
sqlgpt/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── schema.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openai_client.py
│   │   ├── anthropic_client.py
│   │   ├── llamaparse_client.py
│   │   ├── markitdown_client.py
│   │   └── pdf_table_extractor.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── config_dialog.py
│       └── styles.py
├── requirements.txt
├── run.py
├── run.bat
├── install_all.bat
├── package_for_sharing.bat
├── README.md
├── MARKITDOWN_README.md
├── MARKITDOWN_USER_GUIDE.md
├── ENHANCED_TABLE_EXTRACTION.md
├── test_markitdown.py
├── test_markitdown.bat
├── test_enhanced_tables.py
└── test_enhanced_tables.bat
```

## Current Status
✅ Ready for Production

## Next Steps (Immediate)
1. [x] Create installation and test scripts for MarkItDown
2. [x] Document MarkItDown integration
3. [x] Create sample files for testing both conversion methods
4. [x] Debug and fix MarkItDown folder import functionality
   - [x] Verify MarkItDown installation and functionality
   - [x] Test individual PDF file processing
   - [x] Create debug script for folder import
   - [x] Test folder import with debug script
   - [x] Create debug script for progress dialog
   - [x] Identify and fix issue with progress dialog cancellation
5. [x] Enhance PDF table extraction
   - [x] Implement PyMuPDF-based table extraction
   - [x] Integrate with MarkItDown client
   - [x] Fix TableFinder object handling issues
   - [x] Add documentation and test scripts
6. [x] Create comprehensive installation and packaging
   - [x] Create all-in-one installation script
   - [x] Create packaging script for easy sharing
   - [x] Create simple run script
   - [x] Update documentation
7. [x] Perform final end-to-end testing
8. [x] Prepare for release

## Installation
```bash
# Option 1: Quick Installation (Recommended)
# Simply run the install_all.bat script

# Option 2: Manual Installation
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration
1. Set up environment variables:
   - OPENAI_API_KEY
   - ANTHROPIC_API_KEY
2. Configure model settings:
   - Select model (o1, o3-mini, or claude-3)
   - Set reasoning effort (for OpenAI models)
   - Adjust batch size based on rate limits
   - Set system prompt

## Notes
- Updated to latest Anthropic API (v0.7.0)
- Implemented proper rate limit handling
- Added token usage tracking for both APIs
- Added enhanced table extraction with PyMuPDF
- Created comprehensive installation and packaging scripts
- Fixed issues with TableFinder object handling
- Ready for distribution 