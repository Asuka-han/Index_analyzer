# -*- coding: utf-8 -*-
"""
Created on Wed Aug  6 22:17:58 2025

@author: imado
"""
# config_loader.py
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class ConfigLoader:
    def __init__(self, config_path: Path = Path("高频宏观数据指标库.xlsx")):
        """
        从Excel文件加载指标配置（支持WSET多样化参数）
        :param config_path: Excel配置文件路径
        """
        self._config = {}
        if not Path(config_path).is_absolute():
            config_path = Path(__file__).resolve().parents[2] / config_path
        self._load_from_excel(config_path)

    def _load_from_excel(self, config_path: Path) -> None:
        """从Excel文件加载并整合配置数据"""
        try:
            # 读取三张配置表
            df_selected = pd.read_excel(
                config_path,
                sheet_name="选定指标",
                usecols=[
                    "指标名称",
                    "频率",
                    "单位",
                    "指标ID",
                    "来源",
                    "降频方法",
                    "指标分类",
                    "数据来源类型",
                    "存储方式",
                    "数据状态",
                    "表名",
                    "api_params",
                    "索引列名",
                ],
            )
            df_advanced = pd.read_excel(
                config_path,
                sheet_name="高级配置",
                usecols=["指标ID", "异常值处理", "单位转换系数"],
            )

            # 合并配置表
            merged = pd.merge(
                df_selected,
                df_advanced,
                on="指标ID",
                how="left",
            )

            # 转换为内部配置字典
            for _, row in merged.iterrows():
                # 解析WSET参数（如果是JSON字符串）
                api_params = {}
                if pd.notna(row["api_params"]):
                    try:
                        api_params = json.loads(row["api_params"])
                    except json.JSONDecodeError:
                        pass

                config = {
                    "name": row["指标名称"],
                    "freq": row["频率"],
                    "unit": row["单位"],
                    "source": row["来源"],
                    "category": row["指标分类"],
                    "data_source_type": row["数据来源类型"],
                    "storage": row["存储方式"],
                    "status": row["数据状态"],
                    "outlier_treatment": row["异常值处理"],
                    "unit_conversion": float(row["单位转换系数"]),
                    "freq_method": row["降频方法"],
                    "table_name": row["表名"],  # 新增WSET表名字段
                    "api_params": api_params,  # 新增api参数字段
                    "index_col_name": row["索引列名"],
                }
                self._config[row["指标ID"]] = config

        except FileNotFoundError:
            raise Exception(f"配置文件未找到: {config_path}")
        except Exception as e:
            raise Exception(f"配置文件解析失败: {str(e)}")

    # 其他方法保持不变...
    def get_config(self, indicator_id: str) -> Dict[str, Any]:
        return self._config.get(indicator_id, {})

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        return self._config

    def get_all_ids(self) -> List[str]:
        return list(self._config.keys())

    def get_enabled_ids(self) -> List[str]:
        return [
            id_
            for id_, config in self._config.items()
            if config.get("status") == "启用"
        ]

    def get_storage_mode(self, indicator_id: str) -> str:
        return self.get_config(indicator_id).get("storage", "Individual")

    def get_data_source(self, indicator_id: str) -> str:
        return self.get_config(indicator_id).get("data_source_type", "EDB")

    def get_processing_rule(self, indicator_id: str) -> Dict[str, Any]:
        config = self.get_config(indicator_id)
        return {
            "freq_method": config.get("freq_method"),
            "outlier_treatment": config.get("outlier_treatment"),
        }

    def get_enabled_ids_by_category(self, category: str) -> List[str]:
        enabled_ids = []
        for indicator_id, config in self._config.items():
            if (
                config.get("category") == category
                and config.get("status") == "启用"
            ):
                enabled_ids.append(indicator_id)
        return enabled_ids

    def get_para_by_category(self, category: str, para_name: str) -> Dict[str, Any]:
        """
        获取指定类别下所有启用指标的特定参数值
        :param category: 指标分类名称（如"经济指标"）
        :param para_name: 需要提取的参数名（如"freq_method"）
        :return: 字典{指标ID: 参数值}
        """
        result = {}
        for indicator_id, config in self._config.items():
            if config.get("category") == category and config.get("status") == "启用":
                # 安全获取参数值，不存在则返回None
                result[indicator_id] = config.get(para_name)
        return result


# 示例用法
if __name__ == "__main__":
    loader = ConfigLoader()
    try:
        econ_freq_methods = loader.get_para_by_category("经济指标", "freq_method")
        print("\n经济指标类别的降频方法：")
        for id_, method in econ_freq_methods.items():
            print(f"{id_}: {method}")

        # 测试新方法：获取货币指标类别的单位
        monetary_units = loader.get_para_by_category("货币指标", "unit")
        print("\n货币指标类别的单位：")
        for id_, unit in monetary_units.items():
            print(f"{id_}: {unit}")

        # 测试不存在的参数
        test_params = loader.get_para_by_category("资金指标", "non_existent_param")
        print("\n不存在的参数测试:", test_params)  # 应返回空字典

    except Exception as e:
        print(f"配置加载失败: {str(e)}")
