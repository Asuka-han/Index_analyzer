# -*- coding: utf-8 -*-
"""期权数据预处理。"""
import logging
import pandas as pd


logger = logging.getLogger(__name__)


def preprocess_option_data(df: pd.DataFrame) -> pd.DataFrame:
    """预处理期权数据：计算每日PCR(认沽/认购持仓比)。"""
    try:
        date_col = "date"
        if date_col in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                df = df.dropna(subset=[date_col])
            df = df.set_index(date_col, drop=True)
        elif df.index.name != date_col:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, errors="coerce")
                df = df[df.index.notna()]

        daily_pcr = (
            df.groupby(df.index)
            .agg(
                put_sum=("daily_put_position", "sum"),
                call_sum=("daily_call_position", "sum"),
            )
            .assign(PCR=lambda x: x["put_sum"] / x["call_sum"])
        )

        return daily_pcr["PCR"].to_frame("option_data")
    except Exception as e:
        logger.exception(f"期权数据预处理失败: {str(e)}")
        return pd.DataFrame()
