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
        
        # Define cost rates per million tokens (MTok)
        self.cost_rates = {
            "o1": {"input": 15.00, "output": 60.00},  # OpenAI o1 model
            "o3-mini": {"input": 1.10, "output": 4.40},  # OpenAI o3-mini model
            "claude-3-7-sonnet-20250219": {"input": 3.00, "output": 15.00}  # Claude 3.7 Sonnet
        }

    def calculate_cost(self, model_name: str, token_count: int, input_ratio: float = 0.7) -> float:
        """
        Calculate the cost of API usage based on model and token count
        
        Args:
            model_name: The name of the model used
            token_count: Total token count (input + output)
            input_ratio: Estimated ratio of input tokens to total tokens (default 0.7)
            
        Returns:
            Calculated cost in USD
        """
        # Handle empty or None model name
        if not model_name:
            print("Warning: Empty model name provided to calculate_cost, using default o1 rates")
            model_key = "o1"
        # Handle Anthropic models by checking if the model name contains 'claude'
        elif 'claude' in model_name.lower():
            model_key = "claude-3-7-sonnet-20250219"  # Use the standard key for all Claude models
            print(f"Using Claude rate for model: {model_name}")
        # Handle OpenAI models
        elif model_name.startswith('o') and model_name in self.cost_rates:
            model_key = model_name
            print(f"Using exact rate match for model: {model_name}")
        else:
            # Default to o1 rates if model not found
            print(f"Model {model_name} not found in cost rates, using o1 rates")
            model_key = "o1"
            
        rates = self.cost_rates[model_key]
        
        # Estimate input and output tokens based on the ratio
        input_tokens = token_count * input_ratio
        output_tokens = token_count * (1 - input_ratio)
        
        # Calculate cost (rates are per million tokens)
        input_cost = (input_tokens / 1000000) * rates["input"]
        output_cost = (output_tokens / 1000000) * rates["output"]
        
        total_cost = input_cost + output_cost
        
        # Add debug logging
        print(f"Cost calculation for model '{model_name}' (using rates for '{model_key}'):")
        print(f"  Token count: {token_count} (input: {input_tokens:.0f}, output: {output_tokens:.0f})")
        print(f"  Rates: input=${rates['input']}/MTok, output=${rates['output']}/MTok")
        print(f"  Cost: input=${input_cost:.6f}, output=${output_cost:.6f}, total=${total_cost:.6f}")
        
        return total_cost

    async def initialize(self):
        """Initialize the database with schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(get_schema_sql())
            await db.commit()
            
            # Check if cost column exists and add it if it doesn't
            try:
                # Check if the cost column exists
                cursor = await db.execute("PRAGMA table_info(processing_jobs)")
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]
                
                if 'cost' not in column_names:
                    print("Cost column not found in database, adding it now...")
                    # Add the cost column if it doesn't exist
                    await db.execute("ALTER TABLE processing_jobs ADD COLUMN cost REAL DEFAULT 0")
                    await db.commit()
                    print("Cost column added successfully")
            except Exception as e:
                print(f"Error checking/adding cost column: {str(e)}")
                # Continue with initialization even if this fails

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
                # First, get the model name for this job
                cursor = await conn.execute(
                    "SELECT model_name FROM processing_jobs WHERE id = ?",
                    (job_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    print(f"Warning: Job ID {job_id} not found")
                    return
                    
                model_name = row[0]
                
                # Calculate the cost based on model and token count
                cost = self.calculate_cost(model_name, token_count)
                
                # Print detailed debug information
                print(f"Updating job {job_id} with:")
                print(f"  Model: {model_name}")
                print(f"  Token count: {token_count}")
                print(f"  Cost: ${cost:.6f}")
                print(f"  Status: completed")
                
                # Update the job with response, token count, and cost
                await conn.execute(
                    """UPDATE processing_jobs 
                       SET response = ?, token_count = ?, cost = ?, status = 'completed'
                       WHERE id = ?""",
                    (response, token_count, cost, job_id)
                )
                await conn.commit()
                
                # Verify the update was successful
                cursor = await conn.execute(
                    """SELECT token_count, cost, status FROM processing_jobs WHERE id = ?""",
                    (job_id,)
                )
                verify_row = await cursor.fetchone()
                if verify_row:
                    print(f"Verified update for job {job_id}:")
                    print(f"  Token count: {verify_row[0]}")
                    print(f"  Cost: ${verify_row[1]:.6f}")
                    print(f"  Status: {verify_row[2]}")
                else:
                    print(f"Warning: Could not verify update for job {job_id}")
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

    async def clear_responses_in_db(self):
        """Clear all responses in the database"""
        conn = None
        try:
            # Get a database connection
            conn = await self.get_connection()
            
            # Instead of deleting records, update the response column to be empty
            # and reset the status to 'pending', token_count to 0, and cost to 0
            await conn.execute("UPDATE processing_jobs SET response = '', status = 'pending', token_count = 0, cost = 0")
            
            # Commit the changes
            await conn.commit()
            
            # Get all row indices to update the UI
            cursor = await conn.execute("SELECT DISTINCT row_index FROM processing_jobs ORDER BY row_index")
            rows = await cursor.fetchall()
            row_indices = [row[0] for row in rows]
            
            print(f"Successfully cleared all responses from the database. Affected rows: {row_indices}")
            
            # Return the list of row indices that were affected
            return row_indices
        except Exception as e:
            print(f"Error clearing responses from database: {str(e)}")
            if conn:
                await conn.rollback()  # Rollback any uncommitted changes
            raise
        finally:
            # Always release the connection
            if conn:
                await self.release_connection(conn) 