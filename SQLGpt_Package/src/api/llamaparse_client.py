import os
import aiohttp
import asyncio
import json
import tempfile
from typing import Optional, Dict, Any, List
from ..config import config
import PyPDF2
import mimetypes

class LlamaParseClient:
    def __init__(self):
        self.api_key: Optional[str] = None
        self.base_url = "https://api.cloud.llamaindex.ai/api/parsing"

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    async def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Process a file through the LlamaParse API"""
        if not self.api_key:
            raise ValueError("API key not set")

        try:
            # Check if we need to extract specific pages
            temp_file = None
            upload_path = file_path
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Only extract pages for PDFs when max_pages is set
            if file_ext == '.pdf' and config.llamaparse_max_pages > 0:
                # Create a temporary file for the extracted page(s)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                temp_file.close()
                
                # Extract the specified number of pages
                try:
                    with open(file_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        pdf_writer = PyPDF2.PdfWriter()
                        
                        # Get the number of pages to extract (limited by the actual PDF length)
                        num_pages = min(config.llamaparse_max_pages, len(pdf_reader.pages))
                        
                        # Add pages to the new PDF
                        for page_num in range(num_pages):
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                        
                        # Save the new PDF to the temporary file
                        with open(temp_file.name, 'wb') as output_file:
                            pdf_writer.write(output_file)
                    
                    # Use the temporary file for upload
                    upload_path = temp_file.name
                except Exception as e:
                    # If extraction fails, fall back to the original file
                    if temp_file and os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                    raise Exception(f"Failed to extract pages from PDF: {str(e)}")
            
            # Upload the file (either original or extracted pages)
            job_id = await self._upload_file(upload_path)
            
            # Poll for completion
            result = await self._wait_for_completion(job_id)
            
            # Get the markdown result
            markdown_content = await self._get_result(job_id, "markdown")
            
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            
            return {
                "job_id": job_id,
                "content": markdown_content,
                "metadata": result.get("job_metadata", {})
            }
        except Exception as e:
            # Clean up temporary file if there was an error
            if 'temp_file' in locals() and temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            
            print(f"Error in process_pdf: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    async def _upload_file(self, file_path: str, max_retries: int = 3) -> str:
        """Upload a file to LlamaParse and get the job ID"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        # Determine content type based on file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

        # Prepare form data with file and parameters
        data = aiohttp.FormData()
        data.add_field('file', 
                      open(file_path, 'rb'),
                      filename=os.path.basename(file_path),
                      content_type=content_type)
        
        # Map user-friendly modes to API modes
        mode_mapping = {
            "fast": "parse_page_without_llm",
            "balanced": "parse_page_with_llm",
            "premium": "parse_document_with_llm"
        }
        
        # Add LlamaParse parameters with correct API values
        api_mode = mode_mapping.get(config.llamaparse_mode, "parse_page_with_llm")
        data.add_field('parse_mode', api_mode)
        data.add_field('continuous_mode', str(config.llamaparse_continuous_mode).lower())
        data.add_field('auto_mode', str(config.llamaparse_auto_mode).lower())
        
        if config.llamaparse_max_pages > 0:
            data.add_field('max_pages', str(config.llamaparse_max_pages))
        
        data.add_field('language', config.llamaparse_language)
        data.add_field('disable_ocr', str(config.llamaparse_disable_ocr).lower())
        data.add_field('skip_diagonal_text', str(config.llamaparse_skip_diagonal_text).lower())
        data.add_field('do_not_unroll_columns', str(config.llamaparse_do_not_unroll_columns).lower())
        data.add_field('output_tables_as_HTML', str(config.llamaparse_output_tables_as_html).lower())
        data.add_field('preserve_layout_alignment_across_pages', str(config.llamaparse_preserve_layout_alignment).lower())

        # Implement retry logic
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.base_url}/upload", headers=headers, data=data) as response:
                        response_text = await response.text()
                        
                        if response.status != 200:
                            raise Exception(f"Upload failed: {response_text}")
                        
                        try:
                            result = json.loads(response_text)
                        except json.JSONDecodeError:
                            raise Exception(f"Failed to parse response as JSON: {response_text}")
                        
                        # The API returns 'id' instead of 'job_id'
                        job_id = result.get("id")
                        
                        if not job_id:
                            error_msg = result.get("detail", "No job ID returned")
                            raise Exception(f"Failed to get job ID: {error_msg}")
                            
                        return job_id
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Network-related errors that might be temporary
                retry_count += 1
                last_error = e
                if retry_count < max_retries:
                    # Exponential backoff: wait 1s, 2s, 4s, etc.
                    wait_time = 2 ** (retry_count - 1)
                    print(f"Network error, retrying in {wait_time}s ({retry_count}/{max_retries}): {str(e)}")
                    await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                # Other errors should not be retried
                raise e
        
        # If we've exhausted all retries
        raise Exception(f"Failed to upload file after {max_retries} attempts: {str(last_error)}")

    async def _wait_for_completion(self, job_id: str, timeout: int = 1800, max_retries: int = 3) -> Dict[str, Any]:
        """Wait for job completion with timeout"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        start_time = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout} seconds")

            # Implement retry logic for status check
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self.base_url}/job/{job_id}", headers=headers) as response:
                            response_text = await response.text()
                            
                            if response.status != 200:
                                raise Exception(f"Status check failed: {response_text}")
                            
                            try:
                                result = json.loads(response_text)
                            except json.JSONDecodeError:
                                raise Exception(f"Failed to parse status response as JSON: {response_text}")
                            
                            status = result.get("status")
                            
                            # Check for various success statuses
                            if status in ["COMPLETED", "completed", "SUCCESS", "success"]:
                                return result
                            # Check for various failure statuses
                            elif status in ["FAILED", "failed", "ERROR", "error"]:
                                error = result.get("error", "Unknown error")
                                raise Exception(f"Job failed: {error}")
                            
                            # Successfully got status, break retry loop
                            break
                            
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    # Network-related errors that might be temporary
                    retry_count += 1
                    last_error = e
                    if retry_count < max_retries:
                        # Exponential backoff: wait 1s, 2s, 4s, etc.
                        wait_time = 2 ** (retry_count - 1)
                        print(f"Network error during status check, retrying in {wait_time}s ({retry_count}/{max_retries}): {str(e)}")
                        await asyncio.sleep(wait_time)
                    else:
                        # If we've exhausted all retries for this status check
                        print(f"Failed to check status after {max_retries} attempts: {str(last_error)}")
                        # Continue with the outer loop instead of failing completely
                        break
                except Exception as e:
                    # Other errors should not be retried
                    raise e
            
            # Still processing or had temporary network issues, wait before next check
            await asyncio.sleep(5)

    async def _get_result(self, job_id: str, result_type: str = "markdown", max_retries: int = 3) -> str:
        """Get the job result in the specified format"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # First check if the job is completed
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.base_url}/job/{job_id}", headers=headers) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            raise Exception(f"Failed to check job status: {response_text}")
                        
                        result = await response.json()
                        if result.get("status") not in ["COMPLETED", "completed", "SUCCESS", "success"]:
                            raise Exception(f"Job is not completed. Current status: {result.get('status')}")
                        
                        # Job is completed, break retry loop
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Network-related errors that might be temporary
                retry_count += 1
                last_error = e
                if retry_count < max_retries:
                    # Exponential backoff: wait 1s, 2s, 4s, etc.
                    wait_time = 2 ** (retry_count - 1)
                    print(f"Network error checking job status, retrying in {wait_time}s ({retry_count}/{max_retries}): {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    # If we've exhausted all retries
                    raise Exception(f"Failed to check job status after {max_retries} attempts: {str(last_error)}")
                continue
            except Exception as e:
                # Other errors should not be retried
                raise e
        
        # Get the result in the requested format
        result_url = f"{self.base_url}/job/{job_id}/result"
        if result_type == "markdown":
            result_url = f"{result_url}/markdown"
        elif result_type == "text":
            result_url = f"{result_url}/text"
        
        # Implement retry logic for getting results
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(result_url, headers=headers) as response:
                        response_text = await response.text()
                        
                        if response.status != 200:
                            raise Exception(f"Failed to get {result_type} result: {response_text}")
                        
                        try:
                            result = json.loads(response_text)
                        except json.JSONDecodeError:
                            # If the response is not JSON, it might be the raw content
                            return response_text
                        
                        # Try to find the content in the response
                        if result_type in result:
                            return result[result_type]
                        elif "content" in result:
                            return result["content"]
                        elif "text" in result:
                            return result["text"]
                        elif "result" in result:
                            return result["result"]
                        elif "data" in result:
                            return result["data"]
                        else:
                            # If we can't find the content in any known field, return the whole response as JSON
                            return json.dumps(result, indent=2)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Network-related errors that might be temporary
                retry_count += 1
                last_error = e
                if retry_count < max_retries:
                    # Exponential backoff: wait 1s, 2s, 4s, etc.
                    wait_time = 2 ** (retry_count - 1)
                    print(f"Network error getting results, retrying in {wait_time}s ({retry_count}/{max_retries}): {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    # If we've exhausted all retries
                    raise Exception(f"Failed to get results after {max_retries} attempts: {str(last_error)}")
                continue
            except Exception as e:
                # Other errors should not be retried
                raise e

    async def process_pdfs(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple PDF files in parallel"""
        tasks = [self.process_pdf(file_path) for file_path in file_paths]
        return await asyncio.gather(*tasks)

# Global client instance
llamaparse_client = LlamaParseClient() 