# -*- coding: utf-8 -*-
"""
Created on Wed Aug  6 22:55:17 2025

@author: imado
"""

import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from pathlib import Path
import os
import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataManager:
    """优化版数据管理器：支持单指标分区存储 + 整组合并存储"""

    def __init__(self, root_path: str = "data"):
        self.ROOT_DIR = Path(root_path)
        self.RAW_DIR = self.ROOT_DIR / "raw"
        self.PROC_SINGLE_DIR = self.ROOT_DIR / "processed/single"
        self.PROC_COMBINED_DIR = self.ROOT_DIR / "processed/combined"
        self.TABLE_DIR = self.ROOT_DIR / "tables"  # 整张表处理方式
        self._create_dirs()

    def _create_dirs(self):
        """创建分层存储目录"""
        self.RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.PROC_SINGLE_DIR.mkdir(parents=True, exist_ok=True)
        self.PROC_COMBINED_DIR.mkdir(parents=True, exist_ok=True)
        self.TABLE_DIR.mkdir(parents=True, exist_ok=True)  # 新增目录

    def _get_partition_path(
        self,
        data_type: str,
        indicator_id: str,
        category: str,
        year: int = None,
    ) -> Path:
        """生成分区存储路径（格式：category/indicator_id/year.parquet）"""
        if data_type == "raw":
            base_dir = self.RAW_DIR
        elif data_type == "single":
            base_dir = self.PROC_SINGLE_DIR
        else:
            raise ValueError("无效数据类型")

        indicator_dir = base_dir / category / indicator_id
        indicator_dir.mkdir(parents=True, exist_ok=True)
        return indicator_dir / f"{year}.parquet" if year else indicator_dir

    def save_parquet(
        self,
        data: pd.DataFrame,
        category: str,
        indicator_id: str,
        data_type: str = "raw",
        partition_by_year: bool = False,
    ):
        """保存数据到分区文件（按年拆分）[3](@ref)"""
        if data.empty:
            print("⚠️ 空数据，跳过保存")
            return

        if partition_by_year:
            # 按年分区存储（优化增量更新）
            for year, year_data in data.groupby(data.index.year):
                file_path = self._get_partition_path(
                    data_type, indicator_id, category, year
                )
                pq.write_table(
                    pa.Table.from_pandas(year_data),
                    file_path,
                    row_group_size=10000,  # 大RowGroup优化顺序读取[4](@ref)
                )
        else:
            # 全量存储（兼容旧模式）
            file_path = (
                self._get_partition_path(data_type, indicator_id, category)
                / "full.parquet"
            )
            data.to_parquet(file_path)

        print(f"✅ {indicator_id}数据已保存至：{file_path.parent}")

    def load_parquet(
        self,
        data_type: str,
        indicator_id: str,
        category: str,
        years: list = None,
    ) -> pd.DataFrame:
        """加载分区数据（支持年份过滤）[1](@ref)"""
        indicator_dir = self._get_partition_path(
            data_type, indicator_id, category
        )

        # 检测存储模式
        if (indicator_dir / "full.parquet").exists():
            return pd.read_parquet(indicator_dir / "full.parquet")

        # 按需筛选年份文件
        parquet_files = sorted(indicator_dir.glob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(f"无数据文件：{indicator_dir}")

        if years:
            target_files = [f for f in parquet_files if int(f.stem) in years]
        else:
            target_files = parquet_files

        # 并行读取合并（优化IO效率）[4](@ref)
        return pd.concat(
            (pd.read_parquet(f) for f in target_files), axis=0
        ).sort_index()

    def load_combined_processed(self, category: str) -> pd.DataFrame:
        """加载整组处理结果（高效单文件读取）[1](@ref)"""
        file_path = self.PROC_COMBINED_DIR / f"{category}.parquet"
        if not file_path.exists():
            raise FileNotFoundError(f"整组数据不存在: {file_path}")
        return pd.read_parquet(file_path)

    def get_indicators_in_category(self, category: str) -> list:
        """获取类别下所有指标ID"""
        return [
            d.name for d in (self.RAW_DIR / category).iterdir() if d.is_dir()
        ]

    # 新增整表存储方法
    def save_table(
        self,
        data: pd.DataFrame,
        table_name: str,
        partition_by_year: bool = False,
    ):
        """保存整张表格数据（按年分区/全量存储）"""
        if data.empty:
            logger.warning(f"⚠️ 空数据，跳过保存: {table_name}")
            return

        table_dir = self.TABLE_DIR / table_name
        table_dir.mkdir(parents=True, exist_ok=True)

        if partition_by_year:
            # 按年分区存储
            for year, year_data in data.groupby(data.index.year):
                file_path = table_dir / f"{year}.parquet"
                try:
                    pq.write_table(
                        pa.Table.from_pandas(year_data),
                        file_path,
                        row_group_size=10000,
                    )
                    logger.info(f"✅ 保存表分区: {file_path}")
                except Exception as e:
                    logger.error(f"保存分区失败: {file_path}, {str(e)}")
        else:
            # 全量存储
            file_path = table_dir / "full.parquet"
            try:
                data.to_parquet(file_path)
                logger.info(f"✅ 保存整表: {file_path}")
            except Exception as e:
                logger.error(f"保存整表失败: {file_path}, {str(e)}")

        logger.info(f"✅ 整表[{table_name}]数据已保存至：{table_dir}")

    # 新增整表加载方法
    def load_table(self, table_name: str, years: list = None) -> pd.DataFrame:
        """加载整表数据（支持年份过滤）"""
        table_dir = self.TABLE_DIR / table_name

        # === 关键修复：增强错误处理 ===
        if not table_dir.exists():
            raise FileNotFoundError(f"表目录不存在: {table_dir}")

        if not table_dir.is_dir():
            raise NotADirectoryError(f"表路径不是目录: {table_dir}")

        # 检测存储模式
        full_file = table_dir / "full.parquet"
        if full_file.exists():
            try:
                return pd.read_parquet(full_file)
            except Exception as e:
                raise IOError(f"读取整表文件失败: {full_file}, {str(e)}")

        # 按需筛选年份文件
        parquet_files = sorted(table_dir.glob("*.parquet"))
        if not parquet_files:
            available_files = list(table_dir.glob("*"))
            raise FileNotFoundError(
                f"无Parquet文件: {table_dir} | 现有文件: {available_files}"
            )

        if years:
            target_files = []
            for f in parquet_files:
                try:
                    year = int(f.stem)
                    if year in years:
                        target_files.append(f)
                except ValueError:
                    logger.warning(f"忽略非年份文件: {f}")
        else:
            target_files = parquet_files

        if not target_files:
            dir_contents = [f.name for f in table_dir.iterdir()]
            raise FileNotFoundError(
                f"无匹配年份文件: {years} | "
                f"目录内容: {dir_contents} | "
                f"存储模式: {'整表' if full_file.exists() else '分区'}"
            )

        try:
            # 并行读取合并
            return pd.concat(
                (pd.read_parquet(f) for f in target_files), axis=0
            ).sort_index()
        except Exception as e:
            # 提供更详细的错误信息
            file_sizes = {f: f.stat().st_size for f in target_files}
            raise IOError(f"合并表文件失败: {str(e)} | 文件: {file_sizes}")

    def save_combined_excel(self, category: str, data: pd.DataFrame):
        """保存整组数据为Excel文件"""
        excel_path = self.PROC_COMBINED_DIR / f"{category}.xlsx"
        excel_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的工作表
        sheet_name = f"{datetime.now().strftime('%Y%m%d')}"

        # 保存到Excel（保留日期索引）
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            data.to_excel(writer, sheet_name=sheet_name)

    def save_combined_processed(self, category: str, data: pd.DataFrame):
        """保存整组处理结果（全量单文件）"""
        # 确保目录存在
        self.PROC_COMBINED_DIR.mkdir(parents=True, exist_ok=True)

        # 保存为Parquet
        parquet_path = self.PROC_COMBINED_DIR / f"{category}.parquet"
        pq.write_table(
            pa.Table.from_pandas(data), parquet_path, row_group_size=10000
        )

        # 保存为Excel
        excel_path = self.PROC_COMBINED_DIR / f"{category}.xlsx"
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            data.to_excel(writer, sheet_name="data")
