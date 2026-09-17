# 智能股价预测系统 · Docker 部署文档（Docker Desktop / macOS）

本文档面向**本地 Docker Desktop** 环境，描述如何将项目打包为 Docker 镜像并一键部署到本机运行。所有命令均以 macOS + Docker Desktop（Docker Compose v2）为准。

---

## 1. 项目概览

| 项目 | 说明 |
|------|------|
| 系统名称 | 智能股价预测系统 |
| 技术栈 | Python 3.11 + Flask + ECharts + AKShare |
| 部署方式 | Docker 容器化（Dockerfile + docker-compose.yml） |
| 对外端口 | **8766**（宿主机） → 8765（容器内） |
| 镜像名 | `stock_prediction_system-stock-prediction:latest` |
| 容器名 | `stock-prediction` |
| 数据源 | 全部免费，无需付费 API Key |

### 当前功能清单

- **多维度数据采集**：技术面（K 线、资金流向）、基本面（财务指标、估值）、情绪面（新闻舆情 + SnowNLP 情感分析）
- **技术指标**：MA、MACD、RSI、KDJ、BOLL、成交量均量线（纯 pandas/numpy，无 TA-Lib 依赖）
- **多周期预测**：短期（1 周）/ 中期（1 月）/ 长期（3 月）/ 超长期（6 月）
- **财务报告分析**：近 3 年营收、净利润、毛利率（巨潮资讯网）
- **股东人数 & 员工数量**：近 3 年股东户数、员工数变化（东方财富数据中心）

---

## 2. 前置要求

1. 已安装并启动 **Docker Desktop**（要求支持 BuildKit 与 Compose v2）。
2. 终端可用，验证环境：

   ```bash
   docker --version
   docker compose version
   ```

   若第二条报错，请升级 Docker Desktop，或改用 `docker-compose`（v1）替换下文所有 `docker compose`。

---

## 3. 快速开始

```bash
# 进入项目目录
cd stock_prediction_system

# 构建镜像并后台启动容器（首次约 15-20 分钟，取决于网络）
docker compose up -d --build

# 等待健康检查通过（约 1 分钟后 STATUS 显示 healthy）
docker ps --filter name=stock-prediction

# 浏览器访问
open http://localhost:8766
```

---

## 4. 分步部署

### 4.1 构建镜像

```bash
docker compose build
```

> 构建优化：`Dockerfile` 基础镜像已走 daocloud 加速器（`docker.m.daocloud.io/library/python:3.11`），pip 依赖使用阿里云 PyPI 镜像与 300 秒下载超时，避免下载卡死。
> 后续重复构建会命中 Docker 缓存层，速度明显提升；如需彻底重构建使用 `docker compose build --no-cache`。

### 4.2 启动容器

```bash
docker compose up -d
```

`-d` 表示后台运行。省略 `-d` 可前台实时查看启动日志。

### 4.3 校验健康状态

```bash
# 查看运行状态（应显示 healthy）
docker ps --filter name=stock-prediction

# HTTP 探活（返回 200 即正常）
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8766/
```

容器内置了健康检查（间隔 30s、超时 10s、启动等待 60s、最多重试 3 次），探活地址为容器内 `http://127.0.0.1:8765/`。

### 4.4 验证核心接口

```bash
# 财务报告分析（贵州茅台）
curl -s -X POST http://localhost:8766/api/stock/financial_report \
  -H "Content-Type: application/json" \
  -d '{"code":"600519","years":3}'

# 股东人数 & 员工数量
curl -s -X POST http://localhost:8766/api/stock/shareholder_employee \
  -H "Content-Type: application/json" \
  -d '{"code":"000001","years":3}'
```

---

## 5. 端口与目录挂载

### 端口映射

| 宿主机 | 容器内 | 说明 |
|--------|--------|------|
| 8766 | 8765 | Web 服务对外端口 |

- 容器内通过环境变量 `FLASK_HOST=0.0.0.0`、`FLASK_PORT=8765` 全绑定监听。
- 修改对外端口：编辑 `docker-compose.yml` 的 `ports`，例如改为 `"8767:8765"` 后 `docker compose up -d` 生效。

### 目录挂载（代码热更新基础）

`docker-compose.yml` 将以下路径挂载进容器，修改后**重启容器即可生效，无需重新构建镜像**：

| 宿主机（项目内） | 容器内 | 内容 |
|------------------|--------|------|
| `./data` | `/app/data` | 数据采集层（含 `financial_report.py`） |
| `./models` | `/app/models` | 预测模型层 |
| `./indicators` | `/app/indicators` | 技术指标计算层 |
| `./config.py` | `/app/config.py` | 全局配置 |
| `./web/app.py` | `/app/web/app.py` | Flask 服务 |
| `./web/templates` | `/app/web/templates` | 前端页面 |

> 仅当修改了 `Dockerfile` 或 `requirements-docker.txt` 时才需要重新 `docker compose build`。

---

## 6. 数据源说明

