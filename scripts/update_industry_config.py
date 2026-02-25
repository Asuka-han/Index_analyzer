# -*- coding: utf-8 -*-
"""Add industry indicator configs to the Excel config file."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def main() -> None:
    file_path = Path("高频宏观数据指标库.xlsx")
    sel = pd.read_excel(file_path, sheet_name="选定指标")
    adv = pd.read_excel(file_path, sheet_name="高级配置")

    new_rows = [
        {
            "指标名称": "乘用车零售销量",
            "频率": "月度",
            "单位": "万辆",
            "指标ID": "AUTO_SALES_W",
            "来源": "AKShare",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "AKShare",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "",
            "api_params": json.dumps(
                {
                    "func": "car_market_total_cpca",
                    "kwargs": {"symbol": "狭义乘用车", "indicator": "零售"},
                },
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "汽车产量月度数据",
            "频率": "月度",
            "单位": "辆",
            "指标ID": "AUTO_PRODUCTION_M",
            "来源": "Excel",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "EXCEL",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "data/raw/汽车行业指标.xlsx",
            "api_params": json.dumps(
                {"sheet_name": "汽车产量", "date_col": "date", "value_col": "production"},
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "轮胎开工率",
            "频率": "周度",
            "单位": "%",
            "指标ID": "TIRE_OPERATING_RATE",
            "来源": "SQLite",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "SQLITE",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "data/raw/汽车行业数据.db",
            "api_params": json.dumps(
                {"table_name": "tire_operating_rate", "date_col": "date", "value_col": "operating_rate"},
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "钢铁价格指数",
            "频率": "日度",
            "单位": "指数",
            "指标ID": "STEEL_PRICE_INDEX",
            "来源": "AKShare",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "AKShare",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "",
            "api_params": json.dumps(
                {"func": "macro_china_commodity_price_index", "value_col": "最新值"},
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "商品房销售面积",
            "频率": "月度",
            "单位": "万平方米",
            "指标ID": "REAL_ESTATE_SALES",
            "来源": "SQLite",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "SQLITE",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "data/raw/房地产数据.db",
            "api_params": json.dumps(
                {"table_name": "real_estate_sales", "date_col": "date", "value_col": "sales_area"},
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "房地产开发投资完成额",
            "频率": "月度",
            "单位": "亿元",
            "指标ID": "REAL_ESTATE_INVESTMENT",
            "来源": "Excel",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "EXCEL",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "data/raw/房地产行业指标.xlsx",
            "api_params": json.dumps(
                {"sheet_name": "房地产投资", "date_col": "date", "value_col": "investment"},
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "百城住宅价格指数",
            "频率": "月度",
            "单位": "指数",
            "指标ID": "HOUSE_PRICE_INDEX",
            "来源": "AKShare",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "AKShare",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "",
            "api_params": json.dumps(
                {
                    "func": "macro_china_new_house_price",
                    "kwargs": {"city_first": "北京", "city_second": "上海"},
                    "value_col": "新建商品住宅价格指数-同比",
                },
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
        {
            "指标名称": "土地成交面积",
            "频率": "月度",
            "单位": "万平方米",
            "指标ID": "LAND_TRANSACTION_AREA",
            "来源": "SQLite",
            "降频方法": "last",
            "指标分类": "行业指标",
            "数据来源类型": "SQLITE",
            "存储方式": "Individual",
            "数据更新时间": "",
            "数据状态": "启用",
            "表名": "data/raw/房地产数据.db",
            "api_params": json.dumps(
                {"table_name": "land_transaction", "date_col": "date", "value_col": "area"},
                ensure_ascii=False,
            ),
            "索引列名": "",
        },
    ]

    new_ids = [row["指标ID"] for row in new_rows]
    sel = sel[~sel["指标ID"].isin(new_ids)]
    sel = pd.concat([sel, pd.DataFrame(new_rows)], ignore_index=True)

    adv_rows = [
        {
            "指标名称": row["指标名称"],
            "指标ID": row["指标ID"],
            "异常值处理": "",
            "单位转换系数": 1.0,
        }
        for row in new_rows
    ]
    adv = adv[~adv["指标ID"].isin(new_ids)]
    adv = pd.concat([adv, pd.DataFrame(adv_rows)], ignore_index=True)

    with pd.ExcelWriter(
        file_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
    ) as writer:
        sel.to_excel(writer, sheet_name="选定指标", index=False)
        adv.to_excel(writer, sheet_name="高级配置", index=False)

    print("Config updated with industry indicators.")


if __name__ == "__main__":
    main()
