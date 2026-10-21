import pandas as pd
import io
import time

def test_pipeline():
    print("Testing parser...")
    from rga_parser import flatten_rga_wrapper
    with open('/Users/mi/Desktop/KTH internship/massspec_kth/dataset/zzz_converted_csv/kth/training/compressed_air.csv', 'rb') as f:
        df = flatten_rga_wrapper(f)
    print("Parsed DataFrame shape:", df.shape)
    
    print("Testing validator...")
    from validator import validate_air_scan
    is_valid, msg = validate_air_scan(df)
    print("Validator result:", is_valid, msg)
    if not is_valid:
        return
        
    print("Loading model engine...")
    from model_engine import load_model, generate_virtual_calibration
    model, tokenizer = load_model()
    print("Model loaded.")
    
    # Run on just the first 5 rows for a quick test
    df_small = df.head(5).copy()
    print("Generating calibration...")
    out_df, target_col = generate_virtual_calibration(df_small, "Oxygen O2", "1%", model, tokenizer)
    print("Target column created:", target_col)
    print("Sample output predictions:")
    print(out_df[[target_col]].head())
    print("All tests passed.")

if __name__ == "__main__":
    test_pipeline()
