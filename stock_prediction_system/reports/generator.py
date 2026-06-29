"""
报告生成模块
生成格式化的预测报告，支持文本和JSON格式输出
"""

import json
import os
from datetime import datetime

class ReportGenerator:
    """预测报告生成器"""
    
    @staticmethod
    def generate_text_report(stock_info, predictions, technical_signal):
        """生成文本格式报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"  智能股价预测分析报告")
        lines.append(f"  股票: {stock_info.get('name', '')} ({stock_info.get('code', '')})")
        lines.append(f"  当前价格: ¥{stock_info.get('latest_price', 0):.2f}")
        lines.append(f"  生成时间: {stock_info.get('analysis_time', '')}")
        lines.append("=" * 60)
        lines.append("")
        
        # 技术信号
        lines.append("【技术信号】")
        lines.append(f"  趋势方向: {technical_signal.get('trend', '未知')}")
        lines.append(f"  信号强度: {technical_signal.get('strength', 0)}/100")
        if technical_signal.get('signals'):
            for s in technical_signal['signals']:
                lines.append(f"  • {s}")
        lines.append("")
        
        # 预测
        period_labels = {
            'short_term': '短期（1周）',
            'mid_term': '中期（1个月）',
            'long_term': '长期（3个月）',
            'ultra_long_term': '超长期（6个月）'
        }
        
        lines.append("【多周期价格预测】")
        lines.append(f"{'周期':<12} {'趋势':<6} {'预期价格':<12} {'区间':<24} {'置信度':<12}")
        lines.append("-" * 66)
        
        for key, pred in predictions.items():
            if not pred.get('price_range'):
                continue
            r = pred['price_range']
            conf = pred['confidence']
            lines.append(
                f"{period_labels.get(key, key):<12} "
                f"{'↑' if pred['trend']=='up' else '↓' if pred['trend']=='down' else '→':<4} "
                f"¥{pred['expected_price']:<9.2f} "
                f"¥{r['low']:.2f}~¥{r['high']:.2f}      "
                f"{conf['score']}%({conf['level']})"
            )
        lines.append("")
        
        # 驱动因素
        lines.append("【核心驱动因素】")
        for key, pred in predictions.items():
            if pred.get('drivers'):
                for d in pred['drivers'][:1]:
                    lines.append(f"  [{period_labels.get(key, key)}] {d['description']}")
        lines.append("")
        
        # 风险提示
        lines.append("【风险提示】")
        lines.append("  ⚠ 本系统提供的所有预测信息仅供参考，不构成任何投资建议。")
        lines.append("  ⚠ 股市有风险，投资需谨慎。基于历史数据和统计模型的预测")
        lines.append("    无法保证对未来走势的准确判断。")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_json_report(stock_info, predictions, technical_signal):
        """生成JSON格式报告"""
        report = {
            'report_type': '股票价格预测报告',
            'generated_at': datetime.now().isoformat(),
            'stock': stock_info,
            'technical_signal': technical_signal,
            'predictions': predictions,
            'disclaimer': '本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。'
        }
        return report
    
    @staticmethod
    def save_report(report, filepath, format='json'):
        """保存报告到文件"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if format == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
        
        print(f"[Report] 报告已保存: {filepath}")