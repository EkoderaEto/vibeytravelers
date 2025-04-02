import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
import os

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
    KeyboardButton("✏️ Редактировать пост"),
    KeyboardButton("📊 Статистика")
)

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

# ===== Запуск бота =====
if __name__ == "__main__":
    executor.start_polling(dp)
