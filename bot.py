import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
import os
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp
import tempfile
from aiogram.types import InputFile

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 490364050

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

POSTS_FILE = "posts.txt"

def load_posts():
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            posts = f.read().split("---")
            return [p.strip() for p in posts if p.strip()]
    except:
        return []

def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n---\n".join(posts))

# Клавиатура меню
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(
    KeyboardButton("📋 Список постов"),
    KeyboardButton("🆕 Добавить пост")
).add(
    KeyboardButton("🗑 Удалить пост"),
    KeyboardButton("✏️ Редактировать пост")
).add(
    KeyboardButton("⏰ Запланировать пост"),
    KeyboardButton("📊 Статистика")
)

SCHEDULED_POSTS_FILE = "scheduled_posts.json"
scheduler = AsyncIOScheduler()

def load_scheduled_posts():
    try:
        with open(SCHEDULED_POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_scheduled_posts(posts):
    with open(SCHEDULED_POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

async def check_scheduled_posts():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    posts = load_scheduled_posts()
    remaining = []

    for post in posts:
        if post["datetime"] == now:
            try:
                if post["type"] == "text":
                    await bot.send_message(CHANNEL_ID, post["text"], parse_mode=ParseMode.MARKDOWN)

                elif post["type"] == "photo":
                    await bot.send_photo(CHANNEL_ID, post["file_id"], caption=post.get("caption", ""), parse_mode=ParseMode.MARKDOWN)

                elif post["type"] == "album":
                    media = []
                    for m in post["media"]:
                        item = InputMediaPhoto(media=m["media"], caption=m.get("caption", ""))
                        media.append(item)
                    await bot.send_media_group(CHANNEL_ID, media)
                elif post["type"] == "photo_file":
                    photo = InputFile(post["path"])
                    await bot.send_photo(CHANNEL_ID, photo, caption=post.get("caption", ""), parse_mode=ParseMode.MARKDOWN)

            except Exception as e:
                print(f"Ошибка при отправке поста: {e}")
        else:
            remaining.append(post)

    save_scheduled_posts(remaining)

# === Поддержка ссылок на изображения ===
async def download_image_from_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(await resp.read())
                        return tmp_file.name
    except Exception as e:
        print(f"Ошибка при загрузке изображения: {e}")
        return None

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Доступ запрещён.")
    await message.answer("Добро пожаловать в панель управления ботом!", reply_markup=main_kb)

@dp.message_handler(lambda msg: msg.text == "📋 Список постов")
async def list_posts(message: types.Message):
    posts = load_posts()
    if not posts:
        return await message.answer("❌ Постов пока нет.")
    text = ""
    for i, p in enumerate(posts):
        preview = p.replace('\n', ' ')[:100]
        text += "{}. {}...\n\n".format(i + 1, preview)
    await message.answer("📋 Список постов:\n\n{}".format(text))

@dp.message_handler(lambda msg: msg.text == "🆕 Добавить пост")
async def add_post_prompt(message: types.Message):
    await message.answer("✏️ Введите новый пост. Как закончите — отправьте его в одном сообщении.")

    @dp.message_handler()
    async def receive_new_post(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        posts = load_posts()
        posts.append(msg.text.strip())
        save_posts(posts)
        await msg.answer("✅ Пост добавлен!")
        dp.message_handlers.unregister(receive_new_post)

@dp.message_handler(lambda msg: msg.text == "🗑 Удалить пост")
async def delete_post_prompt(message: types.Message):
    await message.answer("Введите номер поста, который хотите удалить.")

    @dp.message_handler()
    async def receive_delete_index(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        try:
            index = int(msg.text.strip()) - 1
            posts = load_posts()
            if 0 <= index < len(posts):
                deleted = posts.pop(index)
                save_posts(posts)
                await msg.answer("🗑 Удалён пост:\n\n{}...".format(deleted[:100]))
            else:
                await msg.answer("❌ Неверный номер.")
        except:
            await msg.answer("⚠️ Введите корректный номер.")
        dp.message_handlers.unregister(receive_delete_index)

@dp.message_handler(lambda msg: msg.text == "📊 Статистика")
async def show_stats(message: types.Message):
    posts = load_posts()
    await message.answer(f"📊 Всего постов: {len(posts)}")

# === ✏️ Редактирование поста ===
@dp.message_handler(lambda msg: msg.text == "✏️ Редактировать пост")
async def edit_post_prompt(message: types.Message):
    await message.answer("Введите номер поста, который хотите отредактировать.")

    @dp.message_handler()
    async def receive_edit_index(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        try:
            index = int(msg.text.strip()) - 1
            posts = load_posts()
            if 0 <= index < len(posts):
                await msg.answer("Введите новый текст для поста №{}:".format(index + 1))

                @dp.message_handler()
                async def receive_new_content(new_msg: types.Message):
                    if new_msg.from_user.id != ADMIN_ID:
                        return
                    posts[index] = new_msg.text.strip()
                    save_posts(posts)
                    await new_msg.answer("✅ Пост №{} обновлён.".format(index + 1))
                    dp.message_handlers.unregister(receive_new_content)

                dp.message_handlers.unregister(receive_edit_index)
            else:
                await msg.answer("❌ Неверный номер поста.")
                dp.message_handlers.unregister(receive_edit_index)
        except:
            await msg.answer("⚠️ Введите корректный номер.")
            dp.message_handlers.unregister(receive_edit_index)

from aiogram.types import ContentType, InputMediaPhoto

@dp.message_handler(lambda msg: msg.text == "⏰ Запланировать пост")
async def schedule_post_prompt(message: types.Message):
    await message.answer("Введите дату и время публикации (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")

    @dp.message_handler()
    async def receive_datetime(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        try:
            scheduled_time = datetime.strptime(msg.text.strip(), "%Y-%m-%d %H:%M")
            await msg.answer("Теперь отправьте пост: это может быть текст, фото или альбом из фото с подписью.")

            album = []

            @dp.message_handler(content_types=ContentType.ANY)
            async def receive_post(msg: types.Message):
                if msg.from_user.id != ADMIN_ID:
                    return

                if msg.content_type == ContentType.TEXT:
                    post = {
                        "datetime": scheduled_time.strftime("%Y-%m-%d %H:%M"),
                        "type": "text",
                        "text": msg.text.strip()
                    }
                elif msg.text.strip().startswith("http"):
                    # Попытка загрузить фото по ссылке
                    img_path = await download_image_from_url(msg.text.strip())
                    if img_path:
                         post = {
                            "datetime": scheduled_time.strftime("%Y-%m-%d %H:%M"),
                            "type": "photo_file",
                            "path": img_path,
                            "caption": ""
                        }
                    else:
                        await msg.answer("⚠️ Не удалось загрузить изображение по ссылке.")
                        return
                elif msg.content_type == ContentType.PHOTO:
                    post = {
                        "datetime": scheduled_time.strftime("%Y-%m-%d %H:%M"),
                        "type": "photo",
                        "file_id": msg.photo[-1].file_id,
                        "caption": msg.caption or ""
                    }

                elif msg.media_group_id:
                    # Собираем альбом
                    album.append(msg)
                    await asyncio.sleep(1.5)
                    if not album or msg.media_group_id != album[0].media_group_id:
                        return

                    post = {
                        "datetime": scheduled_time.strftime("%Y-%m-%d %H:%M"),
                        "type": "album",
                        "media": [{"type": "photo", "media": m.photo[-1].file_id, "caption": m.caption or ""} for m in album]
                    }

                else:
                    await msg.answer("⚠️ Тип контента не поддерживается.")
                    return

                posts = load_scheduled_posts()
                posts.append(post)
                save_scheduled_posts(posts)

                await msg.answer("✅ Пост запланирован на {}.".format(post["datetime"]))
                dp.message_handlers.unregister(receive_post)
                dp.message_handlers.unregister(receive_datetime)

            dp.message_handlers.unregister(receive_datetime)
        except:
            await msg.answer("⚠️ Неверный формат. Используй: 2025-04-10 12:00")
            dp.message_handlers.unregister(receive_datetime)
    
# ===== StubServer для Render (чтобы не падал из-за портов) =====
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class StubServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_stub_server():
    server = HTTPServer(("0.0.0.0", 10000), StubServer)
    server.serve_forever()

threading.Thread(target=run_stub_server, daemon=True).start()

# ===== Запуск планировщика при старте =====
async def on_startup(_):
    scheduler.add_job(check_scheduled_posts, "interval", minutes=1)
    scheduler.start()

# ===== Запуск бота =====
if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
