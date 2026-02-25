# -*- coding: utf-8 -*-
"""Entry point for PyInstaller packaging of the Streamlit UI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    ui_app = root_dir / "ui" / "industry_app.py"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root_dir / "src")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ui_app),
        "--server.address=127.0.0.1",
        "--server.port=8501",
    ]
    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    main()
