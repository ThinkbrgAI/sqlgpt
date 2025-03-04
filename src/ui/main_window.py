import sys
import os
import asyncio
import time
import shutil
from datetime import datetime, timedelta
from collections import deque
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTableWidget, QTableWidgetItem, 
    QProgressBar, QLabel, QFileDialog, QMessageBox, QHeaderView,
    QTextEdit, QSplitter, QDialog, QApplication, QFrame, QInputDialog, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, pyqtSlot, Q_ARG, QMetaObject
from PyQt6.QtGui import QAction, QPixmap
import pandas as pd
from ..config import config
from .config_dialog import ConfigDialog
from ..database.manager import DatabaseManager
from ..api.openai_client import openai_client
from ..api.anthropic_client import anthropic_client
from ..api.llamaparse_client import llamaparse_client
from ..api.markitdown_client import markitdown_client
from .styles import DARK_THEME
import json
import threading

class RateLimiter:
    def __init__(self, requests_per_minute, tokens_per_minute):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_timestamps = deque()
        self.token_usage = deque()
        self.window = 60  # 1 minute in seconds

    def can_make_request(self, estimated_tokens=1000):
        now = time.time()
        self._cleanup_old_entries(now)

        # Check request rate
        if len(self.request_timestamps) >= self.requests_per_minute:
            return False

        # Check token rate
        current_token_usage = sum(tokens for _, tokens in self.token_usage)
        if current_token_usage + estimated_tokens > self.tokens_per_minute:
            return False

        return True

    def add_request(self, token_count):
        now = time.time()
        self.request_timestamps.append(now)
        self.token_usage.append((now, token_count))
        self._cleanup_old_entries(now)

    def _cleanup_old_entries(self, now):
        cutoff = now - self.window
        
        while self.request_timestamps and self.request_timestamps[0] < cutoff:
            self.request_timestamps.popleft()
            
        while self.token_usage and self.token_usage[0][0] < cutoff:
            self.token_usage.popleft()

