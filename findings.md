# 研究发现

## jiji262/douyin-downloader 核心架构

### 项目结构
```
douyin-downloader/
├── core/
│   ├── api_client.py       # 抖音 API 客户端（核心）
│   ├── downloader_base.py   # 下载基类
│   ├── video_downloader.py  # 单视频下载
│   ├── user_downloader.py   # 用户主页批量下载
│   ├── mix_downloader.py    # 合集下载
│   ├── music_downloader.py  # 音乐下载
│   └── transcript_manager.py # 视频转写
├── auth/
│   ├── cookie_manager.py    # Cookie 管理
│   └── ms_token_manager.py  # msToken 管理
├── utils/
│   ├── xbogus.py           # X-Bogus 签名
│   ├──.abogus.py           # ABogus 签名（Browser指纹）
│   └── cookie_utils.py      # Cookie 工具
├── storage/
│   ├── database.py          # SQLite 去重
│   └── file_manager.py      # 文件管理
└── cli/
    └── main.py              # CLI 入口
```

### 关键发现

#### 1. X-Bogus 签名
- 用于签名抖音 API 请求
- 需要 User-Agent
- Python 实现：`utils/xbogus.py`

#### 2. ABogus 签名
- 基于浏览器指纹生成
- 用于风控较高的请求
- 需要 Playwright 支持

#### 3. Cookie 认证
关键 Cookie：
- `msToken`: 必需
- `ttwid`: 必需
- `odin_tt`: 必需
- `passport_csrf_token`: 必需

#### 4. 无水印 URL 构造
```python
params = {
    "video_id": uri,
    "ratio": "1080p",
    "line": "0",
    "is_play_url": "1",
    "watermark": "0",
    "source": "PackSourceEnum_PUBLISH",
}
signed_url = api_client.build_signed_path("/aweme/v1/play/", params)
```

#### 5. 多媒体资源
- 视频: `video.play_addr.url_list`
- 封面: `video.thumbnails[0].url_list`
- 音乐: `music.play_url.url_list`
- 头像: `author.avatar.url_list`

## yt-vdl 现状分析

### 优点
- Flask + Vue 3 SPA 结构清晰
- 前端界面已经可用
- Docker 部署完善

### 问题
- app.py 879 行，代码耦合严重
- 前端全在 templates/index.html
- 没有独立的静态资源
- 抖音解析完全依赖 yt-dlp（需要登录）
- 没有 README
- 没有 LICENSE
