# -*- coding: utf-8 -*-
"""
Created on Wed Aug  6 22:17:58 2025

@author: imado

重构版DataPipeline：统一使用DataConnector的高级接口fetch_data_by_id
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Union
import logging
from datetime import datetime
from core.config_loader import ConfigLoader
from core.data_manager import DataManager
from core.data_connector import DataConnector
from preprocessors.new_fund_data import preprocess_new_fund_data
from preprocessors.option_data import preprocess_option_data

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataPipeline:
    # 全局共享资源
    dm = DataManager(root_path="data")
    cfg_loader = ConfigLoader()  # 使用默认配置路径
    connector = DataConnector(config_loader=cfg_loader)
    BASE_DATE = "2012-01-01"

    # 新增：预处理器映射表（指标ID -> 预处理函数）
    PREPROCESSORS = {
        "new_fund_data": preprocess_new_fund_data,
        "option_data": preprocess_option_data,
    }

    @classmethod
    def _get_last_date(
        cls, category: str, indicator_id: str, storage_mode: str
    ) -> str:
        """智能获取最后更新日期（支持整表/时序两种存储模式）"""
        try:
            if storage_mode == "Full":
                # 整表存储：读取整表最后一行日期
                table_name = cls.cfg_loader.get_config(indicator_id).get(
                    "table_name"
                )
                if not table_name:
                    logger.warning(f"整表存储但未配置表名: {indicator_id}")
                    return cls.BASE_DATE

                df = cls.dm.load_table(table_name)
                return (
                    df.index.max().strftime("%Y-%m-%d")
                    if not df.empty
                    else cls.BASE_DATE
                )
            else:
                # 分指标存储：读取该指标文件最后日期
                df = cls.dm.load_parquet("raw", indicator_id, category)
                return (
                    df.index.max().strftime("%Y-%m-%d")
                    if not df.empty
                    else cls.BASE_DATE
                )
        except Exception as e:
            logger.error(f"获取最后日期失败: {indicator_id}, {str(e)}")
            return cls.BASE_DATE

    @classmethod
    def _auto_preprocess(
        cls, category: str, indicator_id: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        """执行自动预处理并保存结果（增强版）"""
        logger.info(f"预处理分发: 指标ID={indicator_id}")
        logger.info(f"输入数据行数: {len(df)}")
        try:
            # === 特定指标预处理优先 ===
            if indicator_id in cls.PREPROCESSORS:
                processor = cls.PREPROCESSORS[indicator_id]
                return processor(df)

            # 2. 删除重复行
            df = df.drop_duplicates()

            # 3. 日期索引处理（增强版）
            date_col_name = None

            # 如果找到日期列，设置为索引
            if date_col_name:
                df[date_col_name] = pd.to_datetime(
                    df[date_col_name], errors="coerce"
                )
                df = df.dropna(subset=[date_col_name])
                df.set_index(date_col_name, inplace=True)

            return df  # 确保返回处理后的DataFrame

        except Exception as e:
            logger.exception(
                f"⛔⛔⛔ 自动预处理失败: {indicator_id}, {str(e)}"
            )
            return pd.DataFrame()

    @classmethod
    def _fetch_and_save_data(
        cls,
        category: str,
        indicator_id: str,
        source_params: Dict[str, Any],
        incremental: bool = True,
    ) -> bool:
        """统一数据获取与存储逻辑"""
        source_type = source_params.get("data_source_type", "EDB").upper()
        storage_mode = source_params.get("storage", "Individual")
        try:
            # 计算结束日期（默认为上个月最后一天）
            today = pd.Timestamp(datetime.now())
            end_date = (today - pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d")

            # 获取配置中的表名（用于整表存储）
            table_name = cls.cfg_loader.get_config(indicator_id).get(
                "table_name", ""
            )
            index_col_name = cls.cfg_loader.get_config(indicator_id).get(
                "index_col_name", ""
            )

            # 增量更新：获取最后日期
            last_date = (
                cls._get_last_date(category, indicator_id, storage_mode)
                if incremental and source_type not in ["EXCEL", "SQLITE"]
                else cls.BASE_DATE
            )

            # 根据来源类型获取数据
            df = pd.DataFrame()
            print(f"{indicator_id}数据来源:{source_type}")
            if source_type in [
                "EDB",
                "WSD",
                "WSET",
                "AKSHARE",
                "EXCEL",
                "SQLITE",
            ]:
                try:
                    # 使用统一的高级接口获取Wind数据
                    df = cls.connector.fetch_data_by_id(
                        indicator_id=indicator_id,
                        start_date=last_date,
                        end_date=end_date,
                    )
                    print(f"start_date:{last_date}")
                    print(f"end_date:{end_date}")
                    print(df.tail())
                    if source_type == "WSET" and index_col_name:
                        df = df.set_index(index_col_name, drop=False)
                        print(
                            f"WSET数据{indicator_id}重设索引列{index_col_name}成功"
                        )
                except Exception as e:
                    logger.exception(
                        f"Wind数据获取失败: {indicator_id}, {str(e)}"
                    )

            if df.empty:
                logger.info(f"无新数据: {indicator_id}")
                return False

            # 根据存储模式保存
            if storage_mode == "Full":
                if not table_name:
                    logger.error(f"整表存储但未配置表名: {indicator_id}")
                    return False

                # 整表存储：加载现有数据并合并
                try:
                    existing_df = cls.dm.load_table(table_name)
                    existing_dates = existing_df[index_col_name].unique()
                    # 移除重复日期（增量更新）
                    df = df[~df[index_col_name].isin(existing_dates)]
                    df = pd.concat([existing_df, df])
                    df = df.set_index(index_col_name, drop=False)
                except FileNotFoundError:
                    logger.info(f"创建新表: {table_name}")

                cls.dm.save_table(df, table_name, partition_by_year=False)
            else:
                # 分指标存储
                cls.dm.save_parquet(
                    df,
                    category,
                    indicator_id,
                    data_type="raw",
                    partition_by_year=False,
                )

            logger.info(f"更新成功: {indicator_id} | 行数={len(df)}")
            return True
        except Exception as e:
            logger.exception(f"数据处理失败: {indicator_id}, {str(e)}")
            # 记录失败时的数据样本
            sample = str(df.head(2)) if not df.empty else "空数据集"
            logger.debug(f"失败数据样本:\n{sample}")
            return False

    @classmethod
    def update_raw_data(cls, category: str, incremental: bool = True):
        """增量更新原始数据（整类）"""
        try:
            # 获取该类所有启用的指标配置
            indicators = cls.cfg_loader.get_enabled_ids_by_category(category)
            logger.info(
                f"更新【{category}】原始数据 | 指标数={len(indicators)}"
            )

            for indicator_id in indicators:
                cfg = cls.cfg_loader.get_config(indicator_id)
                if not cfg:
                    logger.warning(f"跳过缺失配置的指标: {indicator_id}")
                    continue

                # 执行数据获取
                cls._fetch_and_save_data(
                    category=category,
                    indicator_id=indicator_id,
                    source_params=cfg,
                    incremental=incremental,
                )
        except Exception as e:
            logger.error(f"类别更新失败 [{category}]: {str(e)}")
            raise

    @classmethod
    def update_and_process_category(
        cls, category: str, incremental: bool = True, reprocess: bool = False
    ):
        """
        完整流程：更新+预处理+聚合存储
        ⚙️ 功能：先更新原始数据，再处理并聚合整类指标
        📌 适用场景：需要同时更新数据并生成聚合结果的场景（如每日定时任务）
        :param category: 指标类别
        :param incremental: 是否增量更新
        :param reprocess: 是否重新预处理所有指标
        """
        # 1. 更新原始数据
        cls.update_raw_data(category, incremental)

        # 2. 预处理并聚合数据
        combined_df = cls.process_category(category, reprocess)

        # 3. 保存聚合数据
        if not combined_df.empty:
            cls.dm.save_combined_processed(category, combined_df)
        else:
            logger.error(f"⚠️ 类别[{category}]聚合数据为空，跳过保存")

        return combined_df

    @classmethod
    def process_category(
        cls, category: str, reprocess_all: bool = False
    ) -> pd.DataFrame:
        """
        处理整类指标并聚合（不更新数据）
        ⚙️ 功能：仅处理已有数据并聚合，不进行数据更新
        📌 适用场景：已有最新数据，只需重新处理生成聚合结果（如参数调整后重新处理）
        :param reprocess_all: 是否重新处理所有指标（即使已有预处理文件）
        """
        logger.info(f"开始处理类别: {category}")
        indicators = cls.cfg_loader.get_enabled_ids_by_category(category)

        # 存储所有处理后的DataFrame
        processed_dfs = {}
        error_count = 0  # 跟踪失败指标数量

        for indicator_id in indicators:
            try:
                cfg = cls.cfg_loader.get_config(indicator_id)
                if not cfg:
                    logger.warning(f"跳过缺失配置的指标: {indicator_id}")
                    error_count += 1
                    continue

                storage_mode = cfg.get("storage", "Individual")
                table_name = cfg.get("table_name", "")

                # 检查是否需要重新处理
                processed_path = (
                    cls.dm._get_partition_path(
                        "single", indicator_id, category
                    )
                    / "full.parquet"
                )

                if reprocess_all or not processed_path.exists():
                    try:
                        # === 关键修复：根据存储模式加载原始数据 ===
                        if storage_mode == "Full":
                            if not table_name:
                                logger.error(
                                    f"整表存储但未配置表名: {indicator_id}"
                                )
                                error_count += 1
                                continue
                            raw_df = cls.dm.load_table(table_name)
                        else:
                            raw_df = cls.dm.load_parquet(
                                "raw", indicator_id, category
                            )

                        if raw_df.empty:
                            logger.warning(
                                f"⚠️ 指标[{indicator_id}]原始数据为空"
                            )
                            error_count += 1
                            continue

                        # 执行预处理
                        processed_df = cls._auto_preprocess(
                            category, indicator_id, raw_df
                        )

                        # 保存预处理结果
                        if not processed_df.empty:
                            cls.dm.save_parquet(
                                processed_df,
                                category,
                                indicator_id,
                                data_type="single",
                                partition_by_year=False,
                            )
                        else:
                            logger.error(
                                f"⚠️ 指标[{indicator_id}]预处理后数据为空"
                            )
                            error_count += 1
                            continue
                    except Exception as e:
                        logger.exception(
                            f"🔥🔥 指标[{indicator_id}]预处理失败: {str(e)}"
                        )
                        error_count += 1
                        continue
                else:
                    # 直接加载已有预处理数据
                    try:
                        processed_df = pd.read_parquet(processed_path)
                    except Exception as e:
                        logger.error(
                            f"加载预处理数据失败[{indicator_id}]: {str(e)}"
                        )
                        error_count += 1
                        continue

                # 添加到集合（即使部分指标失败也继续处理）
                if not processed_df.empty:
                    # 重命名列避免冲突
                    if len(processed_df.columns) == 1:
                        processed_df.columns = [indicator_id]
                    else:
                        processed_df = processed_df.add_prefix(
                            f"{indicator_id}_"
                        )

                    processed_dfs[indicator_id] = processed_df
            except Exception as e:
                logger.exception(
                    f"处理指标[{indicator_id}]时发生未知异常: {str(e)}"
                )
                error_count += 1

        # 合并所有数据
        if not processed_dfs:
            logger.error(
                f"⚠️⚠️ 类别[{category}]无任何有效数据，所有{len(indicators)}个指标均失败"
            )
            return pd.DataFrame()

        # 在合并前确保每个DataFrame索引唯一
        for indicator_id, df in processed_dfs.items():
            logger.info(f"指标[{indicator_id}]预处理后行数: {len(df)}")
            if df.empty:
                logger.warning(f"⚠️ 空数据: {indicator_id}")
            if not df.index.is_unique:
                print(df.head())
                logger.warning(f"指标 {indicator_id} 存在重复索引，进行去重")
                df = df[~df.index.duplicated(keep="last")]
                processed_dfs[indicator_id] = df

        # 按索引（日期）外连接合并
        combined_df = pd.concat(
            processed_dfs.values(), axis=1, join="outer"
        ).sort_index()

        logger.info(
            f"✅ 类别[{category}]聚合完成 | "
            f"成功指标: {len(processed_dfs)}/{len(indicators)} | "
            f"失败指标: {error_count} | "
            f"时间范围: {combined_df.index.min().date()} 至 {combined_df.index.max().date()}"
        )
        return combined_df


if __name__ == "__main__":
    import argparse
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="运行行业数据处理")
    parser.add_argument("category", type=str, help="要处理的行业名称（如汽车行业、房地产行业）")
    parser.add_argument("--incremental", type=bool, default=False, help="是否增量更新")
    parser.add_argument("--reprocess", type=bool, default=True, help="是否重新处理")
    
    # 解析参数
    args = parser.parse_args()
    
    # 调用核心方法
    DataPipeline.update_and_process_category(
        category=args.category,
        incremental=args.incremental,
        reprocess=args.reprocess
    )
