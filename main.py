import asyncio
import os
import glob
import signal
import sys
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Thread
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.custom import Button

# ========== ВАШИ ДАННЫЕ ==========
# Данные берутся из переменных окружения Railway
API_ID = int(os.getenv("API_ID", 36594021))
API_HASH = os.getenv("API_HASH", "6dfedd148bf6bba5d4e67ed213178ebb")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8297380746:AAHChWZNlbT-_pc70Nr3zUydC6BebI-ao9Q")

# СПИСОК АДМИНОВ (можно добавить ID друга)
ADMINS = [
    1031953955,  # Ваш ID
    # 123456789,  # ID друга (добавьте сюда)
]

# Настройки рассылки
MESSAGE_TEXT = "qwerty"
DELAY_BETWEEN_MESSAGES = 5

# Папки для хранения данных
SESSIONS_DIR = "sessions"
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
ACTIVE_SESSION_FILE = os.path.join(SESSIONS_DIR, "active_session.txt")
# ==================================

# Создаём необходимые папки
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Глобальные переменные
user_client = None
is_broadcasting = False
target_chat_ids = []
auth_states = {}


# ========== РАБОТА С БАЗОЙ ПОЛЬЗОВАТЕЛЕЙ ==========
def load_users():
    """Загружает список пользователей из файла"""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"❌ Ошибка загрузки пользователей: {e}")
        return {}


def save_users(users):
    """Сохраняет список пользователей в файл"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователей: {e}")
        return False


def add_user(user_id, first_name, username=None):
    """Добавляет нового пользователя в базу"""
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
        # Обновляем время последней активности
        users[user_id_str]["last_active"] = datetime.now().isoformat()
        save_users(users)
        return False


def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMINS


def get_users_list():
    """Возвращает список всех пользователей"""
    users = load_users()
    return users


def get_stats():
    """Возвращает статистику бота"""
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"messages_sent": 0, "broadcasts": 0}
    except:
        return {"messages_sent": 0, "broadcasts": 0}


def update_stats(messages_count=0):
    """Обновляет статистику"""
    stats = get_stats()
    stats["messages_sent"] += messages_count
    if messages_count > 0:
        stats["broadcasts"] += 1
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
    except:
        pass


# ========== ВЕБ-СЕРВЕР ДЛЯ RAILWAY ==========
app = Flask(__name__)


@app.route('/')
def index():
    """Главная страница веб-сервера"""
    users = load_users()
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
            table {{ margin: 0 auto; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>🤖 Telegram Бот Рассыльщик</h1>
        <div class="status">✅ Бот работает!</div>
        <div class="stats">
            <p>📊 Статистика:</p>
            <p>👥 Всего пользователей: {len(users)}</p>
            <p>📨 Отправлено сообщений: {stats.get('messages_sent', 0)}</p>
            <p>📢 Количество рассылок: {stats.get('broadcasts', 0)}</p>
        </div>
        <h3>👥 Список пользователей:</h3>
        <table>
            <tr><th>ID</th><th>Имя</th><th>Username</th><th>Дата присоединения</th></tr>
            {''.join([f"<tr><td>{uid}</td><td>{data.get('first_name', '')}</td><td>{data.get('username', '-')}</td><td>{data.get('joined_at', '')[:10]}</td></tr>" for uid, data in users.items()])}
        </table>
    </body>
    </html>
    """


@app.route('/api/users')
def api_users():
    """API для получения списка пользователей"""
    users = load_users()
    return jsonify(users)


@app.route('/api/stats')
def api_stats():
    """API для получения статистики"""
    stats = get_stats()
    stats['total_users'] = len(load_users())
    return jsonify(stats)


def run_web_server():
    """Запускает веб-сервер в отдельном потоке"""
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


# ========== ОСНОВНАЯ ЛОГИКА БОТА ==========
def cleanup_and_exit(signum=None, frame=None):
    print("\n🔄 Завершение работы...")
    async def cleanup():
        global user_client
        if user_client and user_client.is_connected():
            await user_client.disconnect()
        sys.exit(0)
    asyncio.create_task(cleanup())
    asyncio.get_event_loop().call_later(2, lambda: sys.exit(0))


