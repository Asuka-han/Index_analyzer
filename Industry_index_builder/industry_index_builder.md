# 行业景气度指数构建任务指南

---

## 1. 任务背景 (Background)

我们希望借鉴国信证券“高频宏观扩散指数”的构建思路，利用公开、免费的数据源（如 AKShare），为特定行业创建一个能够**高频（周度或月度）跟踪其景气度变化**的指数。这种方法的核心在于将多个反映行业状况的原始指标，转化为简单的方向性信号（+1, 0, -1），再进行合成，从而得到一个简洁、直观且具有领先性的行业景气度指标。

已经按照报告方法构建了宏观指标，希望在此基础上将该方法扩展到行业景气度层面。

此方法的优势在于：

* **高频性**： 能比官方月度数据更早地感知行业趋势变化。
* **简洁性**： 最终输出为一个易于理解和监控的单一指数。
* **可扩展性**： 方法论可复用于不同行业。

可以先观看三篇研究报告（在./reference下）的内容，做为背景知识，然后进行接下来的程序设计与实现。

---

## 2. 任务目标 (Objective)

本任务固定选择**汽车行业**和**房地产行业**作为研究对象，为每个行业构建独立的景气度扩散指数。每个行业需要获取 **2-4 个核心高频指标**，这些指标**必须来源于多种渠道**（AKShare、Excel 文件、SQLite 数据库等）。最终，参照国信证券的方法并**复用 `fundamental_economy.py` 脚本的核心逻辑**，生成两个行业的**景气度扩散指数**。

**最终交付物**：

1. 一份完整的、可运行的 Python 脚本（`.py` 文件），命名为 `industry_analyzer.py`，放置在 `src/analyzers/` 目录下。
2. 一份详细的说明文档（Markdown 格式），内容包括：
    * 汽车行业和房地产行业的指标选择及理由。
    * 所选的 2-4 个核心指标及其**数据来源**（明确标注每个指标来自 AKShare / Excel / SQLite）。
    * 指数计算逻辑的详细说明（重点说明与 `fundamental_economy.py` 的异同）。
    * 两个行业最终生成的景气度指数走势图。
3. 一个 Excel 文件，包含两个行业计算出的详细结果。
4. 用于演示的**示例数据文件**（一个 `.xlsx` 和/或一个 `.db` 文件），展示如何组织非 AKShare 数据。
5. 可独立打包的 `industry_analyzer` 交付形式，要求既能与老项目并行运行，也能独立分发给非技术同事使用。
6. 简单用户界面（GUI 或 Web UI），用于选择行业、指标、日期范围并一键生成结果与图表。

**注**：以往脚本中使用了wind数据源以及pyarrow数据库，新脚本要求你不修改老的数据提取方式的前提下增加一个数据源（AKshare），并且需要将Excel和SQLite数据源集成到统一的`DataConnector`中。

---

## 2.1 环境依赖项表

建议都从mamba进行安装

| 组件 | 版本/建议 | 用途 | 备注 |
| :--- | :--- | :--- | :--- |
| Python | 3.12+ | 运行环境 | 与现有项目一致即可 |
| pandas | 最新稳定版 | 数据处理 | 必需 |
| numpy | 最新稳定版 | 数值计算 | 必需 |
| pyarrow | 最新稳定版 | Parquet 读写 | 依赖现有数据结构 |
| akshare | 最新稳定版 | AKShare 数据源 | 必需 |
| openpyxl | 最新稳定版 | Excel 读写 | 必需 |
| sqlite3 | Python 内置 | SQLite 读写 | 标准库 |
| matplotlib | 最新稳定版 | 静态可视化 | 必需 |
| ta-lib | 最新稳定版 | 技术指标计算 | 仅 technical 分析使用 |
| WindPy | 可选 | Wind 数据源 | 有 Wind 环境时可用 |
| PyQt5 | 最新稳定版 | GUI 界面 | 必需（GUI版本） |
| tkinter | Python 内置 | GUI 界面 | 标准库（备选） |
| Flask | 最新稳定版 | Web UI 后端 | 必需（Web UI版本） |
| Streamlit | 最新稳定版 | Web UI 框架 | 备选（更简单） |
| plotly | 最新稳定版 | 交互式可视化 | 推荐（Web UI） |
| docker | 最新稳定版 | 容器化打包 | 可选（独立打包） |

## 3. 参考方法论与代码复用指南 (Methodology & Code Reuse)

### 3.1 多数据源适配

