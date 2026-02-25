# -*- coding: utf-8 -*-
"""Run advanced industry analytics tasks."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import logging

from analyzers.industry_advanced import IndustryAdvancedAnalyzer


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    analyzer = IndustryAdvancedAnalyzer(
        output_dir=Path("result") / "industry_advanced"
    )
    analyzer.run_all()
    print("Advanced industry analysis completed.")


if __name__ == "__main__":
    main()
