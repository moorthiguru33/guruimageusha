"""
inject_creds.py — Injects secrets into main_pipeline.ipynb first cell
Secrets via ENV VARS only (never sys.argv) for security.
"""
import sys, os, json

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

# ── Inject into .ipynb (prepend credentials as first cell) ──
nb_path = "kaggle/main_pipeline.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

creds_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {"trusted": True},
    "outputs": [],
    "source": inject_code
}

# Remove any existing creds cell (starts with 'import os\nos.environ["START_INDEX"]')
cells = nb.get("cells", [])
cells = [c for c in cells
         if not (c.get("cell_type") == "code"
                 and "START_INDEX" in "".join(c.get("source", []) if isinstance(c.get("source"), list) else [c.get("source", "")]))]

# Insert creds cell at position 0
cells.insert(0, creds_cell)
nb["cells"] = cells

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Credentials injected into {nb_path}")
print(f"Batch: {start} -> {end} | Repo: {repo1}")
