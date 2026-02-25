# -*- coding: utf-8 -*-
"""
Created on Sun Aug 17 23:34:29 2025

@author: imado
"""
import pandas as pd
import numpy as np
from datetime import datetime
from WindPy import w
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 设置全局字体（支持中文显示）
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
    "STHeiti",
]
plt.rcParams["axes.unicode_minus"] = False

# %%全局参数
start_year = 2012
index_code = "000300.SH"

# 1. 读取Excel文件
file_path = "multi_factor_analysis.xlsx"
df = pd.read_excel(file_path, sheet_name="最终决策信号")

# 2. 安全处理日期列并提取信号
date_col = df.columns[0]
signal_col = df.columns[-1]

# 安全日期转换：处理多种可能的日期格式
if df[date_col].dtype == "datetime64[ns]":
    df["Date"] = df[date_col]
else:
    try:
        # 尝试Excel序列日期转换
        df["Date"] = pd.to_datetime(
            df[date_col], unit="D", origin="1899-12-30", errors="coerce"
        )
        # 如果转换失败，尝试字符串格式转换
        if df["Date"].isnull().any():
            df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    except:
        df["Date"] = pd.to_datetime(df[date_col], errors="coerce")

# 删除无效日期
df = df.dropna(subset=["Date"])
df["Final_Decision"] = df[signal_col]

# 3. 初始化Wind API
w.start()

# 4. 获取指数月度收益率（扩大时间范围）
extended_start = (df["Date"].min() - pd.DateOffset(months=1)).strftime(
    "%Y-%m-%d"
)
end_date = df["Date"].max().strftime("%Y-%m-%d")

# 从Wind获取指数指数月度收益率
benchmark_data = w.wsd(
    index_code,
    "pct_chg,close",
    extended_start,
    end_date,
    "Period=M;Fill=Previous",
)

# 转换为DataFrame并确保日期类型一致
# 转化为百分比
benchmark_df = pd.DataFrame(
    {
        "Date": [pd.to_datetime(date) for date in benchmark_data.Times],
        "benchmark_Return": benchmark_data.Data[0],
        "benchmark_Close": benchmark_data.Data[1],
    }
)
benchmark_df = benchmark_df.set_index("Date", drop=False)
benchmark_df = benchmark_df.resample("ME").last()
# 转化为百分数
benchmark_df["benchmark_Return"] = benchmark_df["benchmark_Return"] / 100

# 5. 创建完整时序数据（含当月和下月收益率）
full_data = (
    pd.merge(
        df[["Date", "Final_Decision"]],
        benchmark_df["benchmark_Return"],
        on="Date",
        how="outer",
    )
    .sort_values("Date")
    .reset_index(drop=True)
)

# 添加下月收益率列
full_data["Next_Month_Return"] = full_data["benchmark_Return"].shift(-1)
full_data = full_data.dropna(subset=["Final_Decision"])  # 保留有信号的月份

# 6. 三种相关性分析（增加中性信号处理）
merged_df = full_data.copy()
merged_df["Return_Sign"] = np.where(merged_df["benchmark_Return"] >= 0, 1, -1)
merged_df["Next_Return_Sign"] = np.where(
    merged_df["Next_Month_Return"] >= 0, 1, -1
)
merged_df["Prev_Signal"] = merged_df["Final_Decision"].shift(1)

# 统计区间
raw_df = merged_df.copy()
merged_df = raw_df[raw_df["Date"].dt.year >= start_year]


# 7. 计算各项相关性指标（增加中性信号处理）s
def calculate_signal_stats(df, signal_col, return_sign_col, return_col):
    """计算各种信号的统计指标"""
    stats = {}
    for signal in [-1, 0, 1]:
        signal_data = df[df[signal_col] == signal]
        if not signal_data.empty:
            stats[signal] = {
                "count": len(signal_data),
                "mean_return": signal_data[return_col].mean(),
                "up_prob": (signal_data[return_sign_col] == 1).mean(),
                "down_prob": (signal_data[return_sign_col] == -1).mean(),
                "accuracy": (
                    (
                        signal_data[signal_col] == signal_data[return_sign_col]
                    ).mean()
                    if signal != 0
                    else np.nan
                ),
            }
    return stats


