"""
Web服务模块 - 基于Flask的交互式预测界面
提供API接口和前端页面
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime
from data.collector import DataCollector
from indicators.calculator import TechnicalIndicatorCalculator
from models.predictor import StockPredictor
from config import WEB_CONFIG, STOCK_DEFAULT

app = Flask(__name__)
CORS(app)

# 模板目录设置
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app.template_folder = template_dir

def convert_types(obj):
    """将numpy类型转换为Python原生类型，便于JSON序列化"""
    if isinstance(obj, dict):
        return {k: convert_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_types(v) for v in obj]
    elif isinstance(obj, pd.Series):
        return obj.to_list()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    elif hasattr(obj, 'item'):  # numpy数值类型
        return obj.item()
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    return obj

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/stock/analyze', methods=['POST'])
def analyze_stock():
    """分析股票API"""
    try:
        data = request.get_json()
        stock_code = data.get('code', STOCK_DEFAULT['code'])
        stock_name = data.get('name', STOCK_DEFAULT['name'])
        market = data.get('market', STOCK_DEFAULT['market'])
        
        print(f"\n{'='*60}")
        print(f"[API] 开始分析股票: {stock_name}({stock_code})")
        print(f"{'='*60}")
        
        # 1. 采集数据
        collector = DataCollector(stock_code, stock_name, market)
        raw_data = collector.collect_all()
        
        # 2. 计算技术指标
        calc = TechnicalIndicatorCalculator()
        tech_data = raw_data['technical']
        multi_period = tech_data.get('multi_period_kline', {})
        
        # 使用3年数据计算指标
        full_data = multi_period.get('3y', pd.DataFrame())
        if full_data.empty:
            # 尝试获取1年数据
            full_data = multi_period.get('1y', pd.DataFrame())
        
        if not full_data.empty:
            full_data = calc.calculate_all(full_data)
            tech_signal = calc.get_latest_signal(full_data)
        else:
            tech_signal = {'trend': 'unknown', 'strength': 0, 'signals': ['数据不足']}
        
        # 3. 执行预测
        predictor = StockPredictor()
        predictions = predictor.predict(
            full_data if not full_data.empty else None,
            raw_data.get('fundamental', {}),
            raw_data.get('sentiment', {})
        )
        
        # 4. 提取摘要信息
        latest_price = None
        if not full_data.empty:
            latest = full_data.iloc[-1]
            latest_price = float(latest.get('close', 0))
        
        # 提取情绪数据
        sentiment_data = raw_data.get('sentiment', {})
        
        # 构建返回结果
        result = {
            'stock': {
                'code': stock_code,
                'name': stock_name,
                'market': market,
                'latest_price': latest_price,
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            'technical_signal': convert_types(tech_signal),
            'predictions': convert_types(predictions),
            'sentiment': convert_types(sentiment_data),
            'data_status': {
                'technical': not full_data.empty,
                'fundamental': bool(raw_data.get('fundamental', {})),
                'sentiment': bool(sentiment_data.get('news', [])),
            }
        }
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# 缓存股票列表，避免每次请求都重新加载
_stock_list_cache = None

@app.route('/api/stock/search', methods=['POST'])
def search_stock():
    """股票搜索API - 根据名称或代码模糊搜索，返回匹配的股票列表"""
    global _stock_list_cache
    try:
        data = request.get_json() or {}
        keyword = data.get('keyword', '').strip()
        
        if _stock_list_cache is None:
            import akshare as ak
            time.sleep(0.3)
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                df.columns = [c.strip() for c in df.columns]
                _stock_list_cache = df.to_dict(orient='records')
        
        if not _stock_list_cache:
            return jsonify({'success': False, 'error': '股票列表为空', 'data': []})
        
        if not keyword:
            # 返回前10只热门股
            hot = _stock_list_cache[:10]
            return jsonify({'success': True, 'data': hot})
        
        keyword_lower = keyword.lower()
        results = []
        for item in _stock_list_cache:
            code = str(item.get('code', '')).lower()
            name = str(item.get('name', ''))
            if keyword_lower in code or keyword_lower in name:
                # 自动识别市场
                market = 'SH' if code.startswith('6') or code.startswith('9') else 'SZ'
                results.append({
                    'code': code.upper(),
                    'name': name,
                    'market': market,
                })
                if len(results) >= 10:
                    break
        
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'data': []})

@app.route('/api/stock/kline', methods=['POST'])
def get_kline():
    """获取K线数据API"""
    try:
        data = request.get_json()
        stock_code = data.get('code', STOCK_DEFAULT['code'])
        market = data.get('market', STOCK_DEFAULT['market'])
        period = data.get('period', 'daily')
        days = data.get('days', 365)
        
        from datetime import timedelta
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        collector = DataCollector(stock_code, '', market)
        df = collector.technical.get_kline_data(start_date=start_date, period=period)
        
        if df.empty:
            return jsonify({'success': False, 'error': '未获取到K线数据'})
        
        # 转换格式
        result = []
        for _, row in df.iterrows():
            result.append({
                'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                'open': float(row['open']),
                'close': float(row['close']),
                'high': float(row['high']),
                'low': float(row['low']),
                'volume': float(row['volume']),
                'amount': float(row['amount']),
                'pct_change': float(row.get('pct_change', 0)),
            })
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stock/fundamental', methods=['POST'])
def get_fundamental():
    """获取基本面数据API"""
    try:
        data = request.get_json()
        stock_code = data.get('code', STOCK_DEFAULT['code'])
        
        collector = DataCollector(stock_code)
        fundamental = collector.fundamental.get_all_fundamental_data()
        
        return jsonify({'success': True, 'data': convert_types(fundamental)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stock/indicators', methods=['POST'])
def get_indicators():
    """获取技术指标数据"""
    try:
        data = request.get_json()
        stock_code = data.get('code', STOCK_DEFAULT['code'])
        market = data.get('market', STOCK_DEFAULT['market'])
        
        collector = DataCollector(stock_code, '', market)
        df = collector.technical.get_kline_data()
        
        if df.empty:
            return jsonify({'success': False, 'error': '未获取到数据'})
        
        calc = TechnicalIndicatorCalculator()
        df = calc.calculate_all(df)
        
        # 转换最近30条数据
        recent = df.tail(30)
        result = []
        for _, row in recent.iterrows():
            item = {}
            for col in ['date', 'close', 'MA5', 'MA10', 'MA20', 'MA60', 
                       'DIF', 'DEA', 'MACD', 'RSI14', 'K', 'D', 'J',
                       'BOLL_UP', 'BOLL_MID', 'BOLL_DN', 'VOL_MA5', 'VOL_MA20']:
                if col in row:
                    val = row[col]
                    if hasattr(val, 'strftime'):
                        val = val.strftime('%Y-%m-%d')
                    elif hasattr(val, 'item'):
                        val = val.item()
                    elif pd.isna(val):
                        val = None
                    item[col] = float(val) if val is not None else None
            result.append(item)
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

def run_server():
    """启动Web服务器"""
    app.run(
        host=WEB_CONFIG['host'],
        port=WEB_CONFIG['port'],
        debug=WEB_CONFIG['debug']
    )

if __name__ == '__main__':
    run_server()