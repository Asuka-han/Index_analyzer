# -*- coding: utf-8 -*-
"""
Created on Thu Jul 31 15:13:53 2025

@author: imado
"""
import pandas as pd
import numpy as np
import talib
import matplotlib.pyplot as plt
from pathlib import Path
import os

# 设置全局字体（支持Windows/macOS/Linux）
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
    "STHeiti",
]  # 常用中文字体
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


class TechIndicatorAnalyzer:
    def __init__(
        self,
        symbol="000300.SH",
        trend_indicator="MACD",
        risk_indicator="ATR",
        trend_params=None,
        risk_params=None,
        period="M",
        auto_plot=True,
    ):
        """\
        技术指标分析系统\
        :param symbol: 标的代码 (默认沪深300)\
        :param trend_indicator: 趋势指标 (MACD/ADX/MA/DMI)\
        :param risk_indicator: 风险指标 (ATR/BOLL/RSI/CCI)\
        :param trend_params: 趋势指标参数 (字典格式)\
        :param risk_params: 风险指标参数 (字典格式)\
        :param period: 分析周期 (D-日线, W-周线, M-月线)\
        :param auto_plot: 是否自动生成可视化图表\
        """
        self.symbol = symbol
        self.trend_indicator = trend_indicator
        self.risk_indicator = risk_indicator
        self.trend_params = trend_params or {}
        self.risk_params = risk_params or {}
        self.period = period.upper()  # 确保大写
        self.auto_plot = auto_plot
        self.results = None

        # 设置默认参数
        self.default_params = {
            "MACD": {"fast": 12, "slow": 26, "signal": 9},
            "ADX": {"timeperiod": 14},
            "MA": {"window": 20},
            "DMI": {"timeperiod": 14},
            "ATR": {"timeperiod": 14},
            "BOLL": {"timeperiod": 20, "nbdevup": 2, "nbdevdn": 2},
            "RSI": {"timeperiod": 14},
            "CCI": {"timeperiod": 14},
        }

    def load_data(
        self,
        start_date="2012-01-01",
        end_date="2025-07-31",
        data_source="wind",
    ):
        """加载数据（支持多种数据源）"""
        if data_source.lower() == "excel":
            return self._load_from_excel()
        elif data_source.lower() == "wind":
            return self._load_from_wind(start_date, end_date)
        else:
            raise ValueError("不支持的data_source类型，请选择'excel'或'wind'")

    def _load_from_excel(self):
        """从Excel文件加载数据"""
        # 获取当前脚本所在目录
        current_dir = (
            Path(__file__).parent if "__file__" in locals() else Path.cwd()
        )
        excel_path = current_dir / "wind_data.xlsx"

        if excel_path.exists():
            print(f"从Excel文件加载数据: {excel_path}")
            data = pd.read_excel(excel_path, index_col=0, parse_dates=True)
            data.index = pd.to_datetime(data.index)
            return data
        else:
            raise FileNotFoundError(f"Excel文件不存在: {excel_path}")

    def _load_from_wind(self, start_date, end_date):
        """从Wind加载数据（需要WindPy支持）"""
        try:
            from WindPy import w
        except ImportError:
            raise ImportError("未安装WindPy，请使用Excel数据源")

        # 初始化Wind接口
        if not w.isconnected():
            w.start()

        # 确定周期参数
        period_map = {"D": "BarSize=1", "W": "BarSize=7", "M": "BarSize=30"}
        if self.period not in period_map:
            raise ValueError(
                "周期参数错误，请使用 'D'(日), 'W'(周) 或 'M'(月)"
            )

        # 从Wind获取数据
        wind_code = self.symbol
        fields = "open,high,low,close,volume"
        options = f"startDate={start_date};endDate={end_date};PriceAdj=F;{period_map[self.period]}"
        wind_data = w.wsd(wind_code, fields, start_date, end_date, options)

        if wind_data.ErrorCode != 0:
            raise ConnectionError(f"Wind数据获取失败: {wind_data.Data}")

        # 转换为DataFrame并处理
        df = pd.DataFrame(
            data=np.array(wind_data.Data).T,
            columns=[f.lower() for f in wind_data.Fields],
            index=pd.to_datetime(wind_data.Times),
        )

        # 确保数据按时间排序
        df = df.sort_index()

        # 处理空值
        df = df.dropna()

        # 周/月线数据需要重新采样
        if self.period in ["W", "M"] and not df.empty:
            df = self._resample_data(df)

        return df

    def _resample_data(self, df):
        """重新采样周/月线数据（Wind返回的是原始日线，需要聚合）"""
        if self.period == "W":
            resampled = df.resample("W-FRI").agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
        elif self.period == "M":
            resampled = df.resample("ME").agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
        return resampled.dropna()

    def calculate_trend(self, data):
        """计算趋势指标分数(0-100)"""
        # 合并默认参数和用户自定义参数
        default = self.default_params.get(self.trend_indicator, {})
        params = {**default, **self.trend_params}  # 字典合并

        if self.trend_indicator == "MACD":
            macd, signal, _ = talib.MACD(
                data["close"].values,
                fastperiod=params["fast"],
                slowperiod=params["slow"],
                signalperiod=params["signal"],
            )
            # 用MACD柱状图强度作为趋势分数
            trend_value = (macd - signal) * 100
        elif self.trend_indicator == "ADX":
            trend_value = talib.ADX(
                data["high"].values,
                data["low"].values,
                data["close"].values,
                timeperiod=params["timeperiod"],
            )
        elif self.trend_indicator == "MA":
            ma = talib.MA(data["close"].values, timeperiod=params["window"])
            # 用价格与均线的距离作为趋势强度
            trend_value = (data["close"] - ma) / ma * 100
        elif self.trend_indicator == "DMI":
            pdi = talib.PLUS_DI(
                data["high"].values,
                data["low"].values,
                data["close"].values,
                timeperiod=params["timeperiod"],
            )
            mdi = talib.MINUS_DI(
                data["high"].values,
                data["low"].values,
                data["close"].values,
                timeperiod=params["timeperiod"],
            )
            trend_value = pdi - mdi  # 多空方向强度差

        # 创建Series并填充初始NaN值为0
        trend_series = pd.Series(trend_value, index=data.index)
        trend_series = trend_series.fillna(0)

        # 归一化到0-100范围
        return self.normalize(trend_series)

    def calculate_risk(self, data):
        """计算风险指标分数(0-100)"""
        # 合并默认参数和用户自定义参数
        default = self.default_params.get(self.risk_indicator, {})
        params = {**default, **self.risk_params}  # 字典合并

        if self.risk_indicator == "ATR":
            risk_value = talib.ATR(
                data["high"].values,
                data["low"].values,
                data["close"].values,
                timeperiod=params["timeperiod"],
            )
        elif self.risk_indicator == "BOLL":
            upper, middle, lower = talib.BBANDS(
                data["close"].values,
                timeperiod=params["timeperiod"],
                nbdevup=params["nbdevup"],
                nbdevdn=params["nbdevdn"],
            )
            # 用布林带宽度作为波动率度量
            risk_value = (upper - lower) / middle
        elif self.risk_indicator == "RSI":
            risk_value = talib.RSI(
                data["close"].values, timeperiod=params["timeperiod"]
            )
            # 将RSI转换为风险度量(离50均衡点的距离)
            risk_value = np.abs(risk_value - 50)
        elif self.risk_indicator == "CCI":
            risk_value = talib.CCI(
                data["high"].values,
                data["low"].values,
                data["close"].values,
                timeperiod=params["timeperiod"],
            )
            # 用CCI绝对值作为风险度量
            risk_value = np.abs(risk_value)

        # 创建Series并填充初始NaN值为0
        risk_series = pd.Series(risk_value, index=data.index)
        risk_series = risk_series.fillna(0)

        # 归一化到0-100范围
        return self.normalize(risk_series)

    def normalize(self, series):
        """滚动窗口归一化到0-100范围（根据周期自动调整窗口）"""
        window = 12 if self.period == "M" else 26
        rolling_min = series.rolling(window).min()
        rolling_max = series.rolling(window).max()
        normalized = (series - rolling_min) / (rolling_max - rolling_min) * 100
        normalized = normalized.fillna(0)
        return normalized

    def calculate_combined_score(self, data):
        """计算综合得分"""
        trend_score = self.calculate_trend(data)
        risk_score = self.calculate_risk(data)

        combined = pd.DataFrame(
            {
                "trend_score": trend_score,
                "risk_score": risk_score,
            }
        )

        combined["final_signal"] = np.where(
            combined["trend_score"] > combined["risk_score"], 1, -1
        )

        return combined

    def analyze(self, start_date="2012-01-01", end_date="2025-07-31"):
        """执行完整分析流程"""
        data = self.load_data(start_date, end_date)
        results = self.calculate_combined_score(data)

        if self.auto_plot:
            self.plot_results(results)

        return {"signal": results}

    def plot_results(self, results):
        """绘制分析结果"""
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

        axes[0].plot(results.index, results["trend_score"], label="趋势得分")
        axes[0].axhline(50, color="gray", linestyle="--", linewidth=0.8)
        axes[0].set_title("趋势指标得分")
        axes[0].legend()
        axes[0].grid(True)

        axes[1].plot(results.index, results["risk_score"], label="风险得分", color="orange")
        axes[1].axhline(50, color="gray", linestyle="--", linewidth=0.8)
        axes[1].set_title("风险指标得分")
        axes[1].legend()
        axes[1].grid(True)

        axes[2].plot(results.index, results["final_signal"], label="final_signal", color="green")
        axes[2].axhline(0, color="gray", linestyle="--", linewidth=0.8)
        axes[2].set_title("综合信号")
        axes[2].legend()
        axes[2].grid(True)

        plt.tight_layout()
        plt.show()
        return fig


if __name__ == "__main__":
    analyzer = TechIndicatorAnalyzer(symbol="000300.SH")
    result = analyzer.analyze()
    signal_df = result.get("signal")
    if signal_df is not None and not signal_df.empty:
        signal_df.to_excel("技术分析结果.xlsx")