# 计算各种信号统计
results = {
    "当月信号-当月涨跌": calculate_signal_stats(
        merged_df, "Final_Decision", "Return_Sign", "benchmark_Return"
    ),
    "当月信号-下月涨跌": calculate_signal_stats(
        merged_df, "Final_Decision", "Next_Return_Sign", "Next_Month_Return"
    ),
    "上月信号-当月涨跌": calculate_signal_stats(
        merged_df.dropna(subset=["Prev_Signal"]),
        "Prev_Signal",
        "Return_Sign",
        "benchmark_Return",
    ),
}

# 8. 连续两个月信号预测下月涨跌
merged_df["Signal_Combination"] = (
    merged_df["Prev_Signal"].astype(str)
    + "_"
    + merged_df["Final_Decision"].astype(str)
)

# 删除无效数据
merged_df_comb = merged_df.dropna(
    subset=["Signal_Combination", "Next_Return_Sign"]
)

# 分析组合信号的有效性
combination_groups = merged_df_comb.groupby("Signal_Combination")
results_comb = {}

for name, group in combination_groups:
    prob_up = (group["Next_Return_Sign"] == 1).mean()
    prob_down = (group["Next_Return_Sign"] == -1).mean()
    mean_return = group["Next_Month_Return"].mean()
    count = len(group)

    results_comb[name] = {
        "count": count,
        "prob_up": prob_up,
        "prob_down": prob_down,
        "mean_return": mean_return,
    }

# 9. 格式化输出结果
print("=" * 80)
print("指数指数信号有效性分析报告")
print("=" * 80)
print(
    f"分析周期: {merged_df['Date'].min().strftime('%Y-%m-%d')} 至 {merged_df['Date'].max().strftime('%Y-%m-%d')}"
)
print(f"有效数据点: {len(merged_df)}个月度")

# 展示三种相关性结果
signal_labels = {-1: "看跌", 0: "中性", 1: "看涨"}

for analysis, stats in results.items():
    print("\n" + "=" * 60)
    print(f"{analysis} 分析:")
    print("-" * 60)

    for signal, data in stats.items():
        if not data:
            continue
        print(f"\n{signal_labels[signal]}信号:")
        print(
            f"  出现次数: {data['count']}次 ({data['count']/len(merged_df):.1%})"
        )
        print(f"  平均收益率: {data['mean_return']:.2%}")
        print(f"  上涨概率: {data['up_prob']:.2%}")
        print(f"  下跌概率: {data['down_prob']:.2%}")
        if signal != 0:
            print(f"  方向准确率: {data['accuracy']:.2%}")

# 10. 输出连续两个月信号预测结果
print("\n" + "=" * 60)
print("连续两个月信号预测下月涨跌效果:")
print("-" * 60)
print("信号组合格式: '上月信号_本月信号'")
print("预测目标: 下个月市场涨跌")
print(f"有效数据点: {len(merged_df_comb)}个月度")

for signal, stats in results_comb.items():
    print(f"\n信号组合 {signal}:")
    print(
        f"  出现次数: {stats['count']}次 ({stats['count']/len(merged_df_comb):.1%})"
    )
    print(f"  下月上涨概率: {stats['prob_up']:.2%}")
    print(f"  下月下跌概率: {stats['prob_down']:.2%}")
    print(f"  信号发出后下月平均收益: {stats['mean_return']:.2%}")

# 11. 信号分布统计
signal_counts = merged_df["Final_Decision"].value_counts()
print("\n" + "=" * 60)
print("信号分布统计:")
print("-" * 60)
for signal, count in signal_counts.items():
    print(
        f"{signal_labels[signal]}信号数量: {count}次 ({count/len(merged_df):.1%})"
    )

# 12. 信号有效性诊断
if 1 in results["当月信号-下月涨跌"] and -1 in results["当月信号-下月涨跌"]:
    bull_accuracy = results["当月信号-下月涨跌"][1]["accuracy"]
    bear_accuracy = results["当月信号-下月涨跌"][-1]["accuracy"]
    bull_advantage = bull_accuracy - bear_accuracy

    if abs(bull_advantage) > 0.15:
        print(
            f"\n★ 信号有效性差异: 看涨信号准确率{'高于' if bull_advantage > 0 else '低于'}看跌信号{abs(bull_advantage):.2%}"
        )

# 13. 可视化分析（保持不变）
plt.figure(figsize=(12, 8))

