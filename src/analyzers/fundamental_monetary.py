# -*- coding: utf-8 -*-
"""
Created on Sun Aug 10 00:08:35 2025

@author: imado
"""
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from core.data_manager import DataManager
from core.config_loader import ConfigLoader
import logging

# 设置全局字体（支持中文显示）
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
    "STHeiti",
]
plt.rcParams["axes.unicode_minus"] = False


class MonetaryAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.cfg = ConfigLoader()
        self.logger = logging.getLogger("MonetaryAnalyzer")
        self.category = "货币指标"  # 配置文件中对应的指标分类

    def analyze(self):
        """分析货币指标并生成信号"""
        try:
            # 从处理好的数据加载货币指标
            df = self.dm.load_combined_processed(self.category)

            # 计算扩散指数和信号
            period_df, direction_df = self._calculate_signals(df)

            # 可视化结果
            self._visualize(period_df)

            return {"period_df": period_df, "signal": direction_df}

        except Exception as e:
            self.logger.error(f"货币指标分析失败: {str(e)}")
            return {"period_df": pd.DataFrame(), "signal": pd.DataFrame()}

    def _calculate_signals(self, df, period="ME", base_date="2012-01-31"):
        """
        计算货币指数信号
        返回包含原始数据、中间变量和三个指数的DataFrame
        """
        # 复制原始数据避免污染输入
        df = df.copy()

        # 确保时间索引并排序
        df = df.asfreq("D").sort_index()

        # 缺失值处理（线性插值+前向填充）
        df = df.interpolate(method="time").ffill().bfill()

        # 重采样到指定周期
        period_df = df.resample(period).last()

        # ===== 中间变量计算 =====
        # 计算各指标环比变化方向，注意货币的最终方向和货币指数走势相反
        direction_df = period_df.apply(lambda x: np.sign(x.diff()))
        direction_df = direction_df.add_suffix("_Direction")
        direction_df["final_signal"] = np.where(
            direction_df.sum(axis=1) > 0, -1, 1
        )

        # 计算扩散指数A
        period_df["Diffusion_Index_A"] = direction_df.mean(axis=1)

        # 计算周期度变化（中间变量）
        period_df["Period_Change"] = period_df["Diffusion_Index_A"]

        # ===== 定基指数B =====
        base_value = 100
        base_date_dt = pd.to_datetime(base_date)

        # 自动选择最早日期作为基准（若base_date不存在）
        if base_date_dt not in period_df.index:
            base_date_dt = period_df.index.min()
            self.logger.warning(
                f"基准日不存在，已自动替换为最早日期: {base_date_dt.strftime('%Y-%m-%d')}"
            )

        period_df = period_df.sort_index()
        period_df["Base_Index_B"] = (
            base_value + period_df["Diffusion_Index_A"].cumsum()
        )

        # 处理缺失值
        period_df["Base_Index_B"] = (
            period_df["Base_Index_B"].ffill().interpolate(method="time")
        )

        # ===== 同比指数C =====
        period_df["YoY_Index_C"] = (
            period_df["Base_Index_B"] / period_df["Base_Index_B"].shift(12) - 1
        ) * 100

        # 处理前12个月没有同比数据的情况
        period_df["YoY_Index_C"] = period_df["YoY_Index_C"].ffill().bfill()

        return period_df, direction_df

    def _visualize(self, result_df, fig_name="货币指标信号"):
        """可视化货币指标信号"""
        result_df = result_df[
            ["Diffusion_Index_A", "Base_Index_B", "YoY_Index_C"]
        ]

        # 创建图形
        fig = plt.figure(figsize=(12, 10))
        fig.suptitle(fig_name, fontsize=16, fontweight="bold", y=0.98)

        # 子图1：高频扩散指数A
        ax1 = plt.subplot(3, 1, 1)
        ax1.plot(result_df.index, result_df["Diffusion_Index_A"], color="blue")
        ax1.axhline(0, color="red", linestyle="--", linewidth=0.8)
        ax1.set_title("货币扩散指数A", pad=15)
        ax1.set_ylabel("指数值")
        ax1.set_ylim(-1, 1)
        ax1.grid(True)
        ax1.legend(["指数", "零线"], loc="upper right")

        # 子图2：基准指数B
        ax2 = plt.subplot(3, 1, 2, sharex=ax1)
        ax2.plot(result_df.index, result_df["Base_Index_B"], color="green")
        ax2.set_title("基准指数B", pad=15)
        ax2.set_ylabel("指数值")
        ax2.grid(True)

        # 子图3：同比指数C
        ax3 = plt.subplot(3, 1, 3, sharex=ax1)
        ax3.plot(result_df.index, result_df["YoY_Index_C"], color="purple")
        ax3.set_title("同比指数C", pad=15)
        ax3.set_ylabel("同比变化 (%)")
        ax3.grid(True)

        # 调整布局
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.gcf().autofmt_xdate()
        plt.subplots_adjust(hspace=0.3, top=0.9)
        plt.show()
        return fig


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    analyzer = MonetaryAnalyzer()
    result = analyzer.analyze()
    period_df = result.get("period_df")
    direction_df = result.get("signal")

    # 可选：保存结果到Excel
    if not period_df.empty:
        with pd.ExcelWriter("货币指数分析结果.xlsx") as writer:
            period_df.to_excel(writer, sheet_name="指数结果")
            direction_df.to_excel(writer, sheet_name="周期景气度")
