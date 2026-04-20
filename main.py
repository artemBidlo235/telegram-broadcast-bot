import sys
import traceback

print("!!! СКРИПТ НАЧАЛ РАБОТУ !!!")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Логирование импортов
print("🔵 Импортирую asyncio...")
import asyncio
print("✅ asyncio импортирован")

print("🔵 Импортирую os...")
import os
print("✅ os импортирован")

print("🔵 Импортирую glob...")
import glob
print("✅ glob импортирован")

print("🔵 Импортирую signal...")
import signal
print("✅ signal импортирован")

print("🔵 Импортирую uuid...")
import uuid
print("✅ uuid импортирован")

print("🔵 Импортирую json...")
import json
print("✅ json импортирован")

print("🔵 Импортирую datetime...")
from datetime import datetime
print("✅ datetime импортирован")

print("🔵 Импортирую threading...")
from threading import Thread
print("✅ threading импортирован")

print("🔵 Импортирую telethon...")
try:
    from telethon import TelegramClient, events
    from telethon.errors import FloodWaitError
    from telethon.tl.custom import Button
    print("✅ telethon импортирован")
except Exception as e:
    print(f"❌ Ошибка импорта telethon: {e}")
    traceback.print_exc()
    sys.exit(1)

print("🔵 Импортирую flask...")
try:
    from flask import Flask, jsonify
    FLASK_AVAILABLE = True
    print("✅ Flask загружен")
except ImportError:
    FLASK_AVAILABLE = False
    print("⚠️ Flask не установлен")
except Exception as e:
    print(f"❌ Ошибка импорта Flask: {e}")
    FLASK_AVAILABLE = False

print("!!! ВСЕ ИМПОРТЫ ЗАГРУЖЕНЫ !!!")

# ========== ВАШИ ДАННЫЕ ==========
print("🔵 Загружаю переменные окружения...")
try:
    API_ID = int(os.getenv("API_ID", 36594021))
    API_HASH = os.getenv("API_HASH", "6dfedd148bf6bba5d4e67ed213178ebb")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8297380746:AAHChWZNlbT-_pc70Nr3zUydC6BebI-ao9Q")
    print(f"✅ API_ID: {API_ID}")
    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:15]}...")
    print(f"✅ API_HASH: {API_HASH[:10]}...")
except Exception as e:
    print(f"❌ Ошибка загрузки переменных: {e}")
    traceback.print_exc()
    sys.exit(1)

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

print("🔵 Создаю папки...")
try:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"📁 Папки созданы: {SESSIONS_DIR}, {DATA_DIR}")
except Exception as e:
    print(f"❌ Ошибка создания папок: {e}")
    traceback.print_exc()
    sys.exit(1)

# Глобальные переменные
user_client = None
is_broadcasting = False
target_chat_ids = []
auth_states = {}
bot_client = None

print("🔵 Определяю функции...")

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
    
    @app.route('/api/users')
    def api_users():
        return jsonify(load_users())
    
    @app.route('/api/admins')
    def api_admins():
        return jsonify(load_admins())
    
    @app.route('/api/stats')
    def api_stats():
        stats = get_stats()
        stats['total_users'] = len(load_users())
        stats['total_admins'] = len(load_admins())
        return jsonify(stats)
    
    def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
else:
    def run_web_server():
        print("⚠️ Веб-сервер не запущен")

print("✅ Все функции определены")

