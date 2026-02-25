# -*- coding: utf-8 -*-
"""
Created on Sat Aug 16 16:28:10 2025

@author: imado
"""

# capital_analyzer.py
import pandas as pd
import numpy as np
import logging
from core.data_manager import DataManager


class CapitalAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.logger = logging.getLogger("CapitalAnalyzer")

    def analyze(self):
        """分析资金指标并生成信号"""
        try:
            # 1. 加载资金指标数据
            capital_df = self.dm.load_combined_processed("资金指标")
            self.logger.info("✅ 资金指标数据加载成功")

            # 2. 预处理：转换为月度数据
            monthly_df = self._preprocess_to_monthly(capital_df)

            # 3. 计算三个指标信号
            signals_df = self._calculate_signals(monthly_df)

            # 4. 合成最终信号
            final_df = self._combine_signals(signals_df)

            return {"signal": final_df}

        except Exception as e:
            self.logger.error(f"分析过程中出错: {str(e)}")
            raise

    def _preprocess_to_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """将数据转换为月度频率（月末）"""
        # 确保索引是DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # 重采样到月末频率，使用前向填充确保数据完整
        monthly_df = df.resample("ME").last().ffill()

        self.logger.info(
            f"✅ 数据已转换为月度频率，新形状: {monthly_df.shape}"
        )
        return monthly_df

    def _calculate_signals(self, monthly_df: pd.DataFrame) -> pd.DataFrame:
        """计算三个指标信号"""
        signals_df = pd.DataFrame(index=monthly_df.index)

        # 1. M0096647信号：环比变化
        if "M0096647" in monthly_df:
            ratio = monthly_df["M0096647"] / monthly_df["M0096647"].shift(1)
            signals_df["M0096647_signal"] = np.where(ratio > 1, 1, -1)

        # 2. option_data信号：认沽/认购持仓量分位数
        if "option_data" in monthly_df:
            # 计算滚动12个月分位数
            rolling_median = (
                monthly_df["option_data"]
                .rolling(12, min_periods=1)
                .quantile(0.5)
            )
            signals_df["option_signal"] = np.where(
                monthly_df["option_data"] > rolling_median, 1, -1
            )

        # 3. new_fund_data信号：3个月均值比较
        if "new_fund_data" in monthly_df:
            rolling_mean = monthly_df["new_fund_data"].rolling(3).mean()
            signals_df["fund_signal"] = np.where(
                monthly_df["new_fund_data"] > rolling_mean, 1, -1
            )

        self.logger.info("✅ 各指标信号计算完成")
        return signals_df

    def _combine_signals(self, signals_df: pd.DataFrame) -> pd.DataFrame:
        """合成最终信号"""

        # 生成最终信号
        signals_df["final_signal"] = signals_df.sum(axis=1)
        signals_df["final_signal"] = np.where(
            signals_df["final_signal"] >= 0, 1, -1
        )

        self.logger.info("✅ 最终信号合成完成")
        return signals_df


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 执行分析
    try:
        analyzer = CapitalAnalyzer()
        signals_df = analyzer.analyze().get("signal")
        print("\n📊 最终信号结果:")
        print(signals_df.tail(12))  # 显示最近12个月的结果
        # 保存结果
        if not signals_df.empty:
            signals_df.to_excel("资金面信号分析结果.xlsx")
            print("分析结果已保存至: 资金面信号分析结果.xlsx")
    except Exception as e:
        print(f"分析失败: {str(e)}")
