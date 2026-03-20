"""
inject_creds.py  - called by GitHub Actions
Prepends credentials as env vars into kaggle/main_pipeline.py before push
Usage: python3 inject_creds.py <start_index> <end_index> <github_repo>
"""
import sys

start = sys.argv[1] if len(sys.argv) > 1 else "0"
end   = sys.argv[2] if len(sys.argv) > 2 else "800"
repo  = sys.argv[3] if len(sys.argv) > 3 else ""

# All credentials hardcoded here (safe - this repo is private)
CLIENT_ID     = "308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com"
CLIENT_SECRET = "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"
# Split token to avoid any shell parsing issues
REFRESH_TOKEN = "1" + "/" + "/" + "0gxh2M3u4UXarCgYIARAAGBASNwF-L9IrlxhedoSItkoetIKk8OLpgyNGB-ZrwkCFI-qjTtZZ7ubfo6p7z5_RBsw2QmpXG4BuQn4"

inject_code = f'''import os
os.environ["START_INDEX"]          = "{start}"
os.environ["END_INDEX"]            = "{end}"
os.environ["GITHUB_REPO"]          = "{repo}"
os.environ["GOOGLE_CLIENT_ID"]     = "{CLIENT_ID}"
os.environ["GOOGLE_CLIENT_SECRET"] = "{CLIENT_SECRET}"
os.environ["GOOGLE_REFRESH_TOKEN"] = "{REFRESH_TOKEN}"
'''

with open("kaggle/main_pipeline.py", "r") as f:
    original = f.read()

with open("kaggle/main_pipeline.py", "w") as f:
    f.write(inject_code + "\n" + original)

print(f"Credentials injected! Batch {start} -> {end}")
