"""
inject_lora_creds.py — Injects credentials as first cell into logo_lora_pipeline.ipynb
Called by trigger_logo_lora.yml with args: start end repo1 category
"""
import sys, os, json

start    = sys.argv[1] if len(sys.argv) > 1 else "0"
end      = sys.argv[2] if len(sys.argv) > 2 else "200"
repo1    = sys.argv[3] if len(sys.argv) > 3 else ""
category = sys.argv[4] if len(sys.argv) > 4 else ""

# All secrets from environment variables (set by GitHub Actions)
client_id       = os.environ.get("GOOGLE_CLIENT_ID", "")
client_secret   = os.environ.get("GOOGLE_CLIENT_SECRET", "")
refresh_token   = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
github_token_r2 = os.environ.get("GITHUB_TOKEN_REPO2_VAL", "")
github_repo2    = os.environ.get("GITHUB_REPO2_VAL", "")
github_token_r1 = os.environ.get("GITHUB_TOKEN_REPO1_VAL", "")

# Unique marker to identify this creds cell
CREDS_MARKER = "# __ULTRAPNG_LORA_CREDENTIALS_CELL__"

inject_code = f'''{CREDS_MARKER}
import os
os.environ["START_INDEX"]          = "{start}"
os.environ["END_INDEX"]            = "{end}"
os.environ["GITHUB_REPO"]          = "{repo1}"
os.environ["GOOGLE_CLIENT_ID"]     = "{client_id}"
os.environ["GOOGLE_CLIENT_SECRET"] = "{client_secret}"
os.environ["GOOGLE_REFRESH_TOKEN"] = "{refresh_token}"
os.environ["GITHUB_TOKEN_REPO2"]   = "{github_token_r2}"
os.environ["GITHUB_REPO2"]         = "{github_repo2}"
os.environ["GITHUB_TOKEN_REPO1"]   = "{github_token_r1}"
os.environ["LOGO_LORA_CATEGORY"]   = "{category}"
print("Logo LoRA credentials loaded. Batch: {start} -> {end}")
print(f"  Category : {category or 'ALL'}")
print(f"  REPO2    : {github_repo2 or '(not set)'}")
print(f"  Google   : {'OK' if client_id else '(not set)'}")
'''

nb_path = "kaggle/logo_lora_pipeline.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

def cell_source(c):
    src = c.get("source", "")
    return "".join(src) if isinstance(src, list) else src

# Remove any previous creds cell
cells = [c for c in nb.get("cells", []) if CREDS_MARKER not in cell_source(c)]

creds_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {"trusted": True},
    "outputs": [],
    "source": inject_code
}
cells.insert(0, creds_cell)
nb["cells"] = cells

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Injected credentials into {nb_path}")
print(f"Total cells: {len(cells)}")
print(f"Batch: {start} -> {end}")
