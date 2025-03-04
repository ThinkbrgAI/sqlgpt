import pandas as pd
import os

def test_excel_export():
    """Test if pandas can export to Excel properly."""
    print("Testing Excel export with pandas...")
    
    # Create a simple DataFrame
    data = [
        {"Column1": "Value1", "Column2": "Value2", "Column3": "Value3"},
        {"Column1": "Value4", "Column2": "Value5", "Column3": "Value6"},
        {"Column1": "Value7", "Column2": "Value8", "Column3": "Value9"}
    ]
    
    df = pd.DataFrame(data)
    print(f"Created DataFrame with shape: {df.shape}")
    
    # Export to Excel
    output_file = "test_export.xlsx"
    try:
        df.to_excel(output_file, index=False)
        print(f"Successfully exported to {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
        return True
    except Exception as e:
        print(f"Error exporting to Excel: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_excel_export()
    print(f"Test {'passed' if success else 'failed'}") 