当前项目的 `DataConnector` 已支持 Wind、EDB、WSET、WSD 与 AKShare 数据源，并且对 WindPy 采用延迟导入与安全降级。Excel 与 SQLite 数据源需要在本任务中集成到统一的 `DataConnector` 架构中，以保持项目架构的一致性。

#### 3.1.1 配置更新

在配置文件 `高频宏观数据指标库.xlsx` 的 **"选定指标"** 表中，为计划使用的指标添加相应的 `data_source_type`。现有支持的数据源类型包括：
* `"EDB"`: Wind EDB 数据库
* `"WSET"`: Wind 数据集
* `"WSD"`: Wind 证券数据
* `"AKShare"`: AKShare 开源数据
* `"EXCEL"`: Excel 本地文件（需新增支持）
* `"SQLITE"`: SQLite 本地数据库（需新增支持）

对于 AKShare 数据源，在 `api_params` 列中以 JSON 字符串的形式填入调用 AKShare 所需的函数名和参数。

**配置样例** (`Excel`)

| 指标ID | 指标名称 | 数据来源类型 | api_params | 表名/文件路径 |
| :--- | :--- | :--- | :--- | :--- |
| AUTO_SALES_W | 乘用车周度销量 | **AKShare** | `{"func": "car_market_weekly", "kwargs": {"symbol": "shanghai"}}` | - |
| AUTO_PRODUCTION_M | 汽车产量月度数据 | **EXCEL** | `{"sheet_name": "汽车产量", "date_col": "date", "value_col": "production"}` | `data/raw/汽车行业指标.xlsx` |
| REAL_ESTATE_SALES | 商品房销售面积 | **SQLITE** | `{"table_name": "real_estate_sales", "date_col": "date", "value_col": "sales_area"}` | `data/raw/房地产数据.db` |

#### 3.1.2 `DataConnector` 扩展说明

`DataConnector.fetch_data_by_id` 已支持 `data_source_type == "AKShare"`，并内置 `_standardize_akshare_df` 标准化逻辑；WindPy 采用延迟导入，Wind 不可用时会安全降级。本任务需要扩展 `DataConnector` 以支持 `"EXCEL"` 和 `"SQLITE"` 数据源类型。

需要在 `DataConnector` 类中新增两个方法：

1. `fetch_excel_data()`: 读取 Excel 文件数据
2. `fetch_sqlite_data()`: 读取 SQLite 数据库数据

并在 `fetch_data_by_id()` 方法中添加对应的分支处理。

### 3.2 行业指标选择示例

#### 3.2.1 汽车行业指标（示例）

汽车行业可选择以下2-4个核心指标，覆盖生产、销售、原材料等环节：

1. **乘用车周度销量** (AKShare)
   * 指标ID: `AUTO_SALES_W`
   * 数据源: AKShare
   * AKShare函数: `car_market_weekly`
   * 频率: 周度
   * 意义: 直接反映汽车终端销售情况

2. **汽车产量月度数据** (Excel)
   * 指标ID: `AUTO_PRODUCTION_M`
   * 数据源: Excel
   * 文件路径: `data/raw/汽车行业指标.xlsx`
   * 频率: 月度
   * 意义: 反映汽车生产情况

3. **轮胎开工率** (SQLite)
   * 指标ID: `TIRE_OPERATING_RATE`
   * 数据源: SQLite
   * 数据库路径: `data/raw/汽车行业数据.db`
   * 表名: `tire_operating_rate`
   * 频率: 周度
   * 意义: 反映汽车产业链上游情况

4. **钢铁价格指数** (AKShare)
   * 指标ID: `STEEL_PRICE_INDEX`
   * 数据源: AKShare
   * AKShare函数: `futures_zh_spot`
   * 频率: 日度
   * 意义: 反映汽车原材料成本

#### 3.2.2 房地产行业指标（示例）

房地产行业可选择以下2-4个核心指标，覆盖销售、投资、价格等环节：

1. **商品房销售面积** (SQLite)
   * 指标ID: `REAL_ESTATE_SALES`
   * 数据源: SQLite
   * 数据库路径: `data/raw/房地产数据.db`
   * 表名: `real_estate_sales`
   * 频率: 月度
   * 意义: 直接反映房地产销售情况

2. **房地产开发投资完成额** (Excel)
   * 指标ID: `REAL_ESTATE_INVESTMENT`
   * 数据源: Excel
   * 文件路径: `data/raw/房地产行业指标.xlsx`
   * 频率: 月度
   * 意义: 反映房地产投资情况

