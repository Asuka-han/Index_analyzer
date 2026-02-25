import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from core.config_loader import ConfigLoader
from core.data_connector import DataConnector

print("=" * 60)
print("Data source diagnostic")
print("=" * 60)

config = ConfigLoader()
connector = DataConnector(config_loader=config)

indicators = [
    "AUTO_SALES_W",
    "AUTO_PRODUCTION_M",
    "TIRE_OPERATING_RATE",
    "REAL_ESTATE_SALES",
    "REAL_ESTATE_INVESTMENT",
    "LAND_TRANSACTION_AREA",
]

for ind in indicators:
    print("\n---", ind, "---")
    info = config.get_config(ind)
    print("config:", info)

    try:
        df = connector.fetch_data_by_id(
            ind, start_date="2022-01-01", end_date="2023-01-01"
        )
    except Exception as exc:
        print("fetch error:", exc)
        continue

    print("rows:", len(df))
    if df is None or df.empty:
        print("no data")
        continue

    col = ind if ind in df.columns else df.columns[0]
    print("date range:", df.index.min(), "->", df.index.max())
    print("latest value:", float(df[col].iloc[-1]))

print("\n" + "=" * 60)
print("Done")
print("=" * 60)
