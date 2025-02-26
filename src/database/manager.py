import aiosqlite
import asyncio
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from .schema import get_schema_sql

class DatabaseManager:
    def __init__(self, db_path: str = "gpt_processor.db"):
        self.db_path = db_path
        self.write_lock = asyncio.Lock()
        self._connection_pool = []
        self._active_connections = set()  # Track all active connections
        self.max_connections = 5

    async def initialize(self):
        """Initialize the database with schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(get_schema_sql())
            await db.commit()

    async def get_connection(self) -> aiosqlite.Connection:
        """Get a database connection from the pool"""
        if not self._connection_pool:
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL")
            self._active_connections.add(conn)  # Track this connection
            return conn
        
        conn = self._connection_pool.pop()
        self._active_connections.add(conn)  # Track this connection
        return conn

    async def release_connection(self, conn: aiosqlite.Connection):
        """Release a connection back to the pool"""
        if conn in self._active_connections:
            self._active_connections.remove(conn)
            
        if len(self._connection_pool) < self.max_connections:
            self._connection_pool.append(conn)
        else:
            await conn.close()

    async def add_batch(self, documents: List[Dict[str, str]], model_name: str) -> int:
        """Add a new batch of documents to process"""
        async with self.write_lock:
            conn = await self.get_connection()
            try:
                cursor = await conn.execute(
                    "SELECT COALESCE(MAX(batch_id), 0) + 1 FROM processing_jobs"
                )
                row = await cursor.fetchone()
                batch_id = int(row[0])
                
                await conn.executemany(
                    """INSERT INTO processing_jobs (filename, source_doc, model_name, batch_id, row_index) 
                       VALUES (?, ?, ?, ?, ?)""",
                    [(doc["filename"], doc["content"], model_name, batch_id, i) 
                     for i, doc in enumerate(documents)]
                )
                await conn.commit()
                return batch_id
            finally:
                await self.release_connection(conn)

    async def update_response(self, job_id: int, response: str, token_count: int):
        """Update the response for a specific job"""
        async with self.write_lock:
            conn = await self.get_connection()
            try:
                await conn.execute(
                    """UPDATE processing_jobs 
                       SET response = ?, token_count = ?, status = 'completed'
                       WHERE id = ?""",
                    (response, token_count, job_id)
                )
                await conn.commit()
            finally:
                await self.release_connection(conn)

    async def get_pending_jobs(self, batch_id: int) -> List[Dict[str, Any]]:
        """Get all pending jobs for a batch"""
        conn = await self.get_connection()
        try:
            async with conn.execute(
                """SELECT id, filename, source_doc, model_name, row_index 
                   FROM processing_jobs 
                   WHERE batch_id = ? AND status = 'pending'
                   ORDER BY row_index""",
                (batch_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "filename": row[1],
                        "source_doc": row[2],
                        "model_name": row[3],
                        "row_index": row[4]
                    }
                    for row in rows
                ]
        finally:
            await self.release_connection(conn)

    async def get_batch_results(self, batch_id: int) -> List[Dict[str, Any]]:
        """Get all results for a batch"""
        conn = await self.get_connection()
        try:
            async with conn.execute(
                """SELECT filename, source_doc, response, status, error, row_index 
                   FROM processing_jobs 
                   WHERE batch_id = ?
                   ORDER BY row_index""",
                (batch_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "filename": row[0],
                        "source_doc": row[1],
                        "response": row[2],
                        "status": row[3],
                        "error": row[4],
                        "row_index": row[5]
                    }
                    for row in rows
                ]
        finally:
            await self.release_connection(conn)

    async def save_config(self, key: str, value: str):
        """Save a configuration value"""
        async with self.write_lock:
            conn = await self.get_connection()
            try:
                await conn.execute(
                    """INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)""",
                    (key, value)
                )
                await conn.commit()
            finally:
                await self.release_connection(conn)

    async def get_config(self, key: str) -> Optional[str]:
        """Get a configuration value"""
        conn = await self.get_connection()
        try:
            async with conn.execute(
                """SELECT value FROM config WHERE key = ?""",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        finally:
            await self.release_connection(conn)

    async def close_all_connections(self):
        """Close all database connections in the pool and any active connections"""
        print(f"Closing all connections. Pool size: {len(self._connection_pool)}, Active connections: {len(self._active_connections)}")
        
        # Close connections in the pool
        while self._connection_pool:
            conn = self._connection_pool.pop()
            try:
                await conn.close()
                print("Closed pooled connection")
            except Exception as e:
                print(f"Error closing pooled connection: {str(e)}")
        
        # Close active connections
        active_connections = list(self._active_connections)
        for conn in active_connections:
            try:
                await conn.close()
                self._active_connections.remove(conn)
                print("Closed active connection")
            except Exception as e:
                print(f"Error closing active connection: {str(e)}")
        
        # Wait a moment to ensure SQLite releases the file
        await asyncio.sleep(0.5)
        
        # Force close any remaining connections by explicitly releasing the database file
        # This is a last resort to ensure the file is not locked
        if os.name == 'nt':  # Windows-specific handling
            try:
                # Try to force close any remaining connections
                for _ in range(3):  # Try a few times
                    try:
                        # Create a temporary file to test if the database is unlocked
                        with open(f"{self.db_path}.test", "w") as f:
                            f.write("test")
                        os.remove(f"{self.db_path}.test")
                        break  # If we get here, the file is unlocked
                    except PermissionError:
                        # If we can't create the test file, the database is still locked
                        print("Database still locked, waiting...")
                        await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error during force close: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_all_connections() 