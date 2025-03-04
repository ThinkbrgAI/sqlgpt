import os
import sys
import asyncio
import traceback
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

class DebugProgressDialog(QDialog):
    """Debug version of the progress dialog"""
    def __init__(self, parent=None, total_files=5):
        super().__init__(parent)
        self.setWindowTitle("Processing Files (Debug)")
        self.setMinimumWidth(450)
        self.setMinimumHeight(250)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        # Initialize with no result code set
        self._user_cancelled = False
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Title label with larger font
        title_label = QLabel("Converting Files to Markdown (Debug)")
        font = title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Add some spacing
        layout.addSpacing(10)
        
        # Status label with border
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_frame.setFrameShadow(QFrame.Shadow.Sunken)
        status_layout = QVBoxLayout(status_frame)
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)
        layout.addWidget(status_frame)
        
        # Progress bar with percentage
        progress_layout = QVBoxLayout()
        progress_label = QLabel("Overall Progress:")
        progress_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, total_files)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/%m files (%p%)")
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)
        
        # Current file label with frame
        file_frame = QFrame()
        file_frame.setFrameShape(QFrame.Shape.StyledPanel)
        file_layout = QVBoxLayout(file_frame)
        file_header = QLabel("Current File:")
        file_header.setStyleSheet("font-weight: bold;")
        file_layout.addWidget(file_header)
        
        self.file_label = QLabel("Preparing...")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        file_layout.addWidget(self.file_label)
        layout.addWidget(file_frame)
        
        # Progress counter
        self.counter_label = QLabel(f"0 / {total_files} files processed")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.counter_label)
        
        # Debug info label
        self.debug_label = QLabel("Debug: Dialog initialized")
        self.debug_label.setStyleSheet("color: red;")
        layout.addWidget(self.debug_label)
        
        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(self.cancel_processing)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # For animation
        self.dots = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(500)  # Update every 500ms
        
        # For debug timer
        self.debug_timer = QTimer(self)
        self.debug_timer.timeout.connect(self.update_debug_info)
        self.debug_timer.start(1000)  # Update every second
        
        self.debug_counter = 0
    
    def update_progress(self, current, total, filename=""):
        """Update the progress display"""
        self.progress_bar.setValue(current)
        self.counter_label.setText(f"{current} / {total} files processed")
        if filename:
            self.file_label.setText(f"{filename}")
        
        # Process events to ensure UI updates
        QApplication.processEvents()
    
    def update_status(self, status):
        """Update the status message"""
        self.status_label.setText(status)
        
        # Process events to ensure UI updates
        QApplication.processEvents()
    
    def update_animation(self):
        """Update the animated dots to show activity"""
        self.dots = (self.dots + 1) % 4
        dots_text = "." * self.dots
        current_text = self.status_label.text().rstrip('.')
        if current_text.endswith(" "):
            current_text = current_text.rstrip()
        self.status_label.setText(f"{current_text}{dots_text}")
        
        # Process events to ensure UI updates
        QApplication.processEvents()
    
    def update_debug_info(self):
        """Update debug information"""
        self.debug_counter += 1
        self.debug_label.setText(f"Debug: Dialog active for {self.debug_counter} seconds, cancelled: {self._user_cancelled}")
        
        # Process events to ensure UI updates
        QApplication.processEvents()

    def cancel_processing(self):
        """Handle cancel button click"""
        self._user_cancelled = True
        self.debug_label.setText(f"Debug: Cancel button clicked, setting cancelled flag to {self._user_cancelled}")
        QApplication.processEvents()
        self.reject()

    def was_cancelled(self):
        """Check if the user cancelled the operation"""
        return self._user_cancelled

async def simulate_processing():
    """Simulate file processing"""
    app = QApplication(sys.argv)
    
    # Create and show the progress dialog
    progress_dialog = DebugProgressDialog(total_files=5)
    progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress_dialog.show()
    
    # Check the dialog's result code right after creation
    print(f"Dialog result code after creation: {progress_dialog.result()}")
    print(f"Dialog was_cancelled after creation: {progress_dialog._user_cancelled}")
    
    # Make sure the dialog is displayed before continuing
    for _ in range(10):
        QApplication.processEvents()
        await asyncio.sleep(0.05)  # Short delay to ensure dialog is rendered
    
    # Check the dialog's result code after processing events
    print(f"Dialog result code after processing events: {progress_dialog.result()}")
    print(f"Dialog was_cancelled after processing events: {progress_dialog._user_cancelled}")
    
    # Simulate processing files
    total_files = 5
    processed_count = 0
    
    # List of sample filenames
    filenames = [
        "2021108.12 INV. 01 - SEPTEMBER.pdf",
        "2021108.12-INV. 2-OCTOBER.pdf",
        "2021108.12-INV. 3-NOVEMBER.pdf",
        "2021108.12-INV. 4-DECEMBER.pdf",
        "xPages from 2021108.12 INV. 01 - SEPTEMBER.pdf"
    ]
    
    for filename in filenames:
        # Check if processing was cancelled
        if progress_dialog.was_cancelled():
            print("User cancelled processing")
            break
        
        # Update progress dialog
        progress_dialog.update_progress(processed_count, total_files, filename)
        progress_dialog.update_status(f"Converting {filename} with MarkItDown")
        
        # Simulate processing time
        print(f"Processing file: {filename}")
        await asyncio.sleep(2)  # Simulate 2 seconds of processing time
        
        processed_count += 1
        print(f"Successfully processed file {processed_count}/{total_files}")
    
    # Close progress dialog if not cancelled
    if not progress_dialog.was_cancelled():
        progress_dialog.accept()
    
    # Show final status
    print(f"Processing complete: {processed_count} files processed")
    
    # Exit the application
    app.quit()

if __name__ == "__main__":
    # Run the simulation
    asyncio.run(simulate_processing())
    
    print("\nDebug complete.") 