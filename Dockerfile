FROM python:3.11-slim

# 安装系统依赖（含 Playwright 浏览器依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git \
    libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 yt-dlp
RUN curl -sL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp \
    && yt-dlp --version

# 工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright（含 chromium）
RUN pip install --no-cache-dir playwright && \
    playwright install chromium && \
    playwright install-deps 2>/dev/null || true

# 复制应用文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/downloads /app/data

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# 启动命令
CMD ["python", "app.py"]
