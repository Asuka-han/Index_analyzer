# -*- coding: utf-8 -*-
"""Run industry analyzer and save outputs."""

from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyzers.industry_analyzer import IndustryAnalyzer


def main() -> None:
    output_dir = Path("result") / "industry"
    analyzer = IndustryAnalyzer()
    analyzer.analyze_both_industries(output_dir=output_dir)


if __name__ == "__main__":
    main()
