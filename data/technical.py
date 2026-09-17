import akshare as ak
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from config import DATA_SOURCE, STOCK_DEFAULT


class TechnicalDataCollector:
    """
    技术面数据采集器
    获取: 日K线(OHLCV)、成交量/额、各时间周期数据
    """

    def __init__(self, stock_code=None, market=None):
        self.stock_code = stock_code or STOCK_DEFAULT['code']
        self.market = market or STOCK_DEFAULT['market']
        self.delay = DATA_SOURCE['request_delay']

    def _make_symbol(self):
        """转换股票代码格式为新浪格式 (sz000001 / sh600000)"""
        if self.market.upper() == 'SZ':
            return f"sz{self.stock_code}"
        else:
            return f"sh{self.stock_code}"

    def get_kline_data(self, start_date=None, end_date=None, period='daily', adjust='qfq'):
        """
        获取日K线数据（使用新浪数据源）
        period: 'daily'(日线), 'weekly'(周线), 'monthly'(月线)
        adjust: 'qfq'(前复权), 'hfq'(后复权), ''(不复权)
        返回DataFrame包含: date, open, close, high, low, volume, amount, amplitude, pct_change, change, turnover
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=3 * 365)).strftime('%Y%m%d')

        time.sleep(self.delay)

        try:
            # 使用新浪数据源替代东方财富（东方财富API在容器中被封禁）
            symbol = self._make_symbol()
            df = ak.stock_zh_a_daily(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )

            if df is not None and not df.empty:
                # 统一列名
                df = df.rename(columns={
                    'date': 'date',
                    'open': 'open',
                    'close': 'close',
                    'high': 'high',
                    'low': 'low',
                    'volume': 'volume',
                    'amount': 'amount',
                    'outstanding_share': 'outstanding_share',
                    'turnover': 'turnover',
                })

                # 确保日期列格式正确
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)

                # 计算缺失的列（新浪数据源不提供涨跌幅、涨跌额、振幅）
                df['change'] = df['close'].diff()
                df['pct_change'] = (df['close'].pct_change() * 100).round(2)
                # 振幅 = (最高 - 最低) / 前收盘 * 100
                df['prev_close'] = df['close'].shift(1)
                df['amplitude'] = np.where(
                    df['prev_close'] > 0,
                    ((df['high'] - df['low']) / df['prev_close'] * 100).round(2),
                    0
                )
                df = df.drop(columns=['prev_close'])

                # 过滤日期范围
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

                # 周线和月线转换
                if period == 'weekly':
                    df = df.set_index('date').resample('W').agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum',
                        'amount': 'sum',
                        'change': 'sum',
                        'pct_change': 'sum',
                        'amplitude': lambda x: (x.max() - x.min()) / x.iloc[0] * 100 if len(x) > 0 and x.iloc[0] != 0 else 0,
                        'turnover': 'sum',
                    }).dropna().reset_index()
                elif period == 'monthly':
                    df = df.set_index('date').resample('ME').agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum',
                        'amount': 'sum',
                        'change': 'sum',
                        'pct_change': 'sum',
                        'amplitude': lambda x: (x.max() - x.min()) / x.iloc[0] * 100 if len(x) > 0 and x.iloc[0] != 0 else 0,
                        'turnover': 'sum',
                    }).dropna().reset_index()

            return df

        except Exception as e:
            print(f"[TechnicalData] 获取K线失败: {e}")
            return pd.DataFrame()

    def get_multi_period_data(self):
        """
        获取多个时间周期的K线数据
        返回: {'3y': df_3year, '1y': df_1year, '3m': df_3month,
               '1m': df_1month, '2w': df_2week, '1w': df_1week,
               '3d': df_3day, '1d': df_1day}
        """
        now = datetime.now()
        periods = {
            '3y': now - timedelta(days=3 * 365),
            '1y': now - timedelta(days=365),
            '3m': now - timedelta(days=90),
            '1m': now - timedelta(days=30),
            '2w': now - timedelta(days=14),
            '1w': now - timedelta(days=7),
            '3d': now - timedelta(days=3),
        }

        result = {}
        full_data = self.get_kline_data()
        if full_data.empty:
            return result

        for name, start in periods.items():
            mask = full_data['date'] >= start
            result[name] = full_data[mask].copy()

        # 当日数据(最后一条)
        if not full_data.empty:
            result['1d'] = full_data.iloc[-1:].copy()

        return result

    def get_fund_flow(self):
        """
        获取个股资金流向数据（主力、超大单、大单、中单、小单）
        注意：东方财富API在容器环境中不可用，此功能暂时返回空数据
        """
        time.sleep(self.delay)
        try:
            market_lower = self.market.lower()
            df = ak.stock_individual_fund_flow(stock=self.stock_code, market=market_lower)
            if df is not None and not df.empty:
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"[TechnicalData] 获取资金流向失败（东方财富API不可用）: {e}")
            return pd.DataFrame()