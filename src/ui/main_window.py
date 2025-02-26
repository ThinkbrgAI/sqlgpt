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
    QTextEdit, QSplitter, QDialog, QApplication, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QAction
import pandas as pd
from ..config import config
from .config_dialog import ConfigDialog
from ..database.manager import DatabaseManager
from ..api.openai_client import openai_client
from ..api.anthropic_client import anthropic_client
from ..api.llamaparse_client import llamaparse_client
from .styles import DARK_THEME
import json

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
            response, token_count = await client.process_document(job["source_doc"])
            if self.should_stop:  # Check again after API call
                return False
            await self.db_manager.update_response(job["id"], response, token_count)
            print(f"Emitting update_response signal for row {job['row_index']}...")  # Debug logging
            self.update_response.emit(job["row_index"], response)
            self.rate_limiter.add_request(token_count)
            print(f"Completed processing for row {job['row_index']}")  # Debug logging
            return True
        except Exception as e:
            self.error.emit(f"Error processing job {job['id']}: {str(e)}")
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
        return self._user_cancelled or self.result() == QDialog.DialogCode.Rejected

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
        
        # Create UI
        self.setup_ui()

    def setup_ui(self):
        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)  # Set spacing between buttons
        toolbar.setContentsMargins(6, 6, 6, 6)  # Set margins around buttons
        
        # Add buttons
        self.import_folder_btn = QPushButton("Import Folder")
        self.import_excel_btn = QPushButton("Import Excel")
        self.import_pdf_btn = QPushButton("Convert Files to MD")
        self.import_folder_pdf_btn = QPushButton("Convert Folder to MD")
        print("Created Convert Folder to MD button")
        self.export_excel_btn = QPushButton("Export Excel")
        self.config_btn = QPushButton("Configure")
        self.process_btn = QPushButton("Process Batch")
        self.stop_btn = QPushButton("Stop")
        self.clear_btn = QPushButton("Clear Responses")
        
        # Set object names for styling
        self.process_btn.setObjectName("process_btn")
        self.stop_btn.setObjectName("stop_btn")
        
        # Add buttons to toolbar with alignment
        toolbar.addWidget(self.import_folder_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.import_excel_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.import_pdf_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.import_folder_pdf_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.export_excel_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.config_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.process_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.stop_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addWidget(self.clear_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addStretch()  # Add stretch at the end to push buttons to the left
        
        # Add toolbar to main layout
        layout.addLayout(toolbar)

        # Progress section below toolbar
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
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
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Filename", "Source Doc", "Response"])
        
        # Set minimum column widths but allow resizing
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(100)  # Minimum width for all columns
        self.table.setColumnWidth(0, 200)  # Initial width for Filename
        self.table.setColumnWidth(1, 300)  # Initial width for Source Doc
        self.table.setColumnWidth(2, 500)  # Initial width for Response
        
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
        self.import_folder_btn.clicked.connect(self.import_folder)
        self.import_pdf_btn.clicked.connect(self.handle_import_pdf)
        print("Connecting Convert Folder to MD button to handler")
        self.import_folder_pdf_btn.clicked.connect(self.handle_import_folder_pdf)
        self.export_excel_btn.clicked.connect(self.export_excel)
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
                for ext in ['.txt', '.md']:
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
                    QMessageBox.warning(self, "Warning", "No valid text files found in the selected folder")
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
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Import Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            try:
                df = pd.read_excel(file_name)
                required_cols = {"Source Doc"}
                if not required_cols.issubset(df.columns):
                    raise ValueError("Excel file must have a 'Source Doc' column")
                
                # Update table
                self.table.setRowCount(len(df))
                for i, row in df.iterrows():
                    # Use Excel filename as default if not specified
                    filename = row.get("Filename", os.path.basename(file_name))
                    self.table.setItem(i, 0, QTableWidgetItem(str(filename)))
                    self.table.setItem(i, 1, QTableWidgetItem(str(row["Source Doc"])))
                    if "Response" in df.columns and pd.notna(row["Response"]):
                        self.table.setItem(i, 2, QTableWidgetItem(str(row["Response"])))
                
                QMessageBox.information(self, "Success", "Data imported successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {str(e)}")

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
                for row in range(self.table.rowCount()):
                    filename = self.table.item(row, 0)
                    source = self.table.item(row, 1)
                    response = self.table.item(row, 2)
                    
                    # Debug logging for row 18
                    if row == 18:
                        print(f"Row 18 data:")
                        print(f"  Filename: {filename.text() if filename else 'None'}")
                        print(f"  Source: {source.text()[:50] if source else 'None'}...")
                        print(f"  Response: {response.text()[:50] if response else 'None'}...")
                    
                    row_data = {
                        "Filename": filename.text() if filename else "",
                        "Source Doc": source.text() if source else "",
                        "Response": response.text() if response else ""
                    }
                    data.append(row_data)
                    
                print(f"Created data list with {len(data)} rows")  # Debug logging
                df = pd.DataFrame(data)
                print(f"Created DataFrame with shape: {df.shape}")  # Debug logging
                df.to_excel(file_name, index=False)
                QMessageBox.information(self, "Success", "Data exported successfully")
            except Exception as e:
                print(f"Export error: {str(e)}")  # Debug logging
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

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
        """Handle completion of processing"""
        self.status_label.setText("Processing completed")
        self.stop_btn.setEnabled(False)
        self.process_btn.setEnabled(True)
        QMessageBox.information(self, "Success", "Batch processing completed")

    def update_table_response(self, row, response):
        """Update a response in the table"""
        print(f"Starting update_table_response for row {row}...")  # Debug logging
        try:
            print(f"Current table row count: {self.table.rowCount()}")  # Debug logging
            print(f"Creating QTableWidgetItem for row {row}, column 2")  # Debug logging
            item = QTableWidgetItem(response)
            
            # Special logging for row 18
            if row == 18:
                print(f"Row 18 update details:")
                print(f"  Response content: {response[:100]}...")
                print(f"  Item created successfully: {item is not None}")
                print(f"  Item text: {item.text()[:100]}...")
            
            print(f"Setting item for row {row}, column 2")  # Debug logging
            self.table.setItem(row, 2, item)
            print(f"Successfully updated row {row}")  # Debug logging
            
            # Verify the update
            updated_item = self.table.item(row, 2)
            if updated_item:
                print(f"Verified update for row {row}: {updated_item.text()[:50]}...")  # Debug logging
                if row == 18:
                    print("Row 18 verification:")
                    print(f"  Item exists: {updated_item is not None}")
                    print(f"  Item text length: {len(updated_item.text())}")
                    print(f"  Item text: {updated_item.text()[:100]}...")
            else:
                print(f"Warning: Could not verify update for row {row}")  # Debug logging
            
            # Force table refresh
            self.table.viewport().update()
            self.table.resizeRowToContents(row)
            self.table.scrollToItem(self.table.item(row, 2))
            
        except Exception as e:
            print(f"Error updating row {row}: {str(e)}")  # Debug logging
            QMessageBox.critical(self, "Error", f"Failed to update row {row}: {str(e)}")

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
        """Load data from database into table"""
        conn = await self.db_manager.get_connection()
        try:
            async with conn.execute(
                """SELECT filename, source_doc, response, status 
                   FROM processing_jobs 
                   ORDER BY id"""
            ) as cursor:
                rows = await cursor.fetchall()
                
                self.table.setRowCount(len(rows))
                for i, row in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(row[0] or ""))
                    self.table.setItem(i, 1, QTableWidgetItem(row[1] or ""))
                    self.table.setItem(i, 2, QTableWidgetItem(row[2] or ""))
                    
                    # Color code based on status
                    if row[3] == 'completed':
                        self.table.item(i, 2).setBackground(Qt.GlobalColor.darkGreen)
                    elif row[3] == 'error':
                        self.table.item(i, 2).setBackground(Qt.GlobalColor.darkRed)
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
                loop = None
                try:
                    # Create a new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    print("Closing all existing database connections")
                    # Close all existing connections
                    loop.run_until_complete(self.db_manager.close_all_connections())
                    
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
                    
                    # Clean up any pending tasks
                    pending_tasks = asyncio.all_tasks(loop)
                    if pending_tasks:
                        print(f"Cancelling {len(pending_tasks)} pending tasks")
                        for task in pending_tasks:
                            task.cancel()
                        # Allow tasks to respond to cancellation
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                except Exception as e:
                    print(f"Error in database saving operation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Always close the loop
                    if loop:
                        try:
                            # Cancel all remaining tasks
                            for task in asyncio.all_tasks(loop):
                                task.cancel()
                            
                            # Run until all tasks are cancelled
                            if not loop.is_closed():
                                loop.run_until_complete(asyncio.sleep(0.1))
                                
                            # Stop and close the loop
                            if loop.is_running():
                                loop.stop()
                            if not loop.is_closed():
                                loop.close()
                                
                            print("Event loop closed successfully")
                        except Exception as e:
                            print(f"Error closing event loop: {str(e)}")
                
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
                loop = None
                try:
                    # Create a new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    print("Closing all existing database connections")
                    # Close all existing connections
                    loop.run_until_complete(self.db_manager.close_all_connections())
                    
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
                        loop.run_until_complete(self.load_table_data())
                    except Exception as e:
                        print(f"Error loading table data: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        raise RuntimeError(f"Failed to load table data: {str(e)}")
                    
                    # Clean up any pending tasks
                    pending_tasks = asyncio.all_tasks(loop)
                    if pending_tasks:
                        print(f"Cancelling {len(pending_tasks)} pending tasks")
                        for task in pending_tasks:
                            task.cancel()
                        # Allow tasks to respond to cancellation
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                except Exception as e:
                    print(f"Error in database loading operation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Always close the loop
                    if loop:
                        try:
                            # Cancel all remaining tasks
                            for task in asyncio.all_tasks(loop):
                                task.cancel()
                            
                            # Run until all tasks are cancelled
                            if not loop.is_closed():
                                loop.run_until_complete(asyncio.sleep(0.1))
                                
                            # Stop and close the loop
                            if loop.is_running():
                                loop.stop()
                            if not loop.is_closed():
                                loop.close()
                                
                            print("Event loop closed successfully")
                        except Exception as e:
                            print(f"Error closing event loop: {str(e)}")
                
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
                # Clear responses in the table
                for row in range(self.table.rowCount()):
                    if self.table.item(row, 2):  # Response column
                        self.table.setItem(row, 2, QTableWidgetItem(""))
                
                # Clear responses in the database
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.clear_responses_in_db())
                
                self.status_label.setText("Responses cleared")
                QMessageBox.information(self, "Success", "All responses have been cleared")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear responses: {str(e)}")

    async def clear_responses_in_db(self):
        """Clear all responses in the database"""
        conn = await self.db_manager.get_connection()
        try:
            await conn.execute(
                """UPDATE processing_jobs 
                   SET response = NULL, 
                       token_count = 0,
                       status = 'pending'"""
            )
            await conn.commit()
        finally:
            await self.db_manager.release_connection(conn)

    def update_content_viewer(self, row, column):
        """Update the content viewer when a cell is clicked"""
        item = self.table.item(row, column)
        if item:
            self.content_viewer.setText(item.text())
            # Move cursor to start without selecting
            cursor = self.content_viewer.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.content_viewer.setTextCursor(cursor)

    async def import_pdf(self):
        """Import and process files to convert to Markdown"""
        try:
            file_dialog = QFileDialog()
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
            file_dialog.setNameFilter(
                "Supported Files (*.pdf *.docx *.doc *.pptx *.ppt *.jpg *.jpeg *.png);;PDF Files (*.pdf);;"
                "Word Files (*.docx *.doc);;PowerPoint Files (*.pptx *.ppt);;Images (*.jpg *.jpeg *.png)"
            )
            
            if file_dialog.exec():
                filenames = file_dialog.selectedFiles()
                if not filenames:
                    return

                # Check if API key is set
                if not config.llamaparse_api_key:
                    QMessageBox.warning(self, "Warning", "Please configure LlamaParse API key first")
                    return

                # Set API key from config
                llamaparse_client.set_api_key(config.llamaparse_api_key)
                
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
                        if file_ext == '.pdf' and config.llamaparse_max_pages > 0:
                            status_msg = f"Extracting {config.llamaparse_max_pages} page(s) from {file_basename}"
                            self.statusBar().showMessage(status_msg)
                            progress_dialog.update_status(status_msg)
                        else:
                            status_msg = f"Converting {file_basename}"
                            self.statusBar().showMessage(status_msg)
                            progress_dialog.update_status(status_msg)
                        
                        # Process the file
                        result = await llamaparse_client.process_pdf(filename)
                        
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

    def handle_import_pdf(self):
        """Handler for the Convert Files to MD button that properly manages the event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.import_pdf())
        finally:
            loop.close()

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

            # Check if API key is set
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
            supported_extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.jpg', '.jpeg', '.png']
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
                QMessageBox.warning(self, "Warning", "No supported files found in the selected folder")
                return
                
            # Confirm with user
            page_limit_msg = ""
            if config.llamaparse_max_pages > 0:
                page_limit_msg = f"\n\nNote: PDFs will be processed using only the first {config.llamaparse_max_pages} page(s) as configured in settings."
            
            reply = QMessageBox.question(
                self,
                "Confirm Processing",
                f"Found {len(files_to_process)} files to process. Continue?{page_limit_msg}",
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
                    if file_ext == '.pdf' and config.llamaparse_max_pages > 0:
                        status_msg = f"Extracting {config.llamaparse_max_pages} page(s) from {file_basename}"
                        self.statusBar().showMessage(status_msg)
                        progress_dialog.update_status(status_msg)
                    else:
                        status_msg = f"Converting {file_basename}"
                        self.statusBar().showMessage(status_msg)
                        progress_dialog.update_status(status_msg)
                    
                    # Process events to keep UI responsive
                    QApplication.processEvents()
                    
                    # Process the file with lock to prevent event loop issues
                    async with method_lock:
                        print(f"Calling llamaparse_client.process_pdf for {filename}")
                        result = await llamaparse_client.process_pdf(filename)
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
                    
                    # Update progress
                    progress_dialog.update_progress(processed_count, len(files_to_process))
                    self.statusBar().showMessage(f"Converted {file_basename} ({processed_count}/{len(files_to_process)})")
                    
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
                print("Running import_folder_pdf in the event loop")
                loop.run_until_complete(self.import_folder_pdf())
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
                    pending_tasks = asyncio.all_tasks(loop)
                    if pending_tasks:
                        print(f"Cancelling {len(pending_tasks)} pending tasks")
                        for task in pending_tasks:
                            task.cancel()
                        # Allow tasks to respond to cancellation
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                except Exception as e:
                    print(f"Error cleaning up tasks: {str(e)}")
                
                print("Closing event loop")
                loop.close()
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
                loop = None
                try:
                    # Create a new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    print("Closing all existing database connections")
                    # Close all existing connections
                    loop.run_until_complete(self.db_manager.close_all_connections())
                    
                    # Create a new database manager with the new path
                    new_db_manager = DatabaseManager(file_name)
                    
                    # Initialize the new database with schema
                    print(f"Initializing new database schema")
                    loop.run_until_complete(new_db_manager.initialize())
                    
                    # Replace the current database manager
                    self.db_manager = new_db_manager
                    
                    # Clear the table
                    self.table.setRowCount(0)
                    
                    print(f"Successfully created new database: {file_name}")
                    
                    # Clean up any pending tasks
                    pending_tasks = asyncio.all_tasks(loop)
                    if pending_tasks:
                        print(f"Cancelling {len(pending_tasks)} pending tasks")
                        for task in pending_tasks:
                            task.cancel()
                        # Allow tasks to respond to cancellation
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                except Exception as e:
                    print(f"Error in database creation: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
                finally:
                    # Always close the loop
                    if loop:
                        try:
                            # Cancel all remaining tasks
                            for task in asyncio.all_tasks(loop):
                                task.cancel()
                            
                            # Run until all tasks are cancelled
                            if not loop.is_closed():
                                loop.run_until_complete(asyncio.sleep(0.1))
                                
                            # Stop and close the loop
                            if loop.is_running():
                                loop.stop()
                            if not loop.is_closed():
                                loop.close()
                                
                            print("Event loop closed successfully")
                        except Exception as e:
                            print(f"Error closing event loop: {str(e)}")
                
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