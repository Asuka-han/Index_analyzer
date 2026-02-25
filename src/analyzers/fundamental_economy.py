# -*- coding: utf-8 -*-
"""
Created on Thu Aug  7 16:28:17 2025

@author: imado
"""

# economy.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from core.data_manager import DataManager
from core.config_loader import ConfigLoader
import logging

# 设置全局字体（支持Windows/macOS/Linux）
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
    "STHeiti",
]  # 常用中文字体
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


class EconomyAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.cfg = ConfigLoader()
        self.logger = logging.getLogger("EconomyAnalyzer")

    def analyze(self):
        """分析经济指标并生成信号"""

        # 从处理好的数据加载经济指标
        df = self.dm.load_combined_processed("经济指标")

        # 计算扩散指数和信号（示例逻辑）
        [period_df, direction_df] = self._calculate_signals(df)

        # 可视化结果
        self._visualize(period_df)

        return {"period_df": period_df, "signal": direction_df}

    # %%功能函数
    # 计算经济景气指数函数
    def _calculate_signals(self, df, period="ME", base_date="2012-01-31"):
        """
        改进版经济指数计算函数，输出中间变量并处理缺失值
        返回包含原始数据、中间变量和三个指数的DataFrame
        """
        # 复制原始数据避免污染输入
        df = df.copy()

        # 确保时间索引并排序
        df = df.asfreq("D").sort_index()  # 先转换为日频处理缺失值

        # 缺失值处理（线性插值+前向填充）
        df = df.interpolate(method="time").ffill().bfill()

        # 获取数据降频字典
        loader = self.cfg
        econ_freq_methods = loader.get_para_by_category("经济指标", "freq_method")

        # 重采样到指定周期
        period_df = df.resample(period).agg(econ_freq_methods)

        # ========== 中间变量计算 ==========
        # 计算各指标环比变化方向
        direction_df = period_df.apply(lambda x: np.sign(x.diff()))
        direction_df = direction_df.add_suffix("_Direction")
        direction_df["final_signal"] = np.where(
            direction_df.sum(axis=1) > 0, 1, -1
        )

        # 计算扩散指数A
        period_df["Diffusion_Index_A"] = direction_df.mean(axis=1)

        # 计算周期度变化（中间变量）
        period_df["Period_Change"] = period_df["Diffusion_Index_A"]

        # ========== 定基指数B ==========
        base_value = 100
        # 统一转换为datetime格式以确保兼容性
        base_date_dt = pd.to_datetime(base_date)
        if not isinstance(period_df.index, pd.DatetimeIndex):
            period_df.index = pd.to_datetime(period_df.index)

        # 自动选择最早日期作为基准（若base_date不存在）
        if base_date_dt not in period_df.index:  # [6,8](@ref)
            base_date_dt = period_df.index.min()  # 取最早日期
            print(
                f"警告：基准日{base_date}不存在，"
                f"已自动替换为最早日期{base_date_dt.strftime('%Y-%m-%d')}"
            )

        # 确保索引排序（避免后续操作错误）
        period_df = period_df.sort_index()

        # 计算基准指数（带日期兼容性处理）
        period_df["Base_Index_B"] = (
            base_value + period_df["Diffusion_Index_A"].cumsum()
        )

        # 处理缺失值
        period_df["Base_Index_B"] = (
            period_df["Base_Index_B"].ffill().interpolate(method="time")
        )

        # ========== 同比指数C ==========
        # 使用向量化操作替代循环，避免KeyError
        # 计算同比变化率（使用shift(12)确保日历对齐）
        period_df["YoY_Index_C"] = (
            period_df["Base_Index_B"] / period_df["Base_Index_B"].shift(12) - 1
        ) * 100  # 转换为百分比形式

        # 处理前12个月没有同比数据的情况
        period_df["YoY_Index_C"] = period_df["YoY_Index_C"].ffill().bfill()

        return period_df, direction_df

    # %%
    def _visualize(
        self, result_df, base_date="2012-01-31", fig_name="经济指标"
    ):
        """可视化经济指标信号"""
        """绘制包含三个子图的扩散指数图表（兼容原函数名）"""
        result_df = result_df[
            ["Diffusion_Index_A", "Base_Index_B", "YoY_Index_C"]
        ]
        if not isinstance(base_date, pd.Timestamp):
            base_date = pd.to_datetime(base_date)

        # 创建图形并添加整体标题
        fig = plt.figure(figsize=(12, 10))  # 增加高度以容纳标题
        fig.suptitle(
            fig_name,  # 整体标题文本
            fontsize=16,  # 标题字体大小
            fontweight="bold",  # 加粗
            y=0.98,
        )  # 垂直位置（0-1之间）

        # 子图1：高频扩散指数A
        ax1 = plt.subplot(3, 1, 1)
        ax1.plot(result_df.index, result_df["Diffusion_Index_A"], color="blue")
        ax1.axhline(0, color="red", linestyle="--", linewidth=0.8)
        ax1.axvline(
            base_date, color="#007500", linestyle=":", linewidth=1.2, alpha=0.7
        )
        ax1.set_title("经济扩散指数A", pad=15)
        ax1.set_ylabel("Index Value")
        ax1.set_ylim(-1, 1)
        ax1.grid(True)
        ax1.legend(["Index", "Zero Line", "Base Date"], loc="upper right")

        # 子图2：基准指数B
        ax2 = plt.subplot(3, 1, 2, sharex=ax1)
        ax2.plot(result_df.index, result_df["Base_Index_B"], color="green")
        ax2.axvline(
            base_date, color="#007500", linestyle=":", linewidth=1.2, alpha=0.7
        )
        ax2.set_title("基准指数B", pad=15)
        ax2.set_ylabel("Index Value")
        ax2.grid(True)

        # 子图3：综合指数C
        ax3 = plt.subplot(3, 1, 3, sharex=ax1)
        ax3.plot(result_df.index, result_df["YoY_Index_C"], color="purple")
        ax3.axvline(
            base_date, color="#007500", linestyle=":", linewidth=1.2, alpha=0.7
        )
        ax3.set_title("同比指数C", pad=15)
        ax3.set_ylabel("Index Value")
        ax3.grid(True)

        # 统一调整布局
        plt.tight_layout(rect=[0, 0, 1, 0.96])  # 为标题预留顶部空间
        plt.gcf().autofmt_xdate()
        plt.subplots_adjust(hspace=0.3, top=0.9)  # 调整顶部间距
        plt.show()
        return fig


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    analyzer = EconomyAnalyzer()
    result = analyzer.analyze()
    period_df = result.get("period_df")
    direction_df = result.get("signal")

    # 可选：保存结果到Excel
    if not period_df.empty:
        with pd.ExcelWriter("经济指数分析结果.xlsx") as writer:
            period_df.to_excel(writer, sheet_name="指数结果")
            direction_df.to_excel(writer, sheet_name="周期景气度")
