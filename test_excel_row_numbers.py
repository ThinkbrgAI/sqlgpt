#!/usr/bin/env python
"""
Test script to verify Excel export and import with Row Numbers.

This script creates a sample DataFrame with Row Number column,
exports it to Excel, and then imports it back to verify that
the Row Number column is properly handled.
"""

import os
import pandas as pd
import sys
from pathlib import Path

def test_excel_with_row_numbers():
    """Test Excel export and import with Row Numbers."""
    print("Testing Excel export and import with Row Numbers...")
    
    # Create a sample DataFrame with Row Number column
    data = []
    for i in range(5):
        data.append({
            "Row Number": i + 1,
            "Filename": f"test{i+1}.pdf",
            "Source Doc": f"This is the source document for test {i+1}.",
            "Response": f"This is the response for test {i+1}."
        })
    
    # Shuffle the data to test sorting
    import random
    random.shuffle(data)
    
    # Create the DataFrame
    df_original = pd.DataFrame(data)
    print(f"Original DataFrame with shape: {df_original.shape}")
    print(df_original[["Row Number", "Filename"]])
    
    # Export to Excel
    output_file = "test_row_numbers.xlsx"
    try:
        print(f"Exporting to {output_file}...")
        df_original.to_excel(output_file, index=False)
        print(f"Successfully exported to {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
        
        # Import back from Excel
        print(f"Importing from {output_file}...")
        df_imported = pd.read_excel(output_file)
        print(f"Imported DataFrame with shape: {df_imported.shape}")
        
        # Check if Row Number column exists
        if "Row Number" in df_imported.columns:
            print("Row Number column found in imported data")
            
            # Sort by Row Number
            df_sorted = df_imported.sort_values(by="Row Number")
            print("Sorted DataFrame by Row Number:")
            print(df_sorted[["Row Number", "Filename"]])
            
            # Verify that the data is in the correct order after sorting
            expected_row_numbers = list(range(1, len(df_sorted) + 1))
            actual_row_numbers = df_sorted["Row Number"].tolist()
            
            print(f"Expected Row Numbers: {expected_row_numbers}")
            print(f"Actual Row Numbers: {actual_row_numbers}")
            
            if expected_row_numbers == actual_row_numbers:
                print("Row Numbers are in the correct order after sorting")
                
                # Also verify that the filenames match the row numbers
                is_correct = True
                for i, row in df_sorted.iterrows():
                    expected_filename = f"test{row['Row Number']}.pdf"
                    if row["Filename"] != expected_filename:
                        print(f"Error: Row with Row Number {row['Row Number']} has Filename {row['Filename']} instead of {expected_filename}")
                        is_correct = False
                
                if is_correct:
                    print("All filenames match their corresponding Row Numbers")
                    return True
                else:
                    print("Some filenames do not match their corresponding Row Numbers")
                    return False
            else:
                print("Row Numbers are not in the correct order after sorting")
                return False
        else:
            print("Error: Row Number column not found in imported data")
            return False
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during export or import: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_excel_with_row_numbers()
    print(f"Test {'passed' if success else 'failed'}")
    input("Press Enter to exit...") 