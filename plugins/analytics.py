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
    analytics_daily = db["analytics_daily"]
except Exception as e:
    print(f"analytics db error: {e}")
    analytics_users = None
    analytics_daily = None

BOT_NAME = os.path.basename(os.getcwd())

def now_utc():
    return datetime.utcnow()

def today_key():
    return now_utc().strftime("%Y-%m-%d")

def day_start():
    n = now_utc()
    return datetime(n.year, n.month, n.day)

def is_admin(user_id):
    try:
        return int(user_id) in ADMINS
    except:
        return False

def is_file_request(message):
    try:
        txt = message.text or ""
        return txt.startswith("/start ") and len(txt.split(" ", 1)[1].strip()) > 5
    except:
        return False

async def save_activity(user, event="message", file_request=False):
    if analytics_users is None or analytics_daily is None or user is None:
        return

    now = now_utc()
    day = today_key()

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
                "$inc": {"message_count": 1}
            },
            upsert=True
        )

        inc = {"events": 1}
        if event == "callback":
            inc["callbacks"] = 1
        else:
            inc["messages"] = 1

        if file_request:
            inc["file_requests"] = 1

        analytics_daily.update_one(
            {"bot": BOT_NAME, "date": day},
            {"$inc": inc, "$set": {"updated_at": now}},
            upsert=True
        )
    except Exception as e:
        print(f"save_activity error: {e}")

@Bot.on_message(filters.private, group=-100)
async def track_private_message(client, message):
    try:
        asyncio.create_task(save_activity(
            message.from_user,
            event="message",
            file_request=is_file_request(message)
        ))
    except:
        pass

@Bot.on_callback_query(group=-100)
async def track_callback(client, query):
    try:
        asyncio.create_task(save_activity(query.from_user, event="callback"))
    except:
        pass

@Bot.on_message(filters.command("analytics") & filters.private)
async def analytics_command(client, message):
    if not is_admin(message.from_user.id):
        return

    if analytics_users is None or analytics_daily is None:
        await message.reply_text("❌ Analytics DB not connected.")
        return

    today = day_start()
    day = today_key()

    total_tracked = analytics_users.count_documents({"bot": BOT_NAME})
    active_today = analytics_users.count_documents({"bot": BOT_NAME, "last_seen": {"$gte": today}})
    new_today = analytics_users.count_documents({"bot": BOT_NAME, "first_seen": {"$gte": today}})
    daily = analytics_daily.find_one({"bot": BOT_NAME, "date": day}) or {}

    await message.reply_text(
        f"📊 <b>{BOT_NAME} Analytics</b>\n\n"
        f"👥 Tracked Users: <code>{total_tracked}</code>\n"
        f"🟢 Active Today: <code>{active_today}</code>\n"
        f"🆕 New Today: <code>{new_today}</code>\n"
        f"📁 File Requests Today: <code>{daily.get('file_requests', 0)}</code>\n"
        f"⚡ Events Today: <code>{daily.get('events', 0)}</code>"
    )
