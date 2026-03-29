"""
build_lora_notebook.py
Converts kaggle/logo_lora_pipeline.py into a single-cell notebook.
Called by trigger_logo_lora.yml before inject_lora_creds.py.
"""
import json, pathlib, sys

py_path = pathlib.Path("kaggle/logo_lora_pipeline.py")
nb_path = pathlib.Path("kaggle/logo_lora_pipeline.ipynb")

if not py_path.exists():
    print(f"ERROR: {py_path} not found!")
    sys.exit(1)

py_src = py_path.read_text(encoding="utf-8")

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.10.0"
        }
    },
    "cells": [
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {"trusted": True},
            "outputs": [],
            "source": py_src
        }
    ]
}

nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Built {nb_path}  ({nb_path.stat().st_size:,} bytes, 1 code cell)")
