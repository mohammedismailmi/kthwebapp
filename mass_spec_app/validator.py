def validate_air_scan(df):
    """
    Sanity check for Air Scan:
    - Inspect for dominant 28_amu (N2) and 32_amu (O2) signals.
    - If 16_amu (hydrocarbon) is unusually high, halt processing.
    """
    col_28 = next((c for c in df.columns if '28_amu' in c), None)
    col_32 = next((c for c in df.columns if '32_amu' in c), None)
    col_16 = next((c for c in df.columns if '16_amu' in c), None)
    
    if not col_28 or not col_32:
        return False, "Error: Missing 28_amu (N2) or 32_amu (O2) columns in the dataset."
        
    if col_16:
        max_16 = df[col_16].max()
        max_28 = df[col_28].max()
        
        # In a clean air scan, 16_amu (O fragment from O2 or CH4) should be very low compared to N2.
        # If it's more than 10% of the 28_amu max, it's likely hydrocarbon interference.
        if max_28 > 0 and max_16 > (0.10 * max_28):
            return False, "Error: Uploaded file contains hydrocarbon interference. Please upload a clean background air scan."
            
    return True, "Valid air scan."
