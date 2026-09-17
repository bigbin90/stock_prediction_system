"""
技术指标计算器
纯pandas/numpy实现，不依赖TA-Lib
支持MA、MACD、RSI、KDJ、BOLL、成交量均量线等常用技术指标
"""

import pandas as pd
import numpy as np
from config import TECHNICAL_PARAMS


class TechnicalIndicatorCalculator:
    """
    技术指标计算器
    使用纯pandas实现所有常用技术指标的计算
    """

    def __init__(self):
        self.params = TECHNICAL_PARAMS

    def calculate_all(self, df):
        """
        计算全部技术指标

        Parameters
        ----------
        df : DataFrame
            必须包含列: open, high, low, close, volume

        Returns
        -------
        DataFrame
            增加了技术指标列的DataFrame
        """
        if df is None or df.empty:
            print("[Indicator] 输入数据为空")
            return df

        if len(df) < 60:
            print(f"[Indicator] 数据不足(仅有{len(df)}行)，无法计算全部指标")
            return df

        result = df.copy()
        result = self._calc_ma(result)
        result = self._calc_macd(result)
        result = self._calc_rsi(result)
        result = self._calc_kdj(result)
        result = self._calc_boll(result)
        result = self._calc_volume_ma(result)
        print(f"[Indicator] 技术指标计算完成，共 {len(result)} 行数据")
        return result

    # ----- 移动平均线 MA -----

    def _calc_ma(self, df):
        """计算移动平均线 (Simple Moving Average)"""
        for period in self.params['ma_periods']:
            df[f'MA{period}'] = df['close'].rolling(window=period).mean()
        return df

    # ----- MACD -----

    def _calc_macd(self, df):
        """
        计算MACD指标
        DIF = EMA(快) - EMA(慢)
        DEA = EMA(DIF, signal)
        MACD柱 = 2 * (DIF - DEA)
        """
        fast = self.params['macd_fast']
        slow = self.params['macd_slow']
        signal = self.params['macd_signal']

        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        df['DIF'] = ema_fast - ema_slow
        df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
        df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        return df

    # ----- RSI -----

    def _calc_rsi(self, df):
        """
        计算RSI指标
        RS = 平均上涨幅度 / 平均下跌幅度
        RSI = 100 - 100 / (1 + RS)
        """
        period = self.params['rsi_period']
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        # 避免除零
        avg_loss_safe = avg_loss.replace(0, np.nan)
        rs = avg_gain / avg_loss_safe
        df[f'RSI{period}'] = result = 100 - (100 / (1 + rs))
        df[f'RSI{period}'] = result.fillna(50)
        return df

    # ----- KDJ -----

    def _calc_kdj(self, df):
        """
        计算KDJ指标
        RSV = (收盘价 - N日内最低) / (N日内最高 - N日内最低) * 100
        K = 2/3 * 前K + 1/3 * RSV
        D = 2/3 * 前D + 1/3 * K
        J = 3K - 2D
        """
        k_period = self.params['kdj_k']
        d_period = self.params['kdj_d']

        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()

        # RSV计算
        denominator = (high_max - low_min).replace(0, np.nan)
        rsv = 100 * (df['close'] - low_min) / denominator
        rsv.fillna(50, inplace=True)

        # K/D/J - 使用EMA平滑
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df

    # ----- 布林带 BOLL -----

    def _calc_boll(self, df):
        """
        计算布林带指标
        中轨 = N日均线
        上轨 = 中轨 + K * 标准差
        下轨 = 中轨 - K * 标准差
        带宽 = (上轨 - 下轨) / 中轨 * 100
        """
        period = self.params['boll_period']
        std_mult = self.params['boll_std']

        df['BOLL_MID'] = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std(ddof=0)
        df['BOLL_UP'] = df['BOLL_MID'] + std_mult * std
        df['BOLL_DN'] = df['BOLL_MID'] - std_mult * std
        df['BOLL_WIDTH'] = (df['BOLL_UP'] - df['BOLL_DN']) / df['BOLL_MID'] * 100
        return df

    # ----- 成交量均量线 -----

    def _calc_volume_ma(self, df):
        """计算成交量均量线"""
        for period in self.params['volume_ma_periods']:
            df[f'VOL_MA{period}'] = df['volume'].rolling(window=period).mean()
        return df

    # ----- 信号生成 -----

    def get_latest_signal(self, df):
        """
        基于最新指标值生成技术信号

        Parameters
        ----------
        df : DataFrame
            必须包含计算好的技术指标列

        Returns
        -------
        dict
            {
                'trend': 'up' | 'down' | 'sideways' | 'unknown',
                'strength': 0~100,
                'signals': [str, ...]
            }
        """
        if df is None or df.empty:
            return {'trend': 'unknown', 'strength': 0, 'signals': []}

        latest = df.iloc[-1]
        signals = []
        score = 50  # 50为中性基准

        # ---- MA信号 ----
        if 'MA5' in df.columns and 'MA20' in df.columns:
            ma5 = latest.get('MA5', 0)
            ma20 = latest.get('MA20', 0)
            if not (pd.isna(ma5) or pd.isna(ma20)):
                if ma5 > ma20:
                    signals.append(f'MA5({ma5:.2f})上穿MA20({ma20:.2f}) [看涨]')
                    score += 8
                else:
                    signals.append(f'MA5({ma5:.2f})下穿MA20({ma20:.2f}) [看跌]')
                    score -= 8

        # ---- MACD信号 ----
        if 'DIF' in df.columns and 'DEA' in df.columns:
            dif_val = latest.get('DIF', 0)
            dea_val = latest.get('DEA', 0)
            macd_val = latest.get('MACD', 0)
            if not (pd.isna(dif_val) or pd.isna(dea_val)):
                if dif_val > dea_val:
                    signals.append(f'MACD金叉(DIF={dif_val:.3f}>DEA={dea_val:.3f}) [看涨]')
                    score += 10
                else:
                    signals.append(f'MACD死叉(DIF={dif_val:.3f}<DEA={dea_val:.3f}) [看跌]')
                    score -= 10
                if not pd.isna(macd_val):
                    if macd_val > 0:
                        score += 3
                    else:
                        score -= 3

        # ---- RSI信号 ----
        rsi_col = f'RSI{self.params["rsi_period"]}'
        if rsi_col in df.columns:
            rsi = latest.get(rsi_col, 50)
            if not pd.isna(rsi):
                if rsi > 80:
                    signals.append(f'RSI超买({rsi:.1f}) [回调风险]')
                    score -= 10
                elif rsi < 20:
                    signals.append(f'RSI超卖({rsi:.1f}) [反弹机会]')
                    score += 10
                elif rsi > 60:
                    signals.append(f'RSI偏强({rsi:.1f})')
                    score += 5
                elif rsi < 40:
                    signals.append(f'RSI偏弱({rsi:.1f})')
                    score -= 5

        # ---- KDJ信号 ----
        if 'K' in df.columns and 'D' in df.columns:
            k_val = latest.get('K', 50)
            d_val = latest.get('D', 50)
            j_val = latest.get('J', 50)
            if not (pd.isna(k_val) or pd.isna(d_val)):
                if k_val > d_val:
                    signals.append(f'KDJ金叉(K={k_val:.1f}>D={d_val:.1f}) [看涨]')
                    score += 8
                else:
                    signals.append(f'KDJ死叉(K={k_val:.1f}<D={d_val:.1f}) [看跌]')
                    score -= 8
                if not pd.isna(j_val):
                    if j_val > 100:
                        signals.append(f'J值超买(J={j_val:.1f}>100)')
                        score -= 5
                    elif j_val < 0:
                        signals.append(f'J值超卖(J={j_val:.1f}<0)')
                        score += 5

        # ---- BOLL信号 ----
        if 'BOLL_UP' in df.columns and 'BOLL_DN' in df.columns:
            close = latest.get('close', 0)
            boll_up = latest.get('BOLL_UP', 0)
            boll_dn = latest.get('BOLL_DN', 0)
            if not (pd.isna(close) or pd.isna(boll_up) or pd.isna(boll_dn)):
                if close > boll_up:
                    signals.append(f'价格突破上轨({close:.2f}>{boll_up:.2f}) [超买]')
                    score -= 5
                elif close < boll_dn:
                    signals.append(f'价格跌破下轨({close:.2f}<{boll_dn:.2f}) [超卖]')
                    score += 5

        # ---- 成交量信号 ----
        if 'VOL_MA5' in df.columns:
            volume = latest.get('volume', 0)
            vol_ma5 = latest.get('VOL_MA5', 0)
            if not (pd.isna(volume) or pd.isna(vol_ma5)) and vol_ma5 > 0:
                if volume > vol_ma5 * 1.5:
                    signals.append(f'成交量放量({volume:.0f}>{vol_ma5*1.5:.0f}) [关注]')
                    score += 5
                elif volume < vol_ma5 * 0.5:
                    signals.append(f'成交量缩量({volume:.0f}<{vol_ma5*0.5:.0f}) [观望]')
                    score -= 3

        # ---- 趋势判定 ----
        score = max(0, min(100, score))
        if score > 60:
            trend = 'up'
        elif score < 40:
            trend = 'down'
        else:
            trend = 'sideways'

        return {
            'trend': trend,
            'strength': score,
            'signals': signals
        }

    # ----- 便捷方法 -----

    def get_indicator_columns(self):
        """
        返回所有指标列名

        Returns
        -------
        list
            所有可能的指标列名列表
        """
        cols = []
        for p in self.params['ma_periods']:
            cols.append(f'MA{p}')
        cols.extend(['DIF', 'DEA', 'MACD'])
        cols.append(f'RSI{self.params["rsi_period"]}')
        cols.extend(['K', 'D', 'J'])
        cols.extend(['BOLL_MID', 'BOLL_UP', 'BOLL_DN', 'BOLL_WIDTH'])
        for p in self.params['volume_ma_periods']:
            cols.append(f'VOL_MA{p}')
        return cols

    def calculate_selected(self, df, indicators):
        """
        选择性计算指定指标

        Parameters
        ----------
        df : DataFrame
            原始行情数据
        indicators : list
            要计算的指标列表，可选: 'ma', 'macd', 'rsi', 'kdj', 'boll', 'volume_ma'

        Returns
        -------
        DataFrame
        """
        if df is None or df.empty:
            return df

        result = df.copy()
        calc_map = {
            'ma': self._calc_ma,
            'macd': self._calc_macd,
            'rsi': self._calc_rsi,
            'kdj': self._calc_kdj,
            'boll': self._calc_boll,
            'volume_ma': self._calc_volume_ma,
        }
        for name in indicators:
            if name in calc_map:
                result = calc_map[name](result)
        return result


# ===== 简易fallback函数 =====

def fallback_simple_indicators(df):
    """
    极简fallback方案 - 仅计算MA和MACD
    当常规计算因数据不足等异常失败时使用

    Parameters
    ----------
    df : DataFrame
        原始行情数据

    Returns
    -------
    DataFrame
    """
    if df is None or df.empty:
        return df

    result = df.copy()
    try:
        # 简单MA
        result['MA5'] = result['close'].rolling(window=5).mean()
        result['MA20'] = result['close'].rolling(window=20).mean()

        # 简单MACD
        ema12 = result['close'].ewm(span=12, adjust=False).mean()
        ema26 = result['close'].ewm(span=26, adjust=False).mean()
        result['DIF'] = ema12 - ema26
        result['DEA'] = result['DIF'].ewm(span=9, adjust=False).mean()
        result['MACD'] = 2 * (result['DIF'] - result['DEA'])
    except Exception as e:
        print(f"[Fallback] 简易指标计算失败: {e}")

    return result