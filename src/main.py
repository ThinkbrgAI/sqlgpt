import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from .ui.main_window import MainWindow
from .database.manager import DatabaseManager

async def init_database():
    db_manager = DatabaseManager()
    await db_manager.initialize()

def main():
    app = QApplication(sys.argv)
    
    # Initialize database
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_database())
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 