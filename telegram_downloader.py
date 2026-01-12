import os
import logging
from logging.handlers import RotatingFileHandler
import time
import asyncio
import requests
import re
import shutil
from urllib.parse import quote
from telethon import TelegramClient, events
from datetime import datetime
from database import db_manager

# --- 辅助函数 ---
def sanitize_filename(filename: str) -> str:
    if not filename: return ""
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    sanitized = sanitized.lstrip('. ')
    if len(sanitized) > 200:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:200] + ext
    return sanitized

def send_push_notification_sync(content: str):
    """从数据库获取所有启用的通知通道并发送"""
    notifs = db_manager.get_notifications()
    for n in notifs:
        if not n['enabled']: continue
        try:
            if n['type'] == 'bark':
                url = n['config'].get('barkUrl')
                if not url: continue
                full_url = f"{url.rstrip('/')}/{quote('TG-Downloader')}/{quote(content)}"
                requests.get(full_url, timeout=10).raise_for_status()
        except Exception as e:
            logging.error(f"发送通知 [{n['name']}] 失败: {e}")

async def send_push_notification(content: str):
    await asyncio.to_thread(send_push_notification_sync, content)

# 全局状态管理
bot_active_status = {} # { account_id: "status_text" }
# { account_id: { message_id: { percentage, ... } } }
progress_status = {}

async def progress_callback(client, account_id, message_id, current, total, file_name, channel_id):
    now = time.time()
    if account_id not in progress_status: progress_status[account_id] = {}
    
    if message_id not in progress_status[account_id]:
        progress_status[account_id][message_id] = {
            'last_update': 0, 
            'start_time': now, 
            'file_name': file_name,
            'channel_id_raw': channel_id
        }

    elapsed = now - progress_status[account_id][message_id]['start_time']
    downloaded_mb = current / 1024 / 1024
    total_mb = total / 1024 / 1024
    percentage = current * 100 / total if total > 0 else 0
    speed = (current / elapsed) / 1024 / 1024 if elapsed > 0 else 0
    
    progress_status[account_id][message_id].update({
        'percentage': round(percentage, 1),
        'downloaded_mb': round(downloaded_mb, 2),
        'total_mb': round(total_mb, 2),
        'speed': f"{speed:.2f} MB/s"
    })

    if now - progress_status[account_id][message_id]['last_update'] < 2.5 and current != total:
        return

    progress_status[account_id][message_id]['last_update'] = now
    try:
        filled_blocks = int(round(percentage / 10))
        progress_bar = '█' * filled_blocks + '░' * (10 - filled_blocks)
        text = (
            f"**正在下载**: `{file_name}`\n\n"
            f"**进度**: `[{progress_bar}] {percentage:.1f}%`\n\n"
            f"**大小**: `{downloaded_mb:.2f}MB / {total_mb:.2f}MB`"
        )
        await client.edit_message(channel_id, message_id, text)
    except: pass
    
    if current == total:
        if message_id in progress_status[account_id]:
            del progress_status[account_id][message_id]

