
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import json
from datetime import datetime, date
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

API_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = 490364050

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

def load_posts():
    try:
        with open("posts.txt", "r", encoding="utf-8") as f:
            posts = f.read().split("---")
            return [p.strip() for p in posts if p.strip()]
    except:
        return []

def load_keywords():
    try:
        with open("keywords.txt", "r", encoding="utf-8") as f:
            return [k.strip().lower() for k in f.readlines() if k.strip()]
    except:
        return []

def log_post(text):
    log_entry = {
        "time": str(datetime.now()),
        "text": text
    }
    try:
        with open("log.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Ошибка записи лога:", e)

async def send_daily_report():
    today_str = str(date.today())
    count = 0
    try:
        with open("log.json", "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if entry["time"].startswith(today_str):
                    count += 1
    except FileNotFoundError:
        pass

    message = "📊 Отчёт за {}:\n• Отправлено постов: {}".format(today_str, count)
    try:
        await bot.send_message(ADMIN_ID, message)
    except Exception as e:
        print("Ошибка при отправке отчёта:", e)

KEYWORDS = load_keywords()
POSTS = load_posts()
POST_INDEX = 0

async def send_scheduled_post():
    global POST_INDEX
    if POST_INDEX < len(POSTS):
        await bot.send_message(CHANNEL_ID, POSTS[POST_INDEX], parse_mode=ParseMode.MARKDOWN)
        log_post(POSTS[POST_INDEX])
        POST_INDEX += 1

@dp.message_handler(commands=["post"])
async def manual_post(message: types.Message):
    global POST_INDEX
    if POST_INDEX < len(POSTS):
        await bot.send_message(CHANNEL_ID, POSTS[POST_INDEX], parse_mode=ParseMode.MARKDOWN)
        log_post(POSTS[POST_INDEX])
        POST_INDEX += 1
        await message.answer("Пост отправлен!")
    else:
        await message.answer("Постов больше нет.")

@dp.channel_post_handler()
async def handle_channel_post(message: types.Message):
    source = message.chat.username
    text = message.text or message.caption
    if not text:
        return
    lower_text = text.lower()
    if any(kw in lower_text for kw in KEYWORDS):
        formatted = "{}\n\n_Источник: @{}_".format(text.strip(), source)
        await bot.send_message(CHANNEL_ID, formatted, parse_mode=ParseMode.MARKDOWN)

async def on_startup(_):
    scheduler.add_job(send_scheduled_post, "cron", hour=12, minute=0)
    scheduler.add_job(send_scheduled_post, "cron", hour=18, minute=0)
    scheduler.add_job(send_daily_report, "cron", hour=21, minute=0)
    scheduler.start()

class StubServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_stub_server():
    server = HTTPServer(("0.0.0.0", 10000), StubServer)
    server.serve_forever()

threading.Thread(target=run_stub_server, daemon=True).start()

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
