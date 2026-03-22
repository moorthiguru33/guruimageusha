"""
inject_creds.py — called by GitHub Actions before Kaggle push
Secrets injected via ENV VARS (not sys.argv) for security.
"""
import sys, os

start  = sys.argv[1] if len(sys.argv) > 1 else "0"
end    = sys.argv[2] if len(sys.argv) > 2 else "200"
repo1  = sys.argv[3] if len(sys.argv) > 3 else ""

client_id       = os.environ.get("GOOGLE_CLIENT_ID", "")
client_secret   = os.environ.get("GOOGLE_CLIENT_SECRET", "")
refresh_token   = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
github_token_r2 = os.environ.get("GITHUB_TOKEN_REPO2_VAL", "")
github_repo2    = os.environ.get("GITHUB_REPO2_VAL", "")
github_token_r1 = os.environ.get("GITHUB_TOKEN_REPO1_VAL", "")
telegram_token  = os.environ.get("TELEGRAM_BOT_TOKEN_VAL", "")
telegram_chat   = os.environ.get("TELEGRAM_CHAT_ID_VAL", "")

inject_code = f'''import os
os.environ["START_INDEX"]             = "{start}"
os.environ["END_INDEX"]               = "{end}"
os.environ["GITHUB_REPO"]             = "{repo1}"
os.environ["GOOGLE_CLIENT_ID"]        = "{client_id}"
os.environ["GOOGLE_CLIENT_SECRET"]    = "{client_secret}"
os.environ["GOOGLE_REFRESH_TOKEN"]    = "{refresh_token}"
os.environ["GITHUB_TOKEN_REPO2"]      = "{github_token_r2}"
os.environ["GITHUB_REPO2"]            = "{github_repo2}"
os.environ["GITHUB_TOKEN_REPO1"]      = "{github_token_r1}"
os.environ["TELEGRAM_BOT_TOKEN"]      = "{telegram_token}"
os.environ["TELEGRAM_CHAT_ID"]        = "{telegram_chat}"
'''

with open("kaggle/main_pipeline.py", "r") as f:
    original = f.read()

with open("kaggle/main_pipeline.py", "w") as f:
    f.write(inject_code + "\n" + original)

print(f"Credentials injected! Batch {start} -> {end}")
