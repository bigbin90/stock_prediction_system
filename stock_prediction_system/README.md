# 智能股价预测系统

基于 AKShare 的多维度股票分析与多周期价格预测系统。集数据采集、技术指标计算、多周期预测与可视化展示于一体，完全基于免费数据源，无需任何付费 API。

## 核心功能

- **多维度数据采集**：整合技术面（OHLCV、资金流向）、基本面（财务指标、估值）、情绪面（新闻舆情情感分析）三类数据
- **全面技术指标**：纯 pandas/numpy 实现 MA、MACD、RSI、KDJ、BOLL、成交量均量线等 6 大类指标
- **多周期预测**：短期（1 周）、中期（1 个月）、长期（3 个月）、超长期（6 个月）四个周期综合预测
- **动态情景分析**：基于实时技术指标状态（RSI、MACD、BOLL 位置等）自动生成情景事件，非硬编码模板
- **交互式 Web 界面**：Flask + ECharts 提供美观的 K 线图展示、预测面板和新闻舆情可视化
- **智能搜索**：支持股票名称/代码实时模糊搜索，自动识别市场（SH/SZ），一键触达

## 系统架构

```
stock_prediction_system/
├── config.py                  # 全局配置（数据源、指标参数、预测参数）
├── main.py                    # 双模式入口（Web / CLI）
├── requirements.txt            # 完整依赖清单
├── requirements-docker.txt     # Docker 精简依赖
├── Dockerfile                  # Docker 镜像构建文件
├── docker-compose.yml          # Docker Compose 编排配置
├── .dockerignore               # Docker 构建忽略规则
│
├── data/                       # 数据采集层
│   ├── collector.py            # DataCollector 协调器
│   ├── technical.py            # 技术面数据采集（K线、资金流向）
│   ├── fundamental.py          # 基本面数据采集（财务指标、行业对比）
│   └── sentiment.py            # 情绪面数据采集（新闻舆情、情感分析）
│
├── indicators/                 # 指标计算层
│   └── calculator.py           # 技术指标计算（MA/MACD/RSI/KDJ/BOLL）
│
├── models/                     # 预测模型层
│   └── predictor.py            # 多周期预测 + 置信度评估 + 情景分析
│
├── reports/                    # 报告生成
│   └── generator.py            # 文本/JSON 格式报告输出
│
└── web/                        # Web 展示层
    ├── app.py                  # Flask API 服务器
    └── templates/
        └── index.html          # 单页 Web 应用（ECharts 可视化）
```

## 数据来源

