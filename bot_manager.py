import logging
import asyncio
import threading
import time
from database import db_manager

logger = logging.getLogger('tg_download_web.bot_manager')

# {account_id: (stop_event, thread)}
bot_instances = {}

def start_account_bot(account_id):
    """为单个账号启动bot (管理该账号下所有频道)"""
    try:
        account_id = int(account_id)
    except (ValueError, TypeError):
        logger.error(f"Cannot start bot: Invalid account_id {account_id}")
        return

    stop_account_bot(account_id)
    
    accounts = db_manager.get_accounts()
    target_acc = next((a for a in accounts if a['id'] == account_id), None)
    
    if not target_acc:
        logger.error(f"Cannot start bot: Account {account_id} not found")
        return
        
    import telegram_downloader
    stop_event = asyncio.Event()
    
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(telegram_downloader.run_account_bot(target_acc, stop_event))
        except Exception as e:
            logger.error(f"Account bot {target_acc['name']} error: {e}")
            
    t = threading.Thread(target=run, daemon=True)
    t.start()
    bot_instances[account_id] = (stop_event, t)

def stop_account_bot(account_id):
    if account_id in bot_instances:
        stop_event, t = bot_instances.pop(account_id)
        try:
            stop_event.set()
            # 必须等待旧线程完全结束，否则 Telethon Session 文件会被锁
            if t.is_alive():
                logger.info(f"Adding wait for thread {account_id} to stop...")
                t.join(timeout=10)
            time.sleep(1) # 给 SQLite 一点时间释放锁
        except Exception as e:
            logger.error(f"Error stopping bot {account_id}: {e}")

def stop_all_bots():
    """停止所有正在运行的 Bot"""
    for acc_id in list(bot_instances.keys()):
        stop_account_bot(acc_id)
    time.sleep(1)
