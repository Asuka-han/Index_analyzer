# -*- coding: utf-8 -*-
"""
Created on Sun Aug 17 15:34:30 2025

@author: imado
"""

# update_data.py
import argparse
import logging
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.data_pipeline import DataPipeline

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("DataUpdater")


def main():
    parser = argparse.ArgumentParser(description="高频数据更新脚本")
    parser.add_argument(
        "--category",
        type=str,
        default="all",
        help="指定更新类别 (all, 经济指标, 货币指标, 信用指标, 国际指标, 估值指标, 资金指标)",
    )
    parser.add_argument(
        "--incremental", action="store_true", help="使用增量更新模式"
    )
    parser.add_argument(
        "--reprocess", action="store_true", help="重新处理所有数据"
    )
    args = parser.parse_args()

    # 需要更新的类别
    categories = [
        "经济指标",
        "货币指标",
        "信用指标",
        "国际指标",
        "估值指标",
        "资金指标",
    ]

    if args.category != "all":
        categories = [args.category]

    # 更新每个类别的数据
    for category in categories:
        try:
            logger.info(f"开始更新 {category} 数据...")
            DataPipeline.update_and_process_category(
                category=category,
                incremental=args.incremental,
                reprocess=args.reprocess,
            )
            logger.info(f"{category} 数据更新完成")
        except Exception as e:
            logger.error(f"{category} 数据更新失败: {str(e)}")

    logger.info("所有数据更新任务完成")


if __name__ == "__main__":
    main()
