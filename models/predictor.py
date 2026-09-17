"""
多周期预测模型
基于技术指标、基本面、情绪面的综合预测
对四个时间维度进行预测：短期(1周)、中期(1月)、长期(3月)、超长期(6月)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from config import PREDICTION_PARAMS, CONFIDENCE_WEIGHTS


class StockPredictor:
    """
    股票价格预测器

    综合技术面、基本面和情绪面数据，对四周期（短期/中期/长期/超长期）
    进行预测，输出预期价格、置信度、核心驱动因素和情景分析。
    """

    def __init__(self):
        self.params = PREDICTION_PARAMS
        self.conf_weights = CONFIDENCE_WEIGHTS

    def predict(self, technical_data, fundamental_data, sentiment_data):
        """
        执行多周期预测

        Parameters
        ----------
        technical_data : DataFrame
            技术面指标DataFrame（含计算好的指标）
        fundamental_data : dict
            基本面数据，至少含 financial_indicators 和 valuation
        sentiment_data : dict
            情绪面数据，至少含 sentiment_score

        Returns
        -------
        dict
            {period_key: prediction_dict}
        """
        predictions = {}

        if technical_data is None or technical_data.empty:
            print("[Predictor] 技术数据为空，无法预测")
            return predictions

        if 'close' not in technical_data.columns:
            print("[Predictor] 技术数据缺少close列")
            return predictions

        latest_price = technical_data['close'].iloc[-1]
        if pd.isna(latest_price) or latest_price == 0:
            print("[Predictor] 最新价格为0或无效")
            return predictions

        # 获取最新技术信号
        from indicators.calculator import TechnicalIndicatorCalculator
        calc = TechnicalIndicatorCalculator()
        tech_signal = calc.get_latest_signal(technical_data)
        print(f"[Predictor] 技术信号: trend={tech_signal['trend']}, "
              f"strength={tech_signal['strength']}, "
              f"signals={len(tech_signal['signals'])}个")

        # 各周期预测
        for period_key in ['short_term', 'mid_term', 'long_term', 'ultra_long_term']:
            predictions[period_key] = self._predict_period(
                technical_data, latest_price, period_key, tech_signal,
                fundamental_data, sentiment_data
            )

        print(f"[Predictor] 多周期预测完成，共 {len(predictions)} 个周期")
        return predictions

    def _predict_period(self, df, latest_price, period_key, tech_signal,
                        fundamental, sentiment):
        """
        对单个周期进行预测

        Parameters
        ----------
        df : DataFrame
            技术指标数据
        latest_price : float
            最新收盘价
        period_key : str
            周期键名 (short_term / mid_term / long_term / ultra_long_term)
        tech_signal : dict
            技术信号
        fundamental : dict
            基本面数据
        sentiment : dict
            情绪面数据

        Returns
        -------
        dict
            单个周期的预测结果
        """
        period_config = self.params[period_key]
        days = period_config['days']

        # 1. 技术面预测 - 基于均线系统和趋势
        tech_pred = self._technical_prediction(df, days, tech_signal)

        # 2. 基本面修正
        fund_adjust = self._fundamental_adjustment(fundamental)

        # 3. 情绪面修正
        sentiment_adjust = self._sentiment_adjustment(sentiment)

        # 4. 综合预测
        base_price = tech_pred['base_price']
        volatility = tech_pred['volatility']

        # 综合偏移
        total_adjust = (
            tech_pred['trend_bias'] * 0.5 +
            fund_adjust * 0.25 +
            sentiment_adjust * 0.25
        )

        # 计算预期变化和价格
        expected_change = volatility * total_adjust * days / 20  # 月化
        expected_price = base_price * (1 + expected_change)

        # 价格区间
        price_range_pct = volatility * max(2, days / 20) * 0.5
        price_low = expected_price * (1 - price_range_pct)
        price_high = expected_price * (1 + price_range_pct)

        # 置信度
        confidence = self._calculate_confidence(
            tech_signal, fundamental, sentiment, days
        )

        # 核心驱动因素
        drivers = self._get_drivers(tech_signal, period_key, days)

        # 情景分析
        scenarios = self._generate_scenarios(df, period_key, latest_price, tech_signal)

        return {
            'period': period_key,
            'period_label': self._get_period_label(period_key),
            'days': days,
            'current_price': latest_price,
            'expected_price': round(expected_price, 2),
            'price_range': {
                'low': round(price_low, 2),
                'high': round(price_high, 2),
                'pct_low': round((price_low / latest_price - 1) * 100, 1),
                'pct_high': round((price_high / latest_price - 1) * 100, 1),
            },
            'expected_change_pct': round(expected_change * 100, 1),
            'confidence': confidence,
            'trend': tech_signal['trend'],
            'drivers': drivers,
            'scenarios': scenarios,
            'volatility': round(volatility * 100, 1),
        }

    def _technical_prediction(self, df, days, tech_signal):
        """
        基于技术面的价格预测
        使用均线系统、趋势强度和当前价格推算基础价格和波动率

        Parameters
        ----------
        df : DataFrame
            含技术指标的数据
        days : int
            预测天数
        tech_signal : dict
            技术信号

        Returns
        -------
        dict
            {base_price, volatility, trend_bias, latest_price}
        """
        latest = df.iloc[-1]

        # 基础价格: 以当前收盘价为核心，均线趋势作为修正参考
        base_price = latest['close']  # 以当前价格为基础
        # 均线方向作为趋势验证
        ma_trend_signal = 0
        for col in df.columns:
            if col.startswith('MA'):
                val = latest.get(col, np.nan)
                if not pd.isna(val) and val > 0:
                    # 均线偏离度作为趋势参考
                    ma_trend_signal += (val / base_price - 1)

        # 计算波动率(年化)
        returns = df['close'].pct_change().dropna()
        if len(returns) > 0:
            volatility = returns.std() * np.sqrt(252)
        else:
            volatility = 0.3

        # 趋势偏差
        trend_map = {'up': 0.3, 'down': -0.3, 'sideways': 0.0, 'unknown': 0.0}
        strength = tech_signal.get('strength', 50)
        strength_factor = (strength - 50) / 50.0 if strength >= 0 else 0
        trend_bias = trend_map.get(tech_signal['trend'], 0) * 0.3 + strength_factor * 0.3
        
        # 均线偏离修正（限制幅度）
        if 'ma_trend_signal' in dir():
            ma_adjust = locals().get('ma_trend_signal', 0) / 3.0
            trend_bias += max(-0.1, min(0.1, ma_adjust))
        
        trend_bias = max(-0.6, min(0.6, trend_bias))

        return {
            'base_price': base_price,
            'volatility': volatility,
            'trend_bias': trend_bias,
            'latest_price': latest['close'],
        }

    def _fundamental_adjustment(self, fundamental):
        """
        基本面修正因子 (-0.3 ~ 0.3)
        基于ROE和营收增长率评估
        """
        if not fundamental:
            return 0.0

        try:
            fin = fundamental.get('financial_indicators', None)
            if fin is None:
                return 0.0

            # 支持DataFrame或dict
            if isinstance(fin, pd.DataFrame):
                if fin.empty:
                    return 0.0
                latest_fin = fin.iloc[0] if not fin.empty else {}
            elif isinstance(fin, dict):
                latest_fin = fin
            else:
                return 0.0

            # ROE评估
            roe_raw = latest_fin.get('净资产收益率ROE', 0)
            roe_val = self._safe_float(roe_raw)

            # 营收增长率评估
            rev_raw = latest_fin.get('营业收入同比增长率', 0)
            rev_val = self._safe_float(rev_raw)

            score = 0.0

            if roe_val > 15:
                score += 0.15
            elif roe_val > 5:
                score += 0.05
            else:
                score -= 0.10

            if rev_val > 20:
                score += 0.15
            elif rev_val > 0:
                score += 0.05
            else:
                score -= 0.10

            return max(-0.3, min(0.3, score))
        except Exception as e:
            print(f"[Predictor] 基本面修正计算异常: {e}")
            return 0.0

    def _sentiment_adjustment(self, sentiment):
        """
        情绪面修正因子 (-0.2 ~ 0.2)
        基于情感分析的平均得分
        """
        if not sentiment:
            return 0.0

        try:
            score_data = sentiment.get('sentiment_score', {})
            if not score_data:
                return 0.0

            avg_score = score_data.get('average', 0.5)
            if avg_score is None:
                return 0.0

            avg_score = float(avg_score)
            adjustment = (avg_score - 0.5) * 0.4
            return max(-0.2, min(0.2, adjustment))
        except Exception as e:
            print(f"[Predictor] 情绪面修正计算异常: {e}")
            return 0.0

    def _calculate_confidence(self, tech_signal, fundamental, sentiment, days):
        """
        计算预测置信度

        基于技术信号强度、数据完整性和预测周期长度综合评估。

        Parameters
        ----------
        tech_signal : dict
            技术信号
        fundamental : dict
            基本面数据
        sentiment : dict
            情绪面数据
        days : int
            预测天数

        Returns
        -------
        dict
            {'score': float, 'level': str}
        """
        score = 50.0  # 基础分

        # 技术信号强度
        strength = abs(tech_signal.get('strength', 50) - 50)
        score += strength * self.conf_weights['technical_score'] * 100 / 50

        # 基本面数据完整性加分
        if fundamental:
            fin = fundamental.get('financial_indicators')
            if fin is not None:
                has_fin = False
                if isinstance(fin, pd.DataFrame) and not fin.empty:
                    has_fin = True
                elif isinstance(fin, dict) and fin:
                    has_fin = True
                if has_fin:
                    score += 10 * self.conf_weights['fundamental_score'] * 100 / 25

            val = fundamental.get('valuation')
            if val is not None:
                has_val = False
                if isinstance(val, pd.DataFrame) and not val.empty:
                    has_val = True
                elif isinstance(val, dict) and val:
                    has_val = True
                if has_val:
                    score += 8 * self.conf_weights['fundamental_score'] * 100 / 25

        # 情绪数据完整性加分
        if sentiment and sentiment.get('sentiment_score'):
            score += 5 * self.conf_weights['sentiment_score'] * 100 / 15

        # 预测周期越长置信度越低 (时间衰减)
        time_decay = 1 - (days / 250) * 0.3
        score *= time_decay

        # 限制范围
        score = max(10, min(90, score))

        # 置信度分级
        if score >= 70:
            level = '较高'
        elif score >= 50:
            level = '中等'
        else:
            level = '较低'

        return {'score': round(score, 1), 'level': level}

    def _get_drivers(self, tech_signal, period_key, days):
        """
        提取核心驱动因素

        Parameters
        ----------
        tech_signal : dict
            技术信号
        period_key : str
            周期键名
        days : int
            预测天数

        Returns
        -------
        list
            [{'type': str, 'description': str}, ...]
        """
        drivers = []

        # 技术面驱动因素
        if tech_signal.get('signals'):
            for s in tech_signal['signals'][:3]:
                drivers.append({'type': 'technical', 'description': s})

        # 周期相关的驱动因素
        if period_key in ('long_term', 'ultra_long_term'):
            drivers.append({
                'type': 'fundamental',
                'description': '超长期预测需重点关注公司基本面变化和行业趋势'
            })
            drivers.append({
                'type': 'macro',
                'description': '宏观经济政策和市场流动性对长期走势影响显著'
            })

        if period_key == 'short_term':
            drivers.append({
                'type': 'event',
                'description': '短期走势受市场情绪和资金面影响较大'
            })

        return drivers

    def _generate_scenarios(self, df, period_key, latest_price, tech_signal):
        """
        生成情景分析 - 基于实际技术指标动态生成

        根据当前的技术指标状态（RSI超买/超卖、MACD金叉/死叉、
        价格相对BOLL位置、MA多空排列等），自动生成与当前市场
        环境匹配的情景事件，不再是固定写死的文本。

        Parameters
        ----------
        df : DataFrame
            含全部技术指标的历史数据
        period_key : str
            周期键名
        latest_price : float
            最新价格
        tech_signal : dict
            技术信号

        Returns
        -------
        list
            [{'event': str, 'direction': str, 'impact': str,
              'description': str, 'probability': str}, ...]
        """
        trend = tech_signal.get('trend', 'unknown')
        strength = tech_signal.get('strength', 50)
        scenarios = []

        # --- 提取当前实时指标状态 ---
        latest = df.iloc[-1] if not df.empty else {}

        rsi = float(latest.get('RSI14', 50)) if not pd.isna(latest.get('RSI14', 50)) else 50
        macd = float(latest.get('MACD', 0)) if not pd.isna(latest.get('MACD', 0)) else 0
        dif = float(latest.get('DIF', 0)) if not pd.isna(latest.get('DIF', 0)) else 0
        dea = float(latest.get('DEA', 0)) if not pd.isna(latest.get('DEA', 0)) else 0
        k_val = float(latest.get('K', 50)) if not pd.isna(latest.get('K', 50)) else 50
        j_val = float(latest.get('J', 50)) if not pd.isna(latest.get('J', 50)) else 50
        boll_up = float(latest.get('BOLL_UP', latest_price * 1.1)) if not pd.isna(latest.get('BOLL_UP', 0)) else latest_price * 1.1
        boll_dn = float(latest.get('BOLL_DN', latest_price * 0.9)) if not pd.isna(latest.get('BOLL_DN', 0)) else latest_price * 0.9
        boll_mid = float(latest.get('BOLL_MID', latest_price)) if not pd.isna(latest.get('BOLL_MID', 0)) else latest_price
        ma5 = float(latest.get('MA5', latest_price)) if not pd.isna(latest.get('MA5', 0)) else latest_price
        ma20 = float(latest.get('MA20', latest_price)) if not pd.isna(latest.get('MA20', 0)) else latest_price
        ma60 = float(latest.get('MA60', latest_price)) if not pd.isna(latest.get('MA60', 0)) else latest_price

        # RSI状态描述
        rsi_state = '超买' if rsi > 75 else '偏强' if rsi > 60 else '中性' if rsi > 40 else '偏弱' if rsi > 25 else '超卖'
        # MACD状态
        macd_state = '金叉' if dif > dea else '死叉'
        # BOLL位置
        if latest_price > boll_up:
            boll_pos = '上轨上方'
        elif latest_price > boll_mid:
            boll_pos = '中轨与上轨之间'
        elif latest_price > boll_dn:
            boll_pos = '中轨与下轨之间'
        else:
            boll_pos = '下轨下方'
        # MA排列
        if ma5 > ma20 > ma60:
            ma_arrange = '多头排列'
        elif ma5 < ma20 < ma60:
            ma_arrange = '空头排列'
        else:
            ma_arrange = '交叉排列'

        # J值状态
        j_state = '超买区(J>100)' if j_val > 100 else '超卖区(J<0)' if j_val < 0 else '正常区'

        base_scenarios = []

        # ====== 正向情景（基于当前数据动态生成） ======
        if rsi <= 60:
            base_scenarios.append({
                'event': f'RSI从{rsi_state}区{rsi:.0f}回升至60上方',
                'direction': 'positive',
                'impact': 'medium',
                'description': f'当前RSI为{rsi:.1f}({rsi_state})，若回升至强势区将带动技术买盘涌入',
            })
        if macd_state == '死叉' or macd < 0:
            base_scenarios.append({
                'event': f'MACD形成金叉(DIF上穿DEA)',
                'direction': 'positive',
                'impact': 'high',
                'description': f'当前DIF={dif:.3f}低于DEA={dea:.3f}({macd_state})，若形成金叉将是重要转多信号',
            })
        else:
            base_scenarios.append({
                'event': 'MACD金叉持续扩张',
                'direction': 'positive',
                'impact': 'high',
                'description': f'当前DIF={dif:.3f}在DEA={dea:.3f}上方运行({macd_state})，多头动能持续',
            })
        if boll_pos in ('中轨与下轨之间', '下轨下方'):
            base_scenarios.append({
                'event': f'价格从BOLL{boll_pos}反弹至中轨',
                'direction': 'positive',
                'impact': 'medium',
                'description': f'当前价格¥{latest_price:.2f}在{boll_pos}，价格触及下轨后反弹是经典技术买入信号',
            })
        if ma_arrange == '空头排列':
            base_scenarios.append({
                'event': '均线系统从空头排列转为多头',
                'direction': 'positive',
                'impact': 'high',
                'description': f'当前MA5={ma5:.2f}<MA20={ma20:.2f}({ma_arrange})，趋势反转将带来中期做多机会',
            })

        # ====== 负向情景（基于当前数据动态生成） ======
        if rsi >= 40:
            base_scenarios.append({
                'event': f'RSI从{rsi_state}区{rsi:.0f}跌破40强弱分界',
                'direction': 'negative',
                'impact': 'medium',
                'description': f'当前RSI为{rsi:.1f}({rsi_state})，若跌破40将引发技术止损盘',
            })
        if macd_state == '金叉' or macd > 0:
            base_scenarios.append({
                'event': f'MACD形成死叉(DIF下穿DEA)',
                'direction': 'negative',
                'impact': 'high',
                'description': f'当前DIF={dif:.3f}在DEA={dea:.3f}上方({macd_state})，若形成死叉将是转空信号',
            })
        else:
            base_scenarios.append({
                'event': 'MACD死叉持续恶化',
                'direction': 'negative',
                'impact': 'high',
                'description': f'当前DIF={dif:.3f}低于DEA={dea:.3f}({macd_state})，空头动能可能进一步释放',
            })
        if boll_pos in ('中轨与上轨之间', '上轨上方'):
            base_scenarios.append({
                'event': f'价格从BOLL{boll_pos}回落至中轨',
                'direction': 'negative',
                'impact': 'medium',
                'description': f'当前价格¥{latest_price:.2f}在{boll_pos}，上轨附近压力明显，回落风险增大',
            })
        if ma_arrange == '多头排列':
            base_scenarios.append({
                'event': '均线系统从多头排列转为空头',
                'direction': 'negative',
                'impact': 'high',
                'description': f'当前MA5={ma5:.2f}>MA20={ma20:.2f}({ma_arrange})，趋势逆转将引发中期调整',
            })

        # J值过高/过低警告
        if j_val > 100:
            base_scenarios.append({
                'event': f'KDJ的J值{j_state}(J={j_val:.0f})',
                'direction': 'negative',
                'impact': 'medium',
                'description': f'J值{j_state}，短期超买严重，技术性回调压力较大',
            })
        elif j_val < 0:
            base_scenarios.append({
                'event': f'KDJ的J值{j_state}(J={j_val:.0f})',
                'direction': 'positive',
                'impact': 'medium',
                'description': f'J值{j_state}，短期超卖严重，技术性反弹需求强烈',
            })

        # 周期相关的情景补充
        period_event = {
            'short_term': ('大盘短期资金流向', '短期市场情绪波动'),
            'mid_term': ('季报业绩披露窗口', '行业政策变化'),
            'long_term': ('宏观经济数据变化', '行业竞争格局变化'),
            'ultra_long_term': ('公司战略转型落地', '行业长期发展趋势'),
        }

        pev = period_event.get(period_key, ('市场环境变化', '市场环境变化'))
        base_scenarios.append({
            'event': pev[0],
            'direction': 'positive' if trend != 'down' else 'negative',
            'impact': 'medium',
            'description': pev[1],
        })

        # --- 按当前趋势筛选并排序 ---
        # 总取5个：按趋势方向取3个同向 + 2个反向（保持客观）
        if trend == 'up':
            pos = [s for s in base_scenarios if s['direction'] == 'positive'][:3]
            neg = [s for s in base_scenarios if s['direction'] == 'negative'][:2]
            scenarios = pos + neg
        elif trend == 'down':
            neg = [s for s in base_scenarios if s['direction'] == 'negative'][:3]
            pos = [s for s in base_scenarios if s['direction'] == 'positive'][:2]
            scenarios = neg + pos
        else:
            pos = [s for s in base_scenarios if s['direction'] == 'positive'][:3]
            neg = [s for s in base_scenarios if s['direction'] == 'negative'][:3]
            scenarios = (pos + neg)[:5]

        # 确保有5个，不够就补充通用的
        generic_events = [
            {'event': '市场流动性显著变化', 'direction': 'positive', 'impact': 'high',
             'description': '货币政策宽松或收紧将系统性影响估值'},
            {'event': '地缘政治事件冲击', 'direction': 'negative', 'impact': 'high',
             'description': '外部不确定性将压制市场风险偏好'},
        ]
        for ge in generic_events:
            if len(scenarios) >= 5:
                break
            already = any(s['event'] == ge['event'] for s in scenarios)
            if not already:
                scenarios.append(ge)

        # 调整概率
        for s in scenarios:
            if s['direction'] == 'positive' and trend == 'up':
                s['probability'] = '较高'
            elif s['direction'] == 'negative' and trend == 'down':
                s['probability'] = '较高'
            else:
                s['probability'] = '中等'

        return scenarios[:5]

    def _get_period_label(self, period_key):
        """获取周期中文标签"""
        labels = {
            'short_term': '短期（1周）',
            'mid_term': '中期（1个月）',
            'long_term': '长期（3个月）',
            'ultra_long_term': '超长期（6个月）',
        }
        return labels.get(period_key, period_key)

    # ----- 辅助方法 -----

    @staticmethod
    def _safe_float(value, default=0.0):
        """安全地将值转为float"""
        if value is None:
            return default
        try:
            v = float(value)
            return v if not np.isnan(v) else default
        except (ValueError, TypeError):
            return default

    # ----- 批量预测 -----

    def predict_batch(self, stock_data_dict, fundamental_data_dict, sentiment_data_dict):
        """
        批量预测多只股票

        Parameters
        ----------
        stock_data_dict : dict
            {stock_code: technical_dataframe}
        fundamental_data_dict : dict
            {stock_code: fundamental_dict}
        sentiment_data_dict : dict
            {stock_code: sentiment_dict}

        Returns
        -------
        dict
            {stock_code: predictions_dict}
        """
        results = {}
        for code in stock_data_dict:
            print(f"\n[Predictor] === 开始预测 {code} ===")
            results[code] = self.predict(
                stock_data_dict[code],
                fundamental_data_dict.get(code, {}),
                sentiment_data_dict.get(code, {}),
            )
        return results

    # ----- 预测摘要 -----

    def generate_summary(self, predictions):
        """
        从多周期预测结果生成摘要

        Parameters
        ----------
        predictions : dict
            predict() 方法的返回结果

        Returns
        -------
        dict
            包含总体趋势、各周期摘要的汇总信息
        """
        if not predictions:
            return {'summary': '无预测数据', 'overall_trend': 'unknown'}

        trends = []
        confidences = []
        changes = []

        for key, pred in predictions.items():
            if not pred:
                continue
            trends.append(pred.get('trend', 'unknown'))
            confidences.append(pred.get('confidence', {}).get('score', 0))
            changes.append(pred.get('expected_change_pct', 0))

        if not trends:
            return {'summary': '无有效预测', 'overall_trend': 'unknown'}

        # 总体趋势判定
        up_count = trends.count('up')
        down_count = trends.count('down')
        if up_count > down_count:
            overall_trend = 'up'
        elif down_count > up_count:
            overall_trend = 'down'
        else:
            overall_trend = 'sideways'

        return {
            'overall_trend': overall_trend,
            'trend_distribution': {
                'up': up_count,
                'down': down_count,
                'sideways': trends.count('sideways'),
            },
            'avg_confidence': round(np.mean(confidences), 1) if confidences else 0,
            'avg_expected_change': round(np.mean(changes), 1) if changes else 0,
            'periods': list(predictions.keys()),
        }