signal.signal(signal.SIGINT, cleanup_and_exit)


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


async def send_broadcast_to_users(message_text, event):
    """Отправляет сообщение всем пользователям бота"""
    users = load_users()
    success_count = 0
    fail_count = 0
    
    status_msg = await event.reply(f"🚀 Рассылка {len(users)} пользователям...")
    
    for user_id_str, user_data in users.items():
        try:
            user_id = int(user_id_str)
            await bot_client.send_message(user_id, message_text)
            success_count += 1
        except:
            fail_count += 1
        await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями
    
    await status_msg.edit(f"✅ Рассылка завершена!\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}")
    update_stats(success_count)


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
    
    # Задержка перед стартом для стабильности
    await asyncio.sleep(2)
    print("🔵 1.5 После задержки")
    
    # Запуск бота с обработкой флуда и уникальным именем сессии
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
            print(f"Попытка {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"⏳ Жду {wait_time} секунд перед следующей попыткой...")
                await asyncio.sleep(wait_time)
            else:
                print("❌ Все попытки исчерпаны. Бот не может запуститься из-за флуда.")
                return
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
            return
    
    print("🔵 2. После запуска бота")
    
    # Меню для обычного пользователя
    user_menu_buttons = [
        [Button.text("📊 Статус")],
        [Button.text("ℹ️ О боте")]
    ]
    
    # Меню для администратора
    admin_menu_buttons = [
        [Button.text("📋 Запустить рассылку (по чатам)")],
        [Button.text("📢 Рассылка пользователям")],
        [Button.text("🔄 Поменять базу чатов")],
        [Button.text("📝 Сменить текст"), Button.text("⏹️ Остановить")],
        [Button.text("📊 Статус"), Button.text("🔑 Логин")],
        [Button.text("📁 Управление сессиями"), Button.text("👥 Пользователи")],
        [Button.text("📈 Статистика")]
    ]
    
    print("🔵 3. Меню создано")
    
    # Проверка папки sessions
    print(f"📁 Папка sessions существует: {os.path.exists(SESSIONS_DIR)}")
    print(f"📁 Полный путь: {os.path.abspath(SESSIONS_DIR)}")
    
    last_session = load_active_session()
    if last_session:
        print(f"🔵 4. Загружаем сессию: {last_session}")
        await switch_to_session(last_session)
    else:
        print("🔵 4. Нет сохранённой сессии")
    
    print("🔵 5. После загрузки сессии")
    
    # ========== ОБРАБОТЧИК КОМАНДЫ /START ==========
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        user_id = event.sender_id
        first_name = event.sender.first_name
        username = event.sender.username
        
        # Добавляем пользователя в базу
        add_user(user_id, first_name, username)
        
        # Приветственное сообщение
        welcome_text = f"""
🤖 **Добро пожаловать, {first_name}!**

Я бот для управления рассылками.

📌 **Доступные команды:**
• /start - Показать это сообщение
• /help - Помощь
• /status - Проверить статус

🔐 **Для администраторов доступны дополнительные функции.**
"""
        await event.reply(welcome_text, buttons=user_menu_buttons)
    
    # ========== ОБРАБОТЧИК КОМАНДЫ /HELP ==========
    @bot_client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        user_id = event.sender_id
        if is_admin(user_id):
            help_text = """
📚 **Помощь по боту**

**Основные функции:**
• 📋 Запустить рассылку (по чатам) - рассылка в указанные чаты
• 📢 Рассылка пользователям - рассылка всем пользователям бота
• 🔄 Поменять базу чатов - загрузить новые чаты из ссылок
• 📝 Сменить текст - изменить текст для рассылки
• ⏹️ Остановить - остановить активную рассылку

**Управление:**
• 📊 Статус - проверить статус аккаунта
• 🔑 Логин - авторизовать аккаунт
• 📁 Управление сессиями - управление сессиями пользователей
• 👥 Пользователи - список пользователей бота
• 📈 Статистика - статистика рассылок
"""
        else:
            help_text = """
📚 **Помощь по боту**

• 📊 Статус - проверить статус бота
• ℹ️ О боте - информация о боте

Для получения доступа к дополнительным функциям обратитесь к администратору.
"""
        await event.reply(help_text)
    
    # ========== ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ==========
    @bot_client.on(events.NewMessage)
    async def unified_handler(event):
        global target_chat_ids, is_broadcasting, MESSAGE_TEXT, user_client
        
        user_id = event.sender_id
        text = event.raw_text
        
        # Добавляем пользователя в базу (если ещё не добавлен)
        if not text.startswith('/'):  # Не добавляем по командам, только по обычным сообщениям
            add_user(user_id, event.sender.first_name, event.sender.username)
        
        # Проверяем, админ ли пользователь
        is_user_admin = is_admin(user_id)
        
        # Меню для обычных пользователей
        if not is_user_admin:
            if text == "📊 Статус" or text == "/status":
                stats = get_stats()
                users_count = len(load_users())
                await event.reply(f"""
📊 **Статус бота**

👥 Пользователей: {users_count}
📨 Всего отправлено: {stats.get('messages_sent', 0)}
📢 Рассылок проведено: {stats.get('broadcasts', 0)}

✅ Бот работает стабильно
""")
            elif text == "ℹ️ О боте":
                await event.reply("""
🤖 **О боте**

Версия: 2.0
Разработчик: @YourUsername

Бот предназначен для управления рассылками в Telegram.
""")
            return  # Обычный пользователь не может использовать админ-функции
        
        # ========== АДМИН-ФУНКЦИИ ==========
        
        # Основное меню
        if text == "📋 Запустить рассылку (по чатам)":
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
            await event.reply("📋 Отправьте список ссылок (по одной на строку)", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📝 Сменить текст":
            auth_states[user_id] = {'step': 'awaiting_new_text'}
            await event.reply(f"📝 Текущий текст:\n{MESSAGE_TEXT}\n\nОтправьте новый текст", buttons=[[Button.text("❌ Отмена")]])
        
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
                    buttons.append([Button.text(f"✅ {s} (активна)")])
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
            
            # Формируем список пользователей
            user_list = "👥 **Список пользователей:**\n\n"
            for uid, data in users.items():
                user_list += f"🆔 ID: `{uid}`\n👤 Имя: {data.get('first_name', '?')}\n📅 Присоединился: {data.get('joined_at', '?')[:10]}\n\n"
            
            # Отправляем частями, если слишком длинное
            if len(user_list) > 4000:
                await event.reply(f"📊 Всего пользователей: {len(users)}\n\nПодробный список доступен по адресу:\n{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'http://localhost:8080')}/")
            else:
                await event.reply(user_list)
        
        elif text == "📈 Статистика":
            stats = get_stats()
            users_count = len(load_users())
            await event.reply(f"""
📊 **Статистика бота**

👥 Всего пользователей: {users_count}
📨 Отправлено сообщений: {stats.get('messages_sent', 0)}
📢 Проведено рассылок: {stats.get('broadcasts', 0)}

📁 Активная сессия: {get_current_session_name() or 'Нет'}
✅ Бот работает стабильно
""")
        
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
        
        elif user_id in auth_states:
            state = auth_states[user_id]
            
            # Рассылка пользователям
            if state['step'] == 'broadcast_to_users' and text != "❌ Отмена":
                users = load_users()
                success_count = 0
                fail_count = 0
                
                status_msg = await event.reply(f"🚀 Начинаю рассылку {len(users)} пользователям...")
                
                for user_id_str, user_data in users.items():
                    try:
                        target_id = int(user_id_str)
                        await bot_client.send_message(target_id, text)
                        success_count += 1
                    except:
                        fail_count += 1
                    await asyncio.sleep(0.3)
                
                await status_msg.edit(f"✅ Рассылка завершена!\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}")
                update_stats(success_count)
                del auth_states[user_id]
            
            # Логин по телефону
            elif state['step'] == 'awaiting_phone' and text.startswith('+'):
                print(f"📱 Получен номер: {text}")
                phone = text
                state['phone'] = phone
                state['step'] = 'awaiting_code'
                temp_path = os.path.join(SESSIONS_DIR, f'temp_{user_id}')
                temp = TelegramClient(temp_path, API_ID, API_HASH)
                await temp.connect()
                state['temp'] = temp
                try:
                    result = await temp.send_code_request(phone)
                    state['hash'] = result.phone_code_hash
                    await event.reply("🔑 Введите код из Telegram", buttons=[[Button.text("❌ Отмена")]])
                except Exception as e:
                    await event.reply(f"❌ {e}", buttons=admin_menu_buttons)
                    del auth_states[user_id]
            
            elif state['step'] == 'awaiting_code' and text.isdigit() and len(text) == 5:
                print(f"🔑 Получен код: {text}")
                code = text
                temp = state['temp']
                try:
                    await temp.sign_in(phone=state['phone'], code=code, phone_code_hash=state['hash'])
                    user_client = temp
                    me = await user_client.get_me()
                    session_name = f"{me.first_name}_{state['phone'][-5:]}.session"
                    session_path = os.path.join(SESSIONS_DIR, session_name)
                    temp_path = os.path.join(SESSIONS_DIR, f'temp_{user_id}.session')
                    if os.path.exists(session_path):
                        await user_client.disconnect()
                        os.remove(temp_path)
                        await switch_to_session(session_name)
                        await event.reply(f"✅ Вход выполнен: {me.first_name}", buttons=admin_menu_buttons)
                    else:
                        await user_client.disconnect()
                        await asyncio.sleep(0.5)
                        os.rename(temp_path, session_path)
                        await switch_to_session(session_name)
                        await event.reply(f"✅ Авторизован: {me.first_name}", buttons=admin_menu_buttons)
                    del auth_states[user_id]
                except Exception as e:
                    await event.reply(f"❌ Ошибка: {e}", buttons=admin_menu_buttons)
                    del auth_states[user_id]
            
            # Ссылки для чатов
            elif state['step'] == 'awaiting_chat_links' and text != "❌ Отмена":
                print(f"📋 Получены ссылки: {len(text.split(chr(10)))} строк")
                links = [l.strip() for l in text.split('\n') if l.strip()]
                if not links:
                    await event.reply("❌ Пустой список", buttons=[[Button.text("❌ Отмена")]])
                    return
                await event.reply(f"🔄 Обрабатываю {len(links)}...")
                results, dups = await convert_links_to_ids(links)
                ok = [r for r in results if r['success']]
                bad = [r for r in results if not r['success']]
                if ok:
                    ids = [r['id'] for r in ok]
                    save_chat_ids_to_file(ids)
                    msg = f"✅ Сохранено {len(ok)} чатов"
                    if dups:
                        msg += f"\n⚠️ Дубликатов: {len(dups)}"
                    if bad:
                        msg += f"\n❌ Ошибок: {len(bad)}"
                    msg += "\n\n🚀 Запустить рассылку?"
                    del auth_states[user_id]
                    await event.reply(msg, buttons=[[Button.text("✅ Да"), Button.text("❌ Нет")]])
                else:
                    await event.reply("❌ Не удалось обработать ссылки", buttons=admin_menu_buttons)
                    del auth_states[user_id]
            
            # Смена текста
            elif state['step'] == 'awaiting_new_text' and text != "❌ Отмена":
                print(f"📝 Новый текст: {text[:50]}...")
                MESSAGE_TEXT = text
                await event.reply(f"✅ Текст изменён", buttons=admin_menu_buttons)
                del auth_states[user_id]
        
        # Обработка Да/Нет после сохранения базы
        elif text == "✅ Да":
            chat_ids = load_chat_ids_from_file()
            if chat_ids:
                await send_broadcast_to_chats(chat_ids, event)
            else:
                await event.reply("❌ Нет чатов", buttons=admin_menu_buttons)
        
        elif text == "❌ Нет":
            await event.reply("✅ База сохранена", buttons=admin_menu_buttons)
    
    print("🔵 6. Обработчик зарегистрирован")
    print(f"📁 Папка для сессий: {SESSIONS_DIR}")
    print(f"📁 Папка для данных: {DATA_DIR}")
    print(f"👥 Администраторы: {ADMINS}")
    print("💡 Нажмите Ctrl+C для безопасного завершения")
    
    # ========== БЕСКОНЕЧНОЕ ОЖИДАНИЕ ==========
    print("🟢 Бот запущен и ожидает сообщения...")
    print(f"🌐 Веб-интерфейс доступен по адресу: https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:8080')}")
