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
    QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import pandas as pd
from ..config import config
from .config_dialog import ConfigDialog
from ..database.manager import DatabaseManager
from ..api.openai_client import openai_client
from ..api.anthropic_client import anthropic_client
from .styles import DARK_THEME

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
        self.export_excel_btn.clicked.connect(self.export_excel)
        self.process_btn.clicked.connect(self.start_processing)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.clear_btn.clicked.connect(self.clear_responses)
        self.table.cellClicked.connect(self.update_content_viewer)
        self.table.currentCellChanged.connect(lambda current_row, current_column, previous_row, previous_column: 
            self.update_content_viewer(current_row, current_column))

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
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.db_manager.close_all_connections())
                
                # Copy database file
                shutil.copy2(self.db_manager.db_path, file_name)
                QMessageBox.information(self, "Success", "Database saved successfully")
            except Exception as e:
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
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.db_manager.close_all_connections())
                
                # Copy selected database to working location
                shutil.copy2(file_name, self.db_manager.db_path)
                
                # Reload data into table
                loop.run_until_complete(self.load_table_data())
                QMessageBox.information(self, "Success", "Database loaded successfully")
            except Exception as e:
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