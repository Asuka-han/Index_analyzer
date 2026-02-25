# Copilot 使用说明

## 全局概览
- 数据流：ConfigLoader 从 高频宏观数据指标库.xlsx 读取配置，DataPipeline 拉取原始数据（Wind/Excel），DataManager 持久化 parquet 表，分析器读取处理后/合并后的数据生成信号与报告。
- 存储划分：raw 数据存放在 data/raw/<category>/<indicator_id>，单指标处理结果在 data/processed/single，类别级聚合在 data/processed/combined。
- Wind 集成集中在 DataConnector.fetch_data_by_id，根据 config 路由到 EDB/WSET/WSD。

## 核心模块与模式
- DataPipeline 负责 update + preprocess + aggregate；见 data_pipeline.py。
- DataManager 封装 parquet/table IO（整表 vs 单指标）；见 data_manager.py。
- ConfigLoader 驱动全流程；data_source_type、storage、table_name、api_params、index_col_name 等配置来自 Excel。
- 类别分析器读取合并数据并输出包含 final_signal 的 "signal" DataFrame；见 fundamental_economy.py、fundamental_monetary.py、fundamental_credit.py、international.py、valuation.py、capital.py、technical.py。
- new_fund_data 与 option_data 的特殊预处理由 indicator_id 分发；见 DataPipeline.PREPROCESSORS。

## 工作流（入口脚本）
- 更新 + 预处理某个类别（或全部）：python task_update_data.py --category 经济指标 --incremental --reprocess。
- 运行多因子分析（合并分析器信号）：python task_analyze_data.py。
- 信号对市场回测使用 multi_factor_analysis.xlsx：stat_vs_mkt_combo.py。

## 外部依赖与数据
- WindPy 用于获取 Wind 数据；DataConnector 采用延迟导入与按需连接，Wind 不可用时会安全降级。
- AKShare 用于 AKShare 数据源；未安装时仅影响相关指标。
- Excel 输入：高频宏观数据指标库.xlsx（配置）与 EXCEL补充数据.xlsx（补充数据）。
- technical.py 使用 TA-Lib 进行指标计算。

## 约定与注意事项
- Categories 为中文字符串（经济指标、货币指标、信用指标、国际指标、估值指标、资金指标）；查询配置或保存数据时需使用精确名称。
- storage == "Full" 表示整表存储在 data/tables/<table_name>；否则按指标保存为 parquet 文件。
- preprocess 输出需保持 DatetimeIndex；合并聚合使用基于 index 的 outer-join。
