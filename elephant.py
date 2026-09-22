#!/usr/bin/env python3
"""Entry point so `el` works from a clone without installation: python3 elephant.py …"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from elephant.main import main  # noqa: E402

main()
