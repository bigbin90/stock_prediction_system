import akshare as ak
import pandas as pd
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
        """转换股票代码格式"""
        if self.market.upper() == 'SZ':
            return f"sz{self.stock_code}"
        else:
            return f"sh{self.stock_code}"

    def get_kline_data(self, start_date=None, end_date=None, period='daily', adjust='qfq'):
        """
        获取日K线数据
        period: 'daily'(日线), 'weekly'(周线), 'monthly'(月线)
        adjust: 'qfq'(前复权), 'hfq'(后复权), ''(不复权)
        返回DataFrame包含: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=3 * 365)).strftime('%Y%m%d')  # 默认3年

        time.sleep(self.delay)  # 控制请求频率
        try:
            df = ak.stock_zh_a_hist(
                symbol=self.stock_code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            if df is not None and not df.empty:
                # 统一列名
                df.columns = [c.strip() for c in df.columns]
                df.rename(columns={
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '成交额': 'amount', '振幅': 'amplitude',
                    '涨跌幅': 'pct_change', '涨跌额': 'change',
                    '换手率': 'turnover'
                }, inplace=True)
                df['date'] = pd.to_datetime(df['date'])
                df.sort_values('date', inplace=True)
                df.reset_index(drop=True, inplace=True)
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
        """获取个股资金流向数据（主力、超大单、大单、中单、小单）"""
        time.sleep(self.delay)
        try:
            market_lower = self.market.lower()  # AKShare要求小写市场代码
            df = ak.stock_individual_fund_flow(stock=self.stock_code, market=market_lower)
            if df is not None and not df.empty:
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"[TechnicalData] 获取资金流向失败: {e}")
            return pd.DataFrame()