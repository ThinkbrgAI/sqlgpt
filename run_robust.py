#!/usr/bin/env python
"""
Robust version of the main application that handles errors gracefully.
"""

import sys
import traceback
import time
from datetime import datetime
import os
import signal

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nApplication interrupted by user. Exiting gracefully...")
    sys.exit(0)

def main():
    try:
        # Register signal handler for Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)
        
        print(f"Starting application at {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 50)
        
        # Import the main module
        from src.ui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # Create the application
        app = QApplication(sys.argv)
        
        # Set up exception handling for Qt
        sys._excepthook = sys.excepthook
        
        def exception_hook(exctype, value, traceback_obj):
            """Global exception handler for Qt exceptions."""
            print("\n" + "!" * 50)
            print("ERROR: Unhandled exception occurred:")
            print(str(value))
            print("\nTraceback:")
            traceback.print_tb(traceback_obj)
            print("!" * 50 + "\n")
            sys._excepthook(exctype, value, traceback_obj)
            
            # Keep the application running if possible
            print("\nAttempting to continue execution...")
        
        sys.excepthook = exception_hook
        
        # Create and show the main window
        window = MainWindow()
        window.show()
        
        # Set up a timer to log that the application is still running
        start_time = time.time()
        
        def check_runtime():
            elapsed = time.time() - start_time
            print(f"Application running for {elapsed:.1f} seconds")
            QApplication.instance().processEvents()
            window._debug_timer = window.startTimer(30000)  # Check every 30 seconds
        
        # Add a timer to the window
        window._debug_timer = window.startTimer(30000)
        window.timerEvent = lambda event: check_runtime() if event.timerId() == window._debug_timer else None
        
        # Run the application
        print("Application started, entering event loop")
        sys.exit(app.exec())
        
    except Exception as e:
        print("\n" + "!" * 50)
        print("ERROR: Application crashed with the following error:")
        print(str(e))
        print("\nTraceback:")
        traceback.print_exc()
        print("!" * 50 + "\n")
        
        # Keep the console open
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
    # Keep the console open even if main() returns
    print("\nApplication has exited. Keeping console open for debugging.")
    input("Press Enter to close this window...") 