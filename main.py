print("!!! СКРИПТ НАЧАЛ РАБОТУ !!!")
import sys
print(f"Python version: {sys.version}")

import asyncio
import os
import glob
import signal
import uuid
import json
from datetime import datetime
from threading import Thread
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.custom import Button

try:
    from flask import Flask, jsonify
    FLASK_AVAILABLE = True
    print("✅ Flask загружен")
except ImportError:
    FLASK_AVAILABLE = False
    print("⚠️ Flask не установлен")

print("!!! ВСЕ ИМПОРТЫ ЗАГРУЖЕНЫ !!!")

# ========== ВАШИ ДАННЫЕ ==========
API_ID = int(os.getenv("API_ID", 36594021))
API_HASH = os.getenv("API_HASH", "6dfedd148bf6bba5d4e67ed213178ebb")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8297380746:AAHChWZNlbT-_pc70Nr3zUydC6BebI-ao9Q")

print(f"✅ API_ID загружен: {API_ID}")
print(f"✅ BOT_TOKEN (первые 10 символов): {BOT_TOKEN[:10]}...")

# Настройки рассылки
MESSAGE_TEXT = "qwerty"
DELAY_BETWEEN_MESSAGES = 5

# Папки для хранения данных
SESSIONS_DIR = "sessions"
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
ACTIVE_SESSION_FILE = os.path.join(SESSIONS_DIR, "active_session.txt")
# ==================================

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
print(f"📁 Папки созданы: {SESSIONS_DIR}, {DATA_DIR}")

# Глобальные переменные
user_client = None
is_broadcasting = False
target_chat_ids = []
auth_states = {}
bot_client = None

# ========== РАБОТА С АДМИНАМИ ==========
def load_admins():
    try:
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            admins = json.load(f)
            return {int(k): v for k, v in admins.items()}
    except FileNotFoundError:
        default_admins = {1031953955: {"role": "owner", "added_by": "system", "added_at": datetime.now().isoformat()}}
        save_admins(default_admins)
        return default_admins
    except Exception as e:
        print(f"❌ Ошибка загрузки админов: {e}")
        return {1031953955: {"role": "owner", "added_by": "system", "added_at": datetime.now().isoformat()}}


def save_admins(admins):
    try:
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admins, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения админов: {e}")
        return False


def is_admin(user_id):
    admins = load_admins()
    return user_id in admins


def is_owner(user_id):
    admins = load_admins()
    return user_id in admins and admins[user_id].get("role") == "owner"


def add_admin(admin_id, added_by, username=None):
    admins = load_admins()
    if admin_id in admins:
        return False, "Пользователь уже является админом"
    
    admins[admin_id] = {
        "role": "admin",
        "added_by": added_by,
        "added_at": datetime.now().isoformat(),
        "username": username
    }
    save_admins(admins)
    return True, "Админ добавлен"


def remove_admin(admin_id):
    admins = load_admins()
    if admin_id not in admins:
        return False, "Пользователь не является админом"
    
    if admins[admin_id].get("role") == "owner":
        return False, "Нельзя удалить владельца"
    
    del admins[admin_id]
    save_admins(admins)
    return True, "Админ удалён"


def get_admins_list():
    admins = load_admins()
    result = []
    for uid, data in admins.items():
        result.append({
            "id": uid,
            "role": data.get("role", "admin"),
            "added_by": data.get("added_by"),
            "added_at": data.get("added_at"),
            "username": data.get("username")
        })
    return result


# ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========
def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"❌ Ошибка загрузки пользователей: {e}")
        return {}


def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователей: {e}")
        return False


def add_user(user_id, first_name, username=None):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = {
            "first_name": first_name,
            "username": username,
            "joined_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
        save_users(users)
        print(f"✅ Новый пользователь: {first_name} (ID: {user_id})")
        return True
    else:
        users[user_id_str]["last_active"] = datetime.now().isoformat()
        save_users(users)
        return False


def get_stats():
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"messages_sent": 0, "broadcasts": 0}
    except:
        return {"messages_sent": 0, "broadcasts": 0}


def update_stats(messages_count=0):
    stats = get_stats()
    stats["messages_sent"] += messages_count
    if messages_count > 0:
        stats["broadcasts"] += 1
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
    except:
        pass


