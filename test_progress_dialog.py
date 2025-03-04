import os
import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

from src.ui.main_window import ProgressDialog

async def test_progress_dialog():
    """Test the progress dialog"""
    app = QApplication(sys.argv)
    
    # Create and show the progress dialog
    progress_dialog = ProgressDialog(total_files=5)
    progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress_dialog.show()
    
    # Check the dialog's result code right after creation
    print(f"Dialog result code after creation: {progress_dialog.result()}")
    print(f"Dialog was_cancelled after creation: {progress_dialog.was_cancelled()}")
    
    # Make sure the dialog is displayed before continuing
    for _ in range(10):
        QApplication.processEvents()
        await asyncio.sleep(0.05)  # Short delay to ensure dialog is rendered
    
    # Check the dialog's result code after processing events
    print(f"Dialog result code after processing events: {progress_dialog.result()}")
    print(f"Dialog was_cancelled after processing events: {progress_dialog.was_cancelled()}")
    
    # Simulate processing files
    total_files = 5
    filenames = [
        "2021108.12 INV. 01 - SEPTEMBER.pdf",
        "2021108.12-INV. 2-OCTOBER.pdf",
        "2021108.12-INV. 3-NOVEMBER.pdf",
        "2021108.12-INV. 4-DECEMBER.pdf",
        "xPages from 2021108.12 INV. 01 - SEPTEMBER.pdf"
    ]
    
    for i, filename in enumerate(filenames):
        # Check if processing was cancelled
        if progress_dialog.was_cancelled():
            print("User cancelled processing")
            break
        
        # Update progress dialog
        progress_dialog.update_progress(i, total_files, filename)
        progress_dialog.update_status(f"Converting {filename} with MarkItDown")
        
        # Simulate processing time
        print(f"Processing file: {filename}")
        await asyncio.sleep(2)  # Simulate 2 seconds of processing time
        
        print(f"Successfully processed file {i+1}/{total_files}")
    
    # Close progress dialog if not cancelled
    if not progress_dialog.was_cancelled():
        progress_dialog.accept()
    
    # Show final status
    print(f"Processing complete: {total_files} files processed")
    
    # Exit the application
    app.quit()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_progress_dialog())
    
    print("\nTest complete.") 