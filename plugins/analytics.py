import os
import asyncio
from datetime import datetime
from pyrogram import filters
from bot import Bot
from config import ADMINS, DB_URI, DB_NAME

try:
    from pymongo import MongoClient
    db = MongoClient(DB_URI)[DB_NAME]
    analytics_users = db["analytics_users"]
except Exception as e:
    print(f"analytics db error: {e}")
    analytics_users = None

BOT_NAME = os.path.basename(os.getcwd())

def now_utc():
    return datetime.utcnow()

def day_start():
    n = now_utc()
    return datetime(n.year, n.month, n.day)

def is_admin(user_id):
    try:
        return int(user_id) in ADMINS
    except:
        return False

async def save_activity(user):
    if analytics_users is None or user is None:
        return

    now = now_utc()

    try:
        analytics_users.update_one(
            {"bot": BOT_NAME, "user_id": user.id},
            {
                "$setOnInsert": {
                    "bot": BOT_NAME,
                    "user_id": user.id,
                    "first_seen": now
                },
                "$set": {
                    "last_seen": now,
                    "first_name": user.first_name,
                    "username": user.username
                },
                "$inc": {
                    "message_count": 1
                }
            },
            upsert=True
        )
    except Exception as e:
        print(f"save_activity error: {e}")

@Bot.on_message(filters.private, group=-100)
async def track_private_message(client, message):
    try:
        asyncio.create_task(save_activity(message.from_user))
    except:
        pass

@Bot.on_callback_query(group=-100)
async def track_callback(client, query):
    try:
        asyncio.create_task(save_activity(query.from_user))
    except:
        pass

@Bot.on_message(filters.command("analytics") & filters.private)
async def analytics_command(client, message):
    if not is_admin(message.from_user.id):
        return

    if analytics_users is None:
        await message.reply_text("❌ Analytics DB not connected.")
        return

    today = day_start()

    try:
        total_tracked = analytics_users.count_documents({"bot": BOT_NAME})
        active_today = analytics_users.count_documents({
            "bot": BOT_NAME,
            "last_seen": {"$gte": today}
        })
        new_today = analytics_users.count_documents({
            "bot": BOT_NAME,
            "first_seen": {"$gte": today}
        })

        await message.reply_text(
            f"📊 <b>{BOT_NAME} Analytics</b>\n\n"
            f"👥 Tracked Users: <code>{total_tracked}</code>\n"
            f"🟢 Active Today: <code>{active_today}</code>\n"
            f"🆕 New Today: <code>{new_today}</code>"
        )
    except Exception as e:
        await message.reply_text(f"❌ Analytics error:\n<code>{e}</code>")
