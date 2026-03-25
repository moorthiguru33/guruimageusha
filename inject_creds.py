"""
inject_creds.py
Prepends environment credentials into the target pipeline .py file.
Called by GitHub Actions before pushing to Kaggle.
Usage: python inject_creds.py <start_index> <end_index> <repo1_name> [target_py_path]
"""
import sys, os

_START = "# <<<CREDS_START>>>\n"
_END   = "# <<<CREDS_END>>>\n"


def inject():
    start = sys.argv[1] if len(sys.argv) > 1 else "0"
    end   = sys.argv[2] if len(sys.argv) > 2 else "200"
    repo1 = sys.argv[3] if len(sys.argv) > 3 else ""
    path  = sys.argv[4] if len(sys.argv) > 4 else "kaggle/phase1_pipeline.py"

    pairs = [
        ("GOOGLE_CLIENT_ID",     os.environ.get("GOOGLE_CLIENT_ID", "")),
        ("GOOGLE_CLIENT_SECRET", os.environ.get("GOOGLE_CLIENT_SECRET", "")),
        ("GOOGLE_REFRESH_TOKEN", os.environ.get("GOOGLE_REFRESH_TOKEN", "")),
        ("GITHUB_TOKEN_REPO2",   os.environ.get("GITHUB_TOKEN_REPO2_VAL", "")),
        ("GITHUB_REPO2",         os.environ.get("GITHUB_REPO2_VAL", "")),
        ("GITHUB_REPO1",         repo1),
        ("GITHUB_TOKEN_REPO1",   os.environ.get("GITHUB_TOKEN_REPO1_VAL", "")),
        ("GOOGLE_SHEETS_ID",     os.environ.get("GOOGLE_SHEETS_ID", "")),
        ("DRIVE_ROOT_FOLDER_ID", os.environ.get("DRIVE_ROOT_FOLDER_ID", "")),
        ("START_INDEX",          start),
        ("END_INDEX",            end),
    ]

    # SEO-specific env vars (only added if present)
    for key in ["GROQ_API_KEY", "SEO_CATEGORY_FILTER", "SEO_LIMIT", "SEO_FORCE_REPROCESS"]:
        val = os.environ.get(key, "")
        if val:
            pairs.append((key, val))

    lines = [_START, "import os\n"]
    for k, v in pairs:
        safe = str(v).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'os.environ["{k}"] = "{safe}"\n')
    lines.append(_END)
    block = "".join(lines)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if _START in content:
        i1 = content.index(_START)
        i2 = content.index(_END) + len(_END)
        content = content[i2:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(block + content)

    print(f"Credentials injected into {path} | batch {start} → {end}")


inject()
