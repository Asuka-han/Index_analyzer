# -*- coding: utf-8 -*-
"""
Created on Sun Aug 17 15:35:12 2025

@author: imado
"""
# analyze_data.py
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyzers.fundamental_economy import EconomyAnalyzer
from analyzers.fundamental_monetary import MonetaryAnalyzer
from analyzers.fundamental_credit import CreditAnalyzer
from analyzers.international import InternationalAnalyzer
from analyzers.valuation import ValuationAnalyzer
from analyzers.capital import CapitalAnalyzer  # 新增资金面分析
from analyzers.technical import TechIndicatorAnalyzer
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("DataAnalyzer")

index_code = "000300.SH"
# index_code = "881001.WI"


def main():
    foundamental_merge = True
    parser = argparse.ArgumentParser(description="多维度数据分析脚本")
    parser.add_argument(
        "--start_date",
        type=str,
        default="2012-01-01",
        help="分析开始日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end_date",
        type=str,
        default=datetime.today().strftime("%Y-%m-%d"),
        help="分析结束日期 (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    # 初始化各分析模块
    analyzers = {
        "经济面": EconomyAnalyzer(),
        "货币面": MonetaryAnalyzer(),
        "信用面": CreditAnalyzer(),
        "国际面": InternationalAnalyzer(),
        "估值面": ValuationAnalyzer(),
        "资金面": CapitalAnalyzer(),  # 新增资金面
        "技术面": TechIndicatorAnalyzer(
            symbol=index_code, trend_indicator="MACD", risk_indicator="RSI"
        ),
    }

    # 存储所有信号
    all_signals = {}

    # 执行各维度分析
    for dimension, analyzer in analyzers.items():
        try:
            logger.info(f"开始 {dimension} 分析...")
            result = analyzer.analyze()  # 接收字典格式的结果

            # 提取信号DataFrame
            signal = result.get("signal")

            if signal is not None and not signal.empty:
                # 确保月度频率
                monthly_signal = signal.resample("ME").last()
                all_signals[dimension] = monthly_signal["final_signal"]
                logger.info(f"{dimension} 分析完成")
            else:
                logger.warning(f"{dimension} 分析未返回有效信号")

        except Exception as e:
            logger.error(f"{dimension} 分析失败: {str(e)}")

    # 合并所有信号
    combined = combine_signals(all_signals, foundamental_merge)

    # 生成最终决策
    final_signal = generate_final_signal(combined)

    # 保存结果
    save_results(combined, final_signal)

    logger.info("多维度分析完成")


def combine_signals(all_signals, foundamental_merge):
    """合并各维度信号"""
    df = pd.DataFrame(all_signals)
    df = df.dropna()  # 移除不完整的数据点

    if foundamental_merge is True:
        df["基本面"] = df[["经济面", "货币面", "信用面"]].sum(axis=1)
        df_final = df[
            ["基本面", "国际面", "估值面", "资金面", "技术面"]
        ].copy()
    else:
        df_final = df.copy()

    # 添加总信号列
    df_final["Total_Signal"] = df_final.sum(axis=1)

    return df_final


def generate_final_signal(df):
    """生成最终决策信号"""
    # 使用np.select实现多条件选择
    conditions = [
        df["Total_Signal"] > 3,  # 大于1时为1
        df["Total_Signal"] < -3,  # 小于-1时为-1
        True,  # 其他情况（介于-1和1之间）为0
    ]

    choices = [1, -1, 0]

    df["Final_Decision"] = np.select(conditions, choices, default=0)
    return df


def save_results(df, final_signal):
    """保存分析结果"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"multi_factor_analysis_{timestamp}.xlsx"
    filename_simple = "multi_factor_analysis.xlsx"
    result_path = Path.cwd() / "result" / filename

    with pd.ExcelWriter(result_path) as writer:
        df.to_excel(writer, sheet_name="各维度信号")
        final_signal.to_excel(writer, sheet_name="最终决策信号")

    with pd.ExcelWriter(filename_simple) as writer:
        df.to_excel(writer, sheet_name="各维度信号")
        final_signal.to_excel(writer, sheet_name="最终决策信号")

    logger.info(f"分析结果已保存至: {filename}")


if __name__ == "__main__":
    main()
