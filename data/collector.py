"""
数据采集核心模块 - 整合所有数据源
协调技术面、基本面、情绪面数据采集
"""

from data.technical import TechnicalDataCollector
from data.fundamental import FundamentalDataCollector
from data.sentiment import SentimentDataCollector
from config import STOCK_DEFAULT


class DataCollector:
    """
    统一数据采集入口
    整合技术面、基本面、情绪面三方面数据
    """

    def __init__(self, stock_code=None, stock_name=None, market=None):
        self.stock_code = stock_code or STOCK_DEFAULT['code']
        self.stock_name = stock_name or STOCK_DEFAULT['name']
        self.market = market or STOCK_DEFAULT['market']

        # 初始化各数据采集器
        self.technical = TechnicalDataCollector(stock_code, market)
        self.fundamental = FundamentalDataCollector(stock_code)
        self.sentiment = SentimentDataCollector(stock_code, stock_name)

    def collect_all(self):
        """
        采集全部数据
        返回: {
            'technical': {...},
            'fundamental': {...},
            'sentiment': {...}
        }
        """
        result = {}

        # 1. 技术面数据
        print("[DataCollector] 正在采集技术面数据...")
        multi_period = self.technical.get_multi_period_data()
        fund_flow = self.technical.get_fund_flow()
        result['technical'] = {
            'multi_period_kline': multi_period,
            'fund_flow': fund_flow,
        }

        # 2. 基本面数据
        print("[DataCollector] 正在采集基本面数据...")
        result['fundamental'] = self.fundamental.get_all_fundamental_data()

        # 3. 情绪面数据
        print("[DataCollector] 正在采集新闻舆情数据...")
        result['sentiment'] = self.sentiment.get_all_sentiment_data()

        return result