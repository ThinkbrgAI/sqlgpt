"""
Utility functions for text processing.
"""

import re
from typing import Dict, Any
from ..config import config

def truncate_text(text: str, include_metadata: bool = True) -> str:
    """
    Truncate text based on configuration settings.
    
    Args:
        text: The text to truncate
        include_metadata: Whether to include document metadata
        
    Returns:
        Truncated text with optional metadata note
    """
    # If truncation is disabled or force_full_document is enabled, return the original text
    if config.truncation_mode == "none" or config.force_full_document:
        return text
    
    # Extract metadata if available (first few lines with key: value format)
    metadata = {}
    metadata_text = ""
    
    if include_metadata and config.truncation_include_metadata:
        # Look for metadata at the beginning of the document
        lines = text.split('\n')
        metadata_lines = []
        
        for line in lines[:20]:  # Check first 20 lines for metadata
            # Look for key-value pairs like "Title: Document Name"
            match = re.match(r'^([A-Za-z\s]+):\s*(.+)$', line.strip())
            if match:
                key, value = match.groups()
                metadata[key.strip()] = value.strip()
                metadata_lines.append(line)
            elif line.strip() and metadata:  # Non-empty line after metadata
                break
        
        if metadata:
            metadata_text = '\n'.join(metadata_lines) + '\n\n'
    
    # Apply truncation based on mode
    truncated_text = ""
    
    if config.truncation_mode == "characters":
        # Truncate by character count
        limit = config.truncation_character_limit
        if len(text) > limit:
            truncated_text = text[:limit] + f"\n\n[Note: Text truncated to first {limit} characters]"
        else:
            truncated_text = text
    
    elif config.truncation_mode == "paragraphs":
        # Truncate by paragraph count
        paragraphs = re.split(r'\n\s*\n', text)
        limit = min(config.truncation_paragraph_limit, len(paragraphs))
        
        if len(paragraphs) > limit:
            truncated_text = '\n\n'.join(paragraphs[:limit])
            truncated_text += f"\n\n[Note: Text truncated to first {limit} paragraphs]"
        else:
            truncated_text = text
    
    # Combine metadata with truncated text
    if metadata_text:
        return metadata_text + truncated_text
    else:
        return truncated_text

def extract_document_metadata(text: str) -> Dict[str, Any]:
    """
    Extract metadata from document text.
    
    Args:
        text: The document text
        
    Returns:
        Dictionary of metadata key-value pairs
    """
    metadata = {}
    lines = text.split('\n')
    
    for line in lines[:20]:  # Check first 20 lines for metadata
        match = re.match(r'^([A-Za-z\s]+):\s*(.+)$', line.strip())
        if match:
            key, value = match.groups()
            metadata[key.strip()] = value.strip()
        elif line.strip() and metadata:  # Non-empty line after metadata
            break
    
    return metadata 