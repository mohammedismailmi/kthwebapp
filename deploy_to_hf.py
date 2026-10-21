#!/usr/bin/env python3
"""
Deploy Mass Spec AI Calibration Web App to Hugging Face Spaces.
"""
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, get_token, create_repo

# Load token from environment or Hugging Face CLI login cache (~/.cache/huggingface/token)
HF_TOKEN = os.environ.get("HF_TOKEN") or get_token()

if not HF_TOKEN:
    # Check .env if available
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("HF_TOKEN="):
                    HF_TOKEN = line.strip().split("=", 1)[1].strip("'\"")
                    break

if not HF_TOKEN:
    print("❌ No Hugging Face token found.")
    print("   Please login using `huggingface-cli login` or set export HF_TOKEN='your_token'.")
    sys.exit(1)

SPACE_ID = "mohammedismailmi/mass-spec-ai-calibration"
APP_DIR = Path(__file__).resolve().parent

api = HfApi(token=HF_TOKEN)

print("=" * 60)
print(f"🚀 Hugging Face Spaces Deployment: {SPACE_ID}")
print("=" * 60)

# Check user status
try:
    user_info = api.whoami()
    is_pro = user_info.get("isPro", False)
    can_pay = user_info.get("canPay", False)
    print(f"👤 Account: {user_info.get('name')}")
    print(f"⭐ Pro Status: {'Active ✅' if is_pro else 'Free Tier (Pro Required for Docker Spaces)'}")
    print(f"💳 Payment / Billing: {'Verified ✅' if can_pay else 'Unverified ⚠️'}")
except Exception as e:
    print(f"❌ Error checking account: {e}")
    sys.exit(1)

# Check existing space SDK
try:
    info = api.space_info(SPACE_ID)
    current_sdk = info.sdk
    print(f"📦 Existing Space detected: SDK is '{current_sdk}'")
    if current_sdk != "docker":
        print(f"⚠️ Space currently has SDK '{current_sdk}'. Deleting and recreating as Docker space...")
        api.delete_repo(repo_id=SPACE_ID, repo_type="space")
        print("   Deleted old space.")
except Exception:
    print(f"📦 Space '{SPACE_ID}' does not exist yet. Will create a new Docker space.")

# Create space with Docker SDK
print(f"\n[1/3] Creating Docker Space: {SPACE_ID} ...")
try:
    repo_url = create_repo(
        repo_id=SPACE_ID,
        repo_type="space",
        space_sdk="docker",
        token=HF_TOKEN,
        exist_ok=True,
        private=False,
    )
    print(f"✅ Space created successfully: {repo_url}")
except Exception as e:
    print(f"\n❌ Failed to create Docker Space: {e}")
    if "402" in str(e) or "Payment Required" in str(e):
        print("\n👉 Hugging Face requires a PRO plan ($9/mo) or a verified card to create Docker spaces.")
        print("   Subscribe at: https://huggingface.co/pricing")
        print("   Once subscribed, simply re-run this script to complete deployment instantly!")
    sys.exit(1)

# Upload directory
print(f"\n[2/3] Uploading application files from {APP_DIR} ...")
api.upload_folder(
    folder_path=str(APP_DIR),
    repo_id=SPACE_ID,
    repo_type="space",
    commit_message="Deploy Mass Spec AI Calibration Web App v2.1",
    ignore_patterns=[
        ".git/*",
        ".git",
        "__pycache__/*",
        "*.pyc",
        "*.db",
        "uploads/*",
        ".env",
        ".DS_Store",
        "peft_adapter_v9/*",
        "peft_adapter_v9",
        "deploy_to_hf.py"
    ]
)
print("✅ Application files uploaded successfully!")

# Set secrets
print(f"\n[3/3] Configuring Space Secrets and Environment Variables ...")
try:
    api.add_space_secret(
        repo_id=SPACE_ID,
        key="GOOGLE_CLIENT_ID",
        value="628191051430-j7mimh3pfioi0u607cjl93is1b4malhl.apps.googleusercontent.com"
    )
    api.add_space_secret(
        repo_id=SPACE_ID,
        key="USE_HOSTED_MODEL",
        value="true"
    )
    api.add_space_secret(
        repo_id=SPACE_ID,
        key="HF_SPACE_ID",
        value="mohammedismailmi/v9-calibration-api"
    )
    print("✅ Secrets configured.")
except Exception as e:
    print(f"⚠️ Note setting secrets: {e}")

print("\n" + "=" * 60)
print(f"🎉 DEPLOYMENT COMPLETE!")
print(f"🌐 Space URL: https://huggingface.co/spaces/{SPACE_ID}")
print("=" * 60)