# ========== ФУНКЦИИ УПРАВЛЕНИЯ СЕССИЯМИ ==========
def save_active_session(session_name):
    try:
        with open(ACTIVE_SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_name)
        print(f"💾 Сохранена сессия: {session_name}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def load_active_session():
    try:
        with open(ACTIVE_SESSION_FILE, 'r', encoding='utf-8') as f:
            session_name = f.read().strip()
            session_path = os.path.join(SESSIONS_DIR, session_name)
            if session_name and os.path.exists(session_path):
                print(f"📁 Загружена сессия: {session_name}")
                return session_name
    except:
        pass
    return None

def get_session_files():
    session_files = glob.glob(os.path.join(SESSIONS_DIR, "*.session"))
    sessions = []
    for f in session_files:
        basename = os.path.basename(f)
        if not basename.startswith('bot_session') and not basename.startswith('temp_'):
            sessions.append(basename)
    return sessions

def get_session_path(session_name):
    return os.path.join(SESSIONS_DIR, session_name)

def get_current_session_name():
    if user_client and hasattr(user_client, 'session') and user_client.session:
        try:
            return os.path.basename(str(user_client.session.filename))
        except:
            return None
    return None

async def force_close_current_session():
    global user_client
    if user_client:
        try:
            if user_client.is_connected():
                await user_client.disconnect()
            session_path = str(user_client.session.filename)
            for ext in ['.lock', '.journal']:
                f = session_path + ext
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
            user_client = None
            await asyncio.sleep(0.5)
            print("✅ Сессия закрыта")
        except:
            pass

async def switch_to_session(session_name, event=None):
    global user_client
    print(f"🔄 Переключение на сессию: {session_name}")
    await force_close_current_session()
    session_path = get_session_path(session_name)
    
    try:
        new_client = TelegramClient(session_path, API_ID, API_HASH)
        await new_client.connect()
        
        if await new_client.is_user_authorized():
            user_client = new_client
            save_active_session(session_name)
            me = await user_client.get_me()
            msg = f"✅ Переключено на: {me.first_name}\n📁 Сессия: {session_name}"
            if event:
                await event.reply(msg)
            print(msg)
            return True, msg
        else:
            await new_client.disconnect()
            msg = f"❌ Сессия {session_name} не авторизована"
            if event:
                await event.reply(msg)
            print(msg)
            return False, msg
    except Exception as e:
        msg = f"❌ Ошибка при переключении: {e}"
        if event:
            await event.reply(msg)
        print(msg)
        return False, msg

async def delete_session(session_name, event):
    current = get_current_session_name()
    if current == session_name:
        await event.reply("⚠️ Нельзя удалить активную сессию")
        return False
    session_path = get_session_path(session_name)
    try:
        os.remove(session_path)
        for ext in ['.json', '.lock', '.journal']:
            f = session_path + ext
            if os.path.exists(f):
                os.remove(f)
        await event.reply(f"✅ Сессия {session_name} удалена")
        return True
    except Exception as e:
        await event.reply(f"❌ Ошибка: {e}")
        return False

# ========== ФУНКЦИИ РАБОТЫ С ЧАТАМИ ==========
def load_chat_ids_from_file():
    chat_ids = []
    try:
        with open('chat.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        chat_ids.append(int(line))
                    except:
                        pass
    except:
        pass
    return chat_ids

def save_chat_ids_to_file(chat_ids):
    try:
        with open('chat.txt', 'w', encoding='utf-8') as f:
            for chat_id in chat_ids:
                f.write(f"{chat_id}\n")
        return True
    except:
        return False

async def convert_links_to_ids(links):
    results = []
    seen_links = set()
    duplicates = []
    for link in links:
        if link in seen_links:
            duplicates.append(link)
        else:
            seen_links.add(link)
    for link in seen_links:
        try:
            entity = await user_client.get_entity(link)
            results.append({
                'link': link,
                'id': entity.id,
                'title': getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Без названия'),
                'success': True
            })
        except Exception as e:
            results.append({
                'link': link,
                'error': str(e),
                'success': False
            })
    return results, duplicates

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

print("🔵 Все вспомогательные функции определены")

# ========== ОСНОВНАЯ ФУНКЦИЯ MAIN ==========
async def main():
    global user_client, MESSAGE_TEXT, bot_client, is_broadcasting
    
    print("🔵 1. Начало main()")
    
    # Запускаем веб-сервер
    print("🌐 Запуск веб-сервера...")
    try:
        web_thread = Thread(target=run_web_server, daemon=True)
        web_thread.start()
        print("✅ Веб-сервер запущен")
    except Exception as e:
        print(f"❌ Ошибка запуска веб-сервера: {e}")
        traceback.print_exc()
    
    await asyncio.sleep(2)
    print("🔵 2. После задержки")
    
    # Запуск бота
    max_retries = 3
    bot_client = None
    
    for attempt in range(max_retries):
        try:
            unique_session = f'bot_session_{uuid.uuid4().hex[:8]}'
            print(f"🔵 Пытаюсь запустить бота с сессией: {unique_session}")
            bot_client = await TelegramClient(unique_session, API_ID, API_HASH).start(bot_token=BOT_TOKEN)
            print("✅ Бот запущен")
            break
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"⚠️ Флуд-ожидание {wait_time} сек. (примерно {wait_time // 60} мин)")
            if attempt < max_retries - 1:
                print(f"⏳ Жду {wait_time} секунд...")
                await asyncio.sleep(wait_time)
            else:
                print("❌ Все попытки исчерпаны")
                return
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
            traceback.print_exc()
            return
    
    print("🔵 3. Бот создан")
    
    # Меню для обычного пользователя
    user_menu_buttons = [
        [Button.text("📊 Статус")],
        [Button.text("ℹ️ О боте")]
    ]
    
    # ПРАВИЛЬНОЕ меню для администратора с inline-кнопками
    admin_menu_buttons = [
        [Button.inline("⚙️ Настройки софта", b"soft_settings")],
        [Button.inline("📢 Рассылка", b"newsletter")],
        [Button.inline("🛠 Admin панель", b"admin_panel")],
        [Button.text("📋 Запустить рассылку (по чатам)")],
        [Button.text("📢 Рассылка пользователям")],
        [Button.text("🔄 Поменять базу чатов")],
        [Button.text("📝 Сменить текст"), Button.text("⏹️ Остановить")],
        [Button.text("📊 Статус"), Button.text("🔑 Логин")],
        [Button.text("📁 Управление сессиями"), Button.text("👥 Пользователи")],
        [Button.text("👑 Управление админами"), Button.text("📈 Статистика")],
        [Button.text("◀️ Назад")]
    ]
    
    print("🔵 4. Меню создано")
    
    # Загружаем последнюю сессию пользователя
    last_session = load_active_session()
    if last_session:
        print(f"🔵 Загружаем сессию: {last_session}")
        await switch_to_session(last_session)
    
    print("🔵 5. Регистрирую обработчики...")
    
    # ========== ОБРАБОТЧИК INLINE-КНОПОК ==========
    @bot_client.on(events.CallbackQuery)
    async def callback_handler(event):
        user_id = event.sender_id
        data = event.data.decode()
        
        if not is_admin(user_id):
            await event.answer("❌ У вас нет доступа!", alert=True)
            return
        
        await event.answer()
        
        if data == "soft_settings":
            await event.edit(f"⚙️ **Настройки софта**\n\nЗдесь будут параметры:\n• Скорость рассылки\n• Тайминги\n\n(Функционал в разработке)", 
                             buttons=admin_menu_buttons)
        elif data == "newsletter":
            await event.edit(f"📢 **Рассылка**\n\nВыберите тип рассылки в разделе 'Admin панель'.\n\n(Функционал в разработке)", 
                             buttons=admin_menu_buttons)
        elif data == "admin_panel":
            await event.edit(f"🛠 **Admin панель**\n\nПолный список команд администратора\n\n(Функционал в разработке)", 
                             buttons=admin_menu_buttons)
    
    # ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
    
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        user_id = event.sender_id
        first_name = event.sender.first_name
        username = event.sender.username
        
        add_user(user_id, first_name, username)
        
        if is_admin(user_id):
            role = "Владелец" if is_owner(user_id) else "Администратор"
            await event.reply(f"👋 Привет, {first_name}!\n\n👑 Ваша роль: {role}\n\n✅ Вам доступны все функции бота.", 
                              buttons=admin_menu_buttons)
        else:
            await event.reply(f"👋 Привет, {first_name}!\n\n✅ Вы зарегистрированы как пользователь.\n\nОжидайте сообщений от администратора.", 
                              buttons=user_menu_buttons)
    
    @bot_client.on(events.NewMessage)
    async def unified_handler(event):
        global target_chat_ids, is_broadcasting, MESSAGE_TEXT, user_client
        
        user_id = event.sender_id
        text = event.raw_text
        
        print(f"📨 Получено: {text} от {user_id}")
        
        if not text.startswith('/'):
            add_user(user_id, event.sender.first_name, event.sender.username)
        
        if not is_admin(user_id):
            if text == "📊 Статус" or text == "/status":
                stats = get_stats()
                users_count = len(load_users())
                await event.reply(f"📊 Статус бота\n👥 Пользователей: {users_count}\n📨 Отправлено: {stats.get('messages_sent', 0)}")
            elif text == "ℹ️ О боте":
                await event.reply("🤖 Бот для управления рассылками\nВерсия: 2.0")
            return
        
        # АДМИН-ФУНКЦИИ
        if text == "👑 Управление админами":
            if not is_owner(user_id):
                await event.reply("❌ Только владелец может управлять администраторами!", buttons=admin_menu_buttons)
                return
            
            admins = get_admins_list()
            admin_list = "👑 **Администраторы:**\n\n"
            for a in admins:
                admin_list += f"🆔 {a['id']} - {a['role']}\n"
            
            buttons = [
                [Button.text("➕ Добавить админа")],
                [Button.text("➖ Удалить админа")],
                [Button.text("◀️ Назад")]
            ]
            await event.reply(admin_list, buttons=buttons)
        
        elif text == "➕ Добавить админа":
            if not is_owner(user_id):
                return
            auth_states[user_id] = {'step': 'adding_admin'}
            await event.reply("👑 Введите ID пользователя:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "➖ Удалить админа":
            if not is_owner(user_id):
                return
            auth_states[user_id] = {'step': 'removing_admin'}
            await event.reply("👑 Введите ID администратора для удаления:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📋 Запустить рассылку (по чатам)":
            if not user_client or not user_client.is_connected():
                await event.reply("❌ Авторизуйтесь: 🔑 Логин", buttons=admin_menu_buttons)
                return
            chat_ids = load_chat_ids_from_file()
            if not chat_ids:
                await event.reply("❌ Нет чатов. Нажмите 🔄 Поменять базу", buttons=admin_menu_buttons)
                return
            await send_broadcast_to_chats(chat_ids, event)
        
        elif text == "📢 Рассылка пользователям":
            users = load_users()
            if not users:
                await event.reply("❌ Нет зарегистрированных пользователей", buttons=admin_menu_buttons)
                return
            auth_states[user_id] = {'step': 'broadcast_to_users'}
            await event.reply(f"📢 Отправьте сообщение для рассылки {len(users)} пользователям:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "🔄 Поменять базу чатов":
            if not user_client or not user_client.is_connected():
                await event.reply("❌ Сначала авторизуйтесь", buttons=admin_menu_buttons)
                return
            auth_states[user_id] = {'step': 'awaiting_chat_links'}
            await event.reply("📋 Отправьте список ссылок (по одной на строку):\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📝 Сменить текст":
            auth_states[user_id] = {'step': 'awaiting_new_text'}
            await event.reply(f"📝 Текущий текст:\n{MESSAGE_TEXT}\n\nОтправьте новый текст:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "⏹️ Остановить":
            if is_broadcasting:
                is_broadcasting = False
                await event.reply("⏸️ Рассылка остановлена", buttons=admin_menu_buttons)
            else:
                await event.reply("ℹ️ Рассылка не активна", buttons=admin_menu_buttons)
        
        elif text == "📊 Статус":
            if user_client and user_client.is_connected():
                try:
                    me = await user_client.get_me()
                    acc = f"✅ {me.first_name}"
                except:
                    acc = "❌ Ошибка"
            else:
                acc = "❌ Не авторизован"
            chat_ids = load_chat_ids_from_file()
            await event.reply(f"👤 {acc}\n📁 {get_current_session_name() or 'Нет'}\n📝 {MESSAGE_TEXT[:50]}\n📋 {len(chat_ids)} чатов", buttons=admin_menu_buttons)
        
        elif text == "🔑 Логин":
            auth_states[user_id] = {'step': 'awaiting_phone'}
            await event.reply("📱 Введите номер телефона (пример: +12399230271)", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📁 Управление сессиями":
            sessions = get_session_files()
            current = get_current_session_name()
            buttons = []
            for s in sessions:
                if s == current:
                    buttons.append([Button.text(f"✅ {s} (активна)")]
                else:
                    buttons.append([Button.text(f"🔑 {s}"), Button.text(f"🗑️ {s}")])
            if not sessions:
                await event.reply("📁 Сессии не найдены", buttons=[[Button.text("◀️ Назад")]])
                return
            buttons.append([Button.text("◀️ Назад")])
            await event.reply(f"📁 Управление сессиями\nТекущая: {current or 'Нет'}\nВсего: {len(sessions)}", buttons=buttons)
        
        elif text == "👥 Пользователи":
            users = load_users()
            if not users:
                await event.reply("📭 Нет зарегистрированных пользователей")
                return
            user_list = "👥 **Пользователи:**\n\n"
            for uid, data in users.items():
                user_list += f"🆔 ID: `{uid}`\n👤 {data.get('first_name', '?')}\n📅 {data.get('joined_at', '?')[:10]}\n\n"
                if len(user_list) > 3500:
                    user_list += f"\n... и ещё {len(users)} пользователей"
                    break
            await event.reply(user_list, buttons=admin_menu_buttons)
        
        elif text == "📈 Статистика":
            stats = get_stats()
            users_count = len(load_users())
            admins_count = len(load_admins())
            await event.reply(f"""
📊 **Статистика бота**

👥 Пользователей: {users_count}
👑 Администраторов: {admins_count}
📨 Отправлено: {stats.get('messages_sent', 0)}
📢 Рассылок: {stats.get('broadcasts', 0)}

📁 Активная сессия: {get_current_session_name() or 'Нет'}
✅ Бот работает стабильно
""", buttons=admin_menu_buttons)
        
        elif text == "◀️ Назад":
            await event.reply("🔙 Главное меню", buttons=admin_menu_buttons)
        
        elif text.startswith("🔑 "):
            session_name = text[2:]
            success, msg = await switch_to_session(session_name, event)
            if success:
                await event.reply("🔙 Возврат в главное меню", buttons=admin_menu_buttons)
        
        elif text.startswith("🗑️ "):
            session_name = text[2:]
            await delete_session(session_name, event)
        
        elif text == "❌ Отмена":
            if user_id in auth_states:
                del auth_states[user_id]
            await event.reply("❌ Отменено", buttons=admin_menu_buttons)
        
        # Обработка состояний
        elif user_id in auth_states:
            state = auth_states[user_id]
            
            if state['step'] == 'adding_admin' and text != "❌ Отмена":
                try:
                    new_admin_id = int(text.strip())
                    success, msg = add_admin(new_admin_id, user_id)
                    if success:
                        await event.reply(f"✅ {msg}!", buttons=admin_menu_buttons)
                        try:
                            await bot_client.send_message(new_admin_id, "🎉 Вам выданы права администратора!")
                        except:
                            pass
                    else:
                        await event.reply(f"❌ {msg}", buttons=admin_menu_buttons)
                    del auth_states[user_id]
                except ValueError:
                    await event.reply("❌ Неверный формат ID", buttons=admin_menu_buttons)
                    del auth_states[user_id]
            
            elif state['step'] == 'removing_admin' and text != "❌ Отмена":
                try:
                    admin_id = int(text.strip())
                    success, msg = remove_admin(admin_id)
                    await event.reply(f"✅ {msg}" if success else f"❌ {msg}", buttons=admin_menu_buttons)
                    del auth_states[user_id]
                except ValueError:
                    await event.reply("❌ Неверный формат ID", buttons=admin_menu_buttons)
                    del auth_states[user_id]
            
            elif state['step'] == 'broadcast_to_users' and text != "❌ Отмена":
                users = load_users()
                success = 0
                fail = 0
                status_msg = await event.reply(f"🚀 Рассылка {len(users)} пользователям...")
                for uid in users:
                    try:
                        await bot_client.send_message(int(uid), text)
                        success += 1
                    except:
                        fail += 1
                    await asyncio.sleep(0.3)
                await status_msg.edit(f"✅ Рассылка завершена!\n✅ {success}\n❌ {fail}")
                update_stats(success)
                del auth_states[user_id]
            
            elif state['step'] ==
