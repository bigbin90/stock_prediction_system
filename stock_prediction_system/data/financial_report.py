"""
财务报告数据分析模块
数据来源: 巨潮资讯网 (cninfo.com.cn) 公开财务数据接口
获取: 近N年财报摘要（营业收入、净利润、毛利率、净利率等），并生成对比总结
"""

import requests
import time
from datetime import datetime, timedelta
from config import DATA_SOURCE, STOCK_DEFAULT

# 巨潮资讯网财务数据接口（公开免费，scode 为 6 位股票代码）
CNINFO_BASE = "http://www.cninfo.com.cn/data20/financialData"
CNINFO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "http://www.cninfo.com.cn/new/index",
    "Accept": "application/json, text/plain, */*",
}

# 东方财富数据中心接口（股东户数、员工数量等非财报摘要类数据）
EM_DATACENTER = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}

# 主要财务指标字段编码（已通过贵州茅台/平安银行年报数据交叉验证）
# F078N = 毛利率(%)，F017N = 净利率(%)，F004N = 每股净资产(元)，F041N = 资产负债率(%)
INDICATOR_FIELDS = {
    "gross_margin": "F078N",   # 销售毛利率(%)
    "net_margin": "F017N",     # 销售净利率(%)
    "bps": "F004N",            # 每股净资产(元)
    "debt_ratio": "F041N",     # 资产负债率(%)
}


