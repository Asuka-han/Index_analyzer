# -*- coding: utf-8 -*-
"""
Created on Thu Feb 12 2026

@author: imado
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from core.config_loader import ConfigLoader
from core.data_connector import DataConnector

# 设置全局字体（支持Windows/macOS/Linux）
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "WenQuanYi Micro Hei",
    "STHeiti",
]
plt.rcParams["axes.unicode_minus"] = False


class IndustryAnalyzer:
    def __init__(self):
        self.cfg = ConfigLoader()
        self.connector = DataConnector(config_loader=self.cfg)
        self.logger = logging.getLogger("IndustryAnalyzer")

        # 指标ID需在配置表中存在
        self.auto_indicators = [
            "AUTO_SALES_W",
            "AUTO_PRODUCTION_M",
            "TIRE_OPERATING_RATE",
            "STEEL_PRICE_INDEX",
        ]
        self.real_estate_indicators = [
            "REAL_ESTATE_SALES",
            "REAL_ESTATE_INVESTMENT",
            "HOUSE_PRICE_INDEX",
            "LAND_TRANSACTION_AREA",
        ]

        self.industry_indicator_map = {
            "汽车行业": self.auto_indicators,
            "房地产行业": self.real_estate_indicators,
        }

    def get_available_indicators(self, industry_name: str) -> List[str]:
        expected = self.industry_indicator_map.get(industry_name, [])
        enabled_ids = set(self.cfg.get_enabled_ids())
        return [indicator_id for indicator_id in expected if indicator_id in enabled_ids]

    def _normalize_indicator_ids(
        self, industry_name: str, indicator_ids: Optional[List[str]]
    ) -> List[str]:
        available_ids = self.get_available_indicators(industry_name)
        if indicator_ids:
            selected = [item for item in indicator_ids if item in available_ids]
            if selected:
                return selected
            self.logger.warning(f"{industry_name}传入指标均不可用，回退为默认可用指标")
        return available_ids

    def analyze_auto_industry(
        self,
        start_date: str = "2012-01-01",
        end_date: str = None,
        indicator_ids: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
        show: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        chosen_ids = self._normalize_indicator_ids("汽车行业", indicator_ids)
        return self._analyze_industry(
            industry_name="汽车行业",
            indicator_ids=chosen_ids,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            show=show,
        )

    def analyze_real_estate_industry(
        self,
        start_date: str = "2012-01-01",
        end_date: str = None,
        indicator_ids: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
        show: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        chosen_ids = self._normalize_indicator_ids("房地产行业", indicator_ids)
        return self._analyze_industry(
            industry_name="房地产行业",
            indicator_ids=chosen_ids,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            show=show,
        )

    def analyze_both_industries(
        self,
        start_date: str = "2012-01-01",
        end_date: Optional[str] = None,
        auto_indicator_ids: Optional[List[str]] = None,
        real_estate_indicator_ids: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
        show: bool = False,
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        auto_result = self.analyze_auto_industry(
            start_date=start_date,
            end_date=end_date,
            indicator_ids=auto_indicator_ids,
            output_dir=output_dir,
            show=show,
        )
        estate_result = self.analyze_real_estate_industry(
            start_date=start_date,
            end_date=end_date,
            indicator_ids=real_estate_indicator_ids,
            output_dir=output_dir,
            show=show,
        )

        if output_dir is not None:
            self._save_full_report(
                output_dir=output_dir,
                auto_result=auto_result,
                estate_result=estate_result,
                auto_indicator_ids=self._normalize_indicator_ids("汽车行业", auto_indicator_ids),
                estate_indicator_ids=self._normalize_indicator_ids(
                    "房地产行业", real_estate_indicator_ids
                ),
            )

        return {"汽车行业": auto_result, "房地产行业": estate_result}

    def _analyze_industry(
        self,
        industry_name: str,
        indicator_ids: List[str],
        start_date: str,
        end_date: Optional[str],
        output_dir: Optional[Path],
        show: bool,
    ) -> Dict[str, pd.DataFrame]:
        df = self._load_industry_data(
            indicator_ids=indicator_ids,
            start_date=start_date,
            end_date=end_date,
        )
        if df.empty:
            self.logger.warning(f"{industry_name}无可用数据")
            return {"period_df": pd.DataFrame(), "signal": pd.DataFrame()}

        period_df, direction_df = self._calculate_signals(df)
        fig = self._visualize(
            period_df, fig_name=f"{industry_name}景气度", show=show
        )
        if output_dir is not None:
            self._save_results(
                industry_name=industry_name,
                period_df=period_df,
                direction_df=direction_df,
                fig=fig,
                output_dir=output_dir,
            )
        return {"period_df": period_df, "signal": direction_df}

    def _load_industry_data(
        self,
        indicator_ids: List[str],
        start_date: str,
        end_date: Optional[str],
    ) -> pd.DataFrame:
        if end_date is None:
            end_date = pd.Timestamp.today().strftime("%Y-%m-%d")

        series_list = []
        for indicator_id in indicator_ids:
            try:
                df = self.connector.fetch_data_by_id(
                    indicator_id=indicator_id,
                    start_date=start_date,
                    end_date=end_date,
                )
                if df is None or df.empty:
                    self.logger.warning(f"无数据: {indicator_id}")
                    continue
                series_list.append(df)
            except Exception as exc:
                self.logger.error(
                    f"加载指标失败: {indicator_id}, {str(exc)}"
                )

        if not series_list:
            return pd.DataFrame()

        combined = pd.concat(series_list, axis=1).sort_index()
        return combined

    def _get_resample_methods(self, columns: List[str]) -> Dict[str, str]:
        methods = {}
        for column in columns:
            config = self.cfg.get_config(column)
            method = config.get("freq_method") if config else None
            methods[column] = method or "last"
        return methods

    def _calculate_signals(self, df: pd.DataFrame, period: str = "ME"):
        df = df.copy()
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[df.index.notna()]
        df = df[~df.index.duplicated(keep="last")]
        df = df.asfreq("D").sort_index()
        df = df.interpolate(method="time").ffill().bfill()

        resample_methods = self._get_resample_methods(list(df.columns))
        period_df = df.resample(period).agg(resample_methods)

        direction_df = period_df.apply(lambda x: np.sign(x.diff()))
        direction_df = direction_df.add_suffix("_Direction")
        direction_df["final_signal"] = np.where(
            direction_df.sum(axis=1) > 0, 1, -1
        )

        period_df["Diffusion_Index_A"] = direction_df.mean(axis=1)
        period_df["Period_Change"] = period_df["Diffusion_Index_A"]

        base_value = 100
        period_df = period_df.sort_index()
        period_df["Base_Index_B"] = (
            base_value + period_df["Diffusion_Index_A"].cumsum()
        )
        period_df["Base_Index_B"] = (
            period_df["Base_Index_B"].ffill().interpolate(method="time")
        )

        period_df["YoY_Index_C"] = (
            period_df["Base_Index_B"] / period_df["Base_Index_B"].shift(12)
            - 1
        ) * 100
        period_df["YoY_Index_C"] = period_df["YoY_Index_C"].ffill().bfill()

        return period_df, direction_df

    def _visualize(self, result_df, fig_name="行业景气度", show: bool = True):
        result_df = result_df[
            ["Diffusion_Index_A", "Base_Index_B", "YoY_Index_C"]
        ]

        fig = plt.figure(figsize=(12, 10))
        fig.suptitle(fig_name, fontsize=16, fontweight="bold", y=0.98)

        ax1 = plt.subplot(3, 1, 1)
        ax1.plot(result_df.index, result_df["Diffusion_Index_A"], color="blue")
        ax1.axhline(0, color="red", linestyle="--", linewidth=0.8)
        ax1.set_title("扩散指数A", pad=15)
        ax1.set_ylabel("Index Value")
        ax1.set_ylim(-1, 1)
        ax1.grid(True)
        ax1.legend(["Index", "Zero Line"], loc="upper right")

        ax2 = plt.subplot(3, 1, 2, sharex=ax1)
        ax2.plot(result_df.index, result_df["Base_Index_B"], color="green")
        ax2.set_title("基准指数B", pad=15)
        ax2.set_ylabel("Index Value")
        ax2.grid(True)

        ax3 = plt.subplot(3, 1, 3, sharex=ax1)
        ax3.plot(result_df.index, result_df["YoY_Index_C"], color="purple")
        ax3.set_title("同比指数C", pad=15)
        ax3.set_ylabel("同比变化 (%)")
        ax3.grid(True)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.gcf().autofmt_xdate()
        plt.subplots_adjust(hspace=0.3, top=0.9)
        if show:
            plt.show()
        return fig

    def _save_results(
        self,
        industry_name: str,
        period_df: pd.DataFrame,
        direction_df: pd.DataFrame,
        fig: plt.Figure,
        output_dir: Path,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = industry_name.replace("/", "_")

        excel_path = output_dir / f"{safe_name}_analysis.xlsx"
        with pd.ExcelWriter(excel_path) as writer:
            period_df.to_excel(writer, sheet_name="index")
            direction_df.to_excel(writer, sheet_name="signal")

        fig_path = output_dir / f"{safe_name}_charts.png"
        fig.savefig(fig_path, dpi=150)
        chart_df = period_df[["Diffusion_Index_A", "Base_Index_B", "YoY_Index_C"]].copy()
        self._save_interactive_chart_html(
            html_path=fig_path.with_suffix(".html"),
            title=f"{industry_name}景气度图表",
            chart_df=chart_df,
            series_labels={
                "Diffusion_Index_A": "扩散指数A",
                "Base_Index_B": "基准指数B",
                "YoY_Index_C": "同比指数C",
            },
        )
        plt.close(fig)

    def _save_interactive_chart_html(
        self,
        html_path: Path,
        title: str,
        chart_df: pd.DataFrame,
        series_labels: Dict[str, str],
    ) -> None:
        if chart_df is None or chart_df.empty:
            return

        clean_df = chart_df.copy()
        clean_df.index = pd.to_datetime(clean_df.index, errors="coerce")
        clean_df = clean_df[clean_df.index.notna()]
        clean_df = clean_df[~clean_df.index.duplicated(keep="last")].sort_index()
        if clean_df.empty:
            return

        x_data = [idx.strftime("%Y-%m-%d") for idx in clean_df.index]
        series = []
        for column in clean_df.columns:
            values = [
                None if pd.isna(value) else float(value)
                for value in clean_df[column].tolist()
            ]
            series.append(
                {
                    "name": series_labels.get(column, column),
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
        html_path.write_text(html_content, encoding="utf-8")

    def _save_full_report(
        self,
        output_dir: Path,
        auto_result: Dict[str, pd.DataFrame],
        estate_result: Dict[str, pd.DataFrame],
        auto_indicator_ids: List[str],
        estate_indicator_ids: List[str],
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_df = pd.DataFrame(
            {
                "industry": ["汽车行业", "房地产行业"],
                "selected_indicators": [
                    ", ".join(auto_indicator_ids),
                    ", ".join(estate_indicator_ids),
                ],
            }
        )

        full_path = output_dir / "industry_full_report.xlsx"
        with pd.ExcelWriter(full_path) as writer:
            summary_df.to_excel(writer, sheet_name="summary", index=False)
            auto_result.get("period_df", pd.DataFrame()).to_excel(
                writer, sheet_name="auto_index"
            )
            auto_result.get("signal", pd.DataFrame()).to_excel(
                writer, sheet_name="auto_signal"
            )
            estate_result.get("period_df", pd.DataFrame()).to_excel(
                writer, sheet_name="estate_index"
            )
            estate_result.get("signal", pd.DataFrame()).to_excel(
                writer, sheet_name="estate_signal"
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    analyzer = IndustryAnalyzer()
    output_dir = Path("result") / "industry"
    analyzer.analyze_auto_industry(output_dir=output_dir)
    analyzer.analyze_real_estate_industry(output_dir=output_dir)
