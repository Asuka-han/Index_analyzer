# -*- coding: utf-8 -*-
"""
Created on Wed Aug  6 15:44:34 2025

@author: imado

重构后的数据连接器，支持通过配置加载器自动获取参数
Created on Wed Aug  6 15:44:34 2025
@author: imado
"""
import pandas as pd
import time
import logging
import sqlite3
from typing import Dict, Union, List, Optional
from core.config_loader import ConfigLoader  # 导入配置加载器
from pathlib import Path
import re


_logger = logging.getLogger(__name__)
_w_wind_instance = None
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_wind_instance():
    """安全获取 Wind API 实例，仅在首次调用且需要时初始化。"""
    global _w_wind_instance
    if _w_wind_instance is not None:
        return _w_wind_instance

    try:
        from WindPy import w as wind_api

        if not wind_api.isconnected():
            wind_api.start()
        if wind_api.isconnected():
            _logger.info("Wind API connected successfully")
            _w_wind_instance = wind_api
            return _w_wind_instance

        _logger.warning("Failed to connect to Wind API")
        return None
    except ImportError:
        _logger.warning("WindPy not installed. Wind data sources unavailable")
        return None
    except Exception as e:
        _logger.warning(f"Wind API initialization error: {e}")
        return None


class DataConnector:
    def __init__(
        self,
        config_loader: ConfigLoader,  # 必须传入配置加载器
        max_retries=3,
        retry_delay=5,
        enable_cache: bool = True,
    ):
        """
        初始化数据连接器
        :param config_loader: 配置加载器实例
        :param max_retries: 最大重试次数
        :param retry_delay: 重试延迟(秒)
        """
        self.config_loader = config_loader
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_cache = enable_cache
        self._cache: Dict = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def _connect(self):
        """连接Wind API（带重试机制）"""
        for attempt in range(self.max_retries):
            try:
                w = _get_wind_instance()
                if w is not None and w.isconnected():
                    self.logger.info("Wind API connected successfully")
                    return True
            except Exception as e:
                self.logger.warning(
                    f"Wind connection attempt {attempt+1} failed: {str(e)}"
                )
            time.sleep(self.retry_delay)
        self.logger.error(
            "Failed to connect to Wind API after multiple attempts"
        )
        return False

    def fetch_data_by_id(
        self, indicator_id: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        统一接口：通过指标ID获取数据（自动识别数据源类型）
        :param indicator_id: 指标ID
        :param start_date: 开始日期 (YYYY-MM-DD)
        :param end_date: 结束日期 (YYYY-MM-DD)
        :return: 包含时间序列的DataFrame
        """
        config = self.config_loader.get_config(indicator_id)
        if not config:
            raise ValueError(f"指标ID {indicator_id} 配置不存在")

        data_source = config.get("data_source_type", "EDB").upper()

        cache_key = (indicator_id, start_date, end_date)
        if self.enable_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()

        result: pd.DataFrame

        if data_source == "EDB":
            result = self.fetch_wind_edb_data(indicator_id, start_date, end_date)
        elif data_source == "WSET":
            # 动态构建WSET参数
            base_params = config.get("api_params", {}).copy()
            # 按目标顺序重建字典
            params = {
                "startdate": start_date,
                "enddate": end_date,
                **base_params,  # 将原始参数解包到新字典中
            }
            print(f"{indicator_id}参数表:{params}")
            result = self.fetch_wind_wset_data(
                table_name=config["table_name"], params=params
            )
        elif data_source == "WSD":
            # 从配置中解析WSD参数
            api_params = config.get("api_params", {})
            result = self.fetch_wind_wsd_data(
                codes=api_params.get("codes", indicator_id),
                fields=api_params.get("fields"),
                start_date=start_date,
                end_date=end_date,
                options=api_params.get("options", ""),
            )
        elif data_source == "AKSHARE":
            api_params = config.get("api_params", {})
            func_name = api_params.get("func")
            kwargs = api_params.get("kwargs", {})
            if not func_name:
                raise ValueError(
                    f"AKShare配置缺少func: {indicator_id}"
                )
            try:
                import akshare as ak
            except ImportError as e:
                raise ImportError(
                    "未安装akshare，无法获取AKShare数据"
                ) from e

            ak_func = getattr(ak, func_name, None)
            if ak_func is None:
                raise AttributeError(f"AKShare函数不存在: {func_name}")

            raw_df = ak_func(**kwargs)
            standardized = self._standardize_akshare_df(
                raw_df, indicator_id, api_params
            )
            if standardized.empty:
                result = standardized
            else:
                start_ts = pd.to_datetime(start_date)
                end_ts = pd.to_datetime(end_date)
                result = standardized.loc[start_ts:end_ts]
        elif data_source == "EXCEL":
            file_path = config.get("table_name", "")
            api_params = config.get("api_params", {})
            result = self.fetch_excel_data(
                file_path=file_path,
                indicator_id=indicator_id,
                start_date=start_date,
                end_date=end_date,
                sheet_name=api_params.get("sheet_name"),
                date_col=api_params.get("date_col", "date"),
                value_col=api_params.get("value_col"),
            )
        elif data_source == "SQLITE":
            db_path = config.get("table_name", "")
            api_params = config.get("api_params", {})
            result = self.fetch_sqlite_data(
                db_path=db_path,
                indicator_id=indicator_id,
                start_date=start_date,
                end_date=end_date,
                table_name=api_params.get("table_name"),
                date_col=api_params.get("date_col", "date"),
                value_col=api_params.get("value_col"),
            )
        else:
            raise ValueError(f"不支持的数据源类型: {data_source}")

        if self.enable_cache:
            self._cache[cache_key] = result.copy()
        return result

    def _standardize_local_df(
        self,
        df: pd.DataFrame,
        indicator_id: str,
        date_col: str,
        value_col: Optional[Union[str, List[str]]],
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        if date_col not in df.columns:
            raise ValueError(f"日期列不存在: {date_col}")

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col, drop=True)

        if value_col is None:
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) == 1:
                value_col = numeric_cols[0]
            elif len(numeric_cols) > 1:
                value_col = numeric_cols[0]
            else:
                self.logger.warning(
                    f"本地数据无可用数值列: {indicator_id}"
                )
                return pd.DataFrame()

        if isinstance(value_col, list):
            missing_cols = [col for col in value_col if col not in df.columns]
            if missing_cols:
                raise ValueError(f"数值列不存在: {missing_cols}")
            result = df[value_col].copy()
        else:
            if value_col not in df.columns:
                raise ValueError(f"数值列不存在: {value_col}")
            result = df[[value_col]].rename(columns={value_col: indicator_id})

        return result.sort_index()

    def fetch_excel_data(
        self,
        file_path: Union[str, Path],
        indicator_id: str,
        start_date: str,
        end_date: str,
        sheet_name: Optional[str] = None,
        date_col: str = "date",
        value_col: Optional[Union[str, List[str]]] = None,
    ) -> pd.DataFrame:
        if not file_path:
            raise ValueError(f"EXCEL未配置文件路径: {indicator_id}")

        excel_path = Path(file_path)
        if not excel_path.is_absolute():
            excel_path = _PROJECT_ROOT / excel_path
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel文件不存在: {excel_path}")

        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        standardized = self._standardize_local_df(
            df=df,
            indicator_id=indicator_id,
            date_col=date_col,
            value_col=value_col,
        )
        if standardized.empty:
            return standardized

        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        return standardized.loc[start_ts:end_ts]

    def fetch_sqlite_data(
        self,
        db_path: Union[str, Path],
        indicator_id: str,
        start_date: str,
        end_date: str,
        table_name: Optional[str],
        date_col: str = "date",
        value_col: Optional[Union[str, List[str]]] = None,
    ) -> pd.DataFrame:
        if not db_path:
            raise ValueError(f"SQLITE未配置数据库路径: {indicator_id}")
        if not table_name:
            raise ValueError(f"SQLITE未配置表名: {indicator_id}")

        sqlite_path = Path(db_path)
        if not sqlite_path.is_absolute():
            sqlite_path = _PROJECT_ROOT / sqlite_path
        if not sqlite_path.exists():
            raise FileNotFoundError(f"SQLite文件不存在: {sqlite_path}")

        if value_col is None:
            select_clause = "*"
        elif isinstance(value_col, list):
            select_clause = ", ".join([date_col, *value_col])
        else:
            select_clause = f"{date_col}, {value_col}"

        query = f"SELECT {select_clause} FROM {table_name}"
        params: List[str] = []
        if start_date and end_date:
            query += f" WHERE {date_col} >= ? AND {date_col} <= ?"
            params.extend([start_date, end_date])

        with sqlite3.connect(sqlite_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)

        standardized = self._standardize_local_df(
            df=df,
            indicator_id=indicator_id,
            date_col=date_col,
            value_col=value_col,
        )
        if standardized.empty:
            return standardized

        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        return standardized.loc[start_ts:end_ts]

    def _standardize_akshare_df(
        self,
        df: pd.DataFrame,
        indicator_id: str,
        api_params: Optional[Dict] = None,
    ) -> pd.DataFrame:
        """标准化AKShare数据为内部时间序列格式"""
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        api_params = api_params or {}
        explicit_value_col = api_params.get("value_col")

        if "月份" in df.columns:
            year_cols = [
                col
                for col in df.columns
                if re.match(r"^\d{4}年$|^\d{4}$", str(col))
            ]
            if year_cols:
                pivot_df = df[["月份", *year_cols]].copy()
                pivot_df["月份"] = (
                    pivot_df["月份"]
                    .astype(str)
                    .str.extract(r"(\d{1,2})")[0]
                )
                pivot_df = pivot_df.dropna(subset=["月份"])
                pivot_df["月份"] = pivot_df["月份"].astype(int)
                long_df = pivot_df.melt(
                    id_vars=["月份"],
                    value_vars=year_cols,
                    var_name="year",
                    value_name="value",
                )
                long_df["year"] = (
                    long_df["year"].astype(str).str.extract(r"(\d{4})")[0]
                )
                long_df = long_df.dropna(subset=["year"])
                long_df["date"] = pd.to_datetime(
                    long_df["year"]
                    + "-"
                    + long_df["月份"].astype(str).str.zfill(2)
                    + "-01",
                    errors="coerce",
                )
                long_df = long_df.dropna(subset=["date"])
                df = long_df[["date", "value"]]

        date_col = None
        for candidate in ["date", "日期", "时间", "统计时间", "TRADE_DATE"]:
            if candidate in df.columns:
                date_col = candidate
                break
        if date_col is None:
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    date_col = col
                    break

        if date_col:
            df.loc[:, date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])
            df = df.set_index(date_col, drop=True)
        else:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, errors="coerce")
                df = df[df.index.notna()]

        value_col = None
        if explicit_value_col:
            if isinstance(explicit_value_col, list):
                for col in explicit_value_col:
                    if col in df.columns:
                        value_col = col
                        break
            elif explicit_value_col in df.columns:
                value_col = explicit_value_col

        if value_col is None:
            if indicator_id in df.columns:
                value_col = indicator_id
            else:
                numeric_cols = df.select_dtypes(include=["number"]).columns
                if len(numeric_cols) == 1:
                    value_col = numeric_cols[0]
                elif len(numeric_cols) > 1:
                    value_col = numeric_cols[0]
                else:
                    self.logger.warning(
                        f"AKShare返回数据无可用数值列: {indicator_id}"
                    )
                    return pd.DataFrame()

        result = df[[value_col]].rename(columns={value_col: indicator_id})
        result = result.sort_index()
        return result

    def fetch_wind_edb_data(
        self,
        indicator_id: Union[str, List[str]],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """从Wind获取EDB数据（支持单个或多个指标）"""
        w = _get_wind_instance()
        if w is None:
            self.logger.error("Wind API unavailable. Skipping EDB fetch.")
            return pd.DataFrame()
        if not re.match(r"\d{4}-\d{2}-\d{2}", start_date) or not re.match(
            r"\d{4}-\d{2}-\d{2}", end_date
        ):
            self.logger.error("日期格式错误，应为YYYY-MM-DD")
            return pd.DataFrame()
        for attempt in range(self.max_retries):
            try:
                # 调用Wind API
                data = w.edb(
                    indicator_id, start_date, end_date, "Fill=Previous"
                )
                if data.ErrorCode != 0:
                    raise ValueError(
                        f"Wind API error {data.ErrorCode}: {data.Data[0]}"
                    )

                # 多指标处理
                if isinstance(indicator_id, list):
                    df = pd.DataFrame(
                        data.Data,
                        index=data.Codes,
                        columns=pd.to_datetime(data.Times),
                    ).T
                # 单指标处理
                else:
                    df = pd.DataFrame(
                        data.Data[0],
                        index=pd.to_datetime(data.Times),
                        columns=[indicator_id],
                    )
                return df

            except Exception as e:
                self.logger.warning(
                    f"EDB请求失败，尝试 {attempt+1}/{self.max_retries}: {str(e)}"
                )
                time.sleep(self.retry_delay)

        self.logger.error(f"EDB数据获取失败: {indicator_id}")
        return pd.DataFrame()

    def fetch_wind_wset_data(
        self, table_name: str, params: dict
    ) -> pd.DataFrame:
        """从Wind获取数据集数据（WSET接口）"""
        w = _get_wind_instance()
        if w is None:
            self.logger.error("Wind API unavailable. Skipping WSET fetch.")
            return pd.DataFrame()
        for attempt in range(self.max_retries):
            try:
                # 构建参数字符串
                param_str = ";".join([f"{k}={v}" for k, v in params.items()])
                print(param_str)

                # 调用Wind API
                data = w.wset(table_name, param_str)

                if data.ErrorCode != 0:
                    self.logger.error(
                        f"WSET错误 {data.ErrorCode}: {data.Data[0]}"
                    )
                    return pd.DataFrame()

                # 转换为DataFrame
                df = pd.DataFrame(
                    data.Data,
                    columns=data.Codes,
                    index=data.Fields,
                ).T
                return df

            except Exception as e:
                self.logger.warning(
                    f"WSET请求失败，尝试 {attempt+1}/{self.max_retries}: {str(e)}"
                )
                time.sleep(self.retry_delay)

        self.logger.error(f"WSET数据获取失败: {table_name}")
        return pd.DataFrame()

    def fetch_wind_wsd_data(
        self,
        codes: Union[str, List[str]],
        fields: Union[str, List[str]],
        start_date: str,
        end_date: str,
        options: str = "",
    ) -> pd.DataFrame:
        """从Wind获取证券序列数据（WSD接口）"""
        w = _get_wind_instance()
        if w is None:
            self.logger.error("Wind API unavailable. Skipping WSD fetch.")
            return pd.DataFrame()
        for attempt in range(self.max_retries):
            try:
                # 调用Wind API
                data = w.wsd(codes, fields, start_date, end_date, options)

                if data.ErrorCode != 0:
                    self.logger.error(
                        f"WSD错误 {data.ErrorCode}: {data.Data[0]}"
                    )
                    return pd.DataFrame()

                # 多代码处理
                if isinstance(codes, list):
                    df = pd.DataFrame(
                        data.Data,
                        index=pd.MultiIndex.from_product(
                            [codes, fields], names=["Code", "Field"]
                        ),
                        columns=pd.to_datetime(data.Times),
                    ).T
                # 单代码处理
                else:
                    df = pd.DataFrame(
                        data.Data,
                        index=data.Fields,
                        columns=pd.to_datetime(data.Times),
                    ).T
                return df

            except Exception as e:
                self.logger.warning(
                    f"WSD请求失败，尝试 {attempt+1}/{self.max_retries}: {str(e)}"
                )
                time.sleep(self.retry_delay)

        self.logger.error(f"WSD数据获取失败: {codes}")
        return pd.DataFrame()


# ====================== 测试代码 ======================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        # 1. 初始化配置加载器
        config_path = Path("高频宏观数据指标库.xlsx")
        loader = ConfigLoader(config_path)

        # 4. 测试WSET数据获取
        print("\n" + "=" * 50)
        print("测试EXCEL数据参数获取")
        # 查找启用的WSET指标
        excel_ids = [
            id_
            for id_ in loader.get_enabled_ids()
            if loader.get_config(id_).get("data_source_type") == "EXCEL"
        ]

        if excel_ids:
            for excel_id in excel_ids:
                config = loader.get_config(excel_id)
                print(f"测试指标: {config['name']}({excel_id})")
                print(f"WSET表名: {config['table_name']}")
                print(f"EXCEL表名: {config['name']}")
                print(f"EXCEL表名: {config.get('name', 0)}")

    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback

        traceback.print_exc()
