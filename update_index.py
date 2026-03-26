"""
update_index.py — Auto-rebuild prompts/splits/index.json

Run this script any time you:
  ✅ Add a new JSON file to prompts/splits/
  ✅ Delete a JSON file from prompts/splits/
  ✅ Add or remove prompts inside any splits JSON file

Usage:
    python update_index.py

It will scan all *.json files in prompts/splits/ (except index.json itself),
count total prompts, and rewrite index.json automatically.
"""

import json
from pathlib import Path


SPLITS_DIR = Path(__file__).parent / "prompts" / "splits"


def rebuild_index(splits_dir: Path = SPLITS_DIR) -> None:
    if not splits_dir.exists():
        print(f"[ERROR] splits dir not found: {splits_dir}")
        return

    # Collect all JSON files except index.json
    json_files = sorted(
        f for f in splits_dir.glob("*.json")
        if f.name != "index.json"
    )

    if not json_files:
        print("[WARN] No JSON files found in splits/ — index.json not updated.")
        return

    categories = []
    files      = []
    total      = 0
    errors     = []

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                errors.append(f"  ⚠  {jf.name} — not a JSON array, skipped")
                continue

            count = len(data)
            total += count

            # Category name = filename without .json
            cat = jf.stem
            categories.append(cat)
            files.append(jf.name)

            print(f"  ✓  {jf.name:<40}  {count:>5} prompts")

        except json.JSONDecodeError as e:
            errors.append(f"  ✗  {jf.name} — JSON parse error: {e}")

    # Write new index.json
    index = {
        "total":      total,
        "categories": categories,
        "files":      files,
    }
    index_path = splits_dir / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    if errors:
        for e in errors:
            print(e)
        print()

    print(f"✅ index.json rebuilt successfully!")
    print(f"   Categories : {len(categories)}")
    print(f"   Total prompts: {total}")
    print(f"   Saved → {index_path}")


if __name__ == "__main__":
    print("=" * 56)
    print("  UltraPNG — index.json Auto-Rebuilder")
    print("=" * 56)
    rebuild_index()
