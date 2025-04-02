import logging
import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.types import ContentType, InputMediaPhoto
import os
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp
import tempfile
from aiogram.types import InputFile

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 490364050
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001234567890"))

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
main_kb.add(
    KeyboardButton("📅 Расписание"),
    KeyboardButton("🗑 Удалить запланированный"),
    KeyboardButton("✏️ Редактировать запланированный"),
    KeyboardButton("📆 Изменить дату поста")
)

SCHEDULED_POSTS_FILE = "scheduled_posts.json"
scheduler = AsyncIOScheduler()
pending_posts = {}  # временное хранилище предпросмотров

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
                    os.remove(post["path"])  # 🧹 Удаляем временный файл

            except Exception as e:
                logging.error(f"[SEND ERROR] {e}")
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
        logging.error(f"[IMAGE DOWNLOAD ERROR] {e}")
        return None

# Кнопки предпросмотра
def get_preview_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_post"),
        InlineKeyboardButton("❌ Отменить", callback_data="cancel_post")
    )
    return keyboard
    
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
        logging.info(f"[POST ADDED] Пользователь {msg.from_user.id} добавил обычный пост.")
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
                logging.info(f"[POST DELETED] Пользователь {msg.from_user.id} удалил пост №{index + 1}")
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

@dp.message_handler(lambda msg: msg.text == "⏰ Запланировать пост")
async def schedule_post_prompt(message: types.Message):
    await message.answer("Введите дату и время публикации (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")

    @dp.message_handler()
    async def receive_datetime(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        try:
            scheduled_str = msg.text.strip()
            scheduled_time = datetime.strptime(scheduled_str, "%Y-%m-%d %H:%M")

            if scheduled_time <= datetime.now():
                await msg.answer("⚠️ Указанное время уже прошло. Пожалуйста, укажи время в будущем.")
                dp.message_handlers.unregister(receive_datetime)
                return

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

                pending_posts[msg.from_user.id] = post

                if post["type"] == "text":
                    await msg.answer(post["text"], parse_mode=ParseMode.MARKDOWN, reply_markup=get_preview_keyboard())
                elif post["type"] == "photo":
                    await bot.send_photo(msg.chat.id, post["file_id"], caption=post.get("caption", ""), parse_mode=ParseMode.MARKDOWN, reply_markup=get_preview_keyboard())
                elif post["type"] == "photo_file":
                    photo = InputFile(post["path"])
                    await bot.send_photo(msg.chat.id, photo, caption=post.get("caption", ""), parse_mode=ParseMode.MARKDOWN, reply_markup=get_preview_keyboard())
                elif post["type"] == "album":
                    await msg.answer("📷 Для альбомов предпросмотр пока не поддерживается. Сохраняю автоматически.")
                    posts = load_scheduled_posts()
                    posts.append(post)
                    save_scheduled_posts(posts)

            dp.message_handlers.unregister(receive_datetime)

        except ValueError:
            await msg.answer("⚠️ Неверный формат даты и времени. Используй формат: `2025-04-15 18:30`", parse_mode=ParseMode.MARKDOWN)
            dp.message_handlers.unregister(receive_datetime)

            dp.message_handlers.unregister(receive_datetime)
        except:
            await msg.answer("⚠️ Неверный формат. Используй: 2025-04-10 12:00")
            dp.message_handlers.unregister(receive_datetime)

@dp.callback_query_handler(lambda c: c.data in ["confirm_post", "cancel_post"])
async def handle_preview_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id != ADMIN_ID:
        return await callback.answer("⛔ Нет доступа", show_alert=True)

    if callback.data == "confirm_post":
        if user_id in pending_posts:
            post = pending_posts.pop(user_id)
            posts = load_scheduled_posts()
            posts.append(post)
            save_scheduled_posts(posts)
            await callback.message.answer(f"✅ Пост запланирован на {post['datetime']}")
            logging.info(f"[POST SCHEDULED] Пользователь {user_id} запланировал пост на {post['datetime']}")
        await callback.message.delete()
    elif callback.data == "cancel_post":
        pending_posts.pop(user_id, None)
        await callback.message.answer("❌ Пост отменён.")
        await callback.message.delete()

@dp.message_handler(lambda msg: msg.text == "📅 Расписание")
async def show_schedule(message: types.Message):
    posts = load_scheduled_posts()
    if not posts:
        return await message.answer("📭 Запланированных постов нет.")

    text = ""
    for i, post in enumerate(posts):
        dt = post["datetime"]
        preview = ""
        if post["type"] == "text":
            preview = post["text"][:80]
        elif post["type"] == "photo":
            preview = f"[Фото] {post.get('caption', '')[:80]}"
        elif post["type"] == "photo_file":
            preview = f"[Фото по ссылке] {post.get('caption', '')[:80]}"
        elif post["type"] == "album":
            preview = f"[Альбом из {len(post['media'])} фото]"

        text += f"{i+1}. 🗓 {dt}\n{preview}\n\n"

    await message.answer("📅 Запланированные посты:\n\n" + text)

@dp.message_handler(lambda msg: msg.text == "🗑 Удалить запланированный")
async def delete_scheduled_prompt(message: types.Message):
    posts = load_scheduled_posts()
    if not posts:
        return await message.answer("📭 Нет запланированных постов для удаления.")

    # Показываем список с номерами
    text = ""
    for i, post in enumerate(posts):
        dt = post["datetime"]
        preview = ""
        if post["type"] == "text":
            preview = post["text"][:60]
        elif post["type"] == "photo":
            preview = f"[Фото] {post.get('caption', '')[:60]}"
        elif post["type"] == "photo_file":
            preview = f"[Фото по ссылке] {post.get('caption', '')[:60]}"
        elif post["type"] == "album":
            preview = f"[Альбом из {len(post['media'])} фото]"
        text += f"{i + 1}. 🗓 {dt}\n{preview}\n\n"

    await message.answer("📅 Запланированные посты:\n\n" + text)
    await message.answer("Введите номер поста, который хотите удалить:")

    @dp.message_handler()
    async def receive_delete_index(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        try:
            index = int(msg.text.strip()) - 1
            if 0 <= index < len(posts):
                deleted = posts.pop(index)
                save_scheduled_posts(posts)
                await msg.answer(f"🗑 Удалён пост на {deleted['datetime']}")
            else:
                await msg.answer("❌ Неверный номер.")
        except:
            await msg.answer("⚠️ Введите корректный номер.")
        dp.message_handlers.unregister(receive_delete_index)

@dp.message_handler(lambda msg: msg.text == "✏️ Редактировать запланированный")
async def edit_scheduled_prompt(message: types.Message):
    posts = load_scheduled_posts()
    if not posts:
        return await message.answer("📭 Нет запланированных постов для редактирования.")

    text = ""
    for i, post in enumerate(posts):
        dt = post["datetime"]
        preview = ""
        if post["type"] == "text":
            preview = post["text"][:60]
        elif post["type"] == "photo":
            preview = f"[Фото] {post.get('caption', '')[:60]}"
        elif post["type"] == "photo_file":
            preview = f"[Фото по ссылке] {post.get('caption', '')[:60]}"
        elif post["type"] == "album":
            preview = f"[Альбом из {len(post['media'])} фото]"
        text += f"{i + 1}. 🗓 {dt}\n{preview}\n\n"

    await message.answer("📅 Запланированные посты:\n\n" + text)
    await message.answer("Введите номер поста, который хотите отредактировать:")

    @dp.message_handler()
    async def receive_edit_index(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return

        try:
            index = int(msg.text.strip()) - 1
            posts = load_scheduled_posts()
            if 0 <= index < len(posts):
                await msg.answer("Отправьте новый пост. Это может быть текст, фото, альбом или ссылка на изображение.")

                @dp.message_handler(content_types=ContentType.ANY)
                async def receive_new_post(msg: types.Message):
                    new_post = None

                    if msg.content_type == ContentType.TEXT:
                        if msg.text.strip().startswith("http"):
                            # Ссылка на изображение
                            img_path = await download_image_from_url(msg.text.strip())
                            if img_path:
                                new_post = {
                                    "datetime": posts[index]["datetime"],
                                    "type": "photo_file",
                                    "path": img_path,
                                    "caption": ""
                                }
                            else:
                                await msg.answer("⚠️ Не удалось загрузить изображение.")
                                return
                        else:
                            new_post = {
                                "datetime": posts[index]["datetime"],
                                "type": "text",
                                "text": msg.text.strip()
                            }
                    elif msg.content_type == ContentType.PHOTO:
                        new_post = {
                            "datetime": posts[index]["datetime"],
                            "type": "photo",
                            "file_id": msg.photo[-1].file_id,
                            "caption": msg.caption or ""
                        }
                    elif msg.media_group_id:
                        # Альбом
                        album = [msg]
                        await asyncio.sleep(1.5)  # немного подождать для других фото
                        new_post = {
                            "datetime": posts[index]["datetime"],
                            "type": "album",
                            "media": [{"type": "photo", "media": m.photo[-1].file_id, "caption": m.caption or ""} for m in album]
                        }
                    else:
                        await msg.answer("⚠️ Неподдерживаемый тип поста.")
                        return

                    posts[index] = new_post
                    save_scheduled_posts(posts)
                    await msg.answer("✅ Пост обновлён.")
                    dp.message_handlers.unregister(receive_new_post)

                dp.message_handlers.unregister(receive_edit_index)
            else:
                await msg.answer("❌ Неверный номер.")
                dp.message_handlers.unregister(receive_edit_index)
        except:
            await msg.answer("⚠️ Введите корректный номер.")
            dp.message_handlers.unregister(receive_edit_index)

@dp.message_handler(lambda msg: msg.text == "📆 Изменить дату поста")
async def change_post_date(message: types.Message):
    posts = load_scheduled_posts()
    if not posts:
        return await message.answer("📭 Запланированных постов нет.")

    text = ""
    for i, post in enumerate(posts):
        dt = post["datetime"]
        preview = ""
        if post["type"] == "text":
            preview = post["text"][:60]
        elif post["type"] == "photo":
            preview = f"[Фото] {post.get('caption', '')[:60]}"
        elif post["type"] == "photo_file":
            preview = f"[Фото по ссылке] {post.get('caption', '')[:60]}"
        elif post["type"] == "album":
            preview = f"[Альбом из {len(post['media'])} фото]"
        text += f"{i + 1}. 🗓 {dt}\n{preview}\n\n"

    await message.answer("📅 Запланированные посты:\n\n" + text)
    await message.answer("Введите номер поста, для которого хотите изменить дату:")

    @dp.message_handler()
    async def receive_post_number(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        try:
            index = int(msg.text.strip()) - 1
            posts = load_scheduled_posts()
            if 0 <= index < len(posts):
                await msg.answer("Введите новую дату и время в формате: `2025-04-15 18:30`", parse_mode=ParseMode.MARKDOWN)

                @dp.message_handler()
                async def receive_new_datetime(new_msg: types.Message):
                    if new_msg.from_user.id != ADMIN_ID:
                        return
                    try:
                        new_dt = datetime.strptime(new_msg.text.strip(), "%Y-%m-%d %H:%M")
                        if new_dt <= datetime.now():
                            await new_msg.answer("⚠️ Дата должна быть в будущем.")
                            return
                        posts[index]["datetime"] = new_dt.strftime("%Y-%m-%d %H:%M")
                        save_scheduled_posts(posts)
                        await new_msg.answer("✅ Дата и время поста обновлены.")
                        dp.message_handlers.unregister(receive_new_datetime)
                    except:
                        await new_msg.answer("⚠️ Неверный формат. Используйте: 2025-04-15 18:30")
                dp.message_handlers.unregister(receive_post_number)
            else:
                await msg.answer("❌ Неверный номер поста.")
                dp.message_handlers.unregister(receive_post_number)
        except:
            await msg.answer("⚠️ Введите корректный номер.")
            dp.message_handlers.unregister(receive_post_number)
    
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