class FinancialReportCollector:
    """
    巨潮资讯网财报摘要采集器
    直接从巨潮资讯网公开接口获取结构化财务报表数据
    """

    def __init__(self, stock_code=None, years=3):
        self.stock_code = stock_code or STOCK_DEFAULT['code']
        self.years = years
        self.delay = DATA_SOURCE['request_delay']

    # ----- 底层请求 -----

    def _request(self, endpoint):
        """请求巨潮资讯网接口，返回 data 字典（失败返回空 dict）"""
        url = f"{CNINFO_BASE}/{endpoint}"
        params = {"scode": self.stock_code, "sign": 1}
        time.sleep(self.delay)
        try:
            resp = requests.get(url, params=params, headers=CNINFO_HEADERS, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("code") == 200 and payload.get("data"):
                    return payload["data"]
        except Exception as e:
            print(f"[FinancialReport] 请求 {endpoint} 失败: {e}")
        return {}

    def _year_records(self, data):
        """从接口返回的 data 中提取年报(year)记录列表"""
        records = data.get("records", [])
        if not records:
            return []
        return records[0].get("year", []) or []

    # ----- 利润表 -----

    def _get_income_yearly(self):
        """获取利润表年报数据，返回 {指标名: {年份: 数值(万元)}}"""
        data = self._request("getIncomeStatement")
        result = {}
        for rec in self._year_records(data):
            name = rec.get("index")
            if not name:
                continue
            years = {k: v for k, v in rec.items() if k != "index" and isinstance(v, (int, float))}
            result[name] = years
        return result

    # ----- 主要财务指标 -----

    def _get_main_indicators_yearly(self):
        """获取主要财务指标年报数据，返回 [{ENDDATE, ...}, ...] 按日期倒序"""
        data = self._request("getMainIndicators")
        records = self._year_records(data)
        # 按 ENDDATE 倒序（最新在前），仅保留有 ENDDATE 的记录
        records = [r for r in records if r.get("ENDDATE")]
        records.sort(key=lambda r: r["ENDDATE"], reverse=True)
        return records

    # ----- 汇总 -----

    def _to_yi(self, wan_value):
        """万元 -> 亿元"""
        if wan_value is None:
            return None
        return round(float(wan_value) / 10000, 2)

    def get_financial_summary(self):
        """
        获取近N年财报摘要并生成总结

        Returns
        -------
        dict
            {
                'years': [年份, ...],          # 升序
                'revenue': [营业收入(亿)],      # 与 years 对齐
                'net_profit': [归母净利润(亿)],
                'gross_margin': [毛利率(%)],
                'net_margin': [净利率(%)],
                'bps': [每股净资产(元)],
                'debt_ratio': [资产负债率(%)],
                'summary': str,
                'yoy': {                         # 最新一年同比
                    'revenue': float, 'net_profit': float,
                    'gross_margin': float, 'net_margin': float,
                }
            }
        """
        income = self._get_income_yearly()
        if "营业总收入" not in income or "归属母公司净利润" not in income:
            print("[FinancialReport] 利润表数据获取失败")
            return self._empty_result("未获取到利润表数据")

        # 确定近年来份（升序）
        all_years = sorted(
            [int(y) for y in income["营业总收入"].keys() if str(y).isdigit()]
        )
        years = all_years[-self.years:]

        # 提取营业收入、净利润（万元 -> 亿元）
        revenue = [self._to_yi(income["营业总收入"].get(str(y))) for y in years]
        net_profit = [self._to_yi(income["归属母公司净利润"].get(str(y))) for y in years]

        # 主要指标（毛利率、净利率等）
        indicators = self._get_main_indicators_yearly()
        indicator_map = {}
        for rec in indicators:
            end_year = str(rec["ENDDATE"])[:4]
            if end_year not in indicator_map:
                indicator_map[end_year] = rec

        gross_margin = []
        net_margin = []
        bps = []
        debt_ratio = []
        for y in years:
            rec = indicator_map.get(str(y), {})
            gross_margin.append(self._safe_pct(rec.get(INDICATOR_FIELDS["gross_margin"])))
            net_margin.append(self._safe_pct(rec.get(INDICATOR_FIELDS["net_margin"])))
            bps.append(self._safe_float(rec.get(INDICATOR_FIELDS["bps"])))
            debt_ratio.append(self._safe_pct(rec.get(INDICATOR_FIELDS["debt_ratio"])))

        # 同比增速（最新一年 vs 上一年）
        yoy = {}
        if len(years) >= 2:
            yoy["revenue"] = self._yoy(revenue)
            yoy["net_profit"] = self._yoy(net_profit)
            yoy["gross_margin"] = self._yoy(gross_margin)
            yoy["net_margin"] = self._yoy(net_margin)

        summary = self._generate_summary(
            years, revenue, net_profit, gross_margin, net_margin, yoy
        )

        return {
            "years": years,
            "revenue": revenue,
            "net_profit": net_profit,
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "bps": bps,
            "debt_ratio": debt_ratio,
            "summary": summary,
            "yoy": yoy,
        }

    # ----- 工具方法 -----

    def _safe_float(self, v):
        try:
            if v is None:
                return None
            return round(float(v), 2)
        except (ValueError, TypeError):
            return None

    def _safe_pct(self, v):
        return self._safe_float(v)

    def _yoy(self, series):
        """计算最新一期同比增速(%)，series 按年份升序"""
        series = [v for v in series if v is not None]
        if len(series) < 2 or series[-2] == 0:
            return None
        cur, prev = series[-1], series[-2]
        return round((cur - prev) / prev * 100, 2)

    def _empty_result(self, msg):
        return {
            "years": [], "revenue": [], "net_profit": [],
            "gross_margin": [], "net_margin": [], "bps": [], "debt_ratio": [],
            "summary": msg, "yoy": {},
        }

    # ----- 总结生成 -----

    def _fmt_yi(self, v):
        return f"{v:.2f} 亿元" if v is not None else "N/A"

    def _fmt_pct(self, v):
        return f"{v:.2f}%" if v is not None else "N/A"

    def _trend_desc(self, series, unit_fmt):
        """基于升序序列描述趋势"""
        vals = [v for v in series if v is not None]
        if len(vals) < 2:
            return ""
        first, last = vals[0], vals[-1]
        if last > first:
            return f"呈上升趋势（从 {unit_fmt(first)} 增至 {unit_fmt(last)}）"
        elif last < first:
            return f"呈下降趋势（从 {unit_fmt(first)} 降至 {unit_fmt(last)}）"
        else:
            return f"基本持平（{unit_fmt(last)}）"

    def _generate_summary(self, years, revenue, net_profit, gross_margin, net_margin, yoy):
        """生成财报阅读总结"""
        if not years:
            return "暂无财报数据"

        latest = years[-1]
        rev_desc = self._trend_desc(revenue, self._fmt_yi)
        np_desc = self._trend_desc(net_profit, self._fmt_yi)
        gm_desc = self._trend_desc(gross_margin, self._fmt_pct)

        parts = []
        parts.append(f"报告期覆盖 {years[0]}-{latest} 年（最近 {len(years)} 个会计年度）。")

        # 营业收入
        rev_yoy = yoy.get("revenue")
        rev_txt = f"营业收入{rev_desc}" if rev_desc else f"营业收入 {self._fmt_yi(revenue[-1] if revenue else None)}"
        if rev_yoy is not None:
            rev_txt += f"，{latest} 年同比 {rev_yoy:+.2f}%"
        parts.append(rev_txt + "。")

        # 净利润
        np_yoy = yoy.get("net_profit")
        np_txt = f"归属母公司净利润{np_desc}" if np_desc else f"归属母公司净利润 {self._fmt_yi(net_profit[-1] if net_profit else None)}"
        if np_yoy is not None:
            trend_word = "增长" if np_yoy > 0 else "下滑" if np_yoy < 0 else "持平"
            np_txt += f"，{latest} 年同比{trend_word} {abs(np_yoy):.2f}%"
        parts.append(np_txt + "。")

        # 毛利率
        gm_vals = [v for v in gross_margin if v is not None]
        if gm_vals:
            parts.append(f"毛利率{self._fmt_pct(gm_vals[-1])}，{gm_desc}。")
        else:
            parts.append("毛利率指标无数据（金融类企业可能存在指标不适用的情况）。")

        # 综合判断
        np_latest = net_profit[-1] if net_profit else None
        rev_latest = revenue[-1] if revenue else None
        if np_latest is not None and np_latest > 0 and rev_latest is not None and rev_latest > 0:
            nm = net_margin[-1] if net_margin else None
            if np_yoy is not None and np_yoy > 0 and rev_yoy is not None:
                parts.append("整体呈现" + ("增收增利" if rev_yoy > 0 else "减收但增利") + "，盈利能力保持" + ("良好" if (nm and nm >= 10) else "一般") + "水平。")
            elif np_yoy is not None and np_yoy < 0:
                parts.append("利润端承压，需关注后续盈利修复情况。")

        summary = "".join(parts)
        return summary

    # ----- 股东户数 & 员工数量（东方财富数据中心）-----

    def _secucode(self):
        """6位代码 -> 带交易所后缀的 SECUCODE（如 600519 -> 600519.SH）"""
        suffix = "SH" if self.stock_code.startswith(("6", "9")) else "SZ"
        return f"{self.stock_code}.{suffix}"

    def _request_em(self, report_name, columns, filter_str, sort_columns,
                    sort_types="-1", source="WEB", client="WEB"):
        """请求东方财富数据中心通用接口，返回 records 列表"""
        params = {
            "reportName": report_name,
            "columns": columns,
            "filter": filter_str,
            "pageNumber": 1,
            "pageSize": 200,
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": source,
            "client": client,
        }
        time.sleep(self.delay)
        try:
            resp = requests.get(EM_DATACENTER, params=params, headers=EM_HEADERS, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("success") and payload.get("result"):
                    return payload["result"].get("data") or []
        except Exception as e:
            print(f"[FinancialReport] 东财接口 {report_name} 失败: {e}")
        return []

    def _pct_change(self, cur, base):
        """计算变化率(%)，base 为 0 或 None 时返回 None"""
        if base is None or base == 0 or cur is None:
            return None
        return round((cur - base) / base * 100, 2)

    def get_shareholder_employee(self):
        """
        获取近N年股东户数、员工数量变化（数据来源：东方财富数据中心）

        Returns
        -------
        dict
            {
                'shareholder_dates': ['2023-09-30', ...],  # 升序（季度）
                'shareholder_count': [户数, ...],
                'employee_years': [2023, 2024, 2025],      # 升序（年度）
                'employee_count': [人数, ...],
                'summary': str,
                'yoy': {'shareholder': float, 'employee': float},  # 最新同比(%)
            }
        """
        # 股东户数（季度，近3年）
        holder_rows = []
        holder_raw = self._request_em(
            "RPT_HOLDERNUM_DET",
            "SECURITY_CODE,END_DATE,HOLDER_NUM",
            f'(SECURITY_CODE="{self.stock_code}")',
            "END_DATE",
        )
        cutoff = (datetime.now() - timedelta(days=365 * self.years)).strftime("%Y-%m-%d")
        for r in holder_raw:
            end = str(r.get("END_DATE") or "")[:10]
            num = r.get("HOLDER_NUM")
            if end >= cutoff and num is not None:
                holder_rows.append((end, int(num)))
        holder_rows.sort(key=lambda x: x[0])
        holder_dates = [x[0] for x in holder_rows]
        holder_count = [x[1] for x in holder_rows]

        # 员工数量（年度，近N年）
        emp_raw = self._request_em(
            "RPT_HSF9_BASIC_STAFFCOMPOSITION",
            "SECURITY_CODE,REPORT_DATE,TOTAL_NUM,PAYYEAR",
            f'(SECUCODE="{self._secucode()}")',
            "PAYYEAR",
            source="HSF10",
            client="PC",
        )
        emp_rows = []
        for r in emp_raw:
            try:
                year = int(str(r.get("PAYYEAR") or "").strip())
            except (ValueError, TypeError):
                continue
            total = r.get("TOTAL_NUM")
            if total is not None:
                emp_rows.append((year, int(total)))
        emp_rows.sort(key=lambda x: x[0])
        emp_rows = emp_rows[-self.years:]
        emp_years = [x[0] for x in emp_rows]
        emp_count = [x[1] for x in emp_rows]

        # 同比
        yoy = {}
        if len(emp_count) >= 2:
            yoy["employee"] = self._pct_change(emp_count[-1], emp_count[-2])
        if len(holder_count) >= 2:
            base = holder_count[-5] if len(holder_count) >= 5 else holder_count[-2]
            yoy["shareholder"] = self._pct_change(holder_count[-1], base)

        summary = self._generate_shareholder_employee_summary(
            holder_dates, holder_count, emp_years, emp_count
        )

        return {
            "shareholder_dates": holder_dates,
            "shareholder_count": holder_count,
            "employee_years": emp_years,
            "employee_count": emp_count,
            "summary": summary,
            "yoy": yoy,
        }

    def _generate_shareholder_employee_summary(self, holder_dates, holder_count, emp_years, emp_count):
        """生成股东户数、员工数量变化的阅读总结"""
        parts = []

        if emp_count:
            tc = self._pct_change(emp_count[-1], emp_count[0])
            tc = tc if tc is not None else 0.0
            direction = "增长" if tc > 0 else "减少" if tc < 0 else "持平"
            parts.append(
                f"员工总数从 {emp_count[0]:,} 人（{emp_years[0]} 年）{direction}"
                f"至 {emp_count[-1]:,} 人（{emp_years[-1]} 年），累计 {tc:+.2f}%。"
            )
        else:
            parts.append("员工数量暂无数据。")

        if holder_count:
            tc = self._pct_change(holder_count[-1], holder_count[0])
            tc = tc if tc is not None else 0.0
            direction = "增长" if tc > 0 else "减少" if tc < 0 else "持平"
            parts.append(
                f"股东户数从 {holder_count[0]:,} 户（{holder_dates[0]}）{direction}"
                f"至 {holder_count[-1]:,} 户（{holder_dates[-1]}），累计 {tc:+.2f}%。"
            )
        else:
            parts.append("股东户数暂无数据。")

        return "".join(parts)