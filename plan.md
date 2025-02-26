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
- [ ] Set up project structure
- [ ] Create initial implementation
- [ ] Add tests
- [ ] Review and refine

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

### Phase 3: Final Integration (20 minutes) 🚀
- [ ] Connect all components
- [ ] Basic error handling
- [ ] Quick testing
- [ ] Initial run with sample data

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
│   │   └── anthropic_client.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       └── config_dialog.py
└── requirements.txt
```

## Current Status
🚀 Ready for Testing

## Next Steps (Immediate)
1. Create a sample Excel file for testing
2. Test rate limit handling
3. Verify token counting and batch sizing
4. Document API-specific configurations

## Installation
```bash
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
- Ready for performance testing 