"""
inject_creds.py — called by GitHub Actions
Prepends all credentials as env vars into kaggle/main_pipeline.py
Usage: python3 inject_creds.py <start> <end> <repo> <client_id> <client_secret> <refresh_token>
All values come from GitHub Secrets — nothing hardcoded here!
"""
import sys

start         = sys.argv[1] if len(sys.argv) > 1 else "0"
end           = sys.argv[2] if len(sys.argv) > 2 else "800"
repo          = sys.argv[3] if len(sys.argv) > 3 else ""
client_id     = sys.argv[4] if len(sys.argv) > 4 else ""
client_secret = sys.argv[5] if len(sys.argv) > 5 else ""
refresh_token = sys.argv[6] if len(sys.argv) > 6 else ""

inject_code = f'''import os
os.environ["START_INDEX"]          = "{start}"
os.environ["END_INDEX"]            = "{end}"
os.environ["GITHUB_REPO"]          = "{repo}"
os.environ["GOOGLE_CLIENT_ID"]     = "{client_id}"
os.environ["GOOGLE_CLIENT_SECRET"] = "{client_secret}"
os.environ["GOOGLE_REFRESH_TOKEN"] = "{refresh_token}"
'''

with open("kaggle/main_pipeline.py", "r") as f:
    original = f.read()

with open("kaggle/main_pipeline.py", "w") as f:
    f.write(inject_code + "\n" + original)

print(f"Credentials injected! Batch {start} -> {end}")
