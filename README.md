# TG-Downloader

基于 Telethon 开发的多账号 Telegram 媒体下载器，支持 Web 界面管理、多账号并发、频道自动监控。

![Version](https://img.shields.io/badge/version-1.0.21-blue.svg)

## 🌟 主要功能

- **多账号支持**：可同时登录多个 Telegram 账号（User 模式或 Bot 模式）。
- **频道监控**：支持监控指定频道/群组，自动下载发送的文件、视频、图片等。
- **Web 管理后台**：提供现代化的 Web 面板，实时查磁盘空间、内存、下载进度。
- **下载历史管理**：完整的下载记录，支持在线重命名文件、清空记录。
- **自动清理**：支持配置文件保留天数，到期自动删除物理文件，节省磁盘空间。
- **通知系统**：支持 Bark 等通知通道，实时获取 Bot 运行状态。

## 🚀 快速部署 (Docker)

推荐使用 Docker 进行一键部署。

### 1. 克隆项目
```bash
git clone <your-repo-url>
cd tg_download
```

### 2. 启动服务
```bash
docker-compose up -d --build
```

### 3. 访问 Web 面板
打开浏览器访问：`http://服务器IP:5001`

- **初始账号**：`admin`
- **初始密码**：`admin123` (建议登录后立即修改)

## ⚙️ 配置说明

所有重要的配置（下载目录、并发数、清理周期）均可在 Web 界面中的 **“通用设置”** 标签页直接修改，实时生效。

- **数据持久化**：数据库与 Session 文件默认存储在 `./data` 目录。
- **下载目录**：建议在 Web 界面配置为 `/app/downloads`。

## 🛠️ 技术栈

- **后端**：Python 3.11, Flask
- **机器人框架**：Telethon (Asyncio)
- **数据库**：SQLite3
- **前端**：Layui 2.9 (Modern Custom UI)
- **部署**：Docker / Docker Compose

## 📦 版本打包
针对 Windows 环境，提供了 `package.ps1` 脚本用于自动打包生产版本。

## 📄 开源协议
MIT License
