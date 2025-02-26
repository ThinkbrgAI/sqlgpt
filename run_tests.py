import os
import sys
import pytest

def main():
    """Run all tests"""
    # Add src to Python path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
    
    # Run tests
    pytest.main([
        "tests",
        "-v",
        "--asyncio-mode=auto",
        "--capture=no"
    ])

if __name__ == "__main__":
    main() 