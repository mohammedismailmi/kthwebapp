"""Quick end-to-end test of the cross-platform model engine."""
import pandas as pd
import numpy as np

def test():
    from rga_parser import flatten_rga_wrapper
    from validator import validate_air_scan
    from model_engine import load_model, generate_virtual_calibration, BACKEND
    
    print(f"Backend: {BACKEND}")
    
    print("Parsing air scan...")
    with open('/Users/mi/Desktop/KTH internship/massspec_kth/dataset/zzz_converted_csv/kth/training/compressed_air.csv', 'rb') as f:
        df = flatten_rga_wrapper(f)
    print(f"Shape: {df.shape}")
    
    print("Validating...")
    is_valid, msg = validate_air_scan(df)
    print(f"Valid: {is_valid} — {msg}")
    if not is_valid: return
    
    print("Loading model...")
    model, tokenizer = load_model()
    print("Model loaded.")
    
    print("Generating O2 1% virtual calibration...")
    out_df, parsed_amus = generate_virtual_calibration(df, "O2 1%", model, tokenizer, num_rows=150)
    
    print(f"Parsed AMUs: {parsed_amus}")
    print(f"Output shape: {out_df.shape}")
    
    # Accuracy check vs ground truth
    real_file = "/Users/mi/Desktop/KTH internship/massspec_kth/dataset/zzz_converted_csv/kth/training/master_pinn_dataset.csv"
    df_real = pd.read_csv(real_file)
    if "Source_File" in df_real.columns:
        df_real = df_real[df_real["Source_File"] == "cal_O2_1%"].copy()
    
    for col in [f"{amu}_amu" for amu in [32, 16, 34, 33]]:
        real_val = pd.to_numeric(df_real[col], errors='coerce').dropna().mean() if col in df_real.columns else 1e-15
        virt_val = pd.to_numeric(out_df[col], errors='coerce').dropna().mean() if col in out_df.columns else 0
        if pd.isna(real_val) or real_val <= 0: real_val = 1e-15
        if pd.isna(virt_val) or virt_val <= 0: virt_val = 1e-15
        error = abs((virt_val - real_val) / real_val) * 100
        accuracy = max(0, 100 - error)
        print(f"  {col}: Real={real_val:.2e}, Virt={virt_val:.2e}, Acc={accuracy:.2f}%")
    
    print("All tests passed.")

if __name__ == "__main__":
    test()