# 看涨/看跌信号准确率对比
plt.subplot(2, 1, 1)
categories = [
    "看涨信号(预测下月)",
    "看跌信号(预测下月)",
    "看涨信号(上月→当月)",
    "看跌信号(上月→当月)",
]
values = [
    results["当月信号-下月涨跌"][1]["accuracy"],
    results["当月信号-下月涨跌"][-1]["accuracy"],
    results["上月信号-当月涨跌"][1]["accuracy"],
    results["上月信号-当月涨跌"][-1]["accuracy"],
]
colors = ["#4CAF50", "#FF5252", "#81C784", "#FF8A80"]
bars = plt.bar(categories, values, color=colors)
plt.title("看涨/看跌信号准确率对比")
plt.ylabel("准确率")
plt.ylim(0, 1)

# 添加准确率标签
for bar in bars:
    height = bar.get_height()
    plt.text(
        bar.get_x() + bar.get_width() / 2.0,
        height,
        f"{height:.1%}",
        ha="center",
        va="bottom",
    )

# 多空收益对比
plt.subplot(2, 1, 2)
categories = ["看涨信号(下月收益)", "看跌信号(下月收益)"]
values = [
    results["当月信号-下月涨跌"][1]["mean_return"],
    results["当月信号-下月涨跌"][-1]["mean_return"],
]
colors = ["#4CAF50", "#FF5252"]
bars = plt.bar(categories, values, color=colors)
plt.title("看涨/看跌信号对应收益率")
plt.ylabel("平均收益率")

# 添加收益率标签
for bar in bars:
    height = bar.get_height()
    plt.text(
        bar.get_x() + bar.get_width() / 2.0,
        height,
        f"{height:.2%}",
        ha="center",
        va="bottom",
    )

plt.tight_layout()
plt.savefig("signal_analysis.png")
print("\n分析图表已保存至: signal_analysis.png")

# 指数指数走势图（保持不变）
plt.figure(figsize=(15, 10))
ax = plt.gca()
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.plot(
    benchmark_df["Date"],
    benchmark_df["benchmark_Close"],
    label="指数指数",
    color="#1f77b4",
    linewidth=1.5,
)

# 标注信号点
signals = merged_df[["Date", "Prev_Signal"]].copy()
signals = pd.merge(
    signals, benchmark_df["benchmark_Close"], on="Date", how="left"
)

# 分离看涨和看跌信号
bull_signals = signals[signals["Prev_Signal"] == 1]
bear_signals = signals[signals["Prev_Signal"] == -1]

# 绘制信号点
plt.scatter(
    bull_signals["Date"],
    bull_signals["benchmark_Close"],
    marker="^",
    color="red",
    s=120,
    label="看涨信号",
    alpha=0.9,
)
plt.scatter(
    bear_signals["Date"],
    bear_signals["benchmark_Close"],
    marker="v",
    color="green",
    s=120,
    label="看跌信号",
    alpha=0.9,
)

# 添加信号文字说明
for _, row in bull_signals.iterrows():
    plt.annotate(
        "↑看涨",
        (mdates.date2num(row["Date"]), row["benchmark_Close"]),
        textcoords="offset points",
        xytext=(0, 15),
        ha="center",
        fontsize=9,
        color="red",
        weight="bold",
    )

for _, row in bear_signals.iterrows():
    plt.annotate(
        "↓看跌",
        (mdates.date2num(row["Date"]), row["benchmark_Close"]),
        textcoords="offset points",
        xytext=(0, -15),
        ha="center",
        fontsize=9,
        color="green",
        weight="bold",
    )

# 设置图表格式
plt.title(f"{index_code}指数走势与信号标注(当月信号->下月涨跌)", fontsize=16)
plt.xlabel("日期", fontsize=12)
plt.ylabel("收盘价", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend(loc="best")

# 设置日期格式
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.gcf().autofmt_xdate()

# 添加背景色区分不同年份
years = sorted(set(signals["Date"].dt.year))
colors = ["#f0f0f0", "#ffffff"]
for i, year in enumerate(years):
    start_date = pd.Timestamp(f"{year}-01-01")
    end_date = pd.Timestamp(f"{year}-12-31")
    plt.axvspan(
        start_date, end_date, facecolor=colors[i % len(colors)], alpha=0.3
    )

plt.tight_layout()
plt.savefig("benchmark_with_signals.png")
print(f"{index_code}指数走势与信号图已保存至: benchmark_with_signals.png")

# 14. 保存详细分析数据
merged_df.to_excel("signal_analysis_full_results.xlsx", index=False)
print("\n详细分析结果已保存至: signal_analysis_full_results.xlsx")
