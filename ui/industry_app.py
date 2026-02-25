# -*- coding: utf-8 -*-
"""Streamlit UI for industry index analysis."""

from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import analyzers.industry_analyzer as industry_analyzer_module
import analyzers.industry_advanced as industry_advanced_module

IndustryAnalyzer = industry_analyzer_module.IndustryAnalyzer
IndustryAdvancedAnalyzer = industry_advanced_module.IndustryAdvancedAnalyzer


APP_TITLE = "行业景气度指数"


def _list_files(paths: List[Path]) -> List[Path]:
    files = []
    for path in paths:
        if path.exists():
            files.extend([p for p in path.iterdir() if p.is_file()])
    return sorted(files)


def _display_images(image_items: List[dict]) -> None:
    if not image_items:
        st.info("暂无图片输出。")
        return
    for item in image_items:
        image_source = item.get("path") or item.get("data")
        st.image(image_source, caption=item["name"], use_container_width=True)


def _display_downloads(file_items: List[dict]) -> None:
    if not file_items:
        st.info("暂无输出文件。")
        return
    for item in file_items:
        st.download_button(
            label=f"下载 {item['name']}",
            data=item["data"],
            file_name=item["name"],
        )


def _display_markdowns(markdown_items: List[dict]) -> None:
    if not markdown_items:
        st.info("暂无结论文档输出。")
        return
    for item in markdown_items:
        with st.expander(item["name"], expanded=(item["name"] == "industry_conclusion.md")):
            st.markdown(item["text"])


def _display_htmls(html_items: List[dict]) -> None:
    if not html_items:
        st.info("暂无HTML输出。")
        return
    for item in html_items:
        with st.expander(item["name"], expanded=False):
            components.html(item["text"], height=520, scrolling=True)


