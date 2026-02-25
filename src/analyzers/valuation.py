# -*- coding: utf-8 -*-
"""
优化版估值分析脚本：按月频率处理数据
"""
import pandas as pd
import numpy as np
import logging
from core.data_manager import DataManager
import traceback


class ValuationAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.logger = logging.getLogger("ValuationAnalyzer")

    def analyze(self):
        """分析估值指标并生成月度信号"""
        try:
            # 1. 加载估值指标数据
            valuation_df = self.dm.load_combined_processed("估值指标")
            self.logger.info("✅ 估值指标数据加载成功")

            # 2. 计算股权风险溢价(ERP)
            erp_df = self._calculate_erp(valuation_df)

            # 3. 转换为月度数据
            monthly_df = self._resample_to_monthly(erp_df)

            # 4. 计算滚动分位数信号
            signals_df = self._calculate_monthly_signals(monthly_df)

            return {"signal": signals_df}

        except Exception as e:
            self.logger.error(f"分析过程中出错: {str(e)}")
            raise

    def _calculate_erp(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算股权风险溢价(ERP)"""
        # 确保所需列存在
        required_cols = ["div_yield", "M1001654"]  # M1001654为10年期国债收益率
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            raise ValueError(f"缺失必要列: {missing}")

        # 计算ERP = 股息率 - 国债收益率
        erp_df = pd.DataFrame(index=df.index)
        erp_df["ERP"] = df["div_yield"] - df["M1001654"]

        # 处理缺失值
        erp_df = erp_df.ffill().bfill()

        self.logger.info(
            f"✅ ERP计算完成，数据范围: {erp_df.index.min()} 至 {erp_df.index.max()}"
        )
        return erp_df

    def _resample_to_monthly(self, erp_df: pd.DataFrame) -> pd.DataFrame:
        """将日频ERP数据转换为月频数据（月末为索引）"""
        # 确保索引是DatetimeIndex
        if not isinstance(erp_df.index, pd.DatetimeIndex):
            erp_df.index = pd.to_datetime(erp_df.index)

        # 按月重采样（取月平均值），索引设为月末日期 [1,3](@ref)
        monthly_df = erp_df.resample("ME").mean()
        monthly_df.index = monthly_df.index.to_period("M").to_timestamp("M")

        self.logger.info(f"✅ 已转换为月度数据，记录数: {len(monthly_df)}")
        return monthly_df

    def _calculate_monthly_signals(
        self, monthly_df: pd.DataFrame
    ) -> pd.DataFrame:
        """按月计算滚动分位数信号"""
        signals_df = monthly_df.copy()

        # 1. 计算滚动42个月均值 [3](@ref)
        signals_df["Rolling_Mean"] = (
            signals_df["ERP"].rolling(window=42, min_periods=12).mean()
        )

        # 2. 计算分位数（使用高效向量化操作替代apply）[7](@ref)
        def calculate_percentile(series):
            """计算当月均值在滚动窗口内的分位数"""
            if len(series) < 12:  # 至少12个月数据
                return np.nan
            current = series[-1]
            return (series <= current).mean()  # 小于等于当前值的比例

        # 计算滚动分位数
        signals_df["Percentile"] = (
            signals_df["ERP"]
            .rolling(window=42, min_periods=12)
            .apply(calculate_percentile, raw=True)
        )

        # 3. 生成信号
        signals_df["final_signal"] = np.where(
            signals_df["Percentile"] > 0.7, 1, -1
        )

        # 标记数据不足的时期
        signals_df.loc[signals_df["Rolling_Mean"].isna(), "final_signal"] = (
            np.nan
        )

        self.logger.info("✅ 月度估值信号计算完成")
        return signals_df


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 执行分析
    try:
        analyzer = ValuationAnalyzer()
        result_df = analyzer.analyze().get("signal")

        # 输出结果
        print("\n📊📊 月度估值分析结果:")
        print(result_df.tail(24))  # 显示最近2年的结果

        # 保存结果
        result_df.to_excel("估值面信号分析结果.xlsx")
        print("✅ 分析结果已保存")

    except Exception as e:
        print(f"分析失败: {str(e)}")
        # 打印详细错误信息
        print(traceback.format_exc())
