import akshare as ak
import pandas as pd
import time
from datetime import datetime
from config import DATA_SOURCE, FUNDAMENTAL_PARAMS, STOCK_DEFAULT


class FundamentalDataCollector:
    """
    基本面数据采集器
    获取: 财务报表、估值指标、行业对比数据
    """

    def __init__(self, stock_code=None):
        self.stock_code = stock_code or STOCK_DEFAULT['code']
        self.delay = DATA_SOURCE['request_delay']

    def _safe_get(self, func, *args, **kwargs):
        """安全调用akshare函数"""
        time.sleep(self.delay)
        try:
            df = func(*args, **kwargs)
            return df
        except Exception as e:
            print(f"[FundamentalData] 获取失败: {e}")
            return pd.DataFrame()

    def get_financial_indicators(self):
        """
        获取财务分析指标（86+指标）
        返回包含: ROE、毛利率、净利率、资产负债率、每股收益等
        """
        df = self._safe_get(ak.stock_financial_analysis_indicator, symbol=self.stock_code, start_year='2023')
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
        return df

    def get_income_sheet(self):
        """获取利润表（按年度）"""
        df = self._safe_get(ak.stock_profit_sheet_by_yearly_em, symbol=self.stock_code)
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
        return df

    def get_balance_sheet(self):
        """获取资产负债表（按报告期）"""
        df = self._safe_get(ak.stock_balance_sheet_by_report_em, symbol=self.stock_code)
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
        return df

    def get_cash_flow(self):
        """获取现金流量表（按季度）"""
        df = self._safe_get(ak.stock_cash_flow_sheet_by_quarterly_em, symbol=self.stock_code)
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
        return df

    def get_valuation_data(self):
        """
        获取估值指标
        从财务指标中提取PE/PB等信息
        """
        # 注意：AKShare 1.18版本中 stock_a_lg_indicator 已移除
        # 使用 stock_financial_analysis_indicator 提供的财务指标替代
        # 如需完整的PE/PB历史数据，可考虑使用乐咕乐股等第三方来源
        df = self.get_financial_indicators()
        if not df.empty:
            # 尝试从财务指标中提取估值相关的衍生数据
            pass
        return pd.DataFrame()  # 返回空DataFrame，估值数据在报告阶段通过其他方式获取

    def get_industry_comparison(self):
        """
        获取行业对比数据
        """
        time.sleep(self.delay)
        try:
            df = ak.stock_board_industry_spot_em()
            if df is not None and not df.empty:
                df.columns = [c.strip() for c in df.columns]
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"[FundamentalData] 获取行业数据失败: {e}")
            return pd.DataFrame()

    def get_stock_info(self):
        """获取股票基本信息（所属行业等）"""
        time.sleep(self.delay)
        try:
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                df.columns = [c.strip() for c in df.columns]
                result = df[df['code'] == self.stock_code]
                if not result.empty:
                    return result.iloc[0].to_dict()
            return {}
        except Exception as e:
            print(f"[FundamentalData] 获取股票信息失败: {e}")
            return {}

    def get_all_fundamental_data(self):
        """获取全部基本面数据（整合后的摘要）"""
        result = {}

        # 财务分析指标
        fin = self.get_financial_indicators()
        if not fin.empty:
            result['financial_indicators'] = fin

        # 估值数据（通过财务指标间接获取）
        # 如需完整PE/PB历史数据，可考虑使用乐咕乐股或东方财富数据
        fin_data = result.get('financial_indicators', pd.DataFrame())
        if not fin_data.empty:
            result['valuation'] = fin_data  # 标记为财务衍生数据

        # 行业对比
        ind = self.get_industry_comparison()
        if not ind.empty:
            result['industry'] = ind

        # 股票信息
        info = self.get_stock_info()
        if info:
            result['stock_info'] = info

        return result