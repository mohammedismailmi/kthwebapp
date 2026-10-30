import pandas as pd
import io
import re

def flatten_rga_wrapper(file_obj):
    """
    Parses a raw Hiden RGA CSV file, fixing lines that were artificially 
    wrapped (e.g., continuous numbers split across lines).
    """
    content = file_obj.read()
    if isinstance(content, bytes):
        content = content.decode('utf-8')
        
    # Fix numbers split across lines implicitly by comma counting and strip()
    # No regex needed, it causes valid rows to merge.
    
    lines = content.split('\n')
    if not lines:
        return pd.DataFrame()
        
    header = lines[0]
    expected_commas = header.count(',')
    
    flattened_lines = [header]
    current_line = ""
    for line in lines[1:]:
        if not line.strip():
            continue
        current_line += line.strip()
        if current_line.count(',') == expected_commas:
            flattened_lines.append(current_line)
            current_line = ""
        elif current_line.count(',') > expected_commas:
            flattened_lines.append(current_line)
            current_line = ""
            
    if current_line:
        flattened_lines.append(current_line)
        
    return pd.read_csv(io.StringIO('\n'.join(flattened_lines)))
