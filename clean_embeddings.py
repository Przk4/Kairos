#!/usr/bin/env python
"""Clean embeddings directory"""
import os
import shutil
from pathlib import Path

embeddings_dir = Path('.embeddings')
if embeddings_dir.exists():
    for file in embeddings_dir.glob('*.json'):
        file.unlink()
        print(f"Deleted: {file.name}")
    print(f"✅ Embeddings directory cleaned")
else:
    print("Directory doesn't exist yet")
