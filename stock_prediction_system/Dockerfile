# ==============================================================
# 智能股价预测系统 - Docker 镜像
# 基于 python:3.11（完整版，自带编译工具），避免 slim 镜像的 apt 依赖
# ==============================================================
FROM python:3.11

LABEL maintainer="stock-prediction-system"
LABEL description="智能股价预测系统 - 基于AKShare的多维度股票分析与预测"

# 环境变量
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=8765
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 设置时区
RUN ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# 创建工作目录
WORKDIR /app

# 先复制依赖文件（利用 Docker 缓存层）
COPY requirements-docker.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements-docker.txt --break-system-packages

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8765

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/', timeout=10)" || exit 1

# 启动 Web 服务
CMD ["python3", "web/app.py"]