# -*- coding: utf-8 -*-
"""
Created on Sun Aug 17 23:34:29 2025

@author: imado
"""
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
foundamental_merge = False
# index_code = "881001.WI"

# 1. 读取Excel文件
if foundamental_merge == True:
    file_path = "multi_factor_analysis_merge.xlsx"
else: 
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

# 4. 获取沪深300月度收益率（扩大时间范围）
extended_start = (df["Date"].min() - pd.DateOffset(months=1)).strftime(
    "%Y-%m-%d"
)
end_date = df["Date"].max().strftime("%Y-%m-%d")

# 从Wind获取沪深300指数月度收益率
benchmark_data = w.wsd(
    index_code,
    "pct_chg,close",
    extended_start,
    end_date,
    "Period=M;Fill=Previous",
)

# 转换为DataFrame并确保日期类型一致
benchmark_df = pd.DataFrame(
    {
        "Date": [pd.to_datetime(date) for date in benchmark_data.Times],
        "benchmark_Return": benchmark_data.Data[0],
        "benchmark_Close": benchmark_data.Data[1]
})
benchmark_df = benchmark_df.set_index("Date", drop=False)
benchmark_df = benchmark_df.resample("ME").last()

# 5. 创建完整时序数据（含当月和下月收益率）
full_data = (
    pd.merge(
        df[["Date", "Final_Decision"]], 
        benchmark_df['benchmark_Return'], on="Date", how="outer"
    )
    .sort_values("Date")
    .reset_index(drop=True)
)


# 添加下月收益率列
full_data["Next_Month_Return"] = full_data["benchmark_Return"].shift(-1)
full_data = full_data.dropna(subset=["Final_Decision"])  # 保留有信号的月份

# 6. 三种相关性分析（增加看涨/看跌信号分离）
merged_df = full_data.copy()
merged_df["Return_Sign"] = np.where(merged_df["benchmark_Return"] >= 0, 1, -1)
merged_df["Next_Return_Sign"] = np.where(
    merged_df["Next_Month_Return"] >= 0, 1, -1
)
merged_df["Prev_Signal"] = merged_df["Final_Decision"].shift(1)

# 统计区间
raw_df = merged_df.copy()
merged_df = raw_df[raw_df['Date'].dt.year >= start_year]

# 7. 计算各项相关性指标（增加看涨/看跌独立分析）
def calculate_signal_accuracy(df, signal_col, return_sign_col):
    """计算看涨和看跌信号的独立准确率"""
    # 看涨信号准确率
    bull_signals = df[df[signal_col] == 1]
    bull_accuracy = (
        (bull_signals[signal_col] == bull_signals[return_sign_col]).mean()
        if not bull_signals.empty
        else np.nan
    )

    # 看跌信号准确率
    bear_signals = df[df[signal_col] == -1]
    bear_accuracy = (
        (bear_signals[signal_col] == bear_signals[return_sign_col]).mean()
        if not bear_signals.empty
        else np.nan
    )

    return bull_accuracy, bear_accuracy

# 计算当月信号vs当月涨跌的独立准确率
bull_current, bear_current = calculate_signal_accuracy(
    merged_df, "Final_Decision", "Return_Sign"
)

# 计算当月信号vs下月涨跌的独立准确率
bull_current_next, bear_current_next = calculate_signal_accuracy(
    merged_df, "Final_Decision", "Next_Return_Sign"
)

# 计算上月信号vs当月涨跌的独立准确率
merged_prev = merged_df.dropna(subset=["Prev_Signal"])
bull_prev_current, bear_prev_current = calculate_signal_accuracy(
    merged_prev, "Prev_Signal", "Return_Sign"
)

# 8. 更新结果字典
results = {
    "当月信号-当月涨跌": {
        "Correlation": merged_df["Final_Decision"].corr(
            merged_df["Return_Sign"]
        ),
        "MatchRate": (
            merged_df["Final_Decision"] == merged_df["Return_Sign"]
        ).mean(),
        "BullReturn": merged_df[merged_df["Final_Decision"] == 1][
            "benchmark_Return"
        ].mean(),
        "BearReturn": merged_df[merged_df["Final_Decision"] == -1][
            "benchmark_Return"
        ].mean(),
        "BullSignalAccuracy": bull_current,
        "BearSignalAccuracy": bear_current,
    },
    "当月信号-下月涨跌": {
        "Correlation": merged_df["Final_Decision"].corr(
            merged_df["Next_Return_Sign"]
        ),
        "MatchRate": (
            merged_df["Final_Decision"] == merged_df["Next_Return_Sign"]
        ).mean(),
        "BullReturn": merged_df[merged_df["Final_Decision"] == 1][
            "Next_Month_Return"
        ].mean(),
        "BearReturn": merged_df[merged_df["Final_Decision"] == -1][
            "Next_Month_Return"
        ].mean(),
        "BullSignalAccuracy": bull_current_next,
        "BearSignalAccuracy": bear_current_next,
    },
    "上月信号-当月涨跌": {
        "Correlation": merged_prev["Prev_Signal"].corr(
            merged_prev["Return_Sign"]
        ),
        "MatchRate": (
            merged_prev["Prev_Signal"] == merged_prev["Return_Sign"]
        ).mean(),
        "BullReturn": merged_prev[merged_prev["Prev_Signal"] == 1][
            "benchmark_Return"
        ].mean(),
        "BearReturn": merged_prev[merged_prev["Prev_Signal"] == -1][
            "benchmark_Return"
        ].mean(),
        "BullSignalAccuracy": bull_prev_current,
        "BearSignalAccuracy": bear_prev_current,
    },
}

