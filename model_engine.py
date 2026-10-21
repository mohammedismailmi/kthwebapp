"""
Model Engine for Mass Spec AI Calibration.
Supports:
1. Online Hosted Inference via Hugging Face ZeroGPU Space (gradio_client)
2. Local Inference via Apple Silicon (MLX) or Cross-Platform PyTorch + PEFT
"""
import os
import re
import sys
import platform
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ---------- Hosted Model Configuration ----------
HF_SPACE_ID = os.environ.get("HF_SPACE_ID", "mohammedismailmi/v9-calibration-api")
USE_HOSTED_MODEL = os.environ.get("USE_HOSTED_MODEL", "true").lower() in ("true", "1", "yes")

# ---------- Local Path Configuration (Fallback) ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MLX_BASE_MODEL = os.environ.get(
    "MLX_BASE_MODEL",
    os.path.expanduser("~/.cache/huggingface/hub/models--google--gemma-2-2b-it/snapshots/299a8560bedf22ed1c72a8a11e7dce4a7f9f51f8")
)
MLX_ADAPTER_PATH = os.environ.get(
    "MLX_ADAPTER_PATH",
    "/Users/mi/Desktop/KTH internship/massspec_kth/dataset/zzz_converted_csv/kth/training/gemma_calibration_adapter_v9"
)
PEFT_ADAPTER_PATH = os.environ.get(
    "PEFT_ADAPTER_PATH",
    os.path.join(SCRIPT_DIR, "peft_adapter_v9")
)
HF_MODEL_NAME = "google/gemma-2-2b-it"


def _detect_backend():
    """Detect the active inference backend."""
    # Prioritize local MLX on Apple Silicon if adapter is available
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        if os.path.exists(MLX_ADAPTER_PATH):
            try:
                import mlx
                import mlx_lm
                return "mlx"
            except ImportError:
                pass

    if USE_HOSTED_MODEL:
        return "hf_space"

    try:
        import torch
        return "pytorch"
    except ImportError:
        pass

    return "hf_space"


BACKEND = _detect_backend()
print(f"[model_engine] Active inference backend: {BACKEND}")

_MODEL_CACHE = None


def load_model():
    """Load and cache the client or local model."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    if BACKEND == "hf_space":
        print(f"[model_engine] Connecting to Hugging Face Space: {HF_SPACE_ID}...")
        try:
            from gradio_client import Client
            client = Client(HF_SPACE_ID)
            _MODEL_CACHE = (client, None)
            print("[model_engine] Successfully connected to hosted Hugging Face Space!")
            return _MODEL_CACHE
        except Exception as e:
            print(f"[model_engine] Warning: Could not connect to Space ({e}). Checking local fallback...")
            # Fall back to local if connection fails
            if platform.system() == "Darwin" and platform.machine() == "arm64":
                try:
                    _MODEL_CACHE = _load_mlx()
                    return _MODEL_CACHE
                except Exception:
                    pass
            raise RuntimeError(f"Failed to connect to hosted model at '{HF_SPACE_ID}': {e}")

    elif BACKEND == "mlx":
        _MODEL_CACHE = _load_mlx()
        return _MODEL_CACHE
    else:
        _MODEL_CACHE = _load_pytorch()
        return _MODEL_CACHE


def _load_mlx():
    """Load model via MLX (Apple Silicon local)."""
    from mlx_lm import load
    print(f"[MLX] Loading base model from: {MLX_BASE_MODEL}")
    print(f"[MLX] Loading adapter from: {MLX_ADAPTER_PATH}")
    model, tokenizer = load(MLX_BASE_MODEL, adapter_path=MLX_ADAPTER_PATH)
    return model, tokenizer


def _load_pytorch():
    """Load model via PyTorch + PEFT (cross-platform local)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    if torch.cuda.is_available():
        device = "cuda"
        dtype = torch.float16
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.float16
    else:
        device = "cpu"
        dtype = torch.float32

    print(f"[PyTorch] Device: {device}, dtype: {dtype}")
    tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME)
    base_model = AutoModelForCausalLM.from_pretrained(
        HF_MODEL_NAME,
        torch_dtype=dtype,
        device_map=device if device != "cpu" else None,
    )
    if device == "cpu":
        base_model = base_model.to(device)

    model = PeftModel.from_pretrained(base_model, PEFT_ADAPTER_PATH)
    model.eval()
    return (model, device, dtype), tokenizer


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
    """Generate text using either the hosted API or local engine."""
    if BACKEND == "hf_space" and model_tuple is not None:
        client = model_tuple[0] if isinstance(model_tuple, tuple) else model_tuple
        return _generate_hosted(client, prompt)
    elif BACKEND == "mlx":
        return _generate_mlx(model_tuple, tokenizer, prompt, max_tokens)
    else:
        return _generate_pytorch(model_tuple, tokenizer, prompt, max_tokens)


def _generate_mlx(model, tokenizer, prompt, max_tokens):
    """Generate using MLX."""
    from mlx_lm import generate
    messages = [{"role": "user", "content": prompt}]
    formatted = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return generate(model, tokenizer, prompt=formatted, max_tokens=max_tokens)


def _generate_pytorch(model_tuple, tokenizer, prompt, max_tokens):
    """Generate using PyTorch."""
    import torch
    model, device, dtype = model_tuple
    messages = [{"role": "user", "content": prompt}]
    formatted = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted, return_tensors="pt").to(device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            temperature=1.0,
        )

    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


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
    Generate a full virtual calibration CSV using the V9 adapter (via hosted Space or local model).

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
