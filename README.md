# 🎬 yt-vdl

> 视频下载 Web 管理工具，支持抖音、B站、YouTube 等多平台

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

## ✨ 特性

- 🌐 **多平台支持**：抖音 / B站 / YouTube / 快手 / 微博 / 小红书 等
- 🎯 **无水印下载**：抖音原生 API，支持无水印视频
- 📺 **高清画质**：支持选择 1080p / 720p / 480p 等格式
- 🔄 **批量下载**：支持用户主页批量下载
- 📊 **实时进度**：下载进度实时显示
- 🗄️ **SQLite 去重**：避免重复下载
- 🐳 **Docker 部署**：一行命令启动

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/yt-vdl.git
cd yt-vdl

# 启动服务
docker-compose up -d

# 访问
open http://localhost:5088
```

### 本地开发

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/yt-vdl.git
cd yt-vdl

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py

# 访问
open http://localhost:5000
```

## 📋 支持平台

| 平台 | 支持状态 | 说明 |
|------|---------|------|
| 🎵 抖音 | ✅ 完整支持 | 无水印下载 |
| 📺 B站 | ✅ 完整支持 | 支持 720p 以下 |
| ▶ YouTube | ✅ 完整支持 | 支持 720p 以下 |
| 📱 快手 | ✅ 支持 | |
| 📝 微博 | ✅ 支持 | |
| 📕 小红书 | ✅ 支持 | 需要页面有视频 |
| 💬 知乎 | ✅ 支持 | |
| 🐧 腾讯视频 | ✅ 支持 | |
| 🎬 爱奇艺 | ✅ 支持 | |
| ☁️ 优酷 | ✅ 支持 | |

## 🔧 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 5000 | 服务端口 |
| `DOWNLOAD_DIR` | /app/downloads | 下载目录 |
| `MAX_CONCURRENT_DOWNLOADS` | 3 | 最大并发数 |
| `SECRET_KEY` | - | Flask 密钥 |

### 抖音 Cookie（可选）

如需下载受限视频，可配置以下 Cookie：

| 变量 | 说明 |
|------|------|
| `DOUYIN_MS_TOKEN` | msToken |
| `DOUYIN_TTWID` | ttwid |
| `DOUYIN_ODIN_TT` | odin_tt |
| `DOUYIN_CSRF_TOKEN` | csrf token |

获取方式：登录抖音网页版，打开开发者工具 → Application → Cookies

## 📁 项目结构

```
yt-vdl/
├── app/
│   ├── __init__.py       # 应用工厂
│   ├── config.py         # 配置
│   ├── auth/             # 认证模块（X-Bogus 签名）
│   ├── downloader/       # 下载核心
│   │   ├── douyin.py     # 抖音 API
│   │   └── engine.py     # 下载引擎
│   ├── routes/           # API 路由
│   └── storage/         # 存储（SQLite）
├── static/              # 静态资源
├── templates/           # HTML 模板
├── docker/              # Docker 配置
├── app.py              # 入口文件
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🐳 Docker 部署

```bash
# 构建镜像
docker build -t yt-vdl .

# 运行容器
docker run -d \
  --name yt-vdl \
  -p 5088:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/data:/app/data \
  -e SECRET_KEY=your-secret-key \
  yt-vdl
```

## 📝 API

### 解析视频

```bash
POST /api/parse
Content-Type: application/json

{"url": "https://www.douyin.com/video/xxx"}
```

### 开始下载

```bash
POST /api/download
Content-Type: application/json

{"url": "https://www.douyin.com/video/xxx", "format_id": "1080p"}
```

### 获取任务列表

```bash
GET /api/tasks
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
