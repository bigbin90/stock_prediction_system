"""
智能股价预测系统 - 配置文件
所有全局参数集中管理，便于调优
"""

# ========== 数据源配置 ==========
DATA_SOURCE = {
    "primary": "akshare",       # 主数据源: akshare
    "fallback": "eastmoney",    # 备用数据源
    "request_delay": 0.5,       # 请求间隔(秒)，避免触发反爬
    "max_retries": 3,           # 最大重试次数
}

# ========== 股票代码配置 ==========
STOCK_DEFAULT = {
    "code": "000001",           # 默认股票代码
    "market": "SZ",             # 市场: SZ(深交所), SH(上交所)
    "name": "平安银行",          # 默认股票名称
}

# ========== 技术分析参数 ==========
TECHNICAL_PARAMS = {
    # 移动平均线周期
    "ma_periods": [5, 10, 20, 60],
    # MACD参数
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    # RSI参数
    "rsi_period": 14,
    # KDJ参数
    "kdj_k": 9,
    "kdj_d": 3,
    # BOLL参数
    "boll_period": 20,
    "boll_std": 2,
    # 成交量均量线周期
    "volume_ma_periods": [5, 20],
}

# ========== 预测模型参数 ==========
PREDICTION_PARAMS = {
    # 短期预测（1周 ≈ 5交易日）
    "short_term": {"period": "1w", "days": 5, "confidence_weight": 0.3},
    # 中期预测（1个月 ≈ 20交易日）
    "mid_term": {"period": "1m", "days": 20, "confidence_weight": 0.3},
    # 长期预测（3个月 ≈ 60交易日）
    "long_term": {"period": "3m", "days": 60, "confidence_weight": 0.25},
    # 超长期预测（6个月 ≈ 120交易日）
    "ultra_long_term": {"period": "6m", "days": 120, "confidence_weight": 0.15},
}

# ========== 基本面分析参数 ==========
FUNDAMENTAL_PARAMS = {
    "recent_years": 2,          # 最近N年年报
    "recent_quarters": 4,       # 最近N个季度
}

# ========== 情绪分析参数 ==========
SENTIMENT_PARAMS = {
    "news_days": 90,            # 近期新闻天数(3个月)
    "max_news_items": 50,       # 最大新闻数量
}

# ========== 置信度评分权重 ==========
CONFIDENCE_WEIGHTS = {
    "technical_score": 0.30,    # 技术面权重
    "fundamental_score": 0.25,  # 基本面权重
    "sentiment_score": 0.15,    # 情绪面权重
    "trend_consistency": 0.20,  # 多周期趋势一致性
    "volatility_factor": 0.10,  # 波动率因子
}

# ========== Web服务配置 ==========
import os
WEB_CONFIG = {
    "host": os.environ.get("FLASK_HOST", "127.0.0.1"),
    "port": int(os.environ.get("FLASK_PORT", "8765")),
    "debug": False,
}