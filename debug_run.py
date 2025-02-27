#!/usr/bin/env python
"""
Debug version of the run script that captures errors and keeps the console open.
"""

import sys
import traceback
import time
from datetime import datetime

def main():
    try:
        print(f"Starting application at {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 50)
        
        # Import the main module
        from src.ui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # Create the application
        app = QApplication(sys.argv)
        
        # Create and show the main window
        window = MainWindow()
        window.show()
        
        # Set up a timer to log that the application is still running
        start_time = time.time()
        
        def check_runtime():
            elapsed = time.time() - start_time
            print(f"Application running for {elapsed:.1f} seconds")
            if elapsed < 120:  # Check for 2 minutes
                QApplication.instance().processEvents()
                window._debug_timer = window.startTimer(5000)  # Check every 5 seconds
        
        # Add a timer to the window
        window._debug_timer = window.startTimer(5000)
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