async def process_video_message(client, message, account_config):
    account_id = account_config['id']
    # 从消息中获取频道ID，而不是从配置中获取
    channel_id = message.chat_id
    
    download_dir = db_manager.get_setting('DOWNLOAD_DIR', '/app/downloads')
    os.makedirs(download_dir, exist_ok=True)
    
    # 1. 获取原始文件名和后缀
    original_file_name = "default.mp4"
    if message.video.attributes:
        for attr in message.video.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                original_file_name = attr.file_name
                break
    _, file_ext = os.path.splitext(original_file_name)
    if not file_ext: file_ext = '.mp4'

    # 2. 智能生成文件名
    # 优先级: Caption第一行 > 原文件名 > 时间戳
    final_name = ""
    caption = (message.text or "").strip()
    
    if caption:
        # 取第一行，且只取 #标签 之前的部分
        first_line = caption.split('\n')[0].strip()
        if '#' in first_line:
            first_line = first_line.split('#')[0].strip()
        final_name = first_line
    
    if not final_name:
        # 如果没有Caption或处理后为空，尝试使用原文件名
        if original_file_name != "default.mp4":
            final_name = os.path.splitext(original_file_name)[0]
    
    if not final_name:
        # 保底使用时间戳
        final_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{message.id}"

    # 3. 净化文件名
    sanitized_name = sanitize_filename(final_name)
    if not sanitized_name:
        sanitized_name = f"video_{message.id}"
        
    new_file_name = f"{sanitized_name}{file_ext}"
    
    # 4. 判重处理 (自动重命名)
    counter = 1
    root_name = sanitized_name
    # 获取频道配置以检查自定义路径
    # 注意：这里需要通过 channel_id (Telegram ID) 反查数据库中的频道配置
    # 由于可能存在多个账号监听同一个频道，这里尽量匹配当前账号下的频道
    target_channel = None
    all_channels = db_manager.get_channels(account_id)
    real_chat_id = message.chat_id
    
    # 尝试匹配数据库记录
    # 获取 Chat 对象以尝试获取 username
    chat_username = None
    try:
        # message.chat 可能已经是 Chat 对象，或者需要 fetch
        if hasattr(message.chat, 'username'):
            chat_username = message.chat.username
    except: pass

    for ch in all_channels:
        # 数据库存的可能是用户名或ID，需要做简单匹配
        stored_id = str(ch['channel_id']).strip()
        
        # 匹配逻辑1: ID直接匹配 (考虑 -100 前缀)
        id_match = (str(real_chat_id) == stored_id) or \
                   (str(real_chat_id) == f"-100{stored_id}") or \
                   (f"-100{real_chat_id}" == stored_id) or \
                   (stored_id in str(real_chat_id)) # 最后的保底
                   
        # 匹配逻辑2: 用户名匹配 (忽略大小写)
        username_match = False
        if chat_username and stored_id.lower() == chat_username.lower():
            username_match = True
            
        # 匹配逻辑3: 数据库存的是完整的链接 t.me/xxx
        link_match = False
        if 't.me/' in stored_id:
            db_uname = stored_id.split('/')[-1]
            if chat_username and db_uname.lower() == chat_username.lower():
                link_match = True

        if id_match or username_match or link_match:
            target_channel = ch
            break
            
    # 如果有自定义路径
    subdir = ""
    db_channel_id = None
    if target_channel:
        db_channel_id = target_channel['id']
        if target_channel.get('custom_path'):
            subdir = target_channel['custom_path'].strip().strip('/\\')
    
    current_download_dir = os.path.join(download_dir, subdir) if subdir else download_dir
    os.makedirs(current_download_dir, exist_ok=True)
    
    # ... (原有文件名生成逻辑保持不变)
    
    file_path = os.path.join(current_download_dir, new_file_name)
    
    # 判重处理需要检查 current_download_dir
    counter = 1
    root_name = sanitized_name
    while os.path.exists(os.path.join(current_download_dir, new_file_name)):
        new_file_name = f"{root_name}_{counter}{file_ext}"
        counter += 1
        file_path = os.path.join(current_download_dir, new_file_name)
    
    status_message = None
    task_id = None

    try:
        initial_text = f"**准备下载**\n\n**文件名**: `{new_file_name}`"
        status_message = await client.send_message(channel_id, initial_text)
        await send_push_notification(f"🚀 [{account_config['name']}] 开始下载: {new_file_name}")
        
        task_id = db_manager.add_task({
            'account_id': account_id,
            'channel_id': db_channel_id,
            'message_id': status_message.id,
            'file_name': new_file_name,
            'file_path': file_path, 
            'file_size': 0,
            'status': 'downloading',
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
        await client.download_media(
            message.media, file=file_path,
            progress_callback=lambda c, t: progress_callback(client, account_id, status_message.id, c, t, new_file_name, channel_id)
        )
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        await client.edit_message(channel_id, status_message.id, f"✅ **下载完成**\n\n**文件名**: `{new_file_name}`\n**大小**: `{file_size_mb:.2f} MB`")
        await send_push_notification(f"✅ [{account_config['name']}] 下载完成: {new_file_name}")
        if task_id: db_manager.update_task_status(task_id, 'completed', end_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    except Exception as e:
        logging.error(f"下载失败: {e}")
        if status_message: 
            try:
                await client.edit_message(channel_id, status_message.id, f"❌ **下载失败**\n\n原因: `{e}`")
            except: pass
        if task_id: db_manager.update_task_status(task_id, 'failed', end_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), error_msg=str(e))

async def queue_worker(client, queue, account_config):
    while True:
        try:
            # 简单的并发控制: 检查当前下载中的任务数
            # 如果超过限制，则等待。这是一个全局限制，虽然每个Bot线程独立，但都查同一个DB。
            setting_val = db_manager.get_setting('MAX_CONCURRENT_DOWNLOADS')
            try:
                max_concurrent = int(setting_val) if setting_val else 3
            except (ValueError, TypeError):
                max_concurrent = 3
            
            while db_manager.get_active_task_count() >= max_concurrent:
                logging.debug(f"并发数已满 ({max_concurrent})，等待中...")
                await asyncio.sleep(5)

            message = await queue.get()
            await process_video_message(client, message, account_config)
            queue.task_done()
        except Exception as e:
            logging.error(f"Worker Error: {e}")

async def run_account_bot(account_config, stop_event):
    """运行单个账号的 Bot 实例，支持监听多个频道"""
    account_id = account_config['id']
    account_name = account_config['name']
    bot_active_status[account_id] = "connecting"
    
    logging.info(f"Bot [{account_name}] 正在初始化Session...")
    session_file = os.path.join('data/sessions', account_config['session_name'])
    os.makedirs('data/sessions', exist_ok=True)
    
    # 从数据库获取该账号下所有启用的频道
    all_channels = db_manager.get_channels(account_id)
    channel_list = []
    
    logging.info(f"Bot [{account_name}] 正在加载频道列表...")
    for ch in all_channels:
        if ch['enabled'] == 1:
            cid = ch['channel_id'].strip()
            if not cid: continue
            
            # 处理 t.me 链接
            if 't.me/' in cid: 
                cid = cid.split('/')[-1]
            
            # 处理 ID (整数) 或 用户名 (字符串)
            if re.match(r'^-?\d+$', cid): 
                channel_list.append(int(cid))
            else:
                channel_list.append(cid.lstrip('@'))
                
            logging.info(f"Bot [{account_name}] 添加监听频道: {ch.get('channel_name', cid)} ({cid})")
            
    if not channel_list:
        logging.warning(f"账号 [{account_name}] 没有启用任何频道，Bot 将暂停运行")
        bot_active_status[account_id] = "stopped"
        return

    logging.info(f"Bot [{account_name}] 正在尝试连接 Telegram (API_ID: {account_config['api_id']})...")
    client = TelegramClient(session_file, account_config['api_id'], account_config['api_hash'])
    queue = asyncio.Queue()
    
    try:
        @client.on(events.NewMessage(chats=channel_list))
        async def handler(event):
            if event.message.video and not event.message.is_reply:
                await queue.put(event.message)

        # 这里使用 wait_for 增加启动超时，防止无限卡死
        logging.info(f"Bot [{account_name}] 开始执行 client.start()...")
        # 如果有Bot Token则使用机器人模式，否则使用用户模式
        if account_config['bot_token']:
            await asyncio.wait_for(client.start(bot_token=account_config['bot_token']), timeout=60)
        else:
            try:
                # 用户模式需要交互式登录，在后台环境中会失败
                # 检查session文件是否存在
                session_path = session_file + '.session'
                if not os.path.exists(session_path):
                     raise Exception("Session file not found. Please login interactivly first.")

                await asyncio.wait_for(client.start(), timeout=60)
            except Exception as e:
                logging.error(f"Bot [{account_name}] 用户模式登录失败: {e}")
                logging.error(f"Bot [{account_name}] 提示: 请提供有效的Bot Token，或确保在交互式环境中运行以完成用户登录")
                raise e
        
        bot_active_status[account_id] = "running"
        asyncio.create_task(queue_worker(client, queue, account_config))
        
        # 记录已连接
        # 记录已连接
        logging.info(f"Bot [{account_name}] 启动成功，正在监听 {len(channel_list)} 个频道")
        await send_push_notification(f"🤖 机器人上线: {account_name}\n监听频道: {len(channel_list)} 个")
        
        # 发送频道上线通知 (根据设置)
        if db_manager.get_setting('SEND_CHANNEL_LOGIN_MSG', False):
            logging.info(f"Bot [{account_name}] 正在向频道发送上线通知...")
            for cid in channel_list:
                try:
                    await client.send_message(cid, f"🤖 **机器人已上线**\n\n**账号**: `{account_name}`\n**时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                except Exception as e:
                    logging.error(f"向频道 [{cid}] 发送上线消息失败: {e}")
        
        # 保持运行
        await asyncio.wait(
            [asyncio.create_task(client.run_until_disconnected()), asyncio.create_task(stop_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.TimeoutError:
        logging.error(f"Bot [{account_name}] 连接超时 (60s)，请检查网络环境或 API ID/Hash 是否正确")
        bot_active_status[account_id] = "error: connection timeout"
    except Exception as e:
        logging.error(f"Bot [{account_name}] 启动或运行时遇到错误: {e}")
        bot_active_status[account_id] = f"error: {str(e)}"
    finally:
        bot_active_status[account_id] = "stopped"
        if client.is_connected():
            await client.disconnect()
        logging.info(f"Bot [{account_name}] 实例已彻底停止")