3. **百城住宅价格指数** (AKShare)
   * 指标ID: `HOUSE_PRICE_INDEX`
   * 数据源: AKShare
   * AKShare函数: `house_zh_average_price`
   * 频率: 月度
   * 意义: 反映房地产价格走势

4. **土地成交面积** (SQLite)
   * 指标ID: `LAND_TRANSACTION_AREA`
   * 数据源: SQLite
   * 数据库路径: `data/raw/房地产数据.db`
   * 表名: `land_transaction`
   * 频率: 月度
   * 意义: 反映土地市场活跃度

#### 3.2.3 数据格式要求

所有数据源的数据格式需要统一为时间序列格式：

* **Excel 数据格式** (`汽车行业指标.xlsx`)

  | date       | production | sales | price_index |
  |------------|------------|-------|-------------|
  | 2025-01-01 | 12000      | 15000 | 105.2       |
  | 2025-02-01 | 12500      | 15500 | 106.5       |
  | ...        | ...        | ...   | ...         |

* **SQLite 数据格式** (`房地产数据.db`)
  * 表名: `real_estate_sales`
  * 字段: `date` (TEXT, 格式 `YYYY-MM-DD`), `sales_area` (REAL), `investment` (REAL), `price_index` (REAL)

### 3.3 计算单个指标的周期扩散度

* 对统一后的 `DataFrame` 进行重采样（如取周均值）。
* 计算每个指标在当前周期相对于上一周期的变化方向（`np.sign(x.diff())`）。
* **代码复用**： 此部分逻辑与 `_calculate_signals` 函数中的 `direction_df = period_df.apply(lambda x: np.sign(x.diff()))` 完全一致，可直接复用。

### 3.4 合成行业景气度指数

* **行业景气度扩散指数A**(Diffusion_Index_A) = 所有指标方向值的平均值（标准化在 `[-1, 1]` 区间）。
* **（推荐）行业基准指数B**(Base_Index_B)： 设定基期（如 `100`），累加 `Diffusion_Index_A`。
* **（可选）同比指数C**(YoY_Index_C)： 计算基准指数B的同比变化率。
* **代码复用**： `_calculate_signals` 函数可直接用于计算。

### 3.5 可视化与输出

* **代码复用**： `_visualize` 函数提供了完美的三图联动模板，可以复用。
* **交互式可视化**： 仿照之前fund_analysis的交互式可视化方式实现网页版的联动图
* **输出**： 将结果保存到 Excel 文件中。

---

## 4. 具体执行步骤 (Action Steps)

### 4.1 扩展 DataConnector 支持 Excel 和 SQLite

1. **修改 `data_connector.py`**:
   * 在 `DataConnector` 类中新增 `fetch_excel_data()` 方法，用于读取 Excel 文件
   * 在 `DataConnector` 类中新增 `fetch_sqlite_data()` 方法，用于读取 SQLite 数据库
   * 在 `fetch_data_by_id()` 方法中添加对 `"EXCEL"` 和 `"SQLITE"` 数据源类型的支持

2. **配置参数说明**:
   * Excel 数据源: `api_params` 中需要包含 `sheet_name`、`date_col`、`value_col` 等参数
   * SQLite 数据源: `api_params` 中需要包含 `table_name`、`date_col`、`value_col` 等参数
   * 文件路径: 在配置表的 `表名/文件路径` 列中指定

### 4.2 更新配置文件

* 在 `高频宏观数据指标库.xlsx` 的 **"选定指标"** 表中，为汽车和房地产行业的指标添加配置：
  * 为 AKShare 指标设置 `data_source_type` 为 `"AKShare"`
  * 为 Excel 指标设置 `data_source_type` 为 `"EXCEL"`
  * 为 SQLite 指标设置 `data_source_type` 为 `"SQLITE"`
* 在 `api_params` 列中以 JSON 字符串的形式填入对应数据源所需的参数
* 在 `表名/文件路径` 列中指定文件路径或数据库表名

### 4.3 创建新脚本 `industry_analyzer.py`

1. **文件位置**: 放置在 `src/analyzers/` 目录下，与其他分析器保持一致
2. **类结构**: 创建 `IndustryAnalyzer` 类，继承或参考 `EconomyAnalyzer` 的设计
3. **核心方法**:
   * `analyze_auto_industry()`: 分析汽车行业
   * `analyze_real_estate_industry()`: 分析房地产行业
   * `_load_industry_data()`: 加载行业数据（复用 DataConnector）
   * `_calculate_signals()`: 复用 `fundamental_economy.py` 中的方法
   * `_visualize()`: 复用 `fundamental_economy.py` 中的可视化方法