# 展示三种相关性结果
for analysis, metrics in results.items():
    print("\n" + "=" * 60)
    print(f"{analysis} 分析:")
    print("-" * 60)
    print(f"信号与涨跌符号的相关系数: {metrics['Correlation']:.4f}")
    print(f"信号方向正确率: {metrics['MatchRate']:.2%}")

    if "BullSignalAccuracy" in metrics and "BearSignalAccuracy" in metrics:
        print(f"看涨信号准确率: {metrics['BullSignalAccuracy']:.2%}")
        print(f"看跌信号准确率: {metrics['BearSignalAccuracy']:.2%}")

    if analysis == "当月信号-下月涨跌":
        print(f"看涨信号期平均收益率: {metrics['BullReturn']:.2%}")
        print(f"看跌信号期平均收益率: {metrics['BearReturn']:.2%}")
        print(
            f"多空收益差: {metrics['BullReturn'] - metrics['BearReturn']:.2%}"
        )

# 10. 信号分布统计
bull_count = (merged_df["Final_Decision"] == 1).sum()
bear_count = (merged_df["Final_Decision"] == -1).sum()
print("\n" + "=" * 60)
print("信号分布统计:")
print("-" * 60)
print(f"看涨信号数量: {bull_count}次 ({bull_count/len(merged_df):.1%})")
print(f"看跌信号数量: {bear_count}次 ({bear_count/len(merged_df):.1%})")

# 11. 信号有效性诊断
if bull_count > 0 and bear_count > 0:
    bull_advantage = (
        results["当月信号-下月涨跌"]["BullSignalAccuracy"]
        - results["当月信号-下月涨跌"]["BearSignalAccuracy"]
    )
    if abs(bull_advantage) > 0.15:
        print(
            f"★ 信号有效性差异: 看涨信号准确率{'高于' if bull_advantage > 0 else '低于'}看跌信号{abs(bull_advantage):.2%}"
        )
elif bull_count == 0:
    print("▲ 警告: 无看涨信号可供分析")
elif bear_count == 0:
    print("▲ 警告: 无看跌信号可供分析")

# 12. 可视化分析
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
    results["当月信号-下月涨跌"]["BullSignalAccuracy"],
    results["当月信号-下月涨跌"]["BearSignalAccuracy"],
    results["上月信号-当月涨跌"]["BullSignalAccuracy"],
    results["上月信号-当月涨跌"]["BearSignalAccuracy"],
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
    results["当月信号-下月涨跌"]["BullReturn"],
    results["当月信号-下月涨跌"]["BearReturn"],
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

# %%绘制沪深300指数走势
# 在绘制沪深300指数走势图之前，重置坐标轴转换器
plt.figure(figsize=(15, 10))  # 创建新的图形
ax = plt.gca()  # 获取当前坐标轴

# 重置日期转换器
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.plot(benchmark_df["Date"], benchmark_df['benchmark_Close'], 
         label='沪深300指数', color='#1f77b4', linewidth=1.5)

# 标注信号点
signals = merged_df[["Date", "Prev_Signal"]].copy()

# 合并信号与日线数据，找到信号日当天的收盘价
signals = pd.merge(signals, benchmark_df[
    'benchmark_Close'], on="Date", how="left")

# 分离看涨和看跌信号
bull_signals = signals[signals["Prev_Signal"] == 1]
bear_signals = signals[signals["Prev_Signal"] == -1]

# 绘制信号点
plt.scatter(bull_signals["Date"], bull_signals["benchmark_Close"], 
            marker='^', color='red', s=120, label='看涨信号', alpha=0.9)
plt.scatter(bear_signals["Date"], bear_signals["benchmark_Close"], 
            marker='v', color='green', s=120, label='看跌信号', alpha=0.9)

# 添加信号文字说明
for _, row in bull_signals.iterrows():
    plt.annotate('↑看涨', 
                (mdates.date2num(row["Date"]), row["benchmark_Close"]),
                textcoords="offset points", 
                xytext=(0,15), 
                ha='center',
                fontsize=9,
                color='red',
                weight='bold')

for _, row in bear_signals.iterrows():
    plt.annotate('↓看跌', 
                (mdates.date2num(row["Date"]), row["benchmark_Close"]),
                textcoords="offset points", 
                xytext=(0,-15), 
                ha='center',
                fontsize=9,
                color='green',
                weight='bold')

# 设置图表格式
plt.title(f'{index_code}指数走势与信号标注(当月信号->下月涨跌)', fontsize=16)
plt.xlabel('日期', fontsize=12)
plt.ylabel('收盘价', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(loc='best')

# 设置日期格式
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.gcf().autofmt_xdate()  # 自动旋转日期标签

# 添加背景色区分不同年份
years = sorted(set(signals["Date"].dt.year))
colors = ['#f0f0f0', '#ffffff']  # 交替的浅灰色和白色
for i, year in enumerate(years):
    start_date = pd.Timestamp(f'{year}-01-01')
    end_date = pd.Timestamp(f'{year}-12-31')
    plt.axvspan(start_date, end_date, 
                facecolor=colors[i % len(colors)], alpha=0.3)

plt.tight_layout()
plt.savefig("benchmark_with_signals.png")
print(f"{index_code}指数走势与信号图已保存至: benchmark_with_signals.png")

# 13. 保存详细分析数据
merged_df.to_excel("signal_analysis_full_results.xlsx", index=False)
print("\n详细分析结果已保存至: signal_analysis_full_results.xlsx")