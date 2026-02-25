# -*- coding: utf-8 -*-
"""
Created on Sun Aug 10 12:30:23 2025

信用指标分析
@author: 刘雨晗
"""
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


class CreditAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.cfg = ConfigLoader()
        self.logger = logging.getLogger("CreditAnalyzer")
        self.category = "信用指标"  # 配置文件中对应的指标分类
        self.target_indicator = "M0043418"  # 中长期贷款余额指标ID

    def analyze(self):
        """分析信用指标并生成信号"""
        try:
            # 从处理好的数据加载信用指标
            df = self.dm.load_combined_processed(self.category)

            # 提取中长期贷款余额数据
            if self.target_indicator not in df.columns:
                self.logger.error(
                    f"目标指标 {self.target_indicator} 不存在于数据中"
                )
                return pd.DataFrame()

            loan_data = df[[self.target_indicator]]

            # 计算信号
            signals = self._calculate_signals(loan_data)

            # 可视化结果
            self._visualize(signals)

            return {"signal": signals}

        except Exception as e:
            self.logger.error(f"信用指标分析失败: {str(e)}")
            return {"signal": pd.DataFrame()}

    def _calculate_signals(self, loan_data):
        """
        计算信用指标信号
        返回包含原始数据、中间变量和信号的DataFrame
        """
        # 复制原始数据避免污染输入
        df = loan_data.copy()

        # 确保时间索引并排序
        df = df.asfreq("ME").sort_index()

        # 重命名列以便清晰
        df = df.rename(columns={self.target_indicator: "loan_balance"})

        # 计算同比变化率
        df["yoy"] = (
            df["loan_balance"] / df["loan_balance"].shift(12) - 1
        ) * 100

        # 计算近3个月同比均值
        df["yoy_3m_avg"] = df["yoy"].rolling(window=3, min_periods=1).mean()

        # 生成信号指标
        df["final_signal"] = np.select(
            [
                df["yoy"] > df["yoy_3m_avg"],  # 当期同比 > 近3个月均值
                df["yoy"] < df["yoy_3m_avg"],  # 当期同比 < 近3个月均值
            ],
            [1, -1],  # 正向信号  # 负向信号
            default=0,  # 相等情况
        )

        return df

    def _visualize(self, signals_df, fig_name="中长期贷款余额分析"):
        """可视化信用指标信号"""
        fig, ax = plt.subplots(figsize=(12, 8))

        # 绘制同比变化率和3个月均值
        ax.plot(
            signals_df.index,
            signals_df["yoy"],
            label="同比变化率(%)",
            marker="o",
            linestyle="-",
            color="blue",
        )
        ax.plot(
            signals_df.index,
            signals_df["yoy_3m_avg"],
            label="3个月均值",
            linestyle="--",
            color="green",
        )

        # 添加信号点
        positive_signals = signals_df[signals_df["final_signal"] == 1]
        negative_signals = signals_df[signals_df["final_signal"] == -1]

        ax.scatter(
            positive_signals.index,
            positive_signals["yoy"] * 1.05,
            color="green",
            s=100,
            marker="^",
            label="正向信号",
        )
        ax.scatter(
            negative_signals.index,
            negative_signals["yoy"] * 0.95,
            color="red",
            s=100,
            marker="v",
            label="负向信号",
        )

        # 添加零线和网格
        ax.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
        ax.grid(True)

        # 设置标题和标签
        ax.set_title(fig_name)
        ax.set_ylabel("百分比(%)")
        ax.legend(loc="best")

        # 优化日期显示
        fig.autofmt_xdate()

        plt.tight_layout()
        plt.show()
        return fig


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    analyzer = CreditAnalyzer()
    signals_df = analyzer.analyze().get("signal")

    # 保存结果
    if not signals_df.empty:
        signals_df.to_excel("信用指标分析结果.xlsx")
        print("分析结果已保存至: 信用指标分析结果.xlsx")
