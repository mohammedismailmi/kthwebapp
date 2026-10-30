"""
Converts MLX LoRA adapter weights to HuggingFace PEFT format.

MLX key format:  model.layers.10.self_attn.q_proj.lora_a  (shape: in_features, rank)
PEFT key format: base_model.model.model.layers.10.self_attn.q_proj.lora_A.weight  (shape: rank, in_features)

MLX stores lora_a as (in_features, rank) — PEFT stores lora_A.weight as (rank, in_features).
MLX stores lora_b as (rank, out_features) — PEFT stores lora_B.weight as (out_features, rank).
"""
import os
import json
import numpy as np
from safetensors.numpy import load_file, save_file

def convert_mlx_to_peft(mlx_adapter_dir, output_dir, base_model_name="google/gemma-2-2b-it"):
    """Convert MLX LoRA adapter to HuggingFace PEFT format."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Load MLX adapter config
    with open(os.path.join(mlx_adapter_dir, "adapter_config.json"), "r") as f:
        mlx_config = json.load(f)
    
    rank = mlx_config["lora_parameters"]["rank"]
    scale = mlx_config["lora_parameters"]["scale"]
    dropout = mlx_config["lora_parameters"]["dropout"]
    lora_alpha = scale * rank  # MLX scale = alpha/rank, so alpha = scale * rank
    
    # Load MLX adapter weights
    mlx_weights = load_file(os.path.join(mlx_adapter_dir, "adapters.safetensors"))
    
    # Convert keys and transpose weights
    peft_weights = {}
    target_modules = set()
    
    for mlx_key, tensor in mlx_weights.items():
        # mlx_key: model.layers.10.self_attn.q_proj.lora_a
        # peft_key: base_model.model.model.layers.10.self_attn.q_proj.lora_A.weight
        
        if mlx_key.startswith("model."):
            inner_key = mlx_key[len("model."):]  # layers.10.self_attn.q_proj.lora_a
        else:
            inner_key = mlx_key
            
        # Extract module name for target_modules
        parts = inner_key.rsplit(".", 1)  # ['layers.10.self_attn.q_proj', 'lora_a']
        module_path = parts[0]
        lora_part = parts[1]  # 'lora_a' or 'lora_b'
        
        # Extract the short module name (e.g., 'q_proj', 'k_proj', 'down_proj')
        module_name = module_path.rsplit(".", 1)[-1]
        target_modules.add(module_name)
        
        # Map lora_a -> lora_A.weight, lora_b -> lora_B.weight
        if lora_part == "lora_a":
            peft_lora_part = "lora_A.weight"
            # MLX: (in_features, rank) -> PEFT: (rank, in_features)
            tensor = tensor.T
        elif lora_part == "lora_b":
            peft_lora_part = "lora_B.weight"
            # MLX: (rank, out_features) -> PEFT: (out_features, rank)
            tensor = tensor.T
        else:
            print(f"Skipping unknown key: {mlx_key}")
            continue
            
        peft_key = f"base_model.model.model.{module_path}.{peft_lora_part}"
        peft_weights[peft_key] = tensor.astype(np.float32)
    
    # Save converted weights
    save_file(peft_weights, os.path.join(output_dir, "adapter_model.safetensors"))
    
    # Create PEFT adapter_config.json
    peft_config = {
        "auto_mapping": None,
        "base_model_name_or_path": base_model_name,
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "init_lora_weights": True,
        "layers_to_transform": None,
        "layers_pattern": None,
        "lora_alpha": int(lora_alpha),
        "lora_dropout": dropout,
        "modules_to_save": None,
        "peft_type": "LORA",
        "r": rank,
        "revision": None,
        "target_modules": sorted(list(target_modules)),
        "task_type": "CAUSAL_LM",
        "use_rslora": False
    }
    
    with open(os.path.join(output_dir, "adapter_config.json"), "w") as f:
        json.dump(peft_config, f, indent=2)
    
    print(f"Converted {len(peft_weights)} tensors")
    print(f"Target modules: {sorted(target_modules)}")
    print(f"LoRA rank={rank}, alpha={int(lora_alpha)}, dropout={dropout}")
    print(f"Saved to: {output_dir}")

if __name__ == "__main__":
    mlx_dir = "/Users/mi/Desktop/KTH internship/massspec_kth/dataset/zzz_converted_csv/kth/training/gemma_calibration_adapter_v9"
    out_dir = "/Users/mi/Desktop/KTH internship/webapp/mass_spec_app/peft_adapter_v9"
    convert_mlx_to_peft(mlx_dir, out_dir)