| 模块 | 数据源 | 获取内容 |
|------|--------|----------|
| `data/technical.py` | AKShare · 新浪 `stock_zh_a_daily` | 日/周/月 K 线（OHLCV + 涨跌幅 + 换手率） |
| `data/technical.py` | AKShare · 东方财富 | 个股资金流向 |
| `data/fundamental.py` | AKShare · 同花顺/巨潮 | 财务指标、利润表、财务摘要、行业对比 |
| `data/sentiment.py` | AKShare · 东方财富（降级新浪/财新） | 个股新闻；SnowNLP 情感打分 |
| `data/financial_report.py` | **巨潮资讯网** `cninfo.com.cn` | 近 3 年营收、净利润、毛利率 |
| `data/financial_report.py` | **东方财富数据中心** `datacenter.eastmoney.com` | 近 3 年股东户数、员工数量 |

> 说明：`financial_report.py` 使用 `requests` 直连上述两个公开接口，不依赖 AKShare，已做沪深证券代码适配（如 `600519.SH` / `000001.SZ`）。东方财富数据处理接口若在容器网段被限流，会走 AKShare 备用源或降级逻辑。

---

## 7. 配置修改（`config.py`）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STOCK_DEFAULT.code/market/name` | 000001 / SZ / 平安银行 | 默认股票 |
| `DATA_SOURCE.request_delay` | 0.5 | 请求间隔（秒） |
| `DATA_SOURCE.max_retries` | 3 | 最大重试次数 |
| `WEB_CONFIG.host` | 127.0.0.1 | 直接本地运行时生效；Docker 中由 `FLASK_HOST` 覆盖 |
| `WEB_CONFIG.port` | 8765 | 监听端口；Docker 中由 `FLASK_PORT` 覆盖 |

修改 `config.py` 后（该文件已挂载），执行 `docker compose restart` 即生效。

---

## 8. 容器日常运维

```bash
# 实时查看日志
docker compose logs -f

# 查看最近 50 条日志
docker compose logs --tail=50

# 重启容器（代码改动后常用）
docker compose restart

# 停止 / 启动
docker compose stop
docker compose start

# 停止并删除容器（保留镜像与挂载的数据）
docker compose down

# 进入容器内部调试
docker compose exec stock-prediction bash

# 查看资源占用
docker stats stock-prediction
```

> `restart: unless-stopped` 已配置，宿主机（Docker Desktop）重启后容器会自动拉起。

---

## 9. 常见问题排查

### Q1：`docker compose up` 报端口被占用
```bash
lsof -i :8766
```
找到占用进程后释放，或在 `docker-compose.yml` 中改 `ports` 为其他端口（如 `8767:8765`）。

### Q2：首次构建下载慢 / 卡住
- `Dockerfile` 基础镜像已显式走 daocloud 加速器（`docker.m.daocloud.io/library/python:3.11`，约 900MB），pip 依赖走阿里云镜像。
- 注意：仅在 Docker Engine 配置 `registry-mirrors` 无法解决 `docker.io` 基镜像的 401/403 解析失败问题（BuildKit 匿名 HEAD 与镜像站鉴权不兼容），因此项目改用「Dockerfile 里显式写镜像主机」的方式拉取基础镜像。

### Q3：容器 STATUS 一直不出现 `healthy` 或显示 `unhealthy`
```bash
docker compose logs --tail=100
```
常见原因：首次启动数据源网络初始化较慢（健康检查起始等待 60s），或依赖下载未完成。等待后仍异常，检查日志中的 Traceback。

### Q4：修改代码后没有生效
确认修改的是**已挂载**的路径（见第 5 节），然后 `docker compose restart`。若改了 `Dockerfile` 或 `requirements-docker.txt`，必须 `docker compose up -d --build`。

### Q5：某只股票财务报告 / 股东数据返回为空
该数据依赖公开接口，部分停牌、次新股或数据未披露的标的可能无数据；前端与接口均已做“无数据”兜底提示。可换用贵州茅台（600519）、平安银行（000001）等验证。

### Q6：如何升级 AKShare
修改 `requirements-docker.txt` 中 `akshare>=x.y.z` 的版本下限，然后：
```bash
docker compose up -d --build
```

---

## 10. 当前 API 接口清单

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页面 |
| `/api/stock/analyze` | POST | 完整分析（技术面 + 基本面 + 情绪面 + 多周期预测） |
| `/api/stock/search` | POST | 股票名称/代码模糊搜索 |
| `/api/stock/kline` | POST | K 线数据 |
| `/api/stock/fundamental` | POST | 基本面数据 |
| `/api/stock/indicators` | POST | 技术指标数据（近 30 条） |
| `/api/stock/financial_report` | POST | 近 3 年财务报告分析（巨潮资讯网） |
| `/api/stock/shareholder_employee` | POST | 近 3 年股东户数、员工数量（东方财富数据中心） |

---

> **免责声明：** 本系统所有预测结果均为基于历史数据的统计推断，不构成任何投资建议。股市有风险，投资需谨慎。