#!/usr/bin/env python3
"""
智能股价预测系统 - 主入口
支持两种运行模式:
1. Web模式: 启动交互式Web服务 (默认)
2. CLI模式: 命令行直接分析指定股票

用法:
  python main.py                     # 启动Web服务
  python main.py --cli 000001 SZ     # CLI模式分析股票
  python main.py --help              # 查看帮助
"""
import sys
import os
import argparse
from datetime import datetime

# 确保导入路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_cli(stock_code, market, stock_name):
    """命令行模式: 直接分析并输出预测结果"""
    from data.collector import DataCollector
    from indicators.calculator import TechnicalIndicatorCalculator
    from models.predictor import StockPredictor
    
    print(f"\n{'='*60}")
    print(f"  智能股价预测系统 - CLI分析模式")
    print(f"  股票: {stock_name or stock_code} ({stock_code}.{market})")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 1. 采集数据
    print("[1/4] 正在采集技术面数据...")
    collector = DataCollector(stock_code, stock_name or '', market)
    raw_data = collector.collect_all()
    
    # 2. 技术指标
    print("[2/4] 正在计算技术指标...")
    calc = TechnicalIndicatorCalculator()
    tech_data = raw_data['technical']
    multi_period = tech_data.get('multi_period_kline', {})
    full_data = multi_period.get('3y', multi_period.get('1y', None))
    
    if full_data is not None and not full_data.empty:
        full_data = calc.calculate_all(full_data)
        tech_signal = calc.get_latest_signal(full_data)
    else:
        print("[!] 数据不足，无法计算技术指标")
        return
    
    # 3. 预测
    print("[3/4] 正在进行多周期预测...")
    predictor = StockPredictor()
    predictions = predictor.predict(
        full_data, raw_data.get('fundamental', {}), raw_data.get('sentiment', {})
    )
    
    # 4. 输出结果
    print("[4/4] 生成预测报告...")
    print_cli_report(stock_code, stock_name, market, full_data, tech_signal, predictions)

def print_cli_report(code, name, market, df, signal, predictions):
    """在CLI模式下输出格式化的预测报告"""
    latest = df.iloc[-1]
    current_price = latest['close']
    
    print(f"\n{'='*60}")
    print(f"  预测报告: {name or code} ({code}.{market})")
    print(f"  当前价格: ¥{current_price:.2f}")
    print(f"  技术信号: {signal['trend']} (强度: {signal['strength']}/100)")
    print(f"{'='*60}\n")
    
    # 技术信号详情
    if signal['signals']:
        print("【技术信号明细】")
        for s in signal['signals']:
            print(f"  • {s}")
        print()
    
    # 各周期预测
    period_labels = {
        'short_term': '短期（1周）', 'mid_term': '中期（1个月）',
        'long_term': '长期（3个月）', 'ultra_long_term': '超长期（6个月）'
    }
    
    print(f"{'周期':<12} {'方向':<6} {'预期价格':<10} {'区间':<22} {'置信度':<10}")
    print('-' * 60)
    
    for key, pred in predictions.items():
        if not pred.get('price_range'):
            continue
        r = pred['price_range']
        conf = pred['confidence']
        trend_icon = '↑' if pred['trend'] == 'up' else ('↓' if pred['trend'] == 'down' else '→')
        
        print(f"{period_labels[key]:<12} {trend_icon:<4} "
              f"¥{pred['expected_price']:<8.2f} "
              f"¥{r['low']:.2f}~¥{r['high']:.2f}     "
              f"{conf['score']}%({conf['level']})")
    
    print(f"\n{'='*60}")
    print("  核心驱动因素:")
    for key, pred in predictions.items():
        if pred.get('drivers'):
            for d in pred['drivers'][:1]:
                print(f"  [{period_labels[key]}] {d['description']}")
    
    print(f"\n{'='*60}")
    print("  ⚠ 风险提示:")
    print("  本预测仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='智能股价预测系统')
    parser.add_argument('--cli', nargs='?', const='000001', default=None,
                       help='CLI模式，指定股票代码 (默认: 000001)')
    parser.add_argument('market', nargs='?', default='SZ',
                       help='市场 (SZ/SH)')
    parser.add_argument('--name', type=str, default='',
                       help='股票名称')
    parser.add_argument('--port', type=int, default=None,
                       help='Web服务端口 (默认: 8765)')
    
    args = parser.parse_args()
    
    if args.cli:
        # CLI模式
        stock_code = args.cli
        market = args.market.upper() if args.market else 'SZ'
        run_cli(stock_code, market, args.name)
    else:
        # Web模式
        if args.port:
            from config import WEB_CONFIG
            WEB_CONFIG['port'] = args.port
        
        print(f"\n{'='*60}")
        print("  智能股价预测系统 - Web服务模式")
        print(f"{'='*60}")
        print(f"\n  启动Web服务...")
        print(f"  访问地址: http://127.0.0.1:{args.port or 8765}")
        print(f"  按 Ctrl+C 停止服务\n")
        
        from web.app import run_server
        run_server()


if __name__ == '__main__':
    main()