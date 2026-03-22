# yt-vdl 重写计划

## 项目目标
将 yt-vdl 改造为完整的抖音视频下载工具，支持：
- 抖音无需登录 Cookie 即可下载（集成 X-Bogus 签名）
- 多平台支持（B站/油管/抖音/微博等）
- 批量下载 + SQLite 去重
- 视频转写（Whisper）
- 可发布到 GitHub

## 项目目录
`/home/peng/.openclaw/workspace/yt-vdl/`

## 阶段计划

### Phase 1: 项目结构重构 ✅
- [x] 创建项目目录结构
- [x] 从 jiji262/douyin-downloader 克隆参考代码到 /tmp
- [x] 创建 app/ 目录结构
- [x] 分离 app.py 为多个模块
- [x] 创建前端静态资源目录
- [x] 添加 README.md
- [x] 添加 LICENSE (MIT)

### Phase 2: 抖音 API 核心 (P0) ✅
- [x] 集成 X-Bogus 签名算法（已修复 float bug）
- [x] 创建 DouyinClient 类
- [x] 实现无水印 URL 构造
- [x] Cookie 管理框架
- [ ] 测试抖音视频解析

### Phase 3: 下载核心 ✅
- [x] 重构 downloader 模块
- [x] 集成 yt-dlp（保留多平台支持）
- [x] SQLite 去重框架

### Phase 4: 前端界面 ⏳
- [ ] 重构 templates/index.html
- [ ] 创建 static/css/ 样式
- [ ] 创建 static/js/ 脚本
- [ ] 响应式设计

### Phase 5: Docker 部署 ✅
- [x] 更新 Dockerfile
- [x] 更新 docker-compose.yml
- [x] Docker 镜像构建成功

### Phase 6: GitHub 发布准备
- [ ] 创建 .gitignore
- [ ] 初始化 Git 仓库
- [ ] 创建 GitHub Actions CI/CD
- [ ] 推送到 GitHub

## 当前状态
Phase 1-3 已完成，Phase 5 已完成，Phase 4 待完成

## 决策记录
- 方案选择: B (完整重写)
- 参考项目: jiji262/douyin-downloader
