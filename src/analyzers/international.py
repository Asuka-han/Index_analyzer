# -*- coding: utf-8 -*-
"""
Created on Sun Aug 10 12:47:43 2025
重构后的国际面数据分析模块
功能：分析中美利差、汇率和QFII持仓，生成综合国际面信号
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


class InternationalAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.cfg = ConfigLoader()
        self.logger = logging.getLogger("InternationalAnalyzer")
        self.category = "国际指标"  # 配置文件中对应的指标分类
        self.column_mapping = {
            "M0325687": "CN_10yr_bond_return",
            "G0000891": "US_10yr_bond_return",
            "M0068008": "offshore_USD/CNY",
            "M5481318": "QFII_equity",
        }

    def analyze(self):
        """分析国际面指标并生成信号"""
        try:
            # 从处理好的数据加载国际指标
            df = self.dm.load_combined_processed(self.category)

            # 重命名列以便清晰
            df = df.rename(columns=self.column_mapping)

            # 计算信号
            signals = self._calculate_signals(df)

            # 可视化结果
            self._visualize(signals)

            return {"signal": signals}

        except Exception as e:
            self.logger.error(f"国际面指标分析失败: {str(e)}")
            return {"signal": pd.DataFrame()}

    def _calculate_signals(self, df):
        """
        计算国际面信号
        返回包含原始数据、中间变量和信号的DataFrame
        """
        # 复制原始数据避免污染输入
        df = df.copy()

        # 缺失值处理（线性插值+前向填充）
        df = df.interpolate(method="time").ffill().bfill()

        # 重采样到指定周期
        df = df.resample("ME").last()

        # 步骤1：计算中美利差
        df["中美利差"] = df["CN_10yr_bond_return"] - df["US_10yr_bond_return"]

        # 步骤2：计算3个月移动平均
        df["中美利差_3MMA"] = (
            df["中美利差"].rolling(window=3, min_periods=1).mean()
        )
        df["汇率_3MMA"] = (
            df["offshore_USD/CNY"].rolling(window=3, min_periods=1).mean()
        )
        df["QFII_3MMA"] = (
            df["QFII_equity"].rolling(window=3, min_periods=1).mean()
        )

        # 生成利差信号
        df["利差信号"] = np.select(
            [
                df["中美利差"] > df["中美利差_3MMA"],
                df["中美利差"] < df["中美利差_3MMA"],
            ],
            [1, -1],  # 吸引力上升  # 吸引力下降
            default=0,  # 中性
        )

        # 生成汇率信号
        df["汇率信号"] = np.select(
            [
                df["offshore_USD/CNY"] < df["汇率_3MMA"],  # 人民币升值
                df["offshore_USD/CNY"] > df["汇率_3MMA"],  # 人民币贬值
            ],
            [1, -1],  # 吸引力上升  # 吸引力下降
            default=0,  # 中性
        )

        # 生成QFII持仓信号
        df["QFII信号"] = np.select(
            [
                df["QFII_equity"] > df["QFII_3MMA"],  # QFII持仓增加
                df["QFII_equity"] < df["QFII_3MMA"],  # QFII持仓减少
            ],
            [1, -1],  # 吸引力上升  # 吸引力下降
            default=0,  # 中性
        )

        # 合并信号生成国际面信号
        df["final_signal"] = df["利差信号"] + df["汇率信号"] + df["QFII信号"]

        return df

    def _visualize(self, signals_df):
        """可视化国际面信号"""
        fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
        fig.suptitle("国际面信号分析", fontsize=16, fontweight="bold")

        # 1. 中美利差信号
        ax1 = axes[0]
        ax1.plot(
            signals_df.index,
            signals_df["中美利差"],
            label="中美利差",
            color="blue",
        )
        ax1.plot(
            signals_df.index,
            signals_df["中美利差_3MMA"],
            label="3个月均值",
            linestyle="--",
            color="green",
        )
        ax1.scatter(
            signals_df.index,
            signals_df["中美利差"] * 1.05,
            c=signals_df["利差信号"],
            cmap="coolwarm",
            s=100,
            label="信号",
        )
        ax1.set_title("中美利差分析")
        ax1.set_ylabel("基点(bp)")
        ax1.legend()
        ax1.grid(True)

        # 2. 汇率信号
        ax2 = axes[1]
        ax2.plot(
            signals_df.index,
            signals_df["offshore_USD/CNY"],
            label="美元/人民币汇率",
            color="purple",
        )
        ax2.plot(
            signals_df.index,
            signals_df["汇率_3MMA"],
            label="3个月均值",
            linestyle="--",
            color="orange",
        )
        ax2.scatter(
            signals_df.index,
            signals_df["offshore_USD/CNY"] * 1.05,
            c=signals_df["汇率信号"],
            cmap="coolwarm",
            s=100,
            label="信号",
        )
        ax2.set_title("美元/离岸人民币汇率分析")
        ax2.set_ylabel("汇率")
        ax2.legend()
        ax2.grid(True)

        # 3. QFII持仓信号
        ax3 = axes[2]
        ax3.plot(
            signals_df.index,
            signals_df["QFII_equity"],
            label="QFII持仓",
            color="brown",
        )
        ax3.plot(
            signals_df.index,
            signals_df["QFII_3MMA"],
            label="3个月均值",
            linestyle="--",
            color="cyan",
        )
        ax3.scatter(
            signals_df.index,
            signals_df["QFII_equity"] * 1.05,
            c=signals_df["QFII信号"],
            cmap="coolwarm",
            s=100,
            label="信号",
        )
        ax3.set_title("QFII持仓分析")
        ax3.set_ylabel("持仓金额")
        ax3.legend()
        ax3.grid(True)

        # 4. 综合国际面信号
        ax4 = axes[3]
        ax4.plot(
            signals_df.index,
            signals_df["final_signal"],
            label="final_signal",
            marker="o",
            color="red",
        )
        ax4.axhline(0, color="gray", linestyle="--", linewidth=0.5)
        ax4.set_title("综合国际面信号")
        ax4.set_ylabel("信号值")
        ax4.legend()
        ax4.grid(True)

        # 调整布局
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.gcf().autofmt_xdate()
        plt.subplots_adjust(hspace=0.3, top=0.95)
        plt.show()
        return fig


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    analyzer = InternationalAnalyzer()
    signals_df = analyzer.analyze().get("signal")

    # 保存结果
    if not signals_df.empty:
        signals_df.to_excel("国际面信号分析结果.xlsx")
        print("分析结果已保存至: 国际面信号分析结果.xlsx")
