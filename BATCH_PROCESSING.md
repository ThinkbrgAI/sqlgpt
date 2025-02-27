# Batch Processing Guide

## Overview

The batch processing functionality allows you to process multiple files automatically without user interaction. This is especially useful for large datasets or when you need to process files overnight.

## Features

- **Automatic Processing**: Process multiple files without manual intervention
- **Resume Capability**: Continue from where processing stopped if interrupted
- **Recursive Directory Processing**: Process files in subdirectories
- **Error Handling**: Retry mechanism for failed files
- **Memory Management**: Garbage collection to prevent memory issues
- **Progress Tracking**: Save progress to resume later
- **Flexible File Selection**: Process specific file types

## Usage

### Using the Batch File (Recommended)

The easiest way to use batch processing is with the provided batch file:

1. Double-click on `batch_process_robust.bat`
2. Enter the directory containing the files to process
3. Optionally specify an output directory
4. Choose whether to resume from a previous run
5. Choose whether to process subdirectories recursively

### Command Line Usage

For advanced users, you can run the batch processing script directly from the command line:

```
python batch_process.py [input_dir] [options]
```

#### Options:

- `--output-dir`, `-o`: Directory to save output files (default: same as input)
- `--recursive`, `-r`: Process subdirectories recursively
- `--extensions`, `-e`: File extensions to process (default: .pdf)
- `--resume`: Resume from previous run
- `--resume-file`: Custom file to track progress for resuming

#### Examples:

Process all PDF files in a directory:
```
python batch_process.py C:\Documents\PDFs
```

Process all PDF files and save output to a different directory:
```
python batch_process.py C:\Documents\PDFs --output-dir C:\Documents\Output
```

Process all PDF files recursively:
```
python batch_process.py C:\Documents\PDFs --recursive
```

Process specific file types:
```
python batch_process.py C:\Documents\Files --extensions .pdf .docx .xlsx
```

Resume from a previous run:
```
python batch_process.py C:\Documents\PDFs --resume
```

## Troubleshooting

### Memory Issues

If you encounter memory issues when processing large files:

1. Process fewer files at a time
2. Close other applications to free up memory
3. Restart your computer before processing

### Processing Errors

If specific files fail to process:

1. Check if the file is corrupted or password-protected
2. Try processing the file individually
3. Check the console output for specific error messages

### Resume Not Working

If the resume functionality isn't working:

1. Check if the progress file exists (`batch_progress_[dirname].json`)
2. Verify that the file has the correct format
3. Try specifying a custom resume file with `--resume-file`

## Advanced Configuration

For advanced users, you can modify the batch processing script to:

- Change the number of retry attempts
- Adjust the delay between processing files
- Modify the garbage collection frequency
- Change the progress file format

## Performance Tips

- Process files in smaller batches for better reliability
- Use an SSD for faster processing
- Close other applications to free up memory
- Run during off-hours for large datasets 