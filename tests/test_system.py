import os
import sys
import time
import asyncio
import pytest
from pathlib import Path
import pandas as pd
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QFileDialog
from PyQt6.QtCore import Qt
from src.ui.main_window import MainWindow
from src.config import config
from src.database.manager import DatabaseManager
from .mock_api_client import mock_openai_client, mock_anthropic_client

# Mock API clients
import src.api.openai_client
import src.api.anthropic_client
src.api.openai_client.openai_client = mock_openai_client
src.api.anthropic_client.anthropic_client = mock_anthropic_client

# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_EXCEL_FILE = TEST_DATA_DIR / "sample.xlsx"

# Mock QFileDialog
def mock_get_open_file_name(*args, **kwargs):
    return str(TEST_EXCEL_FILE), None

def mock_get_save_file_name(*args, **kwargs):
    return "export.xlsx", None

def mock_get_existing_directory(*args, **kwargs):
    return str(TEST_DATA_DIR)

# Original QFileDialog methods
original_get_open_file_name = QFileDialog.getOpenFileName
original_get_save_file_name = QFileDialog.getSaveFileName
original_get_existing_directory = QFileDialog.getExistingDirectory

@pytest.fixture(autouse=True)
def mock_file_dialogs():
    """Mock file dialogs for testing"""
    QFileDialog.getOpenFileName = mock_get_open_file_name
    QFileDialog.getSaveFileName = mock_get_save_file_name
    QFileDialog.getExistingDirectory = mock_get_existing_directory
    yield
    QFileDialog.getOpenFileName = original_get_open_file_name
    QFileDialog.getSaveFileName = original_get_save_file_name
    QFileDialog.getExistingDirectory = original_get_existing_directory

@pytest.fixture
def app():
    """Create QApplication instance"""
    app = QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture
def main_window(app):
    """Create MainWindow instance"""
    window = MainWindow()
    return window

@pytest.fixture
async def db():
    """Create and initialize test database"""
    db_manager = DatabaseManager("test.db")
    await db_manager.initialize()
    yield db_manager
    # Cleanup
    try:
        os.remove("test.db")
    except:
        pass

@pytest.mark.asyncio
async def test_folder_import(main_window):
    """Test importing files from a folder"""
    main_window.import_folder()
    assert main_window.table.rowCount() > 0
    
    # Verify file contents
    found_files = set()
    for row in range(main_window.table.rowCount()):
        filename = main_window.table.item(row, 0).text()
        found_files.add(filename)
    
    assert "test1.txt" in found_files
    assert "subfolder/test3.md" in found_files

@pytest.mark.asyncio
async def test_excel_import(main_window):
    """Test importing from Excel file"""
    main_window.import_excel()
    assert main_window.table.rowCount() == 3
    
    # Verify contents
    assert main_window.table.item(0, 0).text() == "question1.txt"
    assert "quantum entanglement" in main_window.table.item(0, 1).text()

@pytest.mark.asyncio
async def test_processing(main_window, db):
    """Test document processing"""
    # Set up test configuration
    config.openai_api_key = "test_key"
    config.selected_model = "gpt-4-turbo-preview"
    config.system_prompt = "Test prompt"
    
    # Import test data
    main_window.import_folder()
    assert main_window.table.rowCount() > 0
    
    # Start processing
    main_window.start_processing()
    
    # Wait for processing to complete
    while main_window.processing_thread and main_window.processing_thread.isRunning():
        await asyncio.sleep(0.1)
    
    # Verify results
    assert main_window.table.item(0, 2) is not None
    assert "Mock response" in main_window.table.item(0, 2).text()

@pytest.mark.asyncio
async def test_rate_limiting(main_window):
    """Test rate limiting functionality"""
    config.selected_model = "gpt-4-turbo-preview"
    config.openai_api_key = "test_key"
    
    # Create many test documents to trigger rate limiting
    documents = [
        {"filename": f"test{i}.txt", "content": f"Test content {i}"}
        for i in range(50)  # Should trigger rate limiting
    ]
    
    # Add to table
    main_window.table.setRowCount(len(documents))
    for i, doc in enumerate(documents):
        main_window.table.setItem(i, 0, QTableWidgetItem(doc["filename"]))
        main_window.table.setItem(i, 1, QTableWidgetItem(doc["content"]))
    
    # Start processing
    main_window.start_processing()
    
    # Monitor rate limiting
    rate_limit_hit = False
    start_time = time.time()
    while time.time() - start_time < 10:  # Check for 10 seconds
        if "Rate limit reached" in main_window.status_label.text():
            rate_limit_hit = True
            break
        await asyncio.sleep(0.1)
    
    assert rate_limit_hit, "Rate limiting was not triggered"

@pytest.mark.asyncio
async def test_export(main_window):
    """Test exporting results to Excel"""
    # Import and process some test data
    main_window.import_folder()
    
    # Add some mock responses
    for row in range(main_window.table.rowCount()):
        main_window.table.setItem(row, 2, QTableWidgetItem(f"Mock response {row}"))
    
    # Export to Excel
    main_window.export_excel()
    
    # Verify export
    try:
        df = pd.read_excel("export.xlsx")
        assert len(df) > 0
        assert "Filename" in df.columns
        assert "Source Doc" in df.columns
        assert "Response" in df.columns
        assert df["Response"].iloc[0] == "Mock response 0"
    finally:
        try:
            os.remove("export.xlsx")
        except:
            pass

if __name__ == "__main__":
    pytest.main([__file__]) 