# TG Downloader 重构说明

## 数据结构变更

### 旧结构
- accounts表：包含账号信息和频道ID（逗号分隔）
- 一个账号可以监听多个频道（通过逗号分隔）

### 新结构
- accounts表：仅存储TG账号认证信息
  - id, name, api_id, api_hash, bot_token, session_name, created_at
  
- channels表：存储频道监听配置（每个频道一条记录）
  - id, account_id, channel_id, channel_name, enabled, status
  - 通过account_id关联到accounts表

## 优势
1. 每个频道可以单独管理（启用/禁用）
2. 可以为每个频道设置不同的配置
3. 数据结构更清晰，便于扩展
4. 支持一个账号监听多个频道，每个频道独立控制

## API变更

### 账号管理
- GET /api/accounts - 获取所有账号
- POST /api/accounts - 添加/更新账号（不再包含channel_id）
- DELETE /api/accounts/<id> - 删除账号（级联删除关联频道）

### 频道管理（新增）
- GET /api/channels - 获取所有频道
- GET /api/channels?account_id=<id> - 获取指定账号的频道
- POST /api/channels - 添加/更新频道
- DELETE /api/channels/<id> - 删除频道
- POST /api/channels/toggle/<id> - 切换频道启用状态

## 前端变更
- 账号管理：只显示账号基本信息
- 频道管理：新增频道管理页面，显示所有频道及其关联账号
- 每个频道有独立的启停开关和状态显示
