#!/usr/bin/env python
"""
MarkItDown Test Script

This script tests if MarkItDown is properly installed and working.
It creates a simple test document and attempts to convert it to markdown.
"""

import os
import sys
import tempfile

def create_test_file():
    """Create a simple test file to convert."""
    temp_dir = tempfile.gettempdir()
    test_file_path = os.path.join(temp_dir, "markitdown_test.txt")
    
    with open(test_file_path, "w") as f:
        f.write("# MarkItDown Test Document\n\n")
        f.write("This is a test document to verify that MarkItDown is working correctly.\n\n")
        f.write("## Features to test\n\n")
        f.write("- Basic text conversion\n")
        f.write("- Heading preservation\n")
        f.write("- List formatting\n\n")
        f.write("If you can see this converted properly, MarkItDown is working!")
    
    return test_file_path

def test_markitdown(test_file_path):
    """Test MarkItDown conversion."""
    try:
        # Try to import MarkItDown
        try:
            from markitdown import MarkItDown
            print("✅ MarkItDown is installed")
        except ImportError:
            print("❌ MarkItDown is not installed")
            print("Please install it with: pip install markitdown==0.0.1a4")
            return False
        
        # Create a MarkItDown instance
        try:
            # Try without parameters first
            markitdown = MarkItDown()
            print("✅ MarkItDown instance created successfully")
        except Exception as e:
            print(f"❌ Failed to create MarkItDown instance: {str(e)}")
            return False
        
        # Convert the test file
        try:
            result = markitdown.convert(test_file_path)
            print("✅ Test file converted successfully")
            
            # Print the result
            print("\n--- Conversion Result ---")
            print(result.text_content[:200] + "..." if len(result.text_content) > 200 else result.text_content)
            print("------------------------\n")
            
            return True
        except Exception as e:
            print(f"❌ Failed to convert test file: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    """Main function."""
    print("MarkItDown Test Script")
    print("=====================\n")
    
    print("This script will test if MarkItDown is properly installed and working.\n")
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 10):
        print("❌ Python 3.10 or higher is required for MarkItDown")
        return
    else:
        print("✅ Python version is compatible")
    
    # Create test file
    print("\nCreating test file...")
    test_file_path = create_test_file()
    print(f"✅ Test file created at: {test_file_path}")
    
    # Test MarkItDown
    print("\nTesting MarkItDown...")
    success = test_markitdown(test_file_path)
    
    # Clean up
    try:
        os.remove(test_file_path)
        print("✅ Test file cleaned up")
    except:
        print("⚠️ Could not remove test file")
    
    # Final result
    print("\nTest Result:")
    if success:
        print("✅ MarkItDown is working correctly!")
        print("You can now use the local document conversion feature in the application.")
    else:
        print("❌ MarkItDown test failed")
        print("Please check the error messages above and try reinstalling MarkItDown.")

if __name__ == "__main__":
    main()
    print("\nPress Enter to exit...")
    input() 