class ProcessingThread(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal()
    error = pyqtSignal(str)
    update_response = pyqtSignal(int, str)  # row, response
    status_update = pyqtSignal(str)  # status message

    def __init__(self, db_manager, documents, model_name):
        super().__init__()
        self.db_manager = db_manager
        self.documents = documents
        self.model_name = model_name
        self.should_stop = False
        
        # Initialize rate limiter based on model
        limits = config.model_rate_limits[model_name]
        if model_name.startswith("claude"):
            self.rate_limiter = RateLimiter(
                limits["requests_per_minute"],
                min(limits["input_tokens_per_minute"], limits["output_tokens_per_minute"])
            )
        else:
            self.rate_limiter = RateLimiter(
                limits["requests_per_minute"],
                limits["tokens_per_minute"]
            )

    async def process_document(self, job, client):
        """Process a single document"""
        try:
            if self.should_stop:
                return False
            print(f"Processing document for row {job['row_index']}...")  # Debug logging
            
            # Add more debug logging
            print(f"Document content length: {len(job['source_doc'])}")
            print(f"Document content preview: {job['source_doc'][:100]}...")
            print(f"Using model: {self.model_name}")
            
            # Process the document
            response, token_count = await client.process_document(job["source_doc"])
            
            # Add more debug logging for the response
            print(f"Received response length: {len(response)}")
            print(f"Response preview: {response[:100]}...")
            print(f"Token count: {token_count}")
            
            if not response or len(response.strip()) == 0:
                print("WARNING: Empty response received from API!")
                # Use a placeholder response instead of empty string
                response = "No response was generated. Please check API configuration and try again."
            
            if self.should_stop:  # Check again after API call
                return False
                
            # Update the database with the response
            await self.db_manager.update_response(job["id"], response, token_count)
            
            # CRITICAL FIX: Directly update the status to completed and ensure token count and cost are set
            # This ensures the cost will be displayed correctly
            conn = await self.db_manager.get_connection()
            try:
                # Calculate cost
                cost = self.db_manager.calculate_cost(self.model_name, token_count)
                
                # Force update status, token_count, and cost
                await conn.execute(
                    """UPDATE processing_jobs 
                       SET status = 'completed', token_count = ?, cost = ? 
                       WHERE id = ?""",
                    (token_count, cost, job["id"])
                )
                await conn.commit()
                print(f"CRITICAL FIX: Directly updated job {job['id']} with status='completed', token_count={token_count}, cost=${cost:.6f}")
            finally:
                await self.db_manager.release_connection(conn)
            
            print(f"Emitting update_response signal for row {job['row_index']}...")  # Debug logging
            self.update_response.emit(job["row_index"], response)
            self.rate_limiter.add_request(token_count)
            print(f"Completed processing for row {job['row_index']}")  # Debug logging
            return True
        except Exception as e:
            print(f"Error processing job {job['id']}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"Error processing job {job['id']}: {str(e)}")
            
            # Update with error message instead of leaving empty
            error_response = f"Error processing: {str(e)}"
            try:
                await self.db_manager.update_response(job["id"], error_response, 0)
                self.update_response.emit(job["row_index"], error_response)
            except Exception as inner_e:
                print(f"Error updating with error message: {str(inner_e)}")
            return False

    async def process_batch(self):
        try:
            # Initialize API client based on model
            if self.model_name.startswith("o"):
                client = openai_client
                client.set_api_key(config.openai_api_key)
                # OpenAI models have very high rate limits
                if self.model_name == "o1":
                    max_concurrent = min(config.batch_size, 100)  # 1000 RPM -> conservative 100 concurrent
                else:  # o3-mini
                    max_concurrent = min(config.batch_size, 300)  # 30000 RPM -> conservative 300 concurrent
            else:
                client = anthropic_client
                client.set_api_key(config.anthropic_api_key)
                # Claude can handle large concurrent requests
                max_concurrent = min(config.batch_size, 100)  # 4000 RPM -> conservative 100 concurrent

            # Add batch to database
            batch_id = await self.db_manager.add_batch(self.documents, self.model_name)
            pending_jobs = await self.db_manager.get_pending_jobs(batch_id)

            # Process in parallel
            total_jobs = len(pending_jobs)
            processed = 0
            active_tasks = set()

            while (pending_jobs or active_tasks) and not self.should_stop:
                # Start new tasks up to max_concurrent
                while len(active_tasks) < max_concurrent and pending_jobs and not self.should_stop:
                    job = pending_jobs.pop(0)
                    task = asyncio.create_task(self.process_document(job, client))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)

                if not active_tasks:
                    break

                # Wait for at least one task to complete
                done, _ = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                
                # Process completed tasks
                for task in done:
                    try:
                        result = task.result()
                        if result:
                            processed += 1
                    except Exception as e:
                        self.error.emit(f"Task error: {str(e)}")

                # Update progress
                self.progress.emit(processed, total_jobs)
                self.status_update.emit(f"Processing: {len(active_tasks)} active tasks, {len(pending_jobs)} pending")

                # If we got any failures, slow down a bit
                if len(done) > 0 and not any(t.result() for t in done if not t.exception()):
                    await asyncio.sleep(1)

                # Check stop flag
                if self.should_stop:
                    # Cancel all active tasks
                    for task in active_tasks:
                        if not task.done():
                            task.cancel()
                    # Wait for tasks to complete/cancel
                    try:
                        await asyncio.gather(*active_tasks, return_exceptions=True)
                    except asyncio.CancelledError:
                        pass
                    break

            if self.should_stop:
                self.status_update.emit("Processing stopped by user")
            else:
                self.status_update.emit("Processing completed")
            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Batch processing error: {str(e)}")
            self.finished.emit()

    def run(self):
        """Run the processing thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.process_batch())
        finally:
            loop.close()

    def stop(self):
        """Stop processing"""
        print("Stopping processing...")  # Debug logging
        self.should_stop = True
        self.status_update.emit("Stopping... Please wait for in-progress tasks to complete...")

class ProgressDialog(QDialog):
    """Dialog to show progress during file processing"""
    def __init__(self, parent=None, total_files=0):
        super().__init__(parent)
        self.setWindowTitle("Processing Files")
        self.setMinimumWidth(450)
        self.setMinimumHeight(250)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        # Initialize with no result code set
        self._user_cancelled = False
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Title label with larger font
        title_label = QLabel("Converting Files to Markdown")
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
        
        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(self.cancel_processing)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Keep dialog on top
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # For animation
        self.dots = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(500)  # Update every 500ms
    
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

    def cancel_processing(self):
        """Handle cancel button click"""
        self._user_cancelled = True
        self.reject()

    def was_cancelled(self):
        """Check if the user cancelled the operation"""
        return self._user_cancelled

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPT Batch Processor")
        self.setMinimumSize(800, 600)
        
        # Apply dark theme
        self.setStyleSheet(DARK_THEME)
        
        # Initialize components
        self.db_manager = DatabaseManager()
        self.current_batch_id = None
        self.processing_thread = None
        
        # Add flag to prevent double import
        self.is_importing = False
        
        # Create UI
        self.setup_ui()

    def setup_ui(self):
        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for full width

        # Add company header image as background for top section
        header_image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                        "resources", "BRG Personal Header 4.jpg")
        
        if os.path.exists(header_image_path):
            # Create header container
            header_container = QWidget()
            header_container.setFixedHeight(120)  # Set fixed height for header area
            
            # Create a label for the background image
            header_bg_label = QLabel(header_container)
            header_bg_label.setPixmap(QPixmap(header_image_path).scaled(
                2000, 120,  # Make it extra wide to ensure it fills the window
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            header_bg_label.setAlignment(Qt.AlignmentFlag.AlignLeft)  # Align to left
            header_bg_label.setStyleSheet("background-color: #2b2b2b;")  # Match background color
            
            # Create toolbar with transparent background
            toolbar_widget = QWidget(header_container)
            toolbar_widget.setStyleSheet("background-color: rgba(43, 43, 43, 150);")  # Semi-transparent
            
            # Create toolbar layout
            toolbar = QHBoxLayout(toolbar_widget)
            toolbar.setSpacing(6)
            toolbar.setContentsMargins(6, 6, 6, 6)
            
            # Add buttons to toolbar
            self.import_btn = QPushButton("Import PDF")
            self.import_btn.setObjectName("import_btn")
            self.import_btn.clicked.connect(self.handle_import_pdf)
            toolbar.addWidget(self.import_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.import_folder_btn = QPushButton("Import Folder")
            self.import_folder_btn.setObjectName("import_folder_btn")
            self.import_folder_btn.clicked.connect(self.handle_import_folder_pdf)
            toolbar.addWidget(self.import_folder_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.import_md_btn = QPushButton("Import Markdown")
            self.import_md_btn.setObjectName("import_md_btn")
            self.import_md_btn.clicked.connect(self.handle_import_markdown)
            toolbar.addWidget(self.import_md_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.process_btn = QPushButton("Process with GPT")
            self.process_btn.setObjectName("process_btn")
            self.process_btn.clicked.connect(self.start_processing)
            toolbar.addWidget(self.process_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.stop_btn = QPushButton("Stop Processing")
            self.stop_btn.setObjectName("stop_btn")
            self.stop_btn.clicked.connect(self.stop_processing)
            self.stop_btn.setEnabled(False)
            toolbar.addWidget(self.stop_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.clear_btn = QPushButton("Clear Responses")
            self.clear_btn.setObjectName("clear_btn")
            self.clear_btn.clicked.connect(self.clear_responses)
            toolbar.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.clear_all_btn = QPushButton("Clear All Data")
            self.clear_all_btn.setObjectName("clear_all_btn")
            self.clear_all_btn.clicked.connect(self.clear_all_data)
            toolbar.addWidget(self.clear_all_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.export_btn = QPushButton("Export to Excel")
            self.export_btn.setObjectName("export_btn")
            self.export_btn.clicked.connect(self.export_excel)
            toolbar.addWidget(self.export_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.import_excel_btn = QPushButton("Import from Excel")
            self.import_excel_btn.setObjectName("import_excel_btn")
            self.import_excel_btn.clicked.connect(self.import_excel)
            toolbar.addWidget(self.import_excel_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.config_btn = QPushButton("Configure")
            self.config_btn.setObjectName("config_btn")
            self.config_btn.clicked.connect(self.show_config_dialog)
            toolbar.addWidget(self.config_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            # Add stretch to prevent buttons from expanding
            toolbar.addStretch(1)
            
            # Use a stacked layout to position the toolbar over the header image
            from PyQt6.QtWidgets import QStackedLayout
            stacked_layout = QStackedLayout(header_container)
            stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
            stacked_layout.addWidget(header_bg_label)
            stacked_layout.addWidget(toolbar_widget)
            
            # Make sure toolbar is visible
            toolbar_widget.raise_()
            
            # Add the header container to the main layout
            layout.addWidget(header_container)
        else:
            print(f"Warning: Header image not found at {header_image_path}")
            
            # Create toolbar without header image
            toolbar = QHBoxLayout()
            toolbar.setSpacing(6)  # Set spacing between buttons
            toolbar.setContentsMargins(6, 6, 6, 6)  # Set margins around buttons
            
            # Add buttons to toolbar
            self.import_btn = QPushButton("Import PDF")
            self.import_btn.setObjectName("import_btn")
            self.import_btn.clicked.connect(self.handle_import_pdf)
            toolbar.addWidget(self.import_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.import_folder_btn = QPushButton("Import Folder")
            self.import_folder_btn.setObjectName("import_folder_btn")
            self.import_folder_btn.clicked.connect(self.handle_import_folder_pdf)
            toolbar.addWidget(self.import_folder_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.import_md_btn = QPushButton("Import Markdown")
            self.import_md_btn.setObjectName("import_md_btn")
            self.import_md_btn.clicked.connect(self.handle_import_markdown)
            toolbar.addWidget(self.import_md_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.process_btn = QPushButton("Process with GPT")
            self.process_btn.setObjectName("process_btn")
            self.process_btn.clicked.connect(self.start_processing)
            toolbar.addWidget(self.process_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.stop_btn = QPushButton("Stop Processing")
            self.stop_btn.setObjectName("stop_btn")
            self.stop_btn.clicked.connect(self.stop_processing)
            self.stop_btn.setEnabled(False)
            toolbar.addWidget(self.stop_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.clear_btn = QPushButton("Clear Responses")
            self.clear_btn.setObjectName("clear_btn")
            self.clear_btn.clicked.connect(self.clear_responses)
            toolbar.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.clear_all_btn = QPushButton("Clear All Data")
            self.clear_all_btn.setObjectName("clear_all_btn")
            self.clear_all_btn.clicked.connect(self.clear_all_data)
            toolbar.addWidget(self.clear_all_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.export_btn = QPushButton("Export to Excel")
            self.export_btn.setObjectName("export_btn")
            self.export_btn.clicked.connect(self.export_excel)
            toolbar.addWidget(self.export_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.import_excel_btn = QPushButton("Import from Excel")
            self.import_excel_btn.setObjectName("import_excel_btn")
            self.import_excel_btn.clicked.connect(self.import_excel)
            toolbar.addWidget(self.import_excel_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            self.config_btn = QPushButton("Configure")
            self.config_btn.setObjectName("config_btn")
            self.config_btn.clicked.connect(self.show_config_dialog)
            toolbar.addWidget(self.config_btn, 0, Qt.AlignmentFlag.AlignLeft)
            
            # Add toolbar to main layout
            toolbar.addStretch(1)  # Add stretch to prevent buttons from expanding
            layout.addLayout(toolbar)

        # Progress section below toolbar
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        # Add truncation indicator
        self.truncation_indicator = QLabel("")
        self.update_truncation_indicator()
        progress_layout.addWidget(self.truncation_indicator)
        
        layout.addLayout(progress_layout)

        # Create a splitter for the content viewer and table
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Content viewer
        self.content_viewer = QTextEdit()
        self.content_viewer.setReadOnly(True)
        self.content_viewer.setMinimumHeight(50)  # Minimum height when collapsed
        self.content_viewer.setPlaceholderText("Click a cell to view its contents...")
        splitter.addWidget(self.content_viewer)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)  # Increase column count to include Cost
        self.table.setHorizontalHeaderLabels(["Filename", "Source Doc", "Response", "Cost ($)"])
        
        # Set minimum column widths but allow resizing
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(100)  # Minimum width for all columns
        self.table.setColumnWidth(0, 200)  # Initial width for Filename
        self.table.setColumnWidth(1, 300)  # Initial width for Source Doc
        self.table.setColumnWidth(2, 400)  # Initial width for Response
        self.table.setColumnWidth(3, 100)  # Initial width for Cost
        
        # Ensure the response column is visible and has a reasonable width
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Make Response column stretch
        
        # Set strict fixed row height
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setMinimumSectionSize(30)
        self.table.verticalHeader().setMaximumSectionSize(30)
        
        # Disable word wrap to prevent height changes
        self.table.setWordWrap(False)
        
        # Add table to splitter
        splitter.addWidget(self.table)
        
        # Set initial sizes for splitter (content viewer : table ratio)
        splitter.setSizes([100, 500])
        
        # Add splitter to main layout
        layout.addWidget(splitter)

        # Connect signals
        self.config_btn.clicked.connect(self.show_config_dialog)
        self.import_excel_btn.clicked.connect(self.import_excel)
        self.process_btn.clicked.connect(self.start_processing)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.clear_btn.clicked.connect(self.clear_responses)
        self.table.cellClicked.connect(self.update_content_viewer)
        self.table.currentCellChanged.connect(lambda current_row, current_column, previous_row, previous_column: 
            self.update_content_viewer(current_row, current_column))

        # Create File menu
        self.file_menu = self.menuBar().addMenu("File")
        
        # Add new database action
        self.new_database_action = QAction("New Database...", self)
        self.new_database_action.triggered.connect(self.create_new_database)
        self.file_menu.addAction(self.new_database_action)
        
        # Add save database action
        self.save_database_action = QAction("Save Database As...", self)
        self.save_database_action.triggered.connect(self.save_database)
        self.file_menu.addAction(self.save_database_action)
        
        # Add load database action
        self.load_database_action = QAction("Load Database...", self)
        self.load_database_action.triggered.connect(self.load_database)
        self.file_menu.addAction(self.load_database_action)

    def show_config_dialog(self):
        dialog = ConfigDialog(self)
        dialog.exec()

    def import_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Import", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder_path:
            try:
                documents = []
                # Support all text-based formats that can be directly read
                text_extensions = ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm']
                
                for ext in text_extensions:
                    for file_path in Path(folder_path).rglob(f'*{ext}'):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if content:  # Only add non-empty files
                                    documents.append({
                                        "filename": str(file_path.relative_to(folder_path)),
                                        "content": content
                                    })
                        except Exception as e:
                            print(f"Error reading {file_path}: {e}")
                            continue

                if not documents:
                    # If no text files found, suggest using the Convert Folder to MD option
                    reply = QMessageBox.question(
                        self,
                        "No Text Files Found",
                        "No valid text files found in the selected folder.\n\n"
                        "Would you like to use the 'Convert Folder to MD' feature instead? "
                        "This can convert PDFs, Office documents, images, and other file types to Markdown.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        # Call the import_folder_pdf handler
                        self.handle_import_folder_pdf()
                    return

                # Update table
                self.table.setRowCount(len(documents))
                for i, doc in enumerate(documents):
                    self.table.setItem(i, 0, QTableWidgetItem(doc["filename"]))
                    self.table.setItem(i, 1, QTableWidgetItem(doc["content"]))

                QMessageBox.information(
                    self, "Success", 
                    f"Imported {len(documents)} files successfully"
                )

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import folder: {str(e)}")

    def import_excel(self):
        print("Starting import_excel function")
        
        # Check if already importing to prevent double calls
        if self.is_importing:
            print("Already importing, ignoring duplicate call")
            return
            
        self.is_importing = True
        
        try:
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Import Excel File", "", "Excel Files (*.xlsx *.xls)"
            )
            print(f"Selected file: {file_name}")
            
            if file_name:
                try:
                    print(f"Reading Excel file: {file_name}")
                    df = pd.read_excel(file_name)
                    required_cols = {"Source Doc"}
                    if not required_cols.issubset(df.columns):
                        print(f"Required column 'Source Doc' not found. Available columns: {df.columns.tolist()}")
                        raise ValueError("Excel file must have a 'Source Doc' column")
                    
                    # Update table
                    print(f"Updating table with {len(df)} rows")
                    self.table.setRowCount(len(df))
                    
                    # Sort by Row Number if it exists
                    if "Row Number" in df.columns:
                        print("Found Row Number column, sorting by it...")
                        df = df.sort_values(by="Row Number")
                    
                    for i, row in df.iterrows():
                        # Use Excel filename as default if not specified
                        filename = row.get("Filename", os.path.basename(file_name))
                        self.table.setItem(i, 0, QTableWidgetItem(str(filename)))
                        self.table.setItem(i, 1, QTableWidgetItem(str(row["Source Doc"])))
                        if "Response" in df.columns and pd.notna(row["Response"]):
                            self.table.setItem(i, 2, QTableWidgetItem(str(row["Response"])))
                    
                    # Check and fix table display after importing
                    self.check_and_fix_table_display()
                    
                    print("Excel data imported successfully")
                    QMessageBox.information(self, "Success", "Data imported successfully")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Error importing Excel: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to import: {str(e)}")
        finally:
            # Reset the flag when done
            self.is_importing = False

    def export_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No data to export")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export Excel File", "", "Excel Files (*.xlsx)"
        )
        if file_name:
            try:
                data = []
                print(f"Starting Excel export with {self.table.rowCount()} rows")  # Debug logging
                
                # Excel has a cell size limit of approximately 32,767 characters
                max_cell_size = 32000  # Setting slightly below the limit for safety
                
                for row in range(self.table.rowCount()):
                    filename = self.table.item(row, 0)
                    source = self.table.item(row, 1)
                    response = self.table.item(row, 2)
                    cost = self.table.item(row, 3)
                    
                    # Debug logging for row data
                    print(f"Row {row} data:")
                    print(f"  Filename: {filename.text() if filename else 'None'}")
                    print(f"  Source length: {len(source.text()) if source else 0} characters")
                    print(f"  Response length: {len(response.text()) if response else 0} characters")
                    print(f"  Cost: {cost.text() if cost else '$0.00'}")
                    
                    # Get text values, truncating if necessary
                    filename_text = filename.text() if filename else ""
                    
                    source_text = source.text() if source else ""
                    if len(source_text) > max_cell_size:
                        print(f"  Truncating Source Doc for row {row} (length: {len(source_text)})")
                        source_text = source_text[:max_cell_size] + "... (truncated)"
                    
                    response_text = response.text() if response else ""
                    if len(response_text) > max_cell_size:
                        print(f"  Truncating Response for row {row} (length: {len(response_text)})")
                        response_text = response_text[:max_cell_size] + "... (truncated)"
                    
                    # Get cost value, removing the $ symbol if present
                    cost_text = cost.text() if cost else ""
                    cost_value = cost_text.replace('$', '') if cost_text else "0.00"
                    
                    row_data = {
                        "Row Number": row + 1,  # Add row number (1-indexed for user readability)
                        "Filename": filename_text,
                        "Source Doc": source_text,
                        "Response": response_text,
                        "Cost ($)": cost_value
                    }
                    data.append(row_data)
                    
                print(f"Created data list with {len(data)} rows")  # Debug logging
                
                # Try different export methods
                try:
                    print("Attempting standard export...")
                    df = pd.DataFrame(data)
                    print(f"Created DataFrame with shape: {df.shape}")  # Debug logging
                    df.to_excel(file_name, index=False)
                    print("Standard export successful")
                except Exception as e1:
                    print(f"Standard export failed: {str(e1)}")
                    try:
                        print("Attempting export with engine='openpyxl'...")
                        df.to_excel(file_name, index=False, engine='openpyxl')
                        print("Export with engine='openpyxl' successful")
                    except Exception as e2:
                        print(f"Export with engine='openpyxl' failed: {str(e2)}")
                        # If all else fails, try CSV as a fallback
                        try:
                            print("Attempting CSV export as fallback...")
                            csv_file = file_name.replace('.xlsx', '.csv')
                            df.to_csv(csv_file, index=False)
                            print(f"CSV export successful: {csv_file}")
                            QMessageBox.information(
                                self, 
                                "CSV Export", 
                                f"Excel export failed, but data was successfully exported to CSV: {csv_file}"
                            )
                            return
                        except Exception as e3:
                            print(f"CSV export failed: {str(e3)}")
                            raise Exception(f"All export attempts failed")
                
                QMessageBox.information(self, "Success", "Data exported successfully")
            except Exception as e:
                print(f"Export error: {str(e)}")  # Debug logging
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

    def check_and_fix_table_display(self):
        """Check and fix table display issues"""
        print("Checking and fixing table display...")
        
        # Ensure the response column is visible and has a reasonable width
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # Make sure the table is visible
        self.table.show()
        self.table.setVisible(True)
        
        # Force a refresh of the table
        self.table.viewport().update()
        self.table.update()
        
        # Process events to ensure UI updates
        QApplication.processEvents()
        
        print("Table display check completed")

    def start_processing(self):
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Processing is already in progress")
            return

        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No data to process")
            return

        if not config.openai_api_key and not config.anthropic_api_key:
            QMessageBox.warning(self, "Warning", "Please configure API keys first")
            return
            
        # Check and fix table display before processing
        self.check_and_fix_table_display()

        # Collect documents
        documents = []
        for row in range(self.table.rowCount()):
            filename = self.table.item(row, 0)
            source = self.table.item(row, 1)
            if source and source.text().strip():
                documents.append({
                    "filename": filename.text() if filename else "",
                    "content": source.text().strip()
                })

        # Set up progress bar
        total_documents = len(documents)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(total_documents * 100)  # Multiply by 100 for percentage
        self.progress_bar.setValue(0)
        self.status_label.setText("Processing...")
        
        # Enable stop button and disable process button
        self.stop_btn.setEnabled(True)
        self.process_btn.setEnabled(False)
        
        self.processing_thread = ProcessingThread(self.db_manager, documents, config.selected_model)
        self.processing_thread.progress.connect(self.update_progress)
        self.processing_thread.error.connect(self.show_error)
        self.processing_thread.finished.connect(self.processing_finished)
        self.processing_thread.update_response.connect(self.update_table_response)
        self.processing_thread.status_update.connect(self.update_status)
        self.processing_thread.start()

    def update_progress(self, current, total):
        # Convert progress to percentage (0-100) and scale to progress bar range
        progress_value = int((current / total) * 100 * total)
        self.progress_bar.setValue(progress_value)
        self.status_label.setText(f"Processing: {current}/{total} ({int((current/total)*100)}%)")

    def show_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)

    def processing_finished(self):
        """Called when processing is finished"""
        print("Processing finished signal received")
        
        # Update the UI
        self.progress_bar.setValue(0)
        self.status_label.setText("Processing complete")
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # CRITICAL FIX: Update all costs in the table
        self.update_all_costs()
        
        # Show success message
        QMessageBox.information(self, "Success", "Batch processing completed")
        
        print("Processing finished method completed")
        
    def update_all_costs(self):
        """Update all costs in the table"""
        print("Updating all costs in the table")
        
        # Create a new thread to update all costs
        thread = threading.Thread(target=self._update_all_costs_thread)
        thread.daemon = True
        thread.start()
        
    def _update_all_costs_thread(self):
        """Update all costs in a separate thread"""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async update method
                loop.run_until_complete(self._async_update_all_costs())
            finally:
                loop.close()
                
            print("Completed updating all costs")
        except Exception as e:
            print(f"Error updating all costs: {str(e)}")
            import traceback
            traceback.print_exc()
            
    async def _async_update_all_costs(self):
        """Async method to update all costs"""
        conn = await self.db_manager.get_connection()
        try:
            # Get all completed jobs with token counts
            async with conn.execute(
                """SELECT id, row_index, model_name, token_count, cost 
                   FROM processing_jobs 
                   WHERE token_count > 0
                   ORDER BY row_index"""
            ) as cursor:
                rows = await cursor.fetchall()
                
                print(f"Found {len(rows)} jobs with token counts")
                
                for row in rows:
                    job_id = row[0]
                    row_index = row[1]
                    model_name = row[2]
                    token_count = row[3]
                    current_cost = row[4] or 0
                    
                    # If cost is 0 but we have tokens, recalculate it
                    if current_cost == 0 and token_count > 0:
                        # Calculate cost
                        cost = self.db_manager.calculate_cost(model_name, token_count)
                        
                        # Update the database
                        await conn.execute(
                            """UPDATE processing_jobs SET cost = ?, status = 'completed' WHERE id = ?""",
                            (cost, job_id)
                        )
                        await conn.commit()
                        
                        print(f"Updated cost for job {job_id} (row {row_index}): ${cost:.6f}")
                        
                        # Update the UI if the row exists
                        if row_index < self.table.rowCount():
                            cost_text = f"${cost:.6f}"
                            cost_item = QTableWidgetItem(cost_text)
                            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            self.table.setItem(row_index, 3, cost_item)
                            print(f"Updated cost display for row {row_index}: {cost_text}")
                    elif current_cost > 0:
                        # Cost is already set, just update the UI
                        if row_index < self.table.rowCount():
                            cost_text = f"${current_cost:.6f}"
                            cost_item = QTableWidgetItem(cost_text)
                            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            self.table.setItem(row_index, 3, cost_item)
                            print(f"Updated existing cost display for row {row_index}: {cost_text}")
                
                # Force a refresh of the table
                self.table.viewport().update()
                self.table.update()
                QApplication.processEvents()
        finally:
            await self.db_manager.release_connection(conn)

    def update_table_response(self, row, response):
        """Update a response in the table"""
        print(f"Starting update_table_response for row {row}...")  # Debug logging
        try:
            print(f"Current table row count: {self.table.rowCount()}")  # Debug logging
            
            # Validate row index
            if row >= self.table.rowCount():
                print(f"Error: Row index {row} is out of bounds (table has {self.table.rowCount()} rows)")
                return
                
            print(f"Creating QTableWidgetItem for row {row}, column 2")  # Debug logging
            
            # Ensure response is not None and is a string
            if response is None:
                print("Warning: Response is None, using empty string")
                response = ""
            elif not isinstance(response, str):
                print(f"Warning: Response is not a string, converting from {type(response)}")
                response = str(response)
            
            # Debug the response text
            print(f"Response text length: {len(response)}")
            if len(response) > 0:
                print(f"Response text preview: {response[:100]}...")
            else:
                print("Response text is empty!")
            
            # Create a new item with the response text
            item = QTableWidgetItem(response)
            
            # Ensure proper styling for the item - use black text on light green background for better visibility
            item.setForeground(Qt.GlobalColor.black)  # Set text color to black for better visibility
            item.setBackground(Qt.GlobalColor.green)  # Set background to green for completed items
            
            print(f"Setting item for row {row}, column 2")  # Debug logging
            self.table.setItem(row, 2, item)
            print(f"Successfully updated row {row}")  # Debug logging
            
            # Verify the update
            updated_item = self.table.item(row, 2)
            if updated_item:
                print(f"Verified update for row {row}: {updated_item.text()[:50]}...")  # Debug logging
            else:
                print(f"Warning: Could not verify update for row {row}")  # Debug logging
            
            # Process events to ensure UI updates immediately
            QApplication.processEvents()
            
            # Directly update the cost in the UI
            self.update_cost_display(row)
            
            print(f"Completed processing for row {row}")  # Debug logging
            
        except Exception as e:
            print(f"Error updating table response: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def update_cost_display(self, row):
        """Update the cost display for a row"""
        try:
            # Create a new thread to update the cost
            thread = threading.Thread(target=self._update_cost_display_thread, args=(row,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"Error scheduling cost update: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def _update_cost_display_thread(self, row):
        """Update the cost display in a separate thread"""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async update method
                loop.run_until_complete(self._async_update_cost_display(row))
            finally:
                loop.close()
        except Exception as e:
            print(f"Error in cost update thread: {str(e)}")
            import traceback
            traceback.print_exc()
            
    async def _async_update_cost_display(self, row):
        """Async method to update the cost display"""
        # Wait a short time to ensure the database has been updated
        await asyncio.sleep(1.0)
        
        conn = await self.db_manager.get_connection()
        try:
            # Get the job ID for this row
            async with conn.execute(
                """SELECT id FROM processing_jobs WHERE row_index = ? ORDER BY id LIMIT 1""",
                (row,)
            ) as cursor:
                job_row = await cursor.fetchone()
                if not job_row:
                    print(f"Warning: No job found for row index {row}")
                    return
                
                job_id = job_row[0]
                
                # Get the cost for this job
                async with conn.execute(
                    """SELECT cost, token_count, status FROM processing_jobs WHERE id = ?""",
                    (job_id,)
                ) as cursor:
                    data_row = await cursor.fetchone()
                    if not data_row:
                        print(f"Warning: No data found for job ID {job_id}")
                        return
                    
                    cost = data_row[0] if data_row[0] is not None else 0
                    token_count = data_row[1] if data_row[1] is not None else 0
                    status = data_row[2]
                    
                    print(f"Cost data for row {row}:")
                    print(f"  Job ID: {job_id}")
                    print(f"  Token count: {token_count}")
                    print(f"  Status: {status}")
                    print(f"  Cost: ${cost:.6f}")
                    
                    # Update the cost in the table
                    if row < self.table.rowCount() and cost > 0:
                        cost_text = f"${cost:.6f}"
                        cost_item = QTableWidgetItem(cost_text)
                        cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        self.table.setItem(row, 3, cost_item)
                        print(f"  Cost display updated: {cost_text}")
                        
                        # Force a refresh of the table
                        self.table.viewport().update()
                        self.table.update()
                        QApplication.processEvents()
        finally:
            await self.db_manager.release_connection(conn)

    def update_status(self, message: str):
        """Update the status label with a message"""
        self.status_label.setText(message)

    def stop_processing(self):
        """Stop the current processing batch"""
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "Confirm Stop", 
                "Are you sure you want to stop processing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.processing_thread.stop()
                self.status_label.setText("Stopping... Please wait for in-progress tasks to complete...")
                self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait()
        event.accept()

    async def load_table_data(self):
        """Load data from the database into the table"""
        conn = await self.db_manager.get_connection()
        try:
            # Get all rows from the database
            async with conn.execute(
                """SELECT filename, source_doc, response, status, cost, row_index 
                   FROM processing_jobs 
                   ORDER BY id"""
            ) as cursor:
                rows = await cursor.fetchall()
                
                self.table.setRowCount(len(rows))
                for i, row in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(row[0] or ""))
                    self.table.setItem(i, 1, QTableWidgetItem(row[1] or ""))
                    self.table.setItem(i, 2, QTableWidgetItem(row[2] or ""))
                    
                    # Add cost column with formatted value
                    cost = row[4] or 0
                    cost_text = f"${cost:.6f}" if cost > 0 else ""
                    cost_item = QTableWidgetItem(cost_text)
                    cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(i, 3, cost_item)
                    
                    # Print debug info about the cost
                    print(f"Row {i} (index {row[5]}): Cost = {cost}, Display = '{cost_text}'")
                    
                    # Color code based on status
                    if row[3] == 'completed':
                        self.table.item(i, 2).setBackground(Qt.GlobalColor.darkGreen)
        finally:
            await self.db_manager.release_connection(conn)

    async def update_table_response_and_cost(self, row_index):
        """Update the response and cost in the table for a specific row"""
        conn = await self.db_manager.get_connection()
        try:
            # Get the job ID for this row
            async with conn.execute(
                """SELECT id FROM processing_jobs WHERE row_index = ? ORDER BY id LIMIT 1""",
                (row_index,)
            ) as cursor:
                job_row = await cursor.fetchone()
                if not job_row:
                    print(f"Warning: No job found for row index {row_index}")
                    return
                
                job_id = job_row[0]
                
                # Get the cost and other details for this job
                async with conn.execute(
                    """SELECT cost, status, model_name, token_count FROM processing_jobs WHERE id = ?""",
                    (job_id,)
                ) as cursor:
                    data_row = await cursor.fetchone()
                    if not data_row:
                        print(f"Warning: No data found for job ID {job_id}")
                        return
                    
                    cost = data_row[0] if data_row[0] is not None else 0
                    status = data_row[1]
                    model_name = data_row[2]
                    token_count = data_row[3]
                    
                    print(f"Updating cost display for row {row_index}:")
                    print(f"  Job ID: {job_id}")
                    print(f"  Model: {model_name}")
                    print(f"  Status: {status}")
                    print(f"  Token count: {token_count}")
                    print(f"  Cost: ${cost:.6f}")
                    
                    # If we have a response with tokens but status is not completed, update it
                    if token_count > 0 and status != 'completed':
                        print(f"  Updating status to 'completed' for job {job_id} with token count {token_count}")
                        await conn.execute(
                            "UPDATE processing_jobs SET status = 'completed' WHERE id = ?",
                            (job_id,)
                        )
                        await conn.commit()
                        status = 'completed'
                    
                    # Update the cost in the table
                    if row_index < self.table.rowCount():
                        # Always show cost if it's greater than 0
                        if cost > 0:
                            cost_text = f"${cost:.6f}"
                            cost_item = QTableWidgetItem(cost_text)
                            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            self.table.setItem(row_index, 3, cost_item)
                            print(f"  Cost display updated: {cost_text}")
                        else:
                            # Check if the job is completed and has tokens but cost is 0
                            if status == 'completed' and token_count > 0:
                                # Recalculate the cost
                                recalculated_cost = self.db_manager.calculate_cost(model_name, token_count)
                                if recalculated_cost > 0:
                                    # Update the cost in the database
                                    await conn.execute(
                                        "UPDATE processing_jobs SET cost = ? WHERE id = ?",
                                        (recalculated_cost, job_id)
                                    )
                                    await conn.commit()
                                    
                                    # Update the UI
                                    cost_text = f"${recalculated_cost:.6f}"
                                    cost_item = QTableWidgetItem(cost_text)
                                    cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                                    self.table.setItem(row_index, 3, cost_item)
                                    print(f"  Cost recalculated and updated: {cost_text}")
                                else:
                                    print(f"  Cost is zero after recalculation, not displaying")
                            else:
                                print(f"  Cost is zero or negative (${cost:.6f}), not displaying")
                        
                        # Force a refresh of the table
                        self.table.viewport().update()
                        self.table.update()
                        QApplication.processEvents()
        finally:
            await self.db_manager.release_connection(conn)

    def save_database(self):
        """Save current database to a new location"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before saving")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Database", "", "SQLite Database (*.db)"
        )
        if file_name:
            try:
                # Close current database connections
                print(f"Saving database to: {file_name}")
                
                # Create a new event loop for this operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    print("Closing all existing database connections")
                    # Close all existing connections
                    future = asyncio.ensure_future(self.db_manager.close_all_connections(), loop=loop)
                    loop.run_until_complete(future)
                    
                    # Make sure the target file is not locked
                    temp_path = f"{file_name}.temp"
                    print(f"Copying database to temporary file: {temp_path}")
                    
                    # First copy to a temporary file
                    try:
                        shutil.copy2(self.db_manager.db_path, temp_path)
                    except PermissionError as e:
                        print(f"Permission error copying to temp file: {str(e)}")
                        raise PermissionError(f"Cannot access the database file: {str(e)}")
                    
                    # Now try to replace the target file
                    try:
                        # On Windows, we need to use a special approach to replace a file that might be in use
                        if os.name == 'nt':
                            # Try to rename the current target file to a backup if it exists
                            backup_path = f"{file_name}.bak"
                            
                            # Remove old backup if it exists
                            if os.path.exists(backup_path):
                                try:
                                    os.remove(backup_path)
                                except Exception as e:
                                    print(f"Warning: Could not remove old backup: {str(e)}")
                            
                            # Try to rename current target to backup if it exists
                            if os.path.exists(file_name):
                                try:
                                    os.rename(file_name, backup_path)
                                except Exception as e:
                                    print(f"Warning: Could not rename existing file: {str(e)}")
                                    # If we can't rename, try to remove it directly
                                    try:
                                        os.remove(file_name)
                                    except Exception as e2:
                                        print(f"Error: Could not remove existing file: {str(e2)}")
                                        raise PermissionError(f"Target file is locked and cannot be replaced: {str(e2)}")
                            
                            # Now move the temp file to the target location
                            os.rename(temp_path, file_name)
                        else:
                            # On non-Windows platforms, we can just replace the file
                            shutil.move(temp_path, file_name)
                            
                        print(f"Successfully saved database file to {file_name}")
                    except Exception as e:
                        print(f"Error saving database file: {str(e)}")
                        # Clean up temp file if it still exists
                        if os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                        raise
                except Exception as e:
                    print(f"Error in database saving operation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Clean up the event loop
                    try:
                        # Cancel all remaining tasks
                        for task in asyncio.all_tasks(loop):
                            task.cancel()
                        
                        # Run until all tasks are cancelled
                        if not loop.is_closed():
                            loop.run_until_complete(asyncio.sleep(0.1))
                        
                        # Close the loop
                        if not loop.is_closed():
                            loop.close()
                        
                        print("Event loop closed successfully")
                    except Exception as e:
                        print(f"Error cleaning up event loop: {str(e)}")
                
                QMessageBox.information(self, "Success", "Database saved successfully")
            except FileNotFoundError as e:
                print(f"File not found error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Database file not found: {str(e)}")
            except PermissionError as e:
                print(f"Permission error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Permission denied when saving database: {str(e)}")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error saving database: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to save database: {str(e)}")

    def load_database(self):
        """Load a previously saved database"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before loading")
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self, "Load Database", "", "SQLite Database (*.db)"
        )
        if file_name:
            try:
                # Close current database connections
                print(f"Loading database from: {file_name}")
                
                # Create a new event loop for this operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    print("Closing all existing database connections")
                    # Close all existing connections
                    future = asyncio.ensure_future(self.db_manager.close_all_connections(), loop=loop)
                    loop.run_until_complete(future)
                    
                    # Make sure the target file is not locked
                    temp_path = f"{self.db_manager.db_path}.new"
                    print(f"Copying database to temporary file: {temp_path}")
                    
                    # First copy to a temporary file
                    try:
                        shutil.copy2(file_name, temp_path)
                    except PermissionError as e:
                        print(f"Permission error copying to temp file: {str(e)}")
                        raise PermissionError(f"Cannot access the selected database file: {str(e)}")
                    
                    # Now try to replace the actual database file
                    try:
                        # On Windows, we need to use a special approach to replace a file that might be in use
                        if os.name == 'nt':
                            # Try to rename the current database file to a backup
                            backup_path = f"{self.db_manager.db_path}.bak"
                            
                            # Remove old backup if it exists
                            if os.path.exists(backup_path):
                                try:
                                    os.remove(backup_path)
                                except Exception as e:
                                    print(f"Warning: Could not remove old backup: {str(e)}")
                            
                            # Try to rename current db to backup
                            if os.path.exists(self.db_manager.db_path):
                                try:
                                    os.rename(self.db_manager.db_path, backup_path)
                                except Exception as e:
                                    print(f"Warning: Could not rename current database: {str(e)}")
                                    # If we can't rename, try to remove it directly
                                    try:
                                        os.remove(self.db_manager.db_path)
                                    except Exception as e2:
                                        print(f"Error: Could not remove current database: {str(e2)}")
                                        raise PermissionError(f"Database file is locked and cannot be replaced: {str(e2)}")
                            
                            # Now move the temp file to the target location
                            os.rename(temp_path, self.db_manager.db_path)
                        else:
                            # On non-Windows platforms, we can just replace the file
                            shutil.move(temp_path, self.db_manager.db_path)
                            
                        print(f"Successfully replaced database file")
                    except Exception as e:
                        print(f"Error replacing database file: {str(e)}")
                        # Clean up temp file if it still exists
                        if os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                        raise
                    
                    # Reload data into table
                    print("Loading table data")
                    try:
                        load_future = asyncio.ensure_future(self.load_table_data(), loop=loop)
                        loop.run_until_complete(load_future)
                    except Exception as e:
                        print(f"Error loading table data: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        raise RuntimeError(f"Failed to load table data: {str(e)}")
                except Exception as e:
                    print(f"Error in database loading operation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Clean up the event loop
                    try:
                        # Cancel all remaining tasks
                        for task in asyncio.all_tasks(loop):
                            task.cancel()
                        
                        # Run until all tasks are cancelled
                        if not loop.is_closed():
                            loop.run_until_complete(asyncio.sleep(0.1))
                        
                        # Close the loop
                        if not loop.is_closed():
                            loop.close()
                        
                        print("Event loop closed successfully")
                    except Exception as e:
                        print(f"Error cleaning up event loop: {str(e)}")
                
                QMessageBox.information(self, "Success", "Database loaded successfully")
            except FileNotFoundError as e:
                print(f"File not found error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Database file not found: {str(e)}")
            except PermissionError as e:
                print(f"Permission error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Permission denied when accessing database: {str(e)}")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error loading database: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to load database: {str(e)}")

    def clear_responses(self):
        """Clear all responses from the table and database"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before clearing responses")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "Are you sure you want to clear all responses? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                print("Clearing responses from table and database...")
                
                # Disable UI updates temporarily to improve performance
                self.table.setUpdatesEnabled(False)
                
                try:
                    # Clear responses in the table
                    for row in range(self.table.rowCount()):
                        # Clear response column
                        if self.table.item(row, 2):  # Response column
                            # Create a new empty item with proper styling
                            empty_item = QTableWidgetItem("")
                            empty_item.setForeground(Qt.GlobalColor.black)  # Set text color to black
                            self.table.setItem(row, 2, empty_item)
                        
                        # Clear cost column
                        if self.table.item(row, 3):  # Cost column
                            empty_cost_item = QTableWidgetItem("")
                            empty_cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            self.table.setItem(row, 3, empty_cost_item)
                finally:
                    # Re-enable UI updates
                    self.table.setUpdatesEnabled(True)
                
                # Clear responses in the database
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.clear_responses_in_db())
                finally:
                    loop.close()
                
                # Force a refresh of the table
                self.table.viewport().update()
                self.table.update()
                QApplication.processEvents()
                
                # Check and fix table display
                self.check_and_fix_table_display()
                
                self.status_label.setText("Responses cleared")
                QMessageBox.information(self, "Success", "All responses have been cleared")
                print("Responses cleared successfully")
            except Exception as e:
                print(f"Error clearing responses: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to clear responses: {str(e)}")

    async def clear_responses_in_db(self):
        """Clear all responses in the database"""
        try:
            # Use the DatabaseManager's method to clear responses
            # This will return the row indices that were affected
            row_indices = await self.db_manager.clear_responses_in_db()
            
            print("Successfully cleared all responses from the database")
            
            # Update the UI for each affected row
            for row in row_indices:
                if row < self.table.rowCount():
                    # Clear the cost display in the UI
                    cost_item = QTableWidgetItem("")
                    cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row, 3, cost_item)
                    print(f"Cleared cost display for row {row}")
            
            # Force a refresh of the table
            self.table.viewport().update()
            self.table.update()
            QApplication.processEvents()
            
        except Exception as e:
            print(f"Error clearing responses from database: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def update_content_viewer(self, row, column):
        """Update the content viewer with the selected cell's content"""
        if row < 0 or column < 0:
            return
            
        item = self.table.item(row, column)
        if item:
            content = item.text()
            self.content_viewer.setPlainText(content)
            
            # Move cursor to start without selecting
            cursor = self.content_viewer.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.content_viewer.setTextCursor(cursor)
            
            # Update the current row and column
            self.current_row = row
            self.current_column = column
            
            # Enable context menu for the content viewer
            self.content_viewer.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.content_viewer.customContextMenuRequested.connect(self.show_content_menu)
            
    def show_content_menu(self, position):
        """Show context menu for the content viewer"""
        menu = QMenu()
        
        # Only add the reprocess option if we're viewing a source document
        if hasattr(self, 'current_column') and self.current_column == 1:  # Source document column
            process_selection_action = menu.addAction("Process Selected Text")
            process_selection_action.triggered.connect(self.process_selected_text)
        
        menu.exec(self.content_viewer.mapToGlobal(position))
        
    def process_selected_text(self):
        """Process the selected text from the content viewer"""
        selected_text = self.content_viewer.textCursor().selectedText()
        
        if not selected_text:
            QMessageBox.warning(self, "No Selection", "Please select some text to process.")
            return
            
        # Confirm with the user
        reply = QMessageBox.question(
            self,
            "Process Selection",
            f"Process the selected text ({len(selected_text)} characters)?\n\nThis will create a new row in the table.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Create a new document with the selected text
            filename = f"Selection from row {self.current_row}"
            
            # Add the document to the database and start processing
            self.add_selection_to_database(filename, selected_text)

    def add_selection_to_database(self, filename, selected_text):
        """Add the selected text to the database and start processing"""
        # Create a list of documents to add
        documents = [{
            "filename": filename,
            "source_doc": selected_text
        }]
        
        # Show configuration options dialog
        model_name, ok = QInputDialog.getItem(
            self,
            "Select Model",
            "Choose a model for processing:",
            config.available_models,
            config.available_models.index(config.selected_model),
            False
        )
        
        if not ok:
            return
            
        # Ask if user wants to force full document processing
        force_full = QMessageBox.question(
            self,
            "Processing Options",
            "Force processing the entire selection without truncation?\n\n"
            "This may exceed token limits and cause errors for large selections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes
        
        # Temporarily set the force_full_document option
        original_force_full = config.force_full_document
        config.force_full_document = force_full
        
        try:
            # Add the documents to the database
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                batch_id = loop.run_until_complete(self.db_manager.add_batch(documents, model_name))
            finally:
                loop.close()
                
            # Start processing
            self.start_processing()
        finally:
            # Restore the original force_full_document setting
            config.force_full_document = original_force_full

    async def import_pdf(self):
        """Import and process files to convert to Markdown"""
        try:
            file_dialog = QFileDialog()
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
            
            # Set file filters based on the selected conversion method
            if config.document_conversion_method == "llamaparse":
                file_dialog.setNameFilter(
                    "Supported Files (*.pdf *.docx *.doc *.pptx *.ppt *.jpg *.jpeg *.png);;PDF Files (*.pdf);;"
                    "Word Files (*.docx *.doc);;PowerPoint Files (*.pptx *.ppt);;Images (*.jpg *.jpeg *.png)"
                )
            else:  # markitdown
                file_dialog.setNameFilter(
                    "Supported Files (*.pdf *.docx *.doc *.pptx *.ppt *.xlsx *.xls *.jpg *.jpeg *.png *.html *.htm *.txt *.csv *.json *.xml *.wav *.mp3 *.zip);;PDF Files (*.pdf);;"
                    "Word Files (*.docx *.doc);;PowerPoint Files (*.pptx *.ppt);;Excel Files (*.xlsx *.xls);;Images (*.jpg *.jpeg *.png);;"
                    "Web Files (*.html *.htm);;Text Files (*.txt *.csv *.json *.xml);;Audio Files (*.wav *.mp3);;Archives (*.zip)"
                )
            
            if file_dialog.exec():
                filenames = file_dialog.selectedFiles()
                if not filenames:
                    return

                # Check if using LlamaParse and API key is set
                if config.document_conversion_method == "llamaparse":
                    if not config.llamaparse_api_key:
                        QMessageBox.warning(self, "Warning", "Please configure LlamaParse API key first")
                        return
                    # Set API key from config
                    llamaparse_client.set_api_key(config.llamaparse_api_key)
                
                # Check for existing markdown files if using MarkItDown
                force_regenerate = False
                if config.document_conversion_method == "markitdown":
                    cached_files = 0
                    for filename in filenames:
                        if markitdown_client.is_markdown_current(filename):
                            cached_files += 1
                    
                    if cached_files > 0:
                        reply = QMessageBox.question(
                            self,
                            "Cached Files Found",
                            f"{cached_files} of {len(filenames)} files already have up-to-date markdown versions available.\n\nDo you want to use existing markdown files when available?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                        )
                        
                        if reply == QMessageBox.StandardButton.Cancel:
                            print("User cancelled processing")
                            return
                        elif reply == QMessageBox.StandardButton.No:
                            force_regenerate = True
                            print("User chose to regenerate all markdown files")
                
                # Create and show progress dialog
                progress_dialog = ProgressDialog(self, len(filenames))
                progress_dialog.show()
                QApplication.processEvents()  # Ensure dialog is displayed
                
                # Process each file
                processed_count = 0
                
                try:
                    for filename in filenames:
                        # Update progress dialog
                        file_basename = os.path.basename(filename)
                        progress_dialog.update_progress(processed_count, len(filenames), file_basename)
                        
                        # Check if user cancelled
                        if progress_dialog.was_cancelled():
                            print("User cancelled processing")
                            break
                        
                        # Show progress in status bar
                        file_ext = os.path.splitext(filename)[1].lower()
                        
                        # Process based on selected conversion method
                        if config.document_conversion_method == "llamaparse":
                            if file_ext == '.pdf' and config.llamaparse_max_pages > 0:
                                status_msg = f"Extracting {config.llamaparse_max_pages} page(s) from {file_basename}"
                                self.statusBar().showMessage(status_msg)
                                progress_dialog.update_status(status_msg)
                            else:
                                status_msg = f"Converting {file_basename} with LlamaParse"
                                self.statusBar().showMessage(status_msg)
                                progress_dialog.update_status(status_msg)
                            
                            # Process the file with LlamaParse
                            result = await llamaparse_client.process_pdf(filename)
                        else:  # markitdown
                            if file_ext == '.pdf' and config.markitdown_max_pages > 0:
                                status_msg = f"Extracting {config.markitdown_max_pages} page(s) from {file_basename}"
                                self.statusBar().showMessage(status_msg)
                                progress_dialog.update_status(status_msg)
                            else:
                                status_msg = f"Converting {file_basename} with MarkItDown"
                                self.statusBar().showMessage(status_msg)
                                progress_dialog.update_status(status_msg)
                            
                            # Process the file with MarkItDown
                            result = await markitdown_client.process_document(filename, config.markitdown_max_pages, force_regenerate)
                            
                            # Update status if using cached file
                            if "metadata" in result and result["metadata"].get("cached", False):
                                status_msg = f"Using cached markdown file for {file_basename}"
                                self.statusBar().showMessage(status_msg)
                                progress_dialog.update_status(status_msg)
                        
                        # Create a new row in the table
                        row_position = self.table.rowCount()
                        self.table.insertRow(row_position)
                        
                        # Set the filename and content
                        self.table.setItem(row_position, 0, QTableWidgetItem(os.path.basename(filename)))
                        self.table.setItem(row_position, 1, QTableWidgetItem(result["content"]))
                        
                        # Set metadata if available
                        if "metadata" in result:
                            metadata_str = json.dumps(result["metadata"], indent=2)
                            self.table.setItem(row_position, 2, QTableWidgetItem(metadata_str))
                        
                        # Update progress
                        processed_count += 1
                        progress_dialog.update_progress(processed_count, len(filenames))
                        self.statusBar().showMessage(f"Converted {file_basename}")
                        
                        # Process events to keep UI responsive
                        QApplication.processEvents()
                    
                    # Close progress dialog
                    progress_dialog.accept()
                    self.statusBar().showMessage("File conversion complete", 5000)
                    
                except Exception as e:
                    progress_dialog.accept()  # Close dialog on error
                    QMessageBox.critical(self, "Error", f"Failed to convert file: {str(e)}")
                    self.statusBar().showMessage("File conversion failed", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error in file conversion: {str(e)}")

    def handle_import_folder_pdf(self):
        """Handle the import folder PDF button click"""
        try:
            print("Starting handle_import_folder_pdf method")
            
            # Create a new event loop for this method call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Created new event loop")
            
            try:
                # Run the import_folder_pdf method in the event loop
                # Use run_until_complete instead of directly calling the coroutine
                future = asyncio.ensure_future(self.import_folder_pdf(), loop=loop)
                loop.run_until_complete(future)
                print("import_folder_pdf completed successfully")
            except asyncio.CancelledError:
                print("Import folder PDF operation was cancelled")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio event loop error: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error in import_folder_pdf: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Error in folder conversion: {str(e)}")
            finally:
                # Clean up the event loop
                try:
                    # Cancel all remaining tasks
                    for task in asyncio.all_tasks(loop):
                        task.cancel()
                    
                    # Run until all tasks are cancelled
                    if not loop.is_closed():
                        loop.run_until_complete(asyncio.sleep(0.1))
                    
                    # Close the loop
                    if not loop.is_closed():
                        loop.close()
                    
                    print("Event loop closed successfully")
                except Exception as e:
                    print(f"Error cleaning up event loop: {str(e)}")
        except Exception as e:
            print(f"Exception in handle_import_folder_pdf: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error setting up event loop: {str(e)}")

    def create_new_database(self):
        """Create a new blank database with a custom name"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before creating a new database")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, "Create New Database", "", "SQLite Database (*.db)"
        )
        if file_name:
            try:
                # Close current database connections
                print(f"Creating new database: {file_name}")
                
                # Create a new event loop for this operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    print("Closing all existing database connections")
                    # Close all existing connections
                    future = asyncio.ensure_future(self.db_manager.close_all_connections(), loop=loop)
                    
                    # Create a new database manager with the new path
                    new_db_manager = DatabaseManager(file_name)
                    
                    # Initialize the new database with schema
                    print(f"Initializing new database schema")
                    init_future = asyncio.ensure_future(new_db_manager.initialize(), loop=loop)
                    loop.run_until_complete(init_future)
                    
                    # Replace the current database manager
                    self.db_manager = new_db_manager
                    
                    # Clear the table
                    self.table.setRowCount(0)
                    
                    print(f"Successfully created new database: {file_name}")
                except Exception as e:
                    print(f"Error in database creation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Clean up the event loop
                    try:
                        # Cancel all remaining tasks
                        for task in asyncio.all_tasks(loop):
                            task.cancel()
                        
                        # Run until all tasks are cancelled
                        if not loop.is_closed():
                            loop.run_until_complete(asyncio.sleep(0.1))
                        
                        # Close the loop
                        if not loop.is_closed():
                            loop.close()
                        
                        print("Event loop closed successfully")
                    except Exception as e:
                        print(f"Error cleaning up event loop: {str(e)}")
                
                QMessageBox.information(self, "Success", f"New database '{os.path.basename(file_name)}' created successfully")
            except FileNotFoundError as e:
                print(f"File not found error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Could not create database file: {str(e)}")
            except PermissionError as e:
                print(f"Permission error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Permission denied when creating database: {str(e)}")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error creating database: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to create database: {str(e)}")

    def clear_all_data(self):
        """Clear all data from the database and table"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before clearing all data")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Clear All Data",
            "Are you sure you want to clear ALL data from the database? This will delete all documents, responses, and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Clear the table widget
                self.table.setRowCount(0)
                
                # Create a new event loop for this operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Clear all data in the database
                    future = asyncio.ensure_future(self.clear_all_data_in_db(), loop=loop)
                    loop.run_until_complete(future)
                    print("Database cleared successfully")
                except Exception as e:
                    print(f"Error in database clearing operation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Clean up the event loop
                    try:
                        # Cancel all remaining tasks
                        for task in asyncio.all_tasks(loop):
                            task.cancel()
                        
                        # Run until all tasks are cancelled
                        if not loop.is_closed():
                            loop.run_until_complete(asyncio.sleep(0.1))
                        
                        # Close the loop
                        if not loop.is_closed():
                            loop.close()
                        
                        print("Event loop closed successfully")
                    except Exception as e:
                        print(f"Error cleaning up event loop: {str(e)}")
                
                self.status_label.setText("Database cleared")
                QMessageBox.information(self, "Success", "All data has been cleared from the database")
            except Exception as e:
                print(f"Failed to clear database: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to clear database: {str(e)}")

    async def clear_all_data_in_db(self):
        """Delete all records from the database tables"""
        conn = None
        try:
            # Get a database connection
            conn = await self.db_manager.get_connection()
            
            # Delete all records from processing_jobs table
            await conn.execute("DELETE FROM processing_jobs")
            
            # Reset the auto-increment counter
            await conn.execute("DELETE FROM sqlite_sequence WHERE name='processing_jobs'")
            
            # Commit the changes
            await conn.commit()
            
            # Vacuum the database to reclaim space
            await conn.execute("VACUUM")
            await conn.commit()
            
            print("Successfully cleared all data from the database")
        except Exception as e:
            print(f"Error clearing database: {str(e)}")
            if conn:
                await conn.rollback()  # Rollback any uncommitted changes
            raise
        finally:
            # Always release the connection
            if conn:
                await self.db_manager.release_connection(conn) 

    def update_truncation_indicator(self):
        """Update the truncation indicator based on current settings"""
        from ..config import config
        
        if config.truncation_mode == "none":
            self.truncation_indicator.setText("")
            self.truncation_indicator.setStyleSheet("")
        elif config.truncation_mode == "characters":
            self.truncation_indicator.setText(f"Text Truncation: {config.truncation_character_limit} chars")
            self.truncation_indicator.setStyleSheet("color: #FFA500; font-weight: bold;")  # Orange
        elif config.truncation_mode == "paragraphs":
            self.truncation_indicator.setText(f"Text Truncation: {config.truncation_paragraph_limit} paragraphs")
            self.truncation_indicator.setStyleSheet("color: #FFA500; font-weight: bold;")  # Orange

    def _update_cost_in_thread(self, row):
        """Update the cost for a row in a separate thread to avoid blocking the UI"""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async cost update in this thread's event loop
                loop.run_until_complete(self._async_update_cost(row))
            finally:
                loop.close()
        except Exception as e:
            print(f"Error in cost update thread for row {row}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def _async_update_cost(self, row):
        """Async method to update the cost for a row"""
        # Get the job ID for this row
        conn = await self.db_manager.get_connection()
        try:
            # Get the job ID for this row
            async with conn.execute(
                """SELECT id FROM processing_jobs WHERE row_index = ? ORDER BY id LIMIT 1""",
                (row,)
            ) as cursor:
                job_row = await cursor.fetchone()
                if not job_row:
                    print(f"Warning: No job found for row index {row}")
                    return
                
                job_id = job_row[0]
                
                # Get the cost and other details for this job
                async with conn.execute(
                    """SELECT cost, status, model_name, token_count, response FROM processing_jobs WHERE id = ?""",
                    (job_id,)
                ) as cursor:
                    data_row = await cursor.fetchone()
                    if not data_row:
                        print(f"Warning: No data found for job ID {job_id}")
                        return
                    
                    cost = data_row[0] if data_row[0] is not None else 0
                    status = data_row[1]
                    model_name = data_row[2]
                    token_count = data_row[3]
                    response = data_row[4]
                    
                    print(f"Cost data for row {row}:")
                    print(f"  Job ID: {job_id}")
                    print(f"  Model: {model_name}")
                    print(f"  Status: {status}")
                    print(f"  Token count: {token_count}")
                    print(f"  Cost: ${cost:.6f}")
                    print(f"  Response length: {len(response) if response else 0}")
                    
                    # If we have a response but status is not completed, update it
                    if response and len(response) > 0 and status != 'completed':
                        print(f"  Updating status to 'completed' for job {job_id} with response length {len(response)}")
                        await conn.execute(
                            "UPDATE processing_jobs SET status = 'completed' WHERE id = ?",
                            (job_id,)
                        )
                        await conn.commit()
                        status = 'completed'
                    
                    # If we have a response but token_count is 0, estimate it
                    if response and len(response) > 0 and token_count == 0:
                        # Estimate token count based on response length (rough estimate)
                        estimated_tokens = len(response) // 4  # Rough estimate: 4 chars per token
                        print(f"  Estimating token count as {estimated_tokens} for job {job_id}")
                        
                        # Calculate cost based on estimated tokens
                        recalculated_cost = self.db_manager.calculate_cost(model_name, estimated_tokens)
                        
                        # Update the database with estimated token count and cost
                        await conn.execute(
                            "UPDATE processing_jobs SET token_count = ?, cost = ? WHERE id = ?",
                            (estimated_tokens, recalculated_cost, job_id)
                        )
                        await conn.commit()
                        
                        # Update local variables
                        token_count = estimated_tokens
                        cost = recalculated_cost
                        
                        print(f"  Updated token count to {token_count} and cost to ${cost:.6f}")
                    
                    # If cost is still 0 but we have tokens, recalculate it
                    if cost == 0 and token_count > 0:
                        recalculated_cost = self.db_manager.calculate_cost(model_name, token_count)
                        if recalculated_cost > 0:
                            # Update the cost in the database
                            await conn.execute(
                                "UPDATE processing_jobs SET cost = ? WHERE id = ?",
                                (recalculated_cost, job_id)
                            )
                            await conn.commit()
                            cost = recalculated_cost
                            print(f"  Recalculated cost to ${cost:.6f}")
                    
                    # Update the cost in the table
                    if row < self.table.rowCount():
                        # Always show cost if it's greater than 0
                        if cost > 0:
                            cost_text = f"${cost:.6f}"
                            cost_item = QTableWidgetItem(cost_text)
                            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            self.table.setItem(row, 3, cost_item)
                            print(f"  Cost display updated: {cost_text}")
                        else:
                            print(f"  Cost is zero or negative (${cost:.6f}), not displaying")
                        
                        # Force a refresh of the table
                        self.table.viewport().update()
                        self.table.update()
                        QApplication.processEvents()
        finally:
            await self.db_manager.release_connection(conn)
    
    @pyqtSlot(int, str)
    def _update_cost_in_ui(self, row, cost_text):
        """Update the cost in the UI (called from the main thread)"""
        try:
            if row < self.table.rowCount():
                cost_item = QTableWidgetItem(cost_text)
                cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 3, cost_item)
                print(f"  Cost display updated in UI: {cost_text}")
                
                # Force a refresh of the table
                self.table.viewport().update()
                self.table.update()
                QApplication.processEvents()
        except Exception as e:
            print(f"Error updating cost in UI: {str(e)}")

    def handle_import_pdf(self):
        """Handler for the Convert Files to MD button that properly manages the event loop"""
        try:
            print("Starting handle_import_pdf method")
            
            # Create a new event loop for this method call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Created new event loop")
            
            try:
                # Run the import_pdf method in the event loop
                future = asyncio.ensure_future(self.import_pdf(), loop=loop)
                loop.run_until_complete(future)
                print("import_pdf completed successfully")
            except asyncio.CancelledError:
                print("Import PDF operation was cancelled")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio event loop error: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error in import_pdf: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Error in file conversion: {str(e)}")
            finally:
                # Clean up the event loop
                try:
                    # Cancel all remaining tasks
                    for task in asyncio.all_tasks(loop):
                        task.cancel()
                    
                    # Run until all tasks are cancelled
                    if not loop.is_closed():
                        loop.run_until_complete(asyncio.sleep(0.1))
                    
                    # Close the loop
                    if not loop.is_closed():
                        loop.close()
                    
                    print("Event loop closed successfully")
                except Exception as e:
                    print(f"Error cleaning up event loop: {str(e)}")
        except Exception as e:
            print(f"Exception in handle_import_pdf: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error setting up event loop: {str(e)}")

    async def import_folder_pdf(self):
        """Import and process all files in a folder and its subfolders to convert to Markdown"""
        try:
            print("Starting import_folder_pdf method")
            # Create a lock specific to this method call to avoid sharing locks between event loops
            method_lock = asyncio.Lock()
            
            folder_path = QFileDialog.getExistingDirectory(
                self, "Select Folder to Convert", "", QFileDialog.Option.ShowDirsOnly
            )
            print(f"Selected folder path: {folder_path}")
            if not folder_path:
                print("No folder selected, returning")
                return

            # Check if using LlamaParse and API key is set
            if config.document_conversion_method == "llamaparse":
                if not config.llamaparse_api_key:
                    print("LlamaParse API key not configured")
                    QMessageBox.warning(self, "Warning", "Please configure LlamaParse API key first")
                    return
                # Set API key from config
                print(f"Setting API key: {config.llamaparse_api_key[:5]}...")
                llamaparse_client.set_api_key(config.llamaparse_api_key)
            
            # Show a "Scanning folder" message
            self.statusBar().showMessage("Scanning folder for supported files...")
            QApplication.processEvents()
            
            # Find all supported files in the folder and subfolders
            supported_extensions = []
            
            # Set supported extensions based on the selected conversion method
            if config.document_conversion_method == "llamaparse":
                supported_extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.jpg', '.jpeg', '.png']
            else:  # markitdown
                supported_extensions = [
                    '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', 
                    '.jpg', '.jpeg', '.png', '.html', '.htm', '.txt', '.csv', 
                    '.json', '.xml', '.wav', '.mp3', '.zip'
                ]
            
            files_to_process = []
            
            print(f"Searching for files with extensions: {supported_extensions}")
            
            # Create a temporary progress dialog for scanning
            scan_dialog = QDialog(self)
            scan_dialog.setWindowTitle("Scanning Folder")
            scan_dialog.setMinimumWidth(400)
            scan_layout = QVBoxLayout(scan_dialog)
            scan_label = QLabel("Scanning folder for supported files...\nThis may take a moment for large folders.")
            scan_layout.addWidget(scan_label)
            scan_progress = QProgressBar()
            scan_progress.setRange(0, 0)  # Indeterminate progress
            scan_layout.addWidget(scan_progress)
            scan_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            scan_dialog.show()
            QApplication.processEvents()
            
            # Scan for files
            try:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in supported_extensions:
                            full_path = os.path.join(root, file)
                            files_to_process.append(full_path)
                            print(f"Found file: {full_path}")
                        QApplication.processEvents()  # Keep UI responsive during scanning
            finally:
                scan_dialog.close()
            
            print(f"Total files found: {len(files_to_process)}")
            if not files_to_process:
                print("No supported files found")
                QMessageBox.warning(self, "Warning", f"No supported files found in the selected folder.\n\nSupported formats: {', '.join(supported_extensions)}")
                return
                
            # Confirm with user
            page_limit_msg = ""
            if config.document_conversion_method == "llamaparse" and config.llamaparse_max_pages > 0:
                page_limit_msg = f"\n\nNote: PDFs will be processed using only the first {config.llamaparse_max_pages} page(s) as configured in settings."
            elif config.document_conversion_method == "markitdown" and config.markitdown_max_pages > 0:
                page_limit_msg = f"\n\nNote: PDFs will be processed using only the first {config.markitdown_max_pages} page(s) as configured in settings."
            
            conversion_method = "LlamaParse" if config.document_conversion_method == "llamaparse" else "MarkItDown"
            
            # Check for existing markdown files if using MarkItDown
            cached_files = 0
            if config.document_conversion_method == "markitdown":
                for filename in files_to_process:
                    if markitdown_client.is_markdown_current(filename):
                        cached_files += 1
                
                if cached_files > 0:
                    cached_msg = f"\n\n{cached_files} of these files already have up-to-date markdown versions available."
                else:
                    cached_msg = ""
            else:
                cached_msg = ""
            
            # Add option to force regenerate markdown files
            force_regenerate = False
            if config.document_conversion_method == "markitdown" and cached_files > 0:
                reply = QMessageBox.question(
                    self,
                    "Confirm Processing",
                    f"Found {len(files_to_process)} files to process using {conversion_method}.{page_limit_msg}{cached_msg}\n\nDo you want to use existing markdown files when available?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Cancel:
                    print("User cancelled processing")
                    return
                elif reply == QMessageBox.StandardButton.No:
                    force_regenerate = True
                    print("User chose to regenerate all markdown files")
            else:
                reply = QMessageBox.question(
                    self,
                    "Confirm Processing",
                    f"Found {len(files_to_process)} files to process using {conversion_method}. Continue?{page_limit_msg}{cached_msg}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                print(f"User reply: {reply == QMessageBox.StandardButton.Yes}")
                if reply != QMessageBox.StandardButton.Yes:
                    print("User cancelled processing")
                    return
            
            # Create and show progress dialog
            progress_dialog = ProgressDialog(self, len(files_to_process))
            progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress_dialog.show()
            
            # Make sure the dialog is displayed before continuing
            # Process events multiple times with small delays to ensure dialog is shown
            for _ in range(10):
                QApplication.processEvents()
                time.sleep(0.05)  # Short delay to ensure dialog is rendered
            
            # Initialize a flag to track cancellation
            cancelled = False
            
            # Process each file
            processed_count = 0
            error_count = 0
            
            for filename in files_to_process:
                # Check if processing was cancelled
                if progress_dialog.was_cancelled():
                    print("User cancelled processing")
                    cancelled = True
                    break
                
                try:
                    # Update progress dialog
                    file_basename = os.path.basename(filename)
                    progress_dialog.update_progress(processed_count, len(files_to_process), file_basename)
                    
                    # Show progress in status bar
                    print(f"Processing file: {filename}")
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    # Process based on selected conversion method
                    if config.document_conversion_method == "llamaparse":
                        # Show progress in status bar
                        if file_ext == '.pdf' and config.llamaparse_max_pages > 0:
                            status_msg = f"Extracting {config.llamaparse_max_pages} page(s) from {file_basename}"
                            self.statusBar().showMessage(status_msg)
                            progress_dialog.update_status(status_msg)
                        else:
                            status_msg = f"Converting {file_basename} with LlamaParse"
                            self.statusBar().showMessage(status_msg)
                            progress_dialog.update_status(status_msg)
                        
                        # Process events to keep UI responsive
                        QApplication.processEvents()
                        
                        # Process the file with LlamaParse
                        async with method_lock:
                            print(f"Calling llamaparse_client.process_pdf for {filename}")
                            result = await llamaparse_client.process_pdf(filename)
                            print(f"Process complete, got result with content length: {len(result['content'])}")
                    else:  # markitdown
                        # Show progress in status bar
                        if file_ext == '.pdf' and config.markitdown_max_pages > 0:
                            status_msg = f"Extracting {config.markitdown_max_pages} page(s) from {file_basename}"
                            self.statusBar().showMessage(status_msg)
                            progress_dialog.update_status(status_msg)
                        else:
                            status_msg = f"Converting {file_basename} with MarkItDown"
                            self.statusBar().showMessage(status_msg)
                            progress_dialog.update_status(status_msg)
                        
                        # Process events to keep UI responsive
                        QApplication.processEvents()
                        
                        # Process the file with MarkItDown
                        async with method_lock:
                            print(f"Calling markitdown_client.process_document for {filename}")
                            result = await markitdown_client.process_document(filename, config.markitdown_max_pages, force_regenerate)
                            
                            # Add information about whether the file was cached
                            if "metadata" in result and result["metadata"].get("cached", False):
                                status_msg = f"Using cached markdown file for {file_basename}"
                                self.statusBar().showMessage(status_msg)
                                progress_dialog.update_status(status_msg)
                            
                            print(f"Process complete, got result with content length: {len(result['content'])}")
                    
                    # Create a new row in the table
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    print(f"Added new row at position {row_position}")
                    
                    # Set the filename and content
                    relative_path = os.path.relpath(filename, folder_path)
                    self.table.setItem(row_position, 0, QTableWidgetItem(relative_path))
                    self.table.setItem(row_position, 1, QTableWidgetItem(result["content"]))
                    
                    # Set metadata if available
                    if "metadata" in result:
                        metadata_str = json.dumps(result["metadata"], indent=2)
                        self.table.setItem(row_position, 2, QTableWidgetItem(metadata_str))
                    
                    processed_count += 1
                    print(f"Successfully processed file {processed_count}/{len(files_to_process)}")
                    
                except asyncio.InvalidStateError as e:
                    error_count += 1
                    error_msg = f"Asyncio error processing {file_basename}: {str(e)}"
                    print(error_msg)
                    progress_dialog.update_status(f"Error: {error_msg}")
                    
                    # Add to table with error
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    relative_path = os.path.relpath(filename, folder_path)
                    self.table.setItem(row_position, 0, QTableWidgetItem(relative_path))
                    self.table.setItem(row_position, 1, QTableWidgetItem("Error during processing"))
                    self.table.setItem(row_position, 2, QTableWidgetItem(f"Error: {str(e)}"))
                    
                    # Wait a moment to show the error before continuing
                    await asyncio.sleep(1)
                    continue
                except Exception as e:
                    error_count += 1
                    print(f"Error processing {filename}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
                    # Update progress dialog with error
                    error_msg = f"Error processing {os.path.basename(filename)}: {str(e)}"
                    progress_dialog.update_status(error_msg)
                    
                    # Add to table with error
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    relative_path = os.path.relpath(filename, folder_path)
                    self.table.setItem(row_position, 0, QTableWidgetItem(relative_path))
                    self.table.setItem(row_position, 1, QTableWidgetItem("Error during processing"))
                    self.table.setItem(row_position, 2, QTableWidgetItem(f"Error: {str(e)}"))
                    
                    # Wait a moment to show the error before continuing
                    await asyncio.sleep(1)
                    continue
                
                # Process events to keep UI responsive
                QApplication.processEvents()
            
            # Close progress dialog
            if not cancelled:
                progress_dialog.accept()
            
            # Show final status
            print(f"Processing complete: {processed_count} files processed, {error_count} errors")
            if error_count > 0:
                self.statusBar().showMessage(f"Conversion complete: {processed_count} files processed, {error_count} errors", 5000)
                QMessageBox.warning(self, "Warning", f"Completed with {error_count} errors. {processed_count} files were processed successfully.")
            else:
                self.statusBar().showMessage(f"Conversion complete: {processed_count} files processed", 5000)
                QMessageBox.information(self, "Success", f"Successfully processed {processed_count} files.")
                
        except asyncio.InvalidStateError as e:
            print(f"Asyncio event loop error: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
        except Exception as e:
            print(f"Exception in import_folder_pdf: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error in folder conversion: {str(e)}")

    def handle_import_folder_pdf(self):
        """Handle the import folder PDF button click"""
        try:
            print("Starting handle_import_folder_pdf method")
            
            # Create a new event loop for this method call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Created new event loop")
            
            try:
                # Run the import_folder_pdf method in the event loop
                # Use run_until_complete instead of directly calling the coroutine
                future = asyncio.ensure_future(self.import_folder_pdf(), loop=loop)
                loop.run_until_complete(future)
                print("import_folder_pdf completed successfully")
            except asyncio.CancelledError:
                print("Import folder PDF operation was cancelled")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio event loop error: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error in import_folder_pdf: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Error in folder conversion: {str(e)}")
            finally:
                # Clean up the event loop
                try:
                    # Cancel all remaining tasks
                    for task in asyncio.all_tasks(loop):
                        task.cancel()
                    
                    # Run until all tasks are cancelled
                    if not loop.is_closed():
                        loop.run_until_complete(asyncio.sleep(0.1))
                    
                    # Close the loop
                    if not loop.is_closed():
                        loop.close()
                    
                    print("Event loop closed successfully")
                except Exception as e:
                    print(f"Error cleaning up event loop: {str(e)}")
        except Exception as e:
            print(f"Exception in handle_import_folder_pdf: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error setting up event loop: {str(e)}")

    def handle_import_markdown(self):
        """Handler for the Import Markdown button that properly manages the event loop"""
        try:
            print("Starting handle_import_markdown method")
            
            # Create a new event loop for this method call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Created new event loop")
            
            try:
                # Run the import_markdown method in the event loop
                future = asyncio.ensure_future(self.import_markdown(), loop=loop)
                loop.run_until_complete(future)
                print("import_markdown completed successfully")
            except asyncio.CancelledError:
                print("Import markdown operation was cancelled")
            except asyncio.InvalidStateError as e:
                print(f"Asyncio event loop error: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Asyncio error: {str(e)}\n\nThis may be due to event loop issues. Please restart the application and try again.")
            except Exception as e:
                print(f"Error in import_markdown: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Error importing markdown files: {str(e)}")
            finally:
                # Clean up the event loop
                try:
                    # Cancel all remaining tasks
                    for task in asyncio.all_tasks(loop):
                        task.cancel()
                    
                    # Run until all tasks are cancelled
                    if not loop.is_closed():
                        loop.run_until_complete(asyncio.sleep(0.1))
                    
                    # Close the loop
                    if not loop.is_closed():
                        loop.close()
                    
                    print("Event loop closed successfully")
                except Exception as e:
                    print(f"Error cleaning up event loop: {str(e)}")
        except Exception as e:
            print(f"Exception in handle_import_markdown: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error setting up event loop: {str(e)}")

    async def import_markdown(self):
        """Import markdown files directly into the database"""
        try:
            # Ask user if they want to import a single file or a folder
            options = ["Single File", "Folder", "Cancel"]
            choice, ok = QInputDialog.getItem(
                self, 
                "Import Markdown", 
                "Would you like to import a single markdown file or a folder of markdown files?",
                options,
                0,  # Default to "Single File"
                False  # Not editable
            )
            
            if not ok or choice == "Cancel":
                print("User cancelled markdown import")
                return
            
            # Handle single file import
            if choice == "Single File":
                file_dialog = QFileDialog()
                file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)  # Allow multiple files
                file_dialog.setNameFilter("Markdown Files (*.md)")
                
                if file_dialog.exec():
                    filenames = file_dialog.selectedFiles()
                    if not filenames:
                        return
                    
                    # Process each markdown file
                    await self._process_markdown_files(filenames)
            
            # Handle folder import
            elif choice == "Folder":
                folder_path = QFileDialog.getExistingDirectory(
                    self, "Select Folder with Markdown Files", "", QFileDialog.Option.ShowDirsOnly
                )
                
                if not folder_path:
                    print("No folder selected, returning")
                    return
                
                # Find all markdown files in the folder
                files_to_process = []
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        if file.lower().endswith('.md'):
                            full_path = os.path.join(root, file)
                            files_to_process.append(full_path)
                
                if not files_to_process:
                    QMessageBox.warning(self, "Warning", "No markdown files found in the selected folder.")
                    return
                
                # Confirm with user
                reply = QMessageBox.question(
                    self,
                    "Confirm Import",
                    f"Found {len(files_to_process)} markdown files. Import them?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply != QMessageBox.StandardButton.Yes:
                    print("User cancelled import")
                    return
                
                # Process the markdown files
                await self._process_markdown_files(files_to_process)
        
        except Exception as e:
            print(f"Error in import_markdown: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error importing markdown files: {str(e)}")
    
    async def _process_markdown_files(self, file_paths):
        """Process a list of markdown files and import them into the database"""
        try:
            # Create and show progress dialog
            progress_dialog = ProgressDialog(self, len(file_paths))
            progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress_dialog.show()
            QApplication.processEvents()  # Ensure dialog is displayed
            
            # Process each file
            processed_count = 0
            updated_count = 0
            new_count = 0
            error_count = 0
            
            for filename in file_paths:
                # Check if user cancelled
                if progress_dialog.was_cancelled():
                    print("User cancelled processing")
                    break
                
                try:
                    # Update progress dialog
                    file_basename = os.path.basename(filename)
                    progress_dialog.update_progress(processed_count, len(file_paths), file_basename)
                    progress_dialog.update_status(f"Importing {file_basename}")
                    
                    # Read the markdown file
                    with open(filename, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Get the base filename without extension
                    base_name = os.path.splitext(file_basename)[0]
                    
                    # Check if we have an existing entry with this filename
                    existing_row = -1
                    for row in range(self.table.rowCount()):
                        item = self.table.item(row, 0)
                        if item:
                            # Check if the filename (without extension) matches
                            row_filename = item.text()
                            row_base_name = os.path.splitext(row_filename)[0]
                            if row_base_name == base_name:
                                existing_row = row
                                break
                    
                    # If we found an existing entry, ask if user wants to replace it
                    if existing_row >= 0:
                        # Get the current content
                        current_content = ""
                        item = self.table.item(existing_row, 1)
                        if item:
                            current_content = item.text()
                        
                        # Update the content
                        self.table.setItem(existing_row, 1, QTableWidgetItem(content))
                        
                        # Update the database
                        conn = await self.db_manager.get_connection()
                        try:
                            # Get the job ID for this row
                            cursor = await conn.execute(
                                "SELECT id FROM processing_jobs WHERE row_index = ? AND batch_id = (SELECT MAX(batch_id) FROM processing_jobs)",
                                (existing_row,)
                            )
                            row = await cursor.fetchone()
                            if row:
                                job_id = row[0]
                                # Update the source_doc column
                                await conn.execute(
                                    "UPDATE processing_jobs SET source_doc = ? WHERE id = ?",
                                    (content, job_id)
                                )
                                await conn.commit()
                                print(f"Updated existing entry at row {existing_row} with content from {filename}")
                                updated_count += 1
                        finally:
                            await self.db_manager.release_connection(conn)
                    else:
                        # Create a new entry
                        row_position = self.table.rowCount()
                        self.table.insertRow(row_position)
                        
                        # Set the filename and content
                        self.table.setItem(row_position, 0, QTableWidgetItem(file_basename))
                        self.table.setItem(row_position, 1, QTableWidgetItem(content))
                        
                        # Add to database
                        documents = [{
                            "filename": file_basename,
                            "content": content
                        }]
                        await self.db_manager.add_batch(documents, config.selected_model)
                        print(f"Added new entry at row {row_position} with content from {filename}")
                        new_count += 1
                    
                    processed_count += 1
                    progress_dialog.update_progress(processed_count, len(file_paths))
                    
                except Exception as e:
                    error_count += 1
                    print(f"Error processing {filename}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
                    # Update progress dialog with error
                    error_msg = f"Error processing {os.path.basename(filename)}: {str(e)}"
                    progress_dialog.update_status(error_msg)
                    
                    # Wait a moment to show the error before continuing
                    await asyncio.sleep(1)
                    continue
                
                # Process events to keep UI responsive
                QApplication.processEvents()
            
            # Close progress dialog
            progress_dialog.accept()
            
            # Show final status
            status_msg = f"Import complete: {processed_count} files processed"
            if updated_count > 0:
                status_msg += f", {updated_count} entries updated"
            if new_count > 0:
                status_msg += f", {new_count} new entries added"
            if error_count > 0:
                status_msg += f", {error_count} errors"
            
            self.statusBar().showMessage(status_msg, 5000)
            
            if error_count > 0:
                QMessageBox.warning(self, "Warning", f"Completed with {error_count} errors. {processed_count} files were processed successfully.")
            else:
                QMessageBox.information(self, "Success", status_msg)
            
            # Refresh the table display
            self.check_and_fix_table_display()
            
        except Exception as e:
            print(f"Error in _process_markdown_files: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error processing markdown files: {str(e)}")