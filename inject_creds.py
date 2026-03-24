"""
inject_creds.py — Injects credentials as first cell into any pipeline notebook.
Usage:
  python3 inject_creds.py <start> <end> <repo1> <notebook_path>
"""
import sys, os, json

start    = sys.argv[1] if len(sys.argv) > 1 else "0"
end      = sys.argv[2] if len(sys.argv) > 2 else "200"
repo1    = sys.argv[3] if len(sys.argv) > 3 else ""
nb_path  = sys.argv[4] if len(sys.argv) > 4 else "kaggle/pipeline_generate.ipynb"

client_id       = os.environ.get("GOOGLE_CLIENT_ID", "")
client_secret   = os.environ.get("GOOGLE_CLIENT_SECRET", "")
refresh_token   = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
github_token_r2 = os.environ.get("GITHUB_TOKEN_REPO2_VAL", "")
github_repo2    = os.environ.get("GITHUB_REPO2_VAL", "")
github_token_r1 = os.environ.get("GITHUB_TOKEN_REPO1_VAL", "")

# SEO run options (only used by pipeline_seo.py, harmless in pipeline_generate.py)
seo_category    = os.environ.get("SEO_CATEGORY_FILTER", "")
seo_limit       = os.environ.get("SEO_LIMIT", "")
seo_force       = os.environ.get("SEO_FORCE_REPROCESS", "false")

CREDS_MARKER = "# __ULTRAPNG_CREDENTIALS_CELL__"

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
os.environ["SEO_CATEGORY_FILTER"]  = "{seo_category}"
os.environ["SEO_LIMIT"]            = "{seo_limit}"
os.environ["SEO_FORCE_REPROCESS"]  = "{seo_force}"
print("Credentials loaded. Batch: {start} -> {end}")
print(f"  REPO2: {github_repo2 or '(not set)'}")
print(f"  Google: {{'OK' if client_id else '(not set)'}}")
print(f"  SEO options: category={seo_category or 'ALL'}, limit={seo_limit or 'ALL'}, force={seo_force}")
'''

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

def cell_source(c):
    src = c.get("source", "")
    return "".join(src) if isinstance(src, list) else src

# Remove old creds cell if present
cells = [c for c in nb.get("cells", []) if CREDS_MARKER not in cell_source(c)]

creds_cell = {
    "cell_type": "code",
    "id": "creds-cell-000",
    "execution_count": None,
    "metadata": {"trusted": True},
    "outputs": [],
    "source": inject_code
}
cells.insert(0, creds_cell)
nb["cells"] = cells

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Credentials injected into {nb_path}")
print(f"Total cells: {len(cells)} | Batch: {start} -> {end}")