# ========== ВЕБ-СЕРВЕР ==========
if FLASK_AVAILABLE:
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        users = load_users()
        admins = load_admins()
        stats = get_stats()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Telegram Бот Рассыльщик</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
                .status {{ color: green; font-size: 24px; }}
                .stats {{ font-size: 18px; margin: 20px; }}
            </style>
        </head>
        <body>
            <h1>🤖 Telegram Бот Рассыльщик</h1>
            <div class="status">✅ Бот работает!</div>
            <div class="stats">
                <p>👥 Пользователей: {len(users)}</p>
                <p>👑 Администраторов: {len(admins)}</p>
                <p>📨 Отправлено: {stats.get('messages_sent', 0)}</p>
            </div>
        </body>
        </html>
        """
    
    def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
else:
    def run_web_server():
        print("⚠️ Веб-сервер не запущен")


# ========== ОСНОВНАЯ ЛОГИКА БОТА ==========
async def send_broadcast_to_chats(chat_ids, event):
    global is_broadcasting, user_client, MESSAGE_TEXT
    
    if not user_client or not user_client.is_connected():
        await event.reply("❌ Аккаунт не авторизован!")
        return
    if is_broadcasting:
        await event.reply("⏳ Рассылка уже идёт!")
        return
    
    is_broadcasting = True
    success_count = 0
    fail_count = 0
    status_msg = await event.reply(f"🚀 Рассылка в {len(chat_ids)} чатов...")
    
    for i, chat_id in enumerate(chat_ids, 1):
        if not is_broadcasting:
            await event.reply("⏸️ Остановлено")
            break
        try:
            entity = await user_client.get_entity(chat_id)
            await user_client.send_message(entity, MESSAGE_TEXT)
            success_count += 1
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                entity = await user_client.get_entity(chat_id)
                await user_client.send_message(entity, MESSAGE_TEXT)
                success_count += 1
            except:
                fail_count += 1
        except:
            fail_count += 1
        if i % 5 == 0:
            try:
                await status_msg.edit(f"🚀 {i}/{len(chat_ids)}\n✅ {success_count}\n❌ {fail_count}")
            except:
                pass
        if i < len(chat_ids) and is_broadcasting:
            await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
    
    is_broadcasting = False
    await event.reply(f"✅ Завершено!\n✅ {success_count}\n❌ {fail_count}")
    update_stats(success_count)


async def main():
    global user_client, MESSAGE_TEXT, bot_client
    
    print("🔵 1. Начало main()")
    
    # Запускаем веб-сервер в отдельном потоке
    print("🌐 Запуск веб-сервера...")
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("✅ Веб-сервер запущен")
    
    await asyncio.sleep(2)
    print("🔵 2. После задержки")
    
    # Запуск бота
    print("🔵 3. Пытаюсь создать клиента Telegram...")
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            unique_session = f'bot_session_{uuid.uuid4().hex[:8]}'
            print(f"🔵 Попытка {attempt + 1}: создаю сессию {unique_session}")
            bot_client = await TelegramClient(unique_session, API_ID, API_HASH).start(bot_token=BOT_TOKEN)
            print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
            break
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"⚠️ Флуд-ожидание {wait_time} сек. (примерно {wait_time // 60} мин)")
            if attempt < max_retries - 1:
                print(f"⏳ Жду {wait_time} секунд...")
                await asyncio.sleep(wait_time)
            else:
                print("❌ Все попытки исчерпаны. Бот не может запуститься.")
                return
        except Exception as e:
            print(f"❌ ОШИБКА при запуске бота: {type(e).__name__}: {e}")
            return
    
    print("🔵 4. Бот создан, регистрирую обработчики...")
    
    # Простой тестовый обработчик
    @bot_client.on(events.NewMessage)
    async def test_handler(event):
        print(f"📨 Получено сообщение от {event.sender_id}: {event.raw_text}")
        if event.raw_text == "/test":
            await event.reply("✅ Бот работает!")
    
    print("🔵 5. Обработчики зарегистрированы")
    print("🟢 Бот запущен и готов к работе!")
    
    # Бесконечное ожидание
    await bot_client.run_until_disconnected()


if __name__ == "__main__":
    print("!!! ЗАПУСКАЮ MAIN !!!")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен вручную")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
