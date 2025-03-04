#!/usr/bin/env python
"""
Main Application Workflow Test Script

This script simulates the exact workflow in the main application to identify
where the Excel export is failing.
"""

import os
import sys
import asyncio
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, 
    QVBoxLayout, QPushButton, QWidget, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

# Add the src directory to the path so we can import from it
sys.path.append(os.path.abspath("."))

class TestMainWindow(QMainWindow):
    """Test window to simulate the main application workflow."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Main App Workflow")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create table widget
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Filename", "Source Doc", "Response"])
        layout.addWidget(self.table)
        
        # Create buttons
        self.process_btn = QPushButton("Process Test PDF")
        self.export_btn = QPushButton("Export to Excel")
        layout.addWidget(self.process_btn)
        layout.addWidget(self.export_btn)
        
        # Connect signals
        self.process_btn.clicked.connect(self.process_test_pdf)
        self.export_btn.clicked.connect(self.export_excel)
    
    def process_test_pdf(self):
        """Process the test PDF file."""
        try:
            # Check if PyMuPDF is installed
            try:
                import fitz
                print("✅ PyMuPDF is installed")
            except ImportError:
                QMessageBox.critical(self, "Error", "PyMuPDF is not installed")
                return
            
            # Import the table extractor
            try:
                from src.api.pdf_table_extractor import pdf_to_markdown_with_tables
            except ImportError:
                QMessageBox.critical(self, "Error", "Could not import pdf_table_extractor module")
                return
            
            # Use the test PDF file we created
            pdf_path = "test_table.pdf"
            
            if not os.path.exists(pdf_path):
                QMessageBox.critical(self, "Error", f"File {pdf_path} does not exist")
                return
            
            print(f"Processing {pdf_path}...")
            
            # Process the PDF
            result = pdf_to_markdown_with_tables(pdf_path)
            
            # Add to table
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(pdf_path)))
            self.table.setItem(row, 1, QTableWidgetItem(result["content"]))
            self.table.setItem(row, 2, QTableWidgetItem("This is a test response."))
            
            # Resize columns to content
            self.table.resizeColumnsToContents()
            
            QMessageBox.information(self, "Success", "PDF processed successfully")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error processing PDF: {str(e)}")
    
    def export_excel(self):
        """Export table data to Excel."""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No data to export")
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export Excel File", "", "Excel Files (*.xlsx)"
        )
        
        if not file_name:
            return
        
        try:
            import pandas as pd
            
            data = []
            print(f"Starting Excel export with {self.table.rowCount()} rows")
            
            for row in range(self.table.rowCount()):
                filename = self.table.item(row, 0)
                source = self.table.item(row, 1)
                response = self.table.item(row, 2)
                
                # Debug logging for each row
                print(f"Row {row} data:")
                print(f"  Filename: {filename.text() if filename else 'None'}")
                print(f"  Source length: {len(source.text()) if source else 0} characters")
                print(f"  Response length: {len(response.text()) if response else 0} characters")
                
                row_data = {
                    "Filename": filename.text() if filename else "",
                    "Source Doc": source.text() if source else "",
                    "Response": response.text() if response else ""
                }
                data.append(row_data)
            
            print(f"Created data list with {len(data)} rows")
            df = pd.DataFrame(data)
            print(f"Created DataFrame with shape: {df.shape}")
            
            # Try to export with different options
            try:
                print("Attempting standard export...")
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
                    try:
                        print("Attempting export with truncated data...")
                        # Truncate long text fields
                        for i, row_data in enumerate(data):
                            if len(row_data["Source Doc"]) > 32000:
                                data[i]["Source Doc"] = row_data["Source Doc"][:32000] + "... (truncated)"
                            if len(row_data["Response"]) > 32000:
                                data[i]["Response"] = row_data["Response"][:32000] + "... (truncated)"
                        
                        df_truncated = pd.DataFrame(data)
                        df_truncated.to_excel(file_name, index=False)
                        print("Export with truncated data successful")
                    except Exception as e3:
                        print(f"Export with truncated data failed: {str(e3)}")
                        raise Exception(f"All export attempts failed: {str(e1)}, {str(e2)}, {str(e3)}")
            
            QMessageBox.information(self, "Success", "Data exported successfully")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

def main():
    """Main function."""
    app = QApplication(sys.argv)
    window = TestMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 