所有数据通过 [AKShare](https://akshare.akfamily.xyz/) 免费开源库获取，无需付费 API Key。

| 模块 | 数据源 | 获取内容 |
|------|--------|----------|
| `technical.py` | `ak.stock_zh_a_hist` | 日/周/月 K 线（OHLCV + 成交量额 + 涨跌幅 + 换手率） |
| `technical.py` | `ak.stock_individual_fund_flow` | 个股资金流向（主力/超大单/大单/中单/小单） |
| `fundamental.py` | `ak.stock_financial_analysis_indicator` | 86+ 财务分析指标（ROE、毛利率、净利率等） |
| `fundamental.py` | `ak.stock_profit_sheet_by_yearly_em` | 年度利润表 |
| `fundamental.py` | `ak.stock_balance_sheet_by_report_em` | 资产负债表 |
| `fundamental.py` | `ak.stock_board_industry_spot_em` | 行业板块行情对比 |
| `sentiment.py` | `ak.stock_news_em` | 个股相关新闻（标题/来源/时间/链接） |
| `sentiment.py` | SnowNLP | 中文情感分析（积极/中性/消极分类） |

> 注意：系统默认使用 `ak.stock_news_em` 获取个股新闻，若失败则自动降级为新浪财经滚动新闻或财新市场要闻，确保始终有舆情数据可展示。

## 技术指标

纯 pandas/numpy 实现，**无 TA-Lib 依赖**。

- **MA**（移动平均线）：5/10/20/60 日四周期
- **MACD**（指数平滑异同平均）：12/26/9 标准参数，含 DIF、DEA、MACD 柱
- **RSI**（相对强弱指数）：14 日周期，含超买（>80）/超卖（<20）判断
- **KDJ**（随机指标）：9/3/3 标准参数，含 J 值超买（>100）/超卖（<0）
- **BOLL**（布林带）：20 日周期，2 倍标准差，含带宽指标
- **VOL_MA**（成交量均量线）：5/20 日两周期

## 预测模型

### 多周期预测

| 周期 | 时间跨度 | 交易日数 | 基准权重 |
|------|----------|----------|----------|
| 短期 | 1 周 | 5 天 | 0.30 |
| 中期 | 1 个月 | 20 天 | 0.30 |
| 长期 | 3 个月 | 60 天 | 0.25 |
| 超长期 | 6 个月 | 120 天 | 0.15 |

### 预测维度权重

- **技术面（30%）**：均线系统趋势 + MACD 金叉/死叉 + RSI 强度 + KDJ 信号 + BOLL 位置
- **基本面（25%）**：ROE 质量 + 营收增长率
- **情绪面（15%）**：新闻情感分析平均得分
- **多周期趋势一致性（20%）**：不同时间维度信号的相互验证
- **波动率因子（10%）**：历史波动率对价格区间的影响

> **风险提示：** 本系统所有预测均为基于历史数据的统计推断，不构成任何投资建议。股市有风险，投资需谨慎。

### 动态情景分析

情景分析并非硬编码模板，而是基于当前实时技术指标状态自动生成：
- **RSI 状态**：超买区/偏强/中性/偏弱/超卖，对应生成回升或回落情景
- **MACD 状态**：金叉/死叉持续或反转情景
- **BOLL 位置**：价格在轨道中的位置，对应反弹或压力情景
- **均线排列**：多头/空头/交叉排列，对应趋势延续或逆转情景
- **KDJ 的 J 值**：超买/超卖警示情景

每个周期生成 5 个情景事件（3 个同向 + 2 个反向），并附带概率评估（较高/中等）。

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stock/analyze` | POST | 完整分析股票（技术面 + 基本面 + 情绪面 + 多周期预测） |
| `/api/stock/search` | POST | 模糊搜索股票（支持名称/代码，自动识别市场） |
| `/api/stock/kline` | POST | 获取 K 线数据（支持日/周/月，可指定天数） |
| `/api/stock/fundamental` | POST | 获取基本面数据 |
| `/api/stock/indicators` | POST | 获取技术指标数据（最近 30 条） |

### 请求示例

```json
// 分析股票 POST /api/stock/analyze
{
    "code": "000001",
    "name": "平安银行",
    "market": "SZ"
}

// 搜索股票 POST /api/stock/search
{
    "keyword": "平安"
}
```

## 部署方式

### Docker 部署（推荐）

确保 Docker Desktop 已安装并运行。

```bash
# 进入项目目录
cd stock_prediction_system

# 构建并启动容器（首次构建约 15-20 分钟，取决于网络）
docker compose up -d

# 查看启动日志
docker compose logs -f

# 访问 Web 界面
open http://127.0.0.1:8765
```

#### 管理容器

```bash
# 重启容器
docker compose restart

# 停止容器
docker compose down

# 查看容器状态
docker ps --filter name=stock-prediction

# 查看资源占用
docker stats stock-prediction

# 重新构建（修改代码后）
docker compose build --no-cache stock-prediction
docker compose up -d
```

#### Docker 注意事项

- 默认端口为 8765，可通过修改 `docker-compose.yml` 中的 `ports` 映射更改
- 容器设置了健康检查（间隔 30s，超时 10s，起始等待 60s）
- `restart: unless-stopped` 确保宿主机重启后自动运行
- 时区默认北京（Asia/Shanghai）

### 本地直接运行

#### 安装依赖

```bash
# 推荐使用 Python 3.11+
pip install akshare flask flask-cors pandas numpy snownlp lxml beautifulsoup4 requests --break-system-packages
```

#### 启动 Web 服务

```bash
# 方式一：使用主入口
python main.py

# 方式二：直接启动 Flask
python web/app.py

# 方式三：指定端口
python main.py --port 8080
```

#### CLI 模式（无需浏览器）

```bash
# 分析指定股票
python main.py --cli 600519 SH --name 贵州茅台
```

> **注意：** 首次运行需要下载 AKShare 数据缓存和 SnowNLP 词典，可能需要 30-60 秒。后续请求将使用缓存。

## 配置说明

所有配置集中在 `config.py` 文件中，主要参数包括：

| 配置项 | 参数 | 默认值 | 说明 |
|--------|------|--------|------|
| `DATA_SOURCE` | request_delay | 0.5 | API 请求间隔（秒） |
| `DATA_SOURCE` | max_retries | 3 | 最大重试次数 |
| `STOCK_DEFAULT` | code/market/name | 000001/SZ/平安银行 | 默认股票 |
| `TECHNICAL_PARAMS` | ma_periods | [5,10,20,60] | MA 周期列表 |
| `TECHNICAL_PARAMS` | macd_fast/slow/signal | 12/26/9 | MACD 标准参数 |
| `TECHNICAL_PARAMS` | rsi_period | 14 | RSI 周期 |
| `TECHNICAL_PARAMS` | kdj_k/kdj_d | 9/3 | KDJ 参数 |
| `TECHNICAL_PARAMS` | boll_period/boll_std | 20/2 | 布林带参数 |
| `PREDICTION_PARAMS` | 各周期天数 | 5/20/60/120 | 四周期交易日数 |
| `CONFIDENCE_WEIGHTS` | 各维度权重 | 0.30/0.25/0.15/... | 置信度评估权重 |
| `SENTIMENT_PARAMS` | max_news_items | 50 | 最大新闻数量 |
| `WEB_CONFIG` | host/port | 0.0.0.0:8765 | Web 服务地址（Docker 默认全绑定） |

## 常见问题

### Q: 为什么新闻舆情大部分显示"中性"？

系统使用 SnowNLP 对新闻标题进行情感分析，默认阈值划分：评分 > 0.55 为积极，< 0.45 为消极，其余为中性。大部分财经新闻标题本身偏客观报道，因此中性占比较高。这是正常现象，综合得分仍准确反映了整体情感偏向。

### Q: 如何更改默认股票？

修改 `config.py` 中的 `STOCK_DEFAULT` 配置，或在 Web 界面输入框中直接搜索。

### Q: 数据来源是否稳定？

AKShare 是免费的 Python 金融数据接口库，持续维护更新。如果某个 API 失效，系统会自动切换到备用数据源。如遇到版本兼容问题，可更新 AKShare：`pip install akshare --upgrade`

### Q: 为什么 K 线图上涨为红色，下跌为绿色？

这是遵循 A 股市场惯例：红色代表上涨，绿色代表下跌。页面中的"看涨"标签也使用红色显示，保持一致。

### Q: Docker 构建太慢怎么办？

首次构建需要下载 python:3.11 基础镜像（约 900MB）和所有 Python 依赖（约 500MB）。建议使用稳定的网络环境。后续构建会利用 Docker 缓存层，速度将大幅提升。

---

> **免责声明：** 本系统所有预测均为基于历史数据的统计推断，不构成任何投资建议。股市有风险，投资需谨慎。