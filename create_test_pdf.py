import fitz  # PyMuPDF

def create_pdf_with_table():
    """Create a simple PDF file with a table for testing."""
    print("Creating a test PDF file with a table...")
    
    # Create a new PDF document
    doc = fitz.open()
    
    # Add a page
    page = doc.new_page()
    
    # Add some text
    text = "This is a test PDF file with a table."
    page.insert_text((50, 50), text, fontsize=12)
    
    # Add a table
    table_text = """
    | Column 1 | Column 2 | Column 3 |
    |----------|----------|----------|
    | Value 1  | Value 2  | Value 3  |
    | Value 4  | Value 5  | Value 6  |
    | Value 7  | Value 8  | Value 9  |
    """
    
    # Convert the table to a format that PyMuPDF can render
    lines = table_text.strip().split('\n')
    y_pos = 100
    for line in lines:
        page.insert_text((50, y_pos), line, fontsize=10)
        y_pos += 20
    
    # Save the document
    output_file = "test_table.pdf"
    doc.save(output_file)
    doc.close()
    
    print(f"PDF file created: {output_file}")
    return output_file

if __name__ == "__main__":
    try:
        pdf_file = create_pdf_with_table()
        print(f"Successfully created {pdf_file}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to create PDF: {str(e)}") 