### 4.4 实现独立打包和用户界面

1. **独立打包**:
   * 创建 `industry_analyzer` 目录，包含独立的运行脚本
   * 实现命令行接口，支持参数配置
   * 打包为可执行文件或 Docker 镜像

2. **用户界面**:
   * **GUI 版本**: 使用 PyQt5 或 Tkinter 实现桌面应用
   * **Web UI 版本**: 使用 Flask 或 Streamlit 实现网页应用
   * **核心功能**:
     * 行业选择（汽车/房地产）
     * 指标选择（从配置中动态加载）
     * 日期范围选择
     * 一键生成结果和图表
     * 结果导出（Excel、图片）

### 4.5 结果保存与文档撰写

1. **结果保存**:
   * 将两个行业的分析结果保存到 Excel 文件
   * 生成可视化图表（PNG/PDF 格式）
   * 保存中间计算结果

2. **文档撰写**:
   * 撰写详细的说明文档（Markdown 格式）
   * 包含代码说明、配置说明、使用说明
   * 添加示例数据和运行截图

---

## 5. 高级要求 (Advanced Requirements)

为了确保项目的完整性和实用性，以下高级要求必须完成：

### 5.1 信号有效性回测（必须完成）

* **目标**：验证生成的行业景气度指数对行业股价的预测能力
* **具体任务**：
  1. 获取汽车行业ETF（如515030.SH）和房地产行业ETF（如512200.SH）的历史价格数据
  2. 将行业景气度指数（特别是 `Diffusion_Index_A` 的正负切换点）与ETF价格走势进行对比分析
  3. 计算简单的回测指标：
     * 信号发出后N日的平均收益率
     * 胜率（正确预测涨跌的比例）
     * 夏普比率（风险调整后收益）
  4. 生成回测报告和可视化图表

### 5.2 多行业横向比较（必须完成）

* **目标**：分析汽车和房地产两个行业景气度的相关性和领先滞后关系
* **具体任务**：
  1. 将两个行业的 `Diffusion_Index_A` 绘制在同一张图上进行对比
  2. 计算两个指数之间的相关系数（滚动相关系数）
  3. 分析领先滞后关系（使用交叉相关性分析）
  4. 识别两个行业景气度分化或同步的时期，并结合宏观经济背景进行分析

### 5.3 动态权重探索（必须完成）

* **目标**：改进基础的平均权重方法，提升指数质量
* **具体任务**：
  1. 实现基于历史波动率的动态权重方法（波动率越低的指标权重越高）
  2. 实现基于与行业利润相关性的动态权重方法（相关性越高的指标权重越高）
  3. 比较不同权重方法下的指数表现
  4. 选择最优的权重方法并说明理由

### 5.4 数据库性能优化（必须完成）

* **目标**：优化数据存储和读取性能
* **具体任务**：
  1. 分析当前pyarrow和SQLite混合使用的性能瓶颈
  2. 实现数据缓存机制，减少重复读取
  3. 优化数据查询性能（索引优化、查询优化）
  4. 比较优化前后的性能差异，提供性能测试报告

---

## 6. 注意事项 (Notes)

* **代码风格**： 新脚本的代码风格、注释习惯应尽量与现有项目保持一致。
* **健壮性**： 代码应具备一定的健壮性，能处理常见的数据异常情况（如某天数据缺失）。
* **数据对齐**： 合并来自不同源的数据时，务必确保日期索引正确对齐。
* **沟通**： 在执行过程中遇到任何问题（如找不到合适指标、API 报错、逻辑不清晰等），请及时沟通。

---

## 7. 总结

本任务指南已经按照要求进行了全面更新，主要改进包括：

1. **明确项目集成路径**：指定新脚本放置在 `src/analyzers/` 目录下，与现有项目结构保持一致
2. **完善数据源集成**：将 Excel 和 SQLite 数据源集成到统一的 `DataConnector` 架构中，保持项目一致性
3. **固定行业和指标**：明确选择汽车和房地产两个行业，并提供具体的指标示例和数据格式要求
4. **扩展要求改为必须**：将原本的可选扩展方向改为必须完成的高级要求，包括信号回测、多行业比较、动态权重探索和数据库性能优化
5. **详细的环境依赖**：更新了环境依赖项表，包含 GUI 和 Web UI 开发所需的组件
6. **具体的执行步骤**：提供了从数据源扩展、配置更新、脚本开发到独立打包和用户界面实现的完整执行路径

