import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.database.manager import DatabaseManager

async def init_database():
    """Initialize the database"""
    db_manager = DatabaseManager()
    await db_manager.initialize()
    return db_manager

async def async_main():
    """Async main function"""
    return await init_database()

def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Initialize database using asyncio.run()
    try:
        db_manager = asyncio.run(async_main())
    except RuntimeError:
        # If there's already an event loop (e.g., in Jupyter), use this instead
        loop = asyncio.get_event_loop()
        db_manager = loop.run_until_complete(async_main())
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 