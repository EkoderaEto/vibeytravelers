
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

API_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

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

KEYWORDS = load_keywords()
POSTS = load_posts()
POST_INDEX = 0

async def send_scheduled_post():
    global POST_INDEX
    if POST_INDEX < len(POSTS):
        await bot.send_message(CHANNEL_ID, POSTS[POST_INDEX], parse_mode=ParseMode.HTML)
        POST_INDEX += 1

@dp.message_handler(commands=["post"])
async def manual_post(message: types.Message):
    global POST_INDEX
    if POST_INDEX < len(POSTS):
        await bot.send_message(CHANNEL_ID, POSTS[POST_INDEX], parse_mode=ParseMode.HTML)
        POST_INDEX += 1
        await message.answer("Пост отправлен!")
    else:
        await message.answer("Больше нет постов.")

@dp.channel_post_handler()
async def handle_channel_post(message: types.Message):
    source = message.chat.username
    text = message.text or message.caption
    if not text:
        return
    lower_text = text.lower()
    if any(kw in lower_text for kw in KEYWORDS):
        formatted = f"{text.strip()}

_Источник: @{source}_"
        await bot.send_message(CHANNEL_ID, formatted, parse_mode=ParseMode.MARKDOWN)

async def on_startup(_):
    scheduler.add_job(send_scheduled_post, "cron", hour=12, minute=0)
    scheduler.add_job(send_scheduled_post, "cron", hour=18, minute=0)
    scheduler.start()

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
