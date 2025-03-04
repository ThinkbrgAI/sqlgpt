import pandas as pd
import os
import sys
from pathlib import Path

def test_complex_excel_export():
    """Test if pandas can export complex data to Excel properly."""
    print("Testing complex Excel export with pandas...")
    
    # Create a DataFrame with potentially problematic data
    data = []
    
    # Add some normal data
    data.append({
        "Filename": "test1.pdf",
        "Source Doc": "This is a normal text document.",
        "Response": "This is a normal response."
    })
    
    # Add data with special characters
    data.append({
        "Filename": "test2.pdf",
        "Source Doc": "Text with special characters: ©®™§¶†‡",
        "Response": "Response with special characters: ©®™§¶†‡"
    })
    
    # Add data with very long text
    long_text = "This is a very long text. " * 1000  # 24,000 characters
    data.append({
        "Filename": "test3.pdf",
        "Source Doc": long_text,
        "Response": "Response to long text."
    })
    
    # Add data with tables in markdown format
    markdown_table = """
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |
    """
    data.append({
        "Filename": "test4.pdf",
        "Source Doc": f"Document with a table:\n{markdown_table}",
        "Response": "Response to document with table."
    })
    
    # Create the DataFrame
    df = pd.DataFrame(data)
    print(f"Created DataFrame with shape: {df.shape}")
    
    # Export to Excel
    output_file = "test_complex_export.xlsx"
    try:
        print("Exporting to Excel...")
        df.to_excel(output_file, index=False)
        print(f"Successfully exported to {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error exporting to Excel: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_complex_excel_export()
    print(f"Test {'passed' if success else 'failed'}") 