def _load_output_files(
    output_dir: Path,
    name_prefixes: List[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    image_items = []
    excel_items = []
    markdown_items = []
    html_items = []
    for path in _list_files([output_dir]):
        if name_prefixes and not any(path.name.startswith(p) for p in name_prefixes):
            continue
        if path.suffix.lower() == ".png":
            image_items.append({"name": path.name, "path": str(path)})
        elif path.suffix.lower() == ".xlsx":
            try:
                excel_items.append({"name": path.name, "data": path.read_bytes()})
            except PermissionError:
                continue
        elif path.suffix.lower() == ".md":
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="gbk", errors="ignore")
            markdown_items.append({"name": path.name, "text": text})
        elif path.suffix.lower() == ".html":
            try:
                html_text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                html_text = path.read_text(encoding="gbk", errors="ignore")
            html_items.append({"name": path.name, "text": html_text})
    return image_items, excel_items, markdown_items, html_items


def _run_basic(
    industry: str,
    start_date: str,
    end_date: str,
    indicator_ids: Optional[List[str]],
    output_dir: Path,
) -> None:
    analyzer = IndustryAnalyzer()
    if industry == "汽车行业":
        analyzer.analyze_auto_industry(
            start_date=start_date,
            end_date=end_date,
            indicator_ids=indicator_ids,
            output_dir=output_dir,
            show=False,
        )
    else:
        analyzer.analyze_real_estate_industry(
            start_date=start_date,
            end_date=end_date,
            indicator_ids=indicator_ids,
            output_dir=output_dir,
            show=False,
        )

    analyzer.analyze_both_industries(
        start_date=start_date,
        end_date=end_date,
        auto_indicator_ids=(indicator_ids if industry == "汽车行业" else None),
        real_estate_indicator_ids=(indicator_ids if industry == "房地产行业" else None),
        output_dir=output_dir,
        show=False,
    )


def _run_advanced(
    start_date: str,
    end_date: str,
    output_dir: Path,
) -> None:
    global IndustryAdvancedAnalyzer
    importlib.reload(industry_advanced_module)
    IndustryAdvancedAnalyzer = industry_advanced_module.IndustryAdvancedAnalyzer
    analyzer = IndustryAdvancedAnalyzer(output_dir=output_dir)
    analyzer.run_all(start_date=start_date, end_date=end_date)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=Source+Serif+4:wght@400;600&display=swap');
        .stApp {
            background: radial-gradient(circle at 10% 10%, #f7f3e8 0%, #f4f1ea 45%, #efece4 100%);
            color: #1f1f1f;
            font-family: 'IBM Plex Sans', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'Source Serif 4', serif;
            letter-spacing: 0.5px;
        }
        .hero {
            padding: 16px 24px;
            border: 1px solid #d9d2c3;
            border-radius: 12px;
            background: linear-gradient(135deg, #fff7e0 0%, #f0e4cf 100%);
            box-shadow: 0 12px 24px rgba(31, 31, 31, 0.08);
        }
        .tag {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #1f1f1f;
            color: #f4f1ea;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-right: 8px;
        }
        .panel {
            border: 1px solid #d9d2c3;
            border-radius: 12px;
            padding: 16px 18px;
            background: #fffdf7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero">
            <span class="tag">Industry Pulse</span>
            <span class="tag">Diffusion Index</span>
            <h1>行业景气度指数分析台</h1>
            <p>一键生成汽车与房地产行业景气度指数、回测与对比分析结果。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("分析设置")
    indicator_ids: Optional[List[str]] = None
    indicator_analyzer = IndustryAnalyzer()
    mode = st.sidebar.radio("分析类型", ["基础分析", "高级分析"], horizontal=True)
    if mode == "基础分析":
        industry = st.sidebar.selectbox("选择行业", ["汽车行业", "房地产行业"])
        available_indicators = indicator_analyzer.get_available_indicators(industry)
        indicator_ids = st.sidebar.multiselect(
            "指标选择（默认全选）",
            options=available_indicators,
            default=available_indicators,
        )
        if not indicator_ids:
            st.sidebar.warning("请至少选择一个指标")
    else:
        industry = "汽车行业"
        st.sidebar.info("高级分析将同时分析汽车与房地产行业，并生成对比结果。")
    start_date = st.sidebar.text_input("开始日期", value="2012-01-01")
    end_date = st.sidebar.text_input("结束日期", value="")
    st.sidebar.caption("日期格式: YYYY-MM-DD")

    run_btn = st.sidebar.button("开始分析")

    if "last_images" not in st.session_state:
        st.session_state.last_images = []
    if "last_excels" not in st.session_state:
        st.session_state.last_excels = []
    if "last_mode" not in st.session_state:
        st.session_state.last_mode = None
    if "last_industry" not in st.session_state:
        st.session_state.last_industry = None
    if "last_markdowns" not in st.session_state:
        st.session_state.last_markdowns = []
    if "last_htmls" not in st.session_state:
        st.session_state.last_htmls = []

    st.markdown("---")
    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("<div class='panel'><h3>运行日志</h3></div>", unsafe_allow_html=True)
        log_box = st.empty()

    with col2:
        st.markdown("<div class='panel'><h3>输出预览</h3></div>", unsafe_allow_html=True)
        st.caption("提示: 开始分析后输出结果会保存到对应文件夹，且每次运行会覆盖旧文件。")
        preview_box = st.empty()

    if run_btn:
        log_box.info("开始运行，请稍候...")
        if end_date == "":
            end_date = date.today().strftime("%Y-%m-%d")
            log_box.info(f"未填写结束日期，默认使用今天: {end_date}")
        try:
            if mode == "基础分析":
                output_dir = ROOT_DIR / "result" / "industry"
                with st.spinner("正在生成基础分析..."):
                    _run_basic(industry, start_date, end_date, indicator_ids, output_dir)
                log_box.success("基础分析完成。")
                image_items, excel_items, markdown_items, html_items = _load_output_files(
                    output_dir,
                    name_prefixes=[industry, "industry_full_report"],
                )
            else:
                output_dir = ROOT_DIR / "result" / "industry_advanced"
                with st.spinner("正在生成高级分析..."):
                    _run_advanced(start_date, end_date, output_dir)
                log_box.success("高级分析完成。")
                image_items, excel_items, markdown_items, html_items = _load_output_files(output_dir)

            st.session_state.last_images = image_items
            st.session_state.last_excels = excel_items
            st.session_state.last_markdowns = markdown_items
            st.session_state.last_htmls = html_items
            st.session_state.last_mode = mode
            st.session_state.last_industry = industry

            with preview_box:
                label = (
                    "基础分析输出预览"
                    if st.session_state.last_mode == "基础分析"
                    else "高级分析输出预览"
                )
                with st.expander(label, expanded=True):
                    st.subheader("图片")
                    _display_images(st.session_state.last_images)
                    st.subheader("表格")
                    _display_downloads(st.session_state.last_excels)
                    st.subheader("结论文档")
                    _display_markdowns(st.session_state.last_markdowns)
                    st.subheader("HTML预览")
                    _display_htmls(st.session_state.last_htmls)
        except Exception as exc:
            log_box.error(f"分析失败: {exc}")
    elif (
        st.session_state.last_images
        or st.session_state.last_excels
        or st.session_state.last_markdowns
        or st.session_state.last_htmls
    ):
        with preview_box:
            st.caption("提示: 若输出目录中的 *.xlsx 正在打开，将被跳过，请先关闭后再刷新。")
            label = (
                "基础分析输出预览"
                if st.session_state.last_mode == "基础分析"
                else "高级分析输出预览"
            )
            with st.expander(label, expanded=True):
                st.subheader("图片")
                _display_images(st.session_state.last_images)
                st.subheader("表格")
                _display_downloads(st.session_state.last_excels)
                st.subheader("结论文档")
                _display_markdowns(st.session_state.last_markdowns)
                st.subheader("HTML预览")
                _display_htmls(st.session_state.last_htmls)

    st.markdown("---")
    st.caption("提示:1. AKShare 数据需要网络可用；如 ETF 数据不可用，回测将使用合成价格序列。2. 请先关闭已打开的 *.xlsx 文件，再进行分析，否则会报错。")


if __name__ == "__main__":
    main()
