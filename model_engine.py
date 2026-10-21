"""
Model Engine for Mass Spec AI Calibration (Hugging Face Spaces Deployment).
Uses hosted Hugging Face ZeroGPU Space for inference via gradio_client.
"""
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ---------- Hosted Model Configuration ----------
HF_SPACE_ID = os.environ.get("HF_SPACE_ID", "mohammedismailmi/v9-calibration-api")
USE_HOSTED_MODEL = True

BACKEND = "hf_space"
print(f"[model_engine] Active inference backend: {BACKEND}")

_MODEL_CACHE = None


def load_model():
    """Load and cache the Gradio client."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    print(f"[model_engine] Connecting to Hugging Face Space: {HF_SPACE_ID}...")
    try:
        from gradio_client import Client
        client = Client(HF_SPACE_ID)
        _MODEL_CACHE = (client, None)
        print("[model_engine] Successfully connected to hosted Hugging Face Space!")
        return _MODEL_CACHE
    except Exception as e:
        raise RuntimeError(f"Failed to connect to hosted model at '{HF_SPACE_ID}': {e}")


# ---------- Generation Functions ----------

def _generate_hosted(client, prompt):
    """
    Generate predictions via the Hugging Face Space.
    Formats the prompt with Gemma turn tokens so the instruction-tuned model responds correctly.
    """
    chat_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"

    # Try the named endpoint first, then fallback to /predict or positional call
    try:
        return client.predict(mass_spec_data=chat_prompt, api_name="/run_calibration_inference")
    except Exception as e1:
        try:
            return client.predict(mass_spec_data=chat_prompt, api_name="/predict")
        except Exception as e2:
            try:
                return client.predict(mass_spec_data=chat_prompt)
            except Exception as e3:
                raise RuntimeError(f"Gradio Space inference failed: {e1} | {e2} | {e3}")


def _generate_text(model_tuple, tokenizer, prompt, max_tokens=150):
    """Generate text using the hosted API."""
    client = model_tuple[0] if isinstance(model_tuple, tuple) else model_tuple
    return _generate_hosted(client, prompt)


# ---------- Sensor Baseline Extraction ----------

def extract_sensor_baseline(df):
    """
    Extract average pressure, N2, and Argon baselines from an air scan dataframe.
    Normalizes column headers and applies reference instrument baselines for channels
    omitted in custom scan recipes.
    """
    new_cols = {col: re.match(r'^(\d+_amu)', col.strip()).group(1) if re.match(r'^(\d+_amu)', col.strip()) else col.strip() for col in df.columns}
    df_renamed = df.rename(columns=new_cols)

    col_press = next((c for c in df_renamed.columns if 'Pressure' in c and 'External' not in c), None)
    press = pd.to_numeric(df_renamed[col_press], errors='coerce').dropna().mean() if col_press else 3.75e-05
    if pd.isna(press) or press <= 0:
        press = 3.75e-05

    col_28 = next((c for c in df_renamed.columns if c == '28_amu' or '28_amu' in c), None)
    n2 = pd.to_numeric(df_renamed[col_28], errors='coerce').dropna().mean() if col_28 else 1.87e-10
    if pd.isna(n2) or n2 <= 0 or n2 > 2e-10:
        n2 = 1.87e-10

    col_40 = next((c for c in df_renamed.columns if c == '40_amu' or '40_amu' in c), None)
    ar = pd.to_numeric(df_renamed[col_40], errors='coerce').dropna().mean() if col_40 else 2.52e-09
    if pd.isna(ar) or ar <= 0:
        ar = 2.52e-09

    return float(press), float(n2), float(ar)


# ---------- Virtual Calibration Generation ----------

def generate_virtual_calibration(df, gas_name, model=None, tokenizer=None, num_rows=150):
    """
    Generate a full virtual calibration CSV using the V9 adapter (via hosted Space).

    1. Extracts sensor baseline from uploaded air scan.
    2. Prompts the model for a multi-AMU calibration fingerprint.
    3. Parses log10 AMU values from model output.
    4. Inverts to Amps: real_amps = 10^(log_val) - 1e-16
    5. Builds a synthetic 150-row CSV with Gaussian noise.
    """
    press, n2, ar = extract_sensor_baseline(df)

    prompt = (
        f"Generate a full multi-AMU calibration fingerprint for {gas_name}.\n"
        f"Operating Parameters:\n"
        f"- Vacuum Pressure: {press:.2e} mBar\n"
        f"- Current N2 Baseline (28_amu): {n2:.2e} Amps\n"
        f"- Background Argon (40_amu): {ar:.2e} Amps"
    )

    ai_response = _generate_text(model, tokenizer, prompt, max_tokens=150)
    print(f"[model_engine] Model Output:\n{ai_response}")

    # Parse multi-AMU log predictions
    parsed_amuss = {}
    epsilon = 1e-16
    matches = re.findall(r'(\d+)_amu:\s*([+-]?\d+\.\d+)', ai_response)
    for amu_str, log_val_str in matches:
        log_val = float(log_val_str)
        real_amps = (10 ** log_val) - epsilon
        parsed_amuss[f"{amu_str}_amu"] = real_amps

    # Build synthetic calibration CSV
    columns = [
        "Time Relative (sec)", "Time Absolute (UTC)", "Time Absolute (Date_Time)",
        "Ionizer_State", "Pressure_(mBar)", "External_Pressure_(mBar)"
    ]
    amu_cols = [f"{i}_amu" for i in range(1, 51)]
    mcd_cols = ["Sig:_MCD", "Sig:_MCD_CO2", "Sig:_MCD_N2", "Sig:_MCD_O2"]

    out_df = pd.DataFrame(columns=columns + amu_cols + mcd_cols)
    start_time = datetime.utcnow()

    out_df["Time Relative (sec)"] = np.arange(0, num_rows)
    out_df["Time Absolute (UTC)"] = [
        (start_time + timedelta(seconds=int(i))).strftime('%H:%M:%S.%f')[:-3]
        for i in range(num_rows)
    ]
    out_df["Time Absolute (Date_Time)"] = [
        (start_time + timedelta(seconds=int(i))).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        for i in range(num_rows)
    ]

    out_df["Ionizer_State"] = 1
    out_df["Pressure_(mBar)"] = press + np.random.normal(0, press * 0.01, num_rows)
    out_df["External_Pressure_(mBar)"] = 1000.0

    # Fill all AMUs with baseline noise
    baseline_noise = 1e-13
    for col in amu_cols:
        out_df[col] = np.abs(np.random.normal(baseline_noise, baseline_noise * 0.1, num_rows))

    # Overlay predicted AMU signals with small Gaussian noise
    for col, amp_val in parsed_amuss.items():
        if col in out_df.columns:
            out_df[col] = amp_val + np.random.normal(0, amp_val * 0.005, num_rows)

    # Restore baseline N2 and Argon
    out_df["40_amu"] = ar + np.random.normal(0, ar * 0.01, num_rows)
    out_df["28_amu"] = n2 + np.random.normal(0, n2 * 0.01, num_rows)
    for mcd in mcd_cols:
        out_df[mcd] = 0.0

    return out_df, parsed_amuss
