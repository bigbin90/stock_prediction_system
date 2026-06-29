import requests
import pandas as pd
import time
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from config import DATA_SOURCE, SENTIMENT_PARAMS, STOCK_DEFAULT


class SentimentDataCollector:
    """
    市场情绪数据采集器
    获取: 新闻舆情、股吧讨论热度、公司公告
    """

    def __init__(self, stock_code=None, stock_name=None):
        self.stock_code = stock_code or STOCK_DEFAULT['code']
        self.stock_name = stock_name or STOCK_DEFAULT['name']
        self.delay = DATA_SOURCE['request_delay']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://finance.sina.com.cn/'
        })

    def get_news(self, days=90, max_items=50):
        """
        获取近期财经新闻（使用 AKShare 从东方财富获取）
        返回: [{title, url, time, source}]
        """
        news_list = []
        try:
            # 使用 AKShare 获取东方财富个股新闻（官方接口，稳定可靠）
            time.sleep(self.delay)
            import akshare as ak
            df = ak.stock_news_em(symbol=self.stock_code)
            if df is not None and not df.empty:
                # 提取数据
                for _, row in df.iterrows():
                    news_list.append({
                        'title': str(row.get('新闻标题', '')),
                        'url': str(row.get('新闻链接', '')),
                        'time': str(row.get('发布时间', '')),
                        'source': f"东方财富({row.get('文章来源', '未知')})"
                    })
        except Exception as e:
            print(f"[SentimentData] AKShare获取新闻失败，尝试备用方式: {e}")
            # 备用方式：新浪滚动新闻
            try:
                # 新浪滚动新闻API - 财经类(col=97) + 股市类(col=98)
                urls = [
                    'http://roll.news.sina.com.cn/interface/rollnews_ch_out_interface.php',
                ]
                params = {
                    'col': '97',        # 财经新闻
                    'type': '',
                    'num': min(max_items, 20),
                    'up': '',
                    'range': '3day',
                }
                time.sleep(self.delay)
                resp = self.session.get(urls[0], params=params, timeout=10)
                if resp.status_code == 200:
                    text = resp.text
                    # 解析JSONP格式
                    json_match = re.search(r'var jsonData\s*=\s*({.*?});', text, re.DOTALL)
                    if json_match:
                        import json
                        data = json.loads(json_match.group(1))
                        for item in data.get('list', []):
                            news_list.append({
                                'title': item.get('title', ''),
                                'url': item.get('url', ''),
                                'time': item.get('time', 0),
                                'source': '新浪财经'
                            })
            except Exception:
                print(f"[SentimentData] 备用获取也失败")
        
        return news_list[:max_items]
    
    def _get_eastmoney_news(self):
        """获取东方财富个股新闻 - 备选方法（保留做备份）"""
        news_items = []
        try:
            url = f'https://search-api-web.eastmoney.com/search/jsonp'
            params = {
                'param': f'{{"uid":"","keyword":"{self.stock_code}","type":["cmsArticleWebOld"],"client":"web"}}',
                'cb': 'jQuery',
            }
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                # 尝试解析
                try:
                    import json
                    text = resp.text
                    json_str = re.search(r'jQuery\((.*)\)', text)
                    if json_str:
                        data = json.loads(json_str.group(1))
                        for item in data.get('data', {}).get('list', []):
                            news_items.append({
                                'title': item.get('title', ''),
                                'url': item.get('url', ''),
                                'time': item.get('date', ''),
                                'source': '东方财富'
                            })
                except Exception:
                    pass
        except Exception:
            pass
        return news_items

    def analyze_sentiment(self, texts):
        """
        对文本进行情感分析
        返回: [(text, score)] score: 0~1, >0.5积极
        """
        try:
            from snownlp import SnowNLP
            results = []
            for text in texts[:20]:  # 限制分析数量
                try:
                    s = SnowNLP(text)
                    results.append((text, s.sentiments))
                except Exception:
                    results.append((text, 0.5))
            return results
        except ImportError:
            print("[SentimentData] SnowNLP未安装，使用简单规则")
            return self._simple_sentiment_analysis(texts)

    def _simple_sentiment_analysis(self, texts):
        """简单规则情感分析（备用方案）"""
        positive_words = ['大涨', '涨停', '利好', '突破', '增长', '盈利', '创新高',
                          '扩张', '收购', '合作', '增持', '回购', '分红']
        negative_words = ['大跌', '跌停', '利空', '亏损', '下降', '减持', '风险',
                          '处罚', '诉讼', '违约', 'st', '退市', '预警']

        results = []
        for text in texts[:20]:
            score = 0.5
            pos_count = sum(1 for w in positive_words if w in text)
            neg_count = sum(1 for w in negative_words if w in text)
            total = pos_count + neg_count
            if total > 0:
                score = pos_count / total
            results.append((text, score))
        return results

    def get_guba_hot(self):
        """获取东方财富股吧热度（占位，爬虫需谨慎）"""
        # 股吧爬虫反爬严格，作为可选功能
        return {'hot_degree': 'N/A', 'posts_count': 'N/A', 'note': '股吧数据需单独配置爬虫'}

    def get_all_sentiment_data(self):
        """获取全部情绪数据"""
        from config import SENTIMENT_PARAMS
        max_items = SENTIMENT_PARAMS.get('max_news_items', 50)
        result = {}
        
        # 新闻 - 使用 AKShare 个股新闻
        news = self.get_news(max_items=max_items)
        if news:
            titles = [n['title'] for n in news if n['title']]
            sentiments = self.analyze_sentiment(titles)
            if sentiments:
                # 将情感分数和分类标签写入每条新闻
                score_map = {}
                for t, s in sentiments:
                    score_map[t] = {
                        'score': round(s, 3),
                        'label': 'positive' if s > 0.55 else ('negative' if s < 0.45 else 'neutral')
                    }
                for item in news:
                    t = item.get('title', '')
                    if t in score_map:
                        item['sentiment_score'] = score_map[t]['score']
                        item['sentiment_label'] = score_map[t]['label']
                    else:
                        item['sentiment_score'] = 0.5
                        item['sentiment_label'] = 'neutral'
                
                result['news'] = news
                
                scores = [s[1] for s in sentiments]
                result['sentiment_score'] = {
                    'average': sum(scores) / len(scores) if scores else 0.5,
                    'positive_count': sum(1 for s in scores if s > 0.55),
                    'negative_count': sum(1 for s in scores if s < 0.45),
                    'neutral_count': sum(1 for s in scores if 0.45 <= s <= 0.55),
                }
            else:
                result['news'] = news
        else:
            # 备用：获取市场要闻(非个股新闻，但至少保证有新闻舆情数据)
            print("[SentimentData] 个股新闻为空，尝试获取市场要闻")
            try:
                time.sleep(self.delay)
                import akshare as ak
                news_df = ak.stock_news_main_cx()
                if news_df is not None and not news_df.empty:
                    news = []
                    for _, row in news_df.iterrows():
                        news.append({
                            'title': str(row.get('summary', ''))[:80],
                            'url': str(row.get('url', '')),
                            'time': '',
                            'source': '财新'
                        })
                    result['news'] = news[:max_items]
            except Exception:
                print("[SentimentData] 市场要闻也获取失败")
        
        # 股吧热度
        result['guba'] = self.get_guba_hot()
        
        return result