# -*- coding: utf-8 -*-
"""新发基金数据预处理。"""
import logging
import pandas as pd


logger = logging.getLogger(__name__)


def preprocess_new_fund_data(df: pd.DataFrame) -> pd.DataFrame:
    """处理新发基金数据并返回月度时间序列。"""
    try:
        # 不修改原始结构，直接处理副本
        df = df.copy()

        # 日期列标准化处理（不设索引）
        if "fundfounddate" in df.columns:
            df["fundfounddate"] = pd.to_datetime(
                df["fundfounddate"], errors="coerce"
            )
            df = df[df["fundfounddate"].notna()]

        # 过滤股票型和混合型基金
        equity_mask = df["investmenttype"].str.contains("股票|混合", na=False)
        df_equity = df[equity_mask].copy()

        # 按月分组聚合（不依赖索引）
        df_equity["month"] = df_equity["fundfounddate"].dt.to_period("M")
        monthly_sum = (
            df_equity.groupby("month")["enddateshare"].sum().reset_index()
        )
        monthly_sum["month_end"] = monthly_sum["month"].dt.to_timestamp(
            how="end"
        )

        # 创建结果DataFrame并设置日期索引
        result = pd.DataFrame(
            data=monthly_sum["enddateshare"].values,
            index=pd.DatetimeIndex(monthly_sum["month_end"]),
            columns=["equity_fund_share"],
        )
        result.index.name = "date"
        result.index = (
            pd.DatetimeIndex(result.index).to_period("M").to_timestamp("M")
        )

        return result
    except Exception as e:
        logger.error(f"基金预处理失败: {str(e)}")
        return pd.DataFrame(columns=["equity_fund_share"])
