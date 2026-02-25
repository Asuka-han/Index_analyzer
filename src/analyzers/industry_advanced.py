# -*- coding: utf-8 -*-
"""Advanced analytics for industry diffusion indices."""

from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyzers.industry_analyzer import IndustryAnalyzer
from core.data_connector import DataConnector


@dataclass
class BacktestResult:
    metrics: pd.DataFrame
    price_df: pd.DataFrame
    signal_df: pd.DataFrame


class IndustryAdvancedAnalyzer:
    def __init__(
        self,
        industry_analyzer: Optional[IndustryAnalyzer] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.industry = industry_analyzer or IndustryAnalyzer()
        self.logger = logging.getLogger("IndustryAdvancedAnalyzer")
        self.output_dir = Path(output_dir) if output_dir else Path("result") / "industry_advanced"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all(
        self,
        start_date: str = "2012-01-01",
        end_date: Optional[str] = None,
        hold_days: Optional[List[int]] = None,
    ) -> None:
        end_date = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
        hold_days = hold_days or [20, 60]

        auto = self.industry.analyze_auto_industry(
            start_date=start_date,
            end_date=end_date,
            output_dir=None,
            show=False,
        )
        estate = self.industry.analyze_real_estate_industry(
            start_date=start_date,
            end_date=end_date,
            output_dir=None,
            show=False,
        )

        auto_backtest = self._safe_run(
            "汽车行业回测",
            self.backtest_signals,
            "汽车行业",
            auto["period_df"],
            auto["signal"],
            "515030",
            start_date,
            end_date,
            hold_days,
        )
        estate_backtest = self._safe_run(
            "房地产行业回测",
            self.backtest_signals,
            "房地产行业",
            estate["period_df"],
            estate["signal"],
            "512200",
            start_date,
            end_date,
            hold_days,
        )

        compare_result = self._safe_run(
            "行业对比",
            self.compare_industries,
            auto["period_df"],
            estate["period_df"],
        )

        auto_dynamic = self._safe_run(
            "汽车行业动态权重",
            self.dynamic_weight_analysis,
            "汽车行业",
            self.industry.auto_indicators,
            "515030",
            start_date,
            end_date,
        )
        estate_dynamic = self._safe_run(
            "房地产行业动态权重",
            self.dynamic_weight_analysis,
            "房地产行业",
            self.industry.real_estate_indicators,
            "512200",
            start_date,
            end_date,
        )

        self._safe_run(
            "性能报告",
            self.performance_report,
            self.industry.auto_indicators + self.industry.real_estate_indicators,
            start_date,
            end_date,
        )

        if isinstance(auto_backtest, BacktestResult):
            self._save_backtest(auto_backtest, "汽车行业")
        if isinstance(estate_backtest, BacktestResult):
            self._save_backtest(estate_backtest, "房地产行业")

        self._safe_run(
            "结论报告",
            self.write_conclusion_report,
            compare_result,
            auto_dynamic,
            estate_dynamic,
            auto_backtest,
            estate_backtest,
        )

    def run_industry(
        self,
        industry_name: str,
        start_date: str = "2012-01-01",
        end_date: Optional[str] = None,
        hold_days: Optional[List[int]] = None,
    ) -> None:
        end_date = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
        hold_days = hold_days or [20, 60]

        if industry_name == "汽车行业":
            indicator_ids = self.industry.auto_indicators
            etf_symbol = "515030"
            result = self.industry.analyze_auto_industry(
                start_date=start_date,
                end_date=end_date,
                output_dir=None,
                show=False,
            )
        else:
            indicator_ids = self.industry.real_estate_indicators
            etf_symbol = "512200"
            result = self.industry.analyze_real_estate_industry(
                start_date=start_date,
                end_date=end_date,
                output_dir=None,
                show=False,
            )

        backtest = self._safe_run(
            f"{industry_name}回测",
            self.backtest_signals,
            industry_name,
            result["period_df"],
            result["signal"],
            etf_symbol,
            start_date,
            end_date,
            hold_days,
        )

        self._safe_run(
            f"{industry_name}动态权重",
            self.dynamic_weight_analysis,
            industry_name,
            indicator_ids,
            etf_symbol,
            start_date,
            end_date,
        )

        self._safe_run(
            "性能报告",
            self.performance_report,
            indicator_ids,
            start_date,
            end_date,
        )

        if isinstance(backtest, BacktestResult):
            self._save_backtest(backtest, industry_name)

    def backtest_signals(
        self,
        industry_name: str,
        period_df: pd.DataFrame,
        signal_df: pd.DataFrame,
        etf_symbol: str,
        start_date: str,
        end_date: str,
        hold_days: Iterable[int],
    ) -> BacktestResult:
        if period_df.empty or signal_df.empty:
            self.logger.warning(f"{industry_name}无法进行回测: 无指标数据")
            return BacktestResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

        prices = self._fetch_etf_prices(etf_symbol, start_date, end_date)
        price_source = "etf"
        if prices.empty:
            self.logger.warning(
                f"{industry_name}ETF数据为空，使用合成价格序列回测"
            )
            prices = self._build_synthetic_prices(period_df, start_date, end_date)
            price_source = "synthetic"
        if prices.empty:
            self.logger.warning(f"{industry_name}无法进行回测: 价格序列为空")
            return BacktestResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

        signal_series = signal_df["final_signal"].copy()
        signal_series.index = pd.to_datetime(signal_series.index, errors="coerce")
        signal_series = signal_series[signal_series.index.notna()]
        signal_series = signal_series[~signal_series.index.duplicated(keep="last")]
        signal_daily = signal_series.reindex(prices.index, method="ffill").fillna(0)

        daily_return = prices["close"].pct_change()
        strategy_return = daily_return * signal_daily
        sharpe = self._annualized_sharpe(strategy_return)

        metrics_rows = []
        for hold in hold_days:
            forward_return = prices["close"].pct_change(hold).shift(-hold)
            triggered = signal_daily > 0
            avg_return = forward_return[triggered].mean()
            win_rate = (forward_return[triggered] > 0).mean()
            metrics_rows.append(
                {
                    "industry": industry_name,
                    "etf": etf_symbol,
                    "price_source": price_source,
                    "hold_days": hold,
                    "signal_count": int(triggered.sum()),
                    "avg_forward_return": avg_return,
                    "win_rate": win_rate,
                    "sharpe": sharpe,
                }
            )

        metrics_df = pd.DataFrame(metrics_rows)
        signal_out = pd.DataFrame(
            {"signal": signal_daily, "strategy_return": strategy_return}
        )
        return BacktestResult(metrics_df, prices, signal_out)

    def _safe_run(self, name: str, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            self.logger.error(f"{name}执行失败: {exc}")
            print(f"{name}执行失败: {exc}")
            return None

    def compare_industries(
        self, auto_df: pd.DataFrame, estate_df: pd.DataFrame
    ) -> Dict[str, pd.DataFrame | float]:
        if auto_df.empty or estate_df.empty:
            self.logger.warning("行业对比数据不足，跳过比较")
            return {}

        auto = auto_df["Diffusion_Index_A"].rename("auto")
        estate = estate_df["Diffusion_Index_A"].rename("estate")
        combined = pd.concat([auto, estate], axis=1).dropna()

        rolling_corr = combined["auto"].rolling(12).corr(combined["estate"])
        cross_corr_df = self._cross_correlation(combined["auto"], combined["estate"])

        with pd.ExcelWriter(self.output_dir / "industry_comparison.xlsx") as writer:
            combined.to_excel(writer, sheet_name="diffusion")
            rolling_corr.to_frame("rolling_corr_12").to_excel(
                writer, sheet_name="rolling_corr"
            )
            cross_corr_df.to_excel(writer, sheet_name="cross_corr", index=False)

        fig = plt.figure(figsize=(12, 8))
        ax1 = plt.subplot(2, 1, 1)
        ax1.plot(combined.index, combined["auto"], label="汽车行业")
        ax1.plot(combined.index, combined["estate"], label="房地产行业")
        ax1.set_title("行业扩散指数对比")
        ax1.legend(loc="upper left")
        ax1.grid(True)

        ax2 = plt.subplot(2, 1, 2, sharex=ax1)
        ax2.plot(rolling_corr.index, rolling_corr, color="purple")
        ax2.axhline(0, color="gray", linestyle="--", linewidth=0.8)
        ax2.set_title("滚动相关系数(12期)")
        ax2.grid(True)

        fig.tight_layout()
        compare_plot_df = pd.concat(
            [combined, rolling_corr.rename("rolling_corr_12")],
            axis=1,
        )
        self._save_figure_with_html(
            fig,
            self.output_dir / "industry_comparison.png",
            title="行业扩散指数对比",
            chart_df=compare_plot_df,
            series_labels={
                "auto": "汽车行业",
                "estate": "房地产行业",
                "rolling_corr_12": "滚动相关系数(12期)",
            },
        )
        plt.close(fig)

        avg_corr = float(rolling_corr.dropna().mean()) if not rolling_corr.dropna().empty else np.nan
        best_lag_row = cross_corr_df.loc[cross_corr_df["corr"].abs().idxmax()] if not cross_corr_df.empty else pd.Series(dtype=float)
        return {
            "combined": combined,
            "rolling_corr": rolling_corr.to_frame("rolling_corr_12"),
            "cross_corr": cross_corr_df,
            "avg_corr": avg_corr,
            "best_lag": float(best_lag_row.get("lag", np.nan)),
            "best_lag_corr": float(best_lag_row.get("corr", np.nan)),
        }

    def dynamic_weight_analysis(
        self,
        industry_name: str,
        indicator_ids: List[str],
        etf_symbol: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, object]:
        raw_df = self.industry._load_industry_data(
            indicator_ids=indicator_ids,
            start_date=start_date,
            end_date=end_date,
        )
        if raw_df.empty:
            self.logger.warning(f"{industry_name}动态权重分析失败: 无指标数据")
            return {}

        raw_df.index = pd.to_datetime(raw_df.index, errors="coerce")
        raw_df = raw_df[raw_df.index.notna()]
        raw_df = raw_df[~raw_df.index.duplicated(keep="last")]

        resample_methods = self.industry._get_resample_methods(list(raw_df.columns))
        daily_df = raw_df.asfreq("D").interpolate(method="time").ffill().bfill()
        period_df = daily_df.resample("ME").agg(resample_methods)
        direction_df = period_df.apply(lambda x: np.sign(x.diff()))

        equal_df = self._build_weighted_index(period_df, direction_df, None)
        vol_df = self._build_weighted_index(
            period_df, direction_df, self._volatility_weights(period_df)
        )

        etf_prices = self._fetch_etf_prices(etf_symbol, start_date, end_date)
        target_series = pd.Series(dtype=float)
        if not etf_prices.empty:
            target_series = (
                etf_prices["close"].resample("ME").last().pct_change()
            )
        corr_weights = self._correlation_weights(period_df, target_series)
        corr_df = self._build_weighted_index(period_df, direction_df, corr_weights)

        method_metrics = self._evaluate_method_metrics(
            equal_df=equal_df,
            vol_df=vol_df,
            corr_df=corr_df,
            etf_prices=etf_prices,
            fallback_period_df=period_df,
        )
        best_method = "equal"
        if not method_metrics.empty and method_metrics["sharpe"].notna().any():
            best_method = str(
                method_metrics.sort_values("sharpe", ascending=False)
                .iloc[0]["method"]
            )

        safe_name = industry_name.replace("/", "_")
        with pd.ExcelWriter(
            self.output_dir / f"{safe_name}_dynamic_weights.xlsx"
        ) as writer:
            period_df.to_excel(writer, sheet_name="period")
            equal_df.to_excel(writer, sheet_name="equal")
            vol_df.to_excel(writer, sheet_name="volatility")
            corr_df.to_excel(writer, sheet_name="correlation")
            method_metrics.to_excel(writer, sheet_name="method_metrics", index=False)

        fig = plt.figure(figsize=(12, 8))
        ax = plt.subplot(1, 1, 1)
        ax.plot(equal_df.index, equal_df["Diffusion_Index_A"], label="Equal")
        ax.plot(vol_df.index, vol_df["Diffusion_Index_A"], label="Volatility")
        if not corr_df.empty:
            ax.plot(corr_df.index, corr_df["Diffusion_Index_A"], label="Correlation")
        ax.set_title(f"{industry_name} 动态权重扩散指数对比")
        ax.legend(loc="upper left")
        ax.grid(True)
        fig.tight_layout()
        dynamic_plot_df = pd.DataFrame(index=equal_df.index)
        dynamic_plot_df["equal"] = equal_df["Diffusion_Index_A"]
        dynamic_plot_df["volatility"] = vol_df["Diffusion_Index_A"]
        if not corr_df.empty and "Diffusion_Index_A" in corr_df.columns:
            dynamic_plot_df["correlation"] = corr_df["Diffusion_Index_A"]
        self._save_figure_with_html(
            fig,
            self.output_dir / f"{safe_name}_dynamic_weights.png",
            title=f"{industry_name} 动态权重扩散指数对比",
            chart_df=dynamic_plot_df,
            series_labels={
                "equal": "Equal",
                "volatility": "Volatility",
                "correlation": "Correlation",
            },
        )
        plt.close(fig)

        return {
            "industry": industry_name,
            "best_method": best_method,
            "method_metrics": method_metrics,
        }

    def performance_report(
        self,
        indicator_ids: List[str],
        start_date: str,
        end_date: str,
    ) -> None:
        timings = []
        connector_no_cache = DataConnector(
            config_loader=self.industry.cfg, enable_cache=False
        )
        connector_cache = DataConnector(
            config_loader=self.industry.cfg, enable_cache=True
        )

        for indicator_id in indicator_ids:
            config = self.industry.cfg.get_config(indicator_id)
            data_source = (config or {}).get("data_source_type", "").upper()
            if data_source not in {"EXCEL", "SQLITE"}:
                continue

            try:
                start = time.perf_counter()
                connector_no_cache.fetch_data_by_id(
                    indicator_id, start_date, end_date
                )
                elapsed_no_cache = time.perf_counter() - start

                connector_cache._cache.clear()
                start = time.perf_counter()
                connector_cache.fetch_data_by_id(
                    indicator_id, start_date, end_date
                )
                first_cached = time.perf_counter() - start

                start = time.perf_counter()
                connector_cache.fetch_data_by_id(
                    indicator_id, start_date, end_date
                )
                second_cached = time.perf_counter() - start
            except Exception as exc:
                self.logger.warning(
                    f"性能测试跳过: {indicator_id}, {exc}"
                )
                continue

            timings.append(
                {
                    "indicator_id": indicator_id,
                    "no_cache_sec": elapsed_no_cache,
                    "first_cached_sec": first_cached,
                    "second_cached_sec": second_cached,
                }
            )

        report_df = pd.DataFrame(timings)
        report_df.to_excel(
            self.output_dir / "performance_report.xlsx", index=False
        )

    def _fetch_etf_prices(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError:
            self.logger.warning("AKShare未安装，ETF数据不可用")
            return pd.DataFrame()

        df = pd.DataFrame()
        try:
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="",
            )
        except Exception as exc:
            self.logger.warning(f"ETF数据获取失败(EM): {symbol}, {exc}")

        if df is None or df.empty:
            try:
                sina_symbol = self._to_sina_symbol(symbol)
                df = ak.fund_etf_hist_sina(symbol=sina_symbol)
            except Exception as exc:
                self.logger.warning(f"ETF数据获取失败(Sina): {symbol}, {exc}")
                return pd.DataFrame()

        return self._normalize_etf_df(df)

    def _to_sina_symbol(self, symbol: str) -> str:
        if symbol.lower().startswith(("sh", "sz")):
            return symbol.lower()
        return f"sh{symbol}"

    def _normalize_etf_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        date_col = None
        for candidate in ["日期", "date", "交易日期"]:
            if candidate in df.columns:
                date_col = candidate
                break
        if date_col is None:
            return pd.DataFrame()

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).set_index(date_col)
        df = df[~df.index.duplicated(keep="last")]

        close_col = None
        for candidate in ["收盘", "close", "收盘价", "单位净值"]:
            if candidate in df.columns:
                close_col = candidate
                break
        if close_col is None:
            return pd.DataFrame()

        df = df[[close_col]].rename(columns={close_col: "close"}).sort_index()
        return df

    def _build_synthetic_prices(
        self, period_df: pd.DataFrame, start_date: str, end_date: str
    ) -> pd.DataFrame:
        if period_df.empty:
            return pd.DataFrame()

        if "Base_Index_B" in period_df.columns:
            series = period_df["Base_Index_B"].copy()
        else:
            series = period_df["Diffusion_Index_A"].cumsum() + 100

        series.index = pd.to_datetime(series.index, errors="coerce")
        series = series[series.index.notna()]
        series = series[~series.index.duplicated(keep="last")]
        daily = series.asfreq("D").ffill()

        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        daily = daily.loc[start_ts:end_ts]
        return daily.to_frame("close")

    def _build_weighted_index(
        self,
        period_df: pd.DataFrame,
        direction_df: pd.DataFrame,
        weights: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        if period_df.empty:
            return pd.DataFrame()

        if weights is None or weights.empty:
            weighted = direction_df.mean(axis=1)
        else:
            aligned = weights.reindex(direction_df.index).ffill()
            numerator = (direction_df * aligned).sum(axis=1)
            denominator = aligned.sum(axis=1).replace(0, np.nan)
            weighted = numerator / denominator

        result = pd.DataFrame({"Diffusion_Index_A": weighted})
        result["Base_Index_B"] = 100 + result["Diffusion_Index_A"].cumsum()
        result["YoY_Index_C"] = (
            result["Base_Index_B"] / result["Base_Index_B"].shift(12) - 1
        ) * 100
        return result

    def _evaluate_method_metrics(
        self,
        equal_df: pd.DataFrame,
        vol_df: pd.DataFrame,
        corr_df: pd.DataFrame,
        etf_prices: pd.DataFrame,
        fallback_period_df: pd.DataFrame,
    ) -> pd.DataFrame:
        method_map = {
            "equal": equal_df,
            "volatility": vol_df,
            "correlation": corr_df,
        }

        if etf_prices.empty:
            etf_prices = self._build_synthetic_prices(
                fallback_period_df,
                str(fallback_period_df.index.min().date()),
                str(fallback_period_df.index.max().date()),
            )

        price_ret = etf_prices["close"].resample("ME").last().pct_change()
        rows = []
        for method_name, method_df in method_map.items():
            if method_df is None or method_df.empty:
                continue
            signal = np.where(method_df["Diffusion_Index_A"] > 0, 1, -1)
            signal = pd.Series(signal, index=method_df.index)
            aligned_signal = signal.reindex(price_ret.index, method="ffill").fillna(0)
            strategy_ret = aligned_signal * price_ret
            rows.append(
                {
                    "method": method_name,
                    "sharpe": self._annualized_sharpe(strategy_ret.dropna()) * np.sqrt(12 / 252),
                    "avg_monthly_return": strategy_ret.mean(),
                    "win_rate": (strategy_ret > 0).mean(),
                }
            )
        return pd.DataFrame(rows)

    def write_conclusion_report(
        self,
        compare_result: Optional[Dict[str, object]],
        auto_dynamic: Optional[Dict[str, object]],
        estate_dynamic: Optional[Dict[str, object]],
        auto_backtest: Optional[BacktestResult],
        estate_backtest: Optional[BacktestResult],
    ) -> None:
        compare_result = compare_result or {}
        auto_dynamic = auto_dynamic or {}
        estate_dynamic = estate_dynamic or {}

        divergence_lines = self._build_divergence_lines(compare_result)
        auto_best = auto_dynamic.get("best_method", "unknown")
        estate_best = estate_dynamic.get("best_method", "unknown")

        auto_bt_text = self._format_backtest_lines("汽车行业", auto_backtest)
        estate_bt_text = self._format_backtest_lines("房地产行业", estate_backtest)

        avg_corr = compare_result.get("avg_corr", np.nan)
        best_lag = compare_result.get("best_lag", np.nan)
        best_lag_corr = compare_result.get("best_lag_corr", np.nan)

        content = [
            "# 行业景气度高级结论",
            "",
            "## 1. 最优动态权重方法",
            f"- 汽车行业最优方法: {auto_best}",
            f"- 房地产行业最优方法: {estate_best}",
            "- 判定依据: method_metrics 中的策略夏普比率（越高越优）。",
            "",
            "## 2. 多行业相关性与领先滞后",
            f"- 平均滚动相关系数(12期): {avg_corr:.4f}" if pd.notna(avg_corr) else "- 平均滚动相关系数(12期): 无可用结果",
            (
                f"- 交叉相关最强滞后期: lag={int(best_lag)}，相关系数={best_lag_corr:.4f}"
                if pd.notna(best_lag) and pd.notna(best_lag_corr)
                else "- 交叉相关最强滞后期: 无可用结果"
            ),
            "",
            "## 3. 分化/同步时期识别",
            *divergence_lines,
            "",
            "## 4. 信号回测摘要",
            *auto_bt_text,
            *estate_bt_text,
            "",
            "## 5. 宏观背景简析（模板）",
            "- 分化时期可优先检查: 房地产政策边际变化、汽车促消费政策、信贷脉冲与原材料价格变化。",
            "- 同步时期可优先检查: 总需求回升/回落、利率环境变化、信用扩张节奏。",
        ]

        report_path = self.output_dir / "industry_conclusion.md"
        report_path.write_text("\n".join(content), encoding="utf-8")

    def _build_divergence_lines(self, compare_result: Dict[str, object]) -> List[str]:
        combined = compare_result.get("combined")
        if not isinstance(combined, pd.DataFrame) or combined.empty:
            return ["- 无可用分化识别结果"]

        diff = (combined["auto"] - combined["estate"]).dropna()
        if diff.empty:
            return ["- 无可用分化识别结果"]

        threshold = diff.abs().quantile(0.75)
        divergence = diff[diff.abs() >= threshold]
        if divergence.empty:
            return ["- 未识别到显著分化时期"]

        top_points = divergence.abs().sort_values(ascending=False).head(5).index
        lines = []
        for dt in top_points:
            direction = "汽车强于地产" if diff.loc[dt] > 0 else "地产强于汽车"
            lines.append(f"- {dt.strftime('%Y-%m')} 分化显著，{direction}，差值={diff.loc[dt]:.4f}")
        return lines

    def _format_backtest_lines(
        self, industry_name: str, backtest_result: Optional[BacktestResult]
    ) -> List[str]:
        if not isinstance(backtest_result, BacktestResult) or backtest_result.metrics.empty:
            return [f"- {industry_name}: 无可用回测结果"]

        rows = [f"- {industry_name}:"]
        for _, row in backtest_result.metrics.iterrows():
            rows.append(
                "  - "
                f"持有{int(row['hold_days'])}日, 平均远期收益={row['avg_forward_return']:.4f}, "
                f"胜率={row['win_rate']:.2%}, 夏普={row['sharpe']:.4f}"
            )
        return rows

    def _volatility_weights(self, period_df: pd.DataFrame) -> pd.DataFrame:
        vol = period_df.rolling(12, min_periods=6).std()
        inv_vol = 1 / vol.replace(0, np.nan)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        return weights

    def _correlation_weights(
        self, period_df: pd.DataFrame, target_series: pd.Series
    ) -> pd.DataFrame:
        if target_series is None or target_series.empty:
            return pd.DataFrame()

        returns = period_df.pct_change()
        weights = {}
        for col in returns.columns:
            corr = returns[col].rolling(12, min_periods=6).corr(target_series)
            weights[col] = corr.abs()

        weights_df = pd.DataFrame(weights)
        weights_df = weights_df.div(weights_df.sum(axis=1), axis=0)
        return weights_df

    def _cross_correlation(
        self, series_a: pd.Series, series_b: pd.Series, max_lag: int = 12
    ) -> pd.DataFrame:
        series_a = series_a.dropna()
        series_b = series_b.dropna()
        common = series_a.index.intersection(series_b.index)
        series_a = series_a.loc[common]
        series_b = series_b.loc[common]

        results = []
        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                corr = series_a[:lag].corr(series_b[-lag:])
            elif lag > 0:
                corr = series_a[lag:].corr(series_b[:-lag])
            else:
                corr = series_a.corr(series_b)
            results.append({"lag": lag, "corr": corr})

        return pd.DataFrame(results)

    def _save_backtest(self, result: BacktestResult, industry_name: str) -> None:
        if result.metrics.empty:
            return

        safe_name = industry_name.replace("/", "_")
        with pd.ExcelWriter(
            self.output_dir / f"{safe_name}_backtest.xlsx"
        ) as writer:
            result.metrics.to_excel(writer, sheet_name="metrics", index=False)
            result.price_df.to_excel(writer, sheet_name="prices")
            result.signal_df.to_excel(writer, sheet_name="signals")

        fig = plt.figure(figsize=(12, 6))
        ax = plt.subplot(1, 1, 1)
        ax.plot(result.price_df.index, result.price_df["close"], label="ETF")
        signal = result.signal_df["signal"].replace(0, np.nan)
        ax2 = ax.twinx()
        ax2.plot(signal.index, signal, color="orange", alpha=0.5, label="signal")
        ax.set_title(f"{industry_name} ETF与信号")
        ax.grid(True)
        fig.tight_layout()
        backtest_plot_df = pd.DataFrame(index=result.price_df.index)
        backtest_plot_df["etf_close"] = result.price_df["close"]
        backtest_plot_df["signal"] = result.signal_df["signal"].reindex(result.price_df.index)
        self._save_figure_with_html(
            fig,
            self.output_dir / f"{safe_name}_backtest.png",
            title=f"{industry_name} ETF与信号",
            chart_df=backtest_plot_df,
            series_labels={
                "etf_close": "ETF收盘价",
                "signal": "信号",
            },
        )
        plt.close(fig)

    def _save_figure_with_html(
        self,
        fig: plt.Figure,
        png_path: Path,
        title: str,
        chart_df: Optional[pd.DataFrame] = None,
        series_labels: Optional[Dict[str, str]] = None,
    ) -> None:
        fig.savefig(png_path, dpi=150)
        if chart_df is None or chart_df.empty:
            return

        clean_df = chart_df.copy()
        clean_df.index = pd.to_datetime(clean_df.index, errors="coerce")
        clean_df = clean_df[clean_df.index.notna()]
        clean_df = clean_df[~clean_df.index.duplicated(keep="last")].sort_index()
        if clean_df.empty:
            return

        labels = series_labels or {}
        x_data = [idx.strftime("%Y-%m-%d") for idx in clean_df.index]
        series = []
        for column in clean_df.columns:
            values = [
                None if pd.isna(value) else float(value)
                for value in clean_df[column].tolist()
            ]
            series.append(
                {
                    "name": labels.get(column, column),
                    "type": "line",
                    "showSymbol": False,
                    "smooth": True,
                    "data": values,
                }
            )

        option = {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 30},
            "grid": {"left": "3%", "right": "4%", "bottom": "16%", "containLabel": True},
            "xAxis": {"type": "category", "data": x_data, "boundaryGap": False},
            "yAxis": {"type": "value", "scale": True},
            "dataZoom": [
                {"type": "inside", "start": 0, "end": 100},
                {"type": "slider", "start": 0, "end": 100},
            ],
            "series": series,
        }

        html_content = f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <script src=\"https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js\"></script>
  <style>
    body {{ margin: 0; padding: 16px; background: #f7f7f7; font-family: Arial, sans-serif; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; background: #fff; border-radius: 8px; padding: 12px; }}
    #chart {{ width: 100%; height: 560px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div id=\"chart\"></div>
  </div>
  <script>
    const chart = echarts.init(document.getElementById('chart'));
    const option = {json.dumps(option, ensure_ascii=False)};
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
  </script>
</body>
</html>
"""
        png_path.with_suffix(".html").write_text(html_content, encoding="utf-8")

    @staticmethod
    def _annualized_sharpe(daily_returns: pd.Series) -> float:
        daily_returns = daily_returns.dropna()
        if daily_returns.empty:
            return np.nan
        std = daily_returns.std()
        if std == 0 or np.isnan(std):
            return np.nan
        return daily_returns.mean() / std * np.sqrt(252)
