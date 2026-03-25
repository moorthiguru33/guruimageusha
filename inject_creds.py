"""
inject_creds.py — Injects credentials as first cell into main_pipeline.ipynb
Reads ALL secrets from environment variables (set by GitHub Actions secrets).
"""
import sys, os, json

start  = sys.argv[1] if len(sys.argv) > 1 else "0"
end    = sys.argv[2] if len(sys.argv) > 2 else "200"
repo1  = sys.argv[3] if len(sys.argv) > 3 else ""

# All secrets from environment variables
client_id       = os.environ.get("GOOGLE_CLIENT_ID", "")
client_secret   = os.environ.get("GOOGLE_CLIENT_SECRET", "")
refresh_token   = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
github_token_r2 = os.environ.get("GITHUB_TOKEN_REPO2_VAL", "")
github_repo2    = os.environ.get("GITHUB_REPO2_VAL", "")
github_token_r1 = os.environ.get("GITHUB_TOKEN_REPO1_VAL", "")
telegram_token  = os.environ.get("TELEGRAM_BOT_TOKEN_VAL", "")
telegram_chat   = os.environ.get("TELEGRAM_CHAT_ID_VAL", "")

# Unique markers so we can identify THIS creds cell exactly
CREDS_MARKER = "# __ULTRAPNG_CREDENTIALS_CELL__"
CREDS_PY_MARKER = "# __ULTRAPNG_PY_CREDENTIALS_CELL__"
CREDS_PY_END_MARKER = "# __ULTRAPNG_PY_CREDENTIALS_END__"

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
print("Credentials loaded. Batch: {start} -> {end}")
print(f"  REPO2: {github_repo2 or '(not set)'}")
print(f"  Google: {'OK' if client_id else '(not set)'}")
'''

nb_path = "kaggle/main_pipeline.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

def cell_source(c):
    src = c.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return src

# Remove ONLY previous creds cells (identified by unique marker)
cells = [c for c in nb.get("cells", [])
         if CREDS_MARKER not in cell_source(c)]

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

# Also inject into main_pipeline.py (if Kaggle kernel runs python file)
py_path = "kaggle/main_pipeline.py"
try:
    with open(py_path, "r", encoding="utf-8") as f:
        py_src = f.read()
except Exception:
    py_src = ""

py_inject_code = f'''{CREDS_PY_MARKER}
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
print("PY credentials loaded. Batch: {start} -> {end}")
print(f"  REPO2: {github_repo2 or '(not set)'}")
print(f"  Google: {'OK' if client_id else '(not set)'}")
{CREDS_PY_END_MARKER}
'''

if CREDS_PY_MARKER in py_src:
    before = py_src.split(CREDS_PY_MARKER, 1)[0]
    tail = py_src.split(CREDS_PY_MARKER, 1)[1]
    if CREDS_PY_END_MARKER in tail:
        after = tail.split(CREDS_PY_END_MARKER, 1)[1]
        new_src = before + "\n" + py_inject_code + "\n" + after.lstrip("\n")
    else:
        # Fallback: if end marker missing, don't risk deleting code
        new_src = py_inject_code + "\n" + py_src
else:
    new_src = py_inject_code + "\n" + py_src

if new_src.strip():
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"Injected credentials into {py_path}")
