# -*- coding: utf-8 -*-
"""Generate sample Excel/SQLite data for industry analyzer."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


def _make_monthly_series(start: str, periods: int, base: float, step: float):
    index = pd.date_range(start=start, periods=periods, freq="MS")
    values = base + step * np.arange(periods)
    return pd.Series(values, index=index)


def _make_weekly_series(start: str, periods: int, base: float, step: float):
    index = pd.date_range(start=start, periods=periods, freq="W-SUN")
    values = base + step * np.arange(periods)
    return pd.Series(values, index=index)


def build_excel_samples(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)

    auto_path = raw_dir / "汽车行业指标.xlsx"
    auto_df = pd.DataFrame(
        {
            "date": _make_monthly_series("2024-01-01", 24, 12000, 180).index,
            "production": _make_monthly_series(
                "2024-01-01", 24, 12000, 180
            ).values,
        }
    )

    real_path = raw_dir / "房地产行业指标.xlsx"
    real_df = pd.DataFrame(
        {
            "date": _make_monthly_series("2024-01-01", 24, 5000, 60).index,
            "investment": _make_monthly_series(
                "2024-01-01", 24, 5000, 60
            ).values,
        }
    )

    with pd.ExcelWriter(auto_path) as writer:
        auto_df.to_excel(writer, sheet_name="汽车产量", index=False)

    with pd.ExcelWriter(real_path) as writer:
        real_df.to_excel(writer, sheet_name="房地产投资", index=False)


def build_sqlite_samples(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)

    auto_db = raw_dir / "汽车行业数据.db"
    auto_weekly = pd.DataFrame(
        {
            "date": _make_weekly_series("2024-01-07", 80, 70, 0.3).index,
            "operating_rate": _make_weekly_series(
                "2024-01-07", 80, 70, 0.3
            ).values,
        }
    )

    real_db = raw_dir / "房地产数据.db"
    real_sales = pd.DataFrame(
        {
            "date": _make_monthly_series("2024-01-01", 24, 9000, 120).index,
            "sales_area": _make_monthly_series(
                "2024-01-01", 24, 9000, 120
            ).values,
        }
    )
    land_tx = pd.DataFrame(
        {
            "date": _make_monthly_series("2024-01-01", 24, 3000, 50).index,
            "area": _make_monthly_series(
                "2024-01-01", 24, 3000, 50
            ).values,
        }
    )

    with sqlite3.connect(auto_db) as conn:
        auto_weekly.to_sql(
            "tire_operating_rate", conn, index=False, if_exists="replace"
        )

    with sqlite3.connect(real_db) as conn:
        real_sales.to_sql(
            "real_estate_sales", conn, index=False, if_exists="replace"
        )
        land_tx.to_sql(
            "land_transaction", conn, index=False, if_exists="replace"
        )


def main() -> None:
    raw_dir = Path("data") / "raw"
    build_excel_samples(raw_dir)
    build_sqlite_samples(raw_dir)
    print("Sample data generated under data/raw")


if __name__ == "__main__":
    main()
