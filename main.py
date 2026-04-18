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

print(f"✅ API_ID: {API_ID}")
print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")

# Настройки рассылки
MESSAGE_TEXT = "qwerty"
DELAY_BETWEEN_MESSAGES = 5

# Папки для хранения данных
SESSIONS_DIR = "sessions"
DATA_DIR = "data"
CHAT_LISTS_DIR = os.path.join(DATA_DIR, "chat_lists")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
ACTIVE_SESSION_FILE = os.path.join(SESSIONS_DIR, "active_session.txt")
CURRENT_CHAT_LIST_FILE = os.path.join(DATA_DIR, "current_chat_list.txt")
# ==================================

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHAT_LISTS_DIR, exist_ok=True)
print(f"📁 Папки созданы: {SESSIONS_DIR}, {DATA_DIR}, {CHAT_LISTS_DIR}")

# Глобальные переменные
user_client = None
is_broadcasting = False
target_chat_ids = []
auth_states = {}
bot_client = None
current_message_ids = {}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def delete_previous_messages(event, user_id):
    if user_id in current_message_ids:
        try:
            for msg_id in current_message_ids[user_id]:
                try:
                    await bot_client.delete_messages(event.chat_id, msg_id)
                except:
                    pass
        except:
            pass
    current_message_ids[user_id] = []


async def send_and_track(event, text, buttons=None, user_id=None):
    if user_id is None:
        user_id = event.sender_id
    msg = await event.reply(text, buttons=buttons)
    if user_id not in current_message_ids:
        current_message_ids[user_id] = []
    current_message_ids[user_id].append(msg.id)
    if len(current_message_ids[user_id]) > 50:
        current_message_ids[user_id] = current_message_ids[user_id][-30:]
    return msg


# ========== РАБОТА СО СПИСКАМИ ЧАТОВ ==========
def get_chat_lists():
    lists = []
    for file in os.listdir(CHAT_LISTS_DIR):
        if file.endswith('.json'):
            lists.append(file[:-5])
    return lists


def load_chat_list(list_name):
    file_path = os.path.join(CHAT_LISTS_DIR, f"{list_name}.json")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('chat_ids', []), data.get('chat_links', []), data.get('created_at', '')
    except:
        return [], [], ''


def save_chat_list(list_name, chat_ids, chat_links):
    file_path = os.path.join(CHAT_LISTS_DIR, f"{list_name}.json")
    data = {
        'chat_ids': chat_ids,
        'chat_links': chat_links,
        'created_at': datetime.now().isoformat()
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_current_chat_list():
    try:
        with open(CURRENT_CHAT_LIST_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except:
        return None


def set_current_chat_list(list_name):
    with open(CURRENT_CHAT_LIST_FILE, 'w', encoding='utf-8') as f:
        f.write(list_name)


def load_current_chat_ids():
    current_list = get_current_chat_list()
    if current_list:
        chat_ids, _, _ = load_chat_list(current_list)
        return chat_ids
    return []


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
        print(f"Ошибка загрузки админов: {e}")
        return {1031953955: {"role": "owner", "added_by": "system", "added_at": datetime.now().isoformat()}}


def save_admins(admins):
    try:
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admins, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения админов: {e}")
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
        print(f"Ошибка загрузки пользователей: {e}")
        return {}


def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения пользователей: {e}")
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
        print(f"Новый пользователь: {first_name} (ID: {user_id})")
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
        return f"<h1>Telegram Бот Рассыльщик</h1><p>Пользователей: {len(users)}</p><p>Администраторов: {len(admins)}</p><p>Отправлено: {stats.get('messages_sent', 0)}</p>"
    
    def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
else:
    def run_web_server():
        print("Веб-сервер не запущен")


# ========== ФУНКЦИИ УПРАВЛЕНИЯ СЕССИЯМИ ==========
def save_active_session(session_name):
    try:
        with open(ACTIVE_SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(session_name)
        print(f"Сохранена сессия: {session_name}")
        return True
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return False


def load_active_session():
    try:
        with open(ACTIVE_SESSION_FILE, 'r', encoding='utf-8') as f:
            session_name = f.read().strip()
            session_path = os.path.join(SESSIONS_DIR, session_name)
            if session_name and os.path.exists(session_path):
                print(f"Загружена сессия: {session_name}")
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
            print("Сессия закрыта")
        except:
            pass


async def switch_to_session(session_name, event=None):
    global user_client
    print(f"Переключение на сессию: {session_name}")
    await force_close_current_session()
    session_path = get_session_path(session_name)
    try:
        new_client = TelegramClient(session_path, API_ID, API_HASH)
        await new_client.connect()
        if await new_client.is_user_authorized():
            user_client = new_client
            save_active_session(session_name)
            me = await user_client.get_me()
            msg = f"Переключено на: {me.first_name}\nСессия: {session_name}"
            if event:
                await send_and_track(event, msg, user_id=event.sender_id)
            print(msg)
            return True, msg
        else:
            await new_client.disconnect()
            msg = f"Сессия {session_name} не авторизована"
            if event:
                await send_and_track(event, msg, user_id=event.sender_id)
            print(msg)
            return False, msg
    except Exception as e:
        msg = f"Ошибка при переключении: {e}"
        if event:
            await send_and_track(event, msg, user_id=event.sender_id)
        print(msg)
        return False, msg


async def delete_session(session_name, event):
    current = get_current_session_name()
    if current == session_name:
        await send_and_track(event, "Нельзя удалить активную сессию", user_id=event.sender_id)
        return False
    session_path = get_session_path(session_name)
    try:
        os.remove(session_path)
        for ext in ['.json', '.lock', '.journal']:
            f = session_path + ext
            if os.path.exists(f):
                os.remove(f)
        await send_and_track(event, f"Сессия {session_name} удалена", user_id=event.sender_id)
        return True
    except Exception as e:
        await send_and_track(event, f"Ошибка: {e}", user_id=event.sender_id)
        return False


# ========== ФУНКЦИИ РАБОТЫ С ЧАТАМИ ==========
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
        await send_and_track(event, "Аккаунт не авторизован!", user_id=event.sender_id)
        return
    if is_broadcasting:
        await send_and_track(event, "Рассылка уже идёт!", user_id=event.sender_id)
        return
    is_broadcasting = True
    success_count = 0
    fail_count = 0
    status_msg = await send_and_track(event, f"Рассылка в {len(chat_ids)} чатов...", user_id=event.sender_id)
    for i, chat_id in enumerate(chat_ids, 1):
        if not is_broadcasting:
            await send_and_track(event, "Остановлено", user_id=event.sender_id)
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
                await status_msg.edit(f"{i}/{len(chat_ids)}\nУспешно: {success_count}\nОшибок: {fail_count}")
            except:
                pass
        if i < len(chat_ids) and is_broadcasting:
            await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
    is_broadcasting = False
    await send_and_track(event, f"Завершено!\nУспешно: {success_count}\nОшибок: {fail_count}", user_id=event.sender_id)
    update_stats(success_count)


# ========== МЕНЮ ==========
async def show_main_menu(event, user_id):
    await delete_previous_messages(event, user_id)
    buttons = [
        [Button.text("Настройки софта")],
        [Button.text("Рассылка")],
        [Button.text("Admin панель")],
        [Button.text("Выход")]
    ]
    await send_and_track(event, "Главное меню\n\nВыберите раздел:", buttons=buttons, user_id=user_id)


async def show_settings_menu(event, user_id):
    await delete_previous_messages(event, user_id)
    buttons = [
        [Button.text("Настройка базы чатов")],
        [Button.text("Редактирование текста")],
        [Button.text("Управление аккаунтами")],
        [Button.text("Назад")]
    ]
    await send_and_track(event, "Настройки софта\n\nВыберите действие:", buttons=buttons, user_id=user_id)


async def show_accounts_menu(event, user_id):
    await delete_previous_messages(event, user_id)
    buttons = [
        [Button.text("Авторизация")],
        [Button.text("Управление сессиями")],
        [Button.text("Назад")]
    ]
    await send_and_track(event, "Управление аккаунтами\n\nВыберите действие:", buttons=buttons, user_id=user_id)


async def show_broadcast_menu(event, user_id):
    await delete_previous_messages(event, user_id)
    buttons = [
        [Button.text("Запуск")],
        [Button.text("Стоп")],
        [Button.text("Статус")],
        [Button.text("Назад")]
    ]
    await send_and_track(event, "Рассылка\n\nВыберите действие:", buttons=buttons, user_id=user_id)


async def show_chat_lists_menu(event, user_id):
    await delete_previous_messages(event, user_id)
    chat_lists = get_chat_lists()
    current_list = get_current_chat_list()
    buttons = []
    for lst in chat_lists:
        if lst == current_list:
            buttons.append([Button.text(f"✅ {lst} (активен)")])
        else:
            buttons.append([Button.text(f"📁 {lst}")])
    buttons.append([Button.text("Создать новый список")])
    buttons.append([Button.text("Редактировать список")])
    buttons.append([Button.text("Назад")])
    await send_and_track(event, f"Управление базами чатов\n\nАктивный список: {current_list or 'не выбран'}", buttons=buttons, user_id=user_id)


async def show_admin_panel(event, user_id):
    await delete_previous_messages(event, user_id)
    if not is_owner(user_id):
        await send_and_track(event, "У вас нет доступа к Admin панели. Только владелец бота может использовать этот раздел.", user_id=user_id)
        return
    buttons = [
        [Button.text("Управление админами")],
        [Button.text("Пользователи")],
        [Button.text("Статистика бота")],
        [Button.text("Рассылка пользователям")],
        [Button.text("Назад")]
    ]
    await send_and_track(event, "Admin панель\n\nУправление ботом:", buttons=buttons, user_id=user_id)


async def show_chat_list_actions(event, user_id, list_name):
    await delete_previous_messages(event, user_id)
    chat_ids, chat_links, created_at = load_chat_list(list_name)
    buttons = [
        [Button.text("Подтвердить (сделать активным)")],
        [Button.text("Просмотреть список")],
        [Button.text("Назад к спискам")]
    ]
    await send_and_track(event, f"Список: {list_name}\n\nЧатов в списке: {len(chat_ids)}\nСоздан: {created_at[:10] if created_at else 'неизвестно'}\n\nВыберите действие:", buttons=buttons, user_id=user_id)


async def show_chat_list_view_options(event, user_id, list_name):
    await delete_previous_messages(event, user_id)
    buttons = [
        [Button.text("По ID")],
        [Button.text("По ссылкам")],
        [Button.text("Назад")]
    ]
    auth_states[user_id] = {'step': 'viewing_chat_list', 'list_name': list_name}
    await send_and_track(event, f"Просмотр списка {list_name}\n\nВыберите формат отображения:", buttons=buttons, user_id=user_id)


async def show_chat_list_edit_menu(event, user_id, list_name):
    await delete_previous_messages(event, user_id)
    buttons = [
        [Button.text("Просмотреть список")],
        [Button.text("Добавить ссылки")],
        [Button.text("Перезаписать список")],
        [Button.text("Назад")]
    ]
    auth_states[user_id] = {'step': 'editing_chat_list', 'edit_list_name': list_name}
    await send_and_track(event, f"Редактирование списка: {list_name}\n\nВыберите действие:", buttons=buttons, user_id=user_id)


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def main():
    global user_client, MESSAGE_TEXT, bot_client, is_broadcasting
    
    print("1. Начало main()")
    print("Запуск веб-сервера...")
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("Веб-сервер запущен")
    
    await asyncio.sleep(2)
    print("2. После задержки")
    
    max_retries = 3
    bot_client = None
    
    for attempt in range(max_retries):
        try:
            unique_session = f'bot_session_{uuid.uuid4().hex[:8]}'
            print(f"Пытаюсь запустить бота с сессией: {unique_session}")
            bot_client = await TelegramClient(unique_session, API_ID, API_HASH).start(bot_token=BOT_TOKEN)
            print("Бот запущен")
            break
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"Флуд-ожидание {wait_time} сек. (примерно {wait_time // 60} мин)")
            if attempt < max_retries - 1:
                print(f"Жду {wait_time} секунд...")
                await asyncio.sleep(wait_time)
            else:
                print("Все попытки исчерпаны")
                return
        except Exception as e:
            print(f"Ошибка запуска бота: {e}")
            return
    
    print("3. Бот создан")
    
    last_session = load_active_session()
    if last_session:
        print(f"Загружаем сессию: {last_session}")
        await switch_to_session(last_session)
    
    print("4. Регистрирую обработчики...")
    
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        user_id = event.sender_id
        first_name = event.sender.first_name
        username = event.sender.username
        add_user(user_id, first_name, username)
        await show_main_menu(event, user_id)
    
    @bot_client.on(events.NewMessage)
    async def unified_handler(event):
        global user_client, MESSAGE_TEXT, is_broadcasting
        user_id = event.sender_id
        text = event.raw_text
        
        print(f"Получено: {text} от {user_id}")
        
        if not text.startswith('/') and text != "Выход":
            add_user(user_id, event.sender.first_name, event.sender.username)
        
        if not is_admin(user_id):
            if text == "Статус" or text == "/status":
                stats = get_stats()
                users_count = len(load_users())
                await send_and_track(event, f"Статус бота\nПользователей: {users_count}\nОтправлено: {stats.get('messages_sent', 0)}", user_id=user_id)
            elif text == "Выход":
                await show_main_menu(event, user_id)
            return
        
        # ГЛАВНОЕ МЕНЮ
        if text == "Настройки софта":
            await show_settings_menu(event, user_id)
        elif text == "Рассылка":
            await show_broadcast_menu(event, user_id)
        elif text == "Admin панель":
            await show_admin_panel(event, user_id)
        elif text == "Выход":
            await show_main_menu(event, user_id)
        
        # НАСТРОЙКИ СОФТА
        elif text == "Настройка базы чатов":
            await show_chat_lists_menu(event, user_id)
        elif text == "Редактирование текста":
            auth_states[user_id] = {'step': 'awaiting_new_text'}
            await send_and_track(event, f"Текущий текст:\n{MESSAGE_TEXT}\n\nОтправьте новый текст:", buttons=[[Button.text("Отмена")]], user_id=user_id)
        elif text == "Управление аккаунтами":
            await show_accounts_menu(event, user_id)
        elif text == "Авторизация":
            auth_states[user_id] = {'step': 'awaiting_phone'}
            await send_and_track(event, "Введите номер телефона (пример: +12399230271)", buttons=[[Button.text("Отмена")]], user_id=user_id)
        elif text == "Управление сессиями":
            sessions = get_session_files()
            current = get_current_session_name()
            buttons = []
            for s in sessions:
                if s == current:
                    buttons.append([Button.text(f"✅ {s} (активна)")])
                else:
                    buttons.append([Button.text(f"🔑 {s}"), Button.text(f"🗑️ {s}")])
            if not sessions:
                await send_and_track(event, "Сессии не найдены", buttons=[[Button.text("Назад")]], user_id=user_id)
                return
            buttons.append([Button.text("Назад")])
            await send_and_track(event, f"Управление сессиями\n\nТекущая: {current or 'Нет'}\nВсего: {len(sessions)}", buttons=buttons, user_id=user_id)
        
        # УПРАВЛЕНИЕ СПИСКАМИ ЧАТОВ
        elif text.startswith("📁 "):
            list_name = text[2:]
            if list_name.endswith(" (активен)"):
                list_name = list_name[:-10]
            auth_states[user_id] = {'step': 'chat_list_selected', 'list_name': list_name}
            await show_chat_list_actions(event, user_id, list_name)
        elif text == "Создать новый список":
            auth_states[user_id] = {'step': 'creating_chat_list_name'}
            await send_and_track(event, "Введите название для нового списка чатов:", buttons=[[Button.text("Отмена")]], user_id=user_id)
        elif text == "Редактировать список":
            chat_lists = get_chat_lists()
            if not chat_lists:
                await send_and_track(event, "Нет созданных списков. Сначала создайте список.", user_id=user_id)
                return
            buttons = []
            for lst in chat_lists:
                buttons.append([Button.text(f"✏️ {lst}")])
            buttons.append([Button.text("Назад")])
            await send_and_track(event, "Выберите список для редактирования:", buttons=buttons, user_id=user_id)
        elif text.startswith("✏️ "):
            list_name = text[2:]
            await show_chat_list_edit_menu(event, user_id, list_name)
        elif text == "Подтвердить (сделать активным)":
            if user_id in auth_states and 'list_name' in auth_states[user_id]:
                list_name = auth_states[user_id]['list_name']
                set_current_chat_list(list_name)
                await send_and_track(event, f"Список {list_name} установлен как активный для рассылки!", user_id=user_id)
                await show_chat_lists_menu(event, user_id)
            else:
                await show_chat_lists_menu(event, user_id)
        elif text == "Просмотреть список":
            if user_id in auth_states:
                if 'list_name' in auth_states[user_id]:
                    await show_chat_list_view_options(event, user_id, auth_states[user_id]['list_name'])
                elif 'edit_list_name' in auth_states[user_id]:
                    await show_chat_list_view_options(event, user_id, auth_states[user_id]['edit_list_name'])
        elif text == "Добавить ссылки":
            if user_id in auth_states and 'edit_list_name' in auth_states[user_id]:
                list_name = auth_states[user_id]['edit_list_name']
                auth_states[user_id] = {'step': 'adding_links_to_list', 'edit_list_name': list_name}
                await send_and_track(event, f"Отправьте список ссылок для ДОБАВЛЕНИЯ в список {list_name}:\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("Отмена")]], user_id=user_id)
        elif text == "Перезаписать список":
            if user_id in auth_states and 'edit_list_name' in auth_states[user_id]:
                list_name = auth_states[user_id]['edit_list_name']
                auth_states[user_id] = {'step': 'overwrite_chat_list', 'edit_list_name': list_name}
                await send_and_track(event, f"ВНИМАНИЕ! Вы перезаписываете список {list_name}.\n\nОтправьте новый список ссылок (старый будет удалён):", buttons=[[Button.text("Отмена")]], user_id=user_id)
        
        # РАССЫЛКА
        elif text == "Запуск":
            if not user_client or not user_client.is_connected():
                await send_and_track(event, "Авторизуйтесь в Управление аккаунтами -> Авторизация", user_id=user_id)
                return
            chat_ids = load_current_chat_ids()
            if not chat_ids:
                await send_and_track(event, "Нет активного списка чатов. Настройте базу чатов.", user_id=user_id)
                return
            await send_broadcast_to_chats(chat_ids, event)
        elif text == "Стоп":
            if is_broadcasting:
                is_broadcasting = False
                await send_and_track(event, "Рассылка остановлена", user_id=user_id)
            else:
                await send_and_track(event, "Рассылка не активна", user_id=user_id)
        elif text == "Статус":
            if user_client and user_client.is_connected():
                try:
                    me = await user_client.get_me()
                    acc = f"✅ {me.first_name}"
                except:
                    acc = "Ошибка"
            else:
                acc = "Не авторизован"
            chat_ids = load_current_chat_ids()
            current_list = get_current_chat_list() or "не выбран"
            await send_and_track(event, f"{acc}\nАктивный список: {current_list}\nЧатов в списке: {len(chat_ids)}\nТекст: {MESSAGE_TEXT[:50]}", user_id=user_id)
        
        # ADMIN ПАНЕЛЬ
        elif text == "Управление админами":
            if not is_owner(user_id):
                await send_and_track(event, "Только владелец может управлять администраторами!", user_id=user_id)
                return
            admins = get_admins_list()
            admin_list = "Администраторы:\n\n"
            for a in admins:
                admin_list += f"ID: {a['id']} - {a['role']}\n"
            buttons = [[Button.text("Добавить админа")], [Button.text("Удалить админа")], [Button.text("Назад")]]
            await send_and_track(event, admin_list, buttons=buttons, user_id=user_id)
        elif text == "Добавить админа":
            if not is_owner(user_id):
                return
            auth_states[user_id] = {'step': 'adding_admin'}
            await send_and_track(event, "Введите ID пользователя:", buttons=[[Button.text("Отмена")]], user_id=user_id)
        elif text == "Удалить админа":
            if not is_owner(user_id):
                return
            auth_states[user_id] = {'step': 'removing_admin'}
            await send_and_track(event, "Введите ID администратора для удаления:", buttons=[[Button.text("Отмена")]], user_id=user_id)
        elif text == "Пользователи":
            users = load_users()
            if not users:
                await send_and_track(event, "Нет зарегистрированных пользователей", user_id=user_id)
                return
            user_list = "Пользователи:\n\n"
            for uid, data in users.items():
                user_list += f"ID: {uid}\n{data.get('first_name', '?')}\n{data.get('joined_at', '?')[:10]}\n\n"
                if len(user_list) > 3500:
                    user_list += "\n... и ещё"
                    break
                      await send_and_track(event, user_list, user_id=user_id)
        
        elif text == "Статистика бота":
            stats = get_stats()
            users_count = len(load_users())
            admins_count = len(load_admins())
            await send_and_track(event, f"Статистика бота\n\nПользователей: {users_count}\nАдминистраторов: {admins_count}\nОтправлено: {stats.get('messages_sent', 0)}\nРассылок: {stats.get('broadcasts', 0)}", user_id=user_id)
        
        # НАЗАД
        elif text == "Назад":
            await show_main_menu(event, user_id)
        
        # ОБРАБОТКА ОТМЕНЫ
        elif text == "Отмена":
            if user_id in auth_states:
                del auth_states[user_id]
            await show_main_menu(event, user_id)
        
        # ОБРАБОТКА СОСТОЯНИЙ
        elif user_id in auth_states:
            state = auth_states[user_id]
            
            if state['step'] == 'adding_admin' and text != "Отмена":
                try:
                    new_admin_id = int(text.strip())
                    success, msg = add_admin(new_admin_id, user_id)
                    if success:
                        await send_and_track(event, f"{msg}!", user_id=user_id)
                        try:
                            await bot_client.send_message(new_admin_id, "Вам выданы права администратора!")
                        except:
                            pass
                    else:
                        await send_and_track(event, f"{msg}", user_id=user_id)
                    del auth_states[user_id]
                    await show_admin_panel(event, user_id)
                except ValueError:
                    await send_and_track(event, "Неверный формат ID", user_id=user_id)
                    del auth_states[user_id]
            
            elif state['step'] == 'removing_admin' and text != "Отмена":
                try:
                    admin_id = int(text.strip())
                    success, msg = remove_admin(admin_id)
                    await send_and_track(event, f"{msg}", user_id=user_id)
                    del auth_states[user_id]
                    await show_admin_panel(event, user_id)
                except ValueError:
                    await send_and_track(event, "Неверный формат ID", user_id=user_id)
                    del auth_states[user_id]
            
            elif state['step'] == 'awaiting_new_text' and text != "Отмена":
                MESSAGE_TEXT = text
                await send_and_track(event, f"Текст изменён!", user_id=user_id)
                del auth_states[user_id]
                await show_settings_menu(event, user_id)
            
            elif state['step'] == 'awaiting_phone' and text.startswith('+'):
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
                    await send_and_track(event, "Введите код из Telegram", buttons=[[Button.text("Отмена")]], user_id=user_id)
                except Exception as e:
                    await send_and_track(event, f"Ошибка: {e}", user_id=user_id)
                    del auth_states[user_id]
            
            elif state['step'] == 'awaiting_code' and text.isdigit() and len(text) == 5:
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
                        await send_and_track(event, f"Вход выполнен: {me.first_name}", user_id=user_id)
                    else:
                        await user_client.disconnect()
                        await asyncio.sleep(0.5)
                        os.rename(temp_path, session_path)
                        await switch_to_session(session_name)
                        await send_and_track(event, f"Авторизован: {me.first_name}", user_id=user_id)
                    del auth_states[user_id]
                    await show_accounts_menu(event, user_id)
                except Exception as e:
                    await send_and_track(event, f"Ошибка: {e}", user_id=user_id)
                    del auth_states[user_id]
            
            elif state['step'] == 'creating_chat_list_name' and text != "Отмена":
                list_name = text.strip()
                if list_name in get_chat_lists():
                    await send_and_track(event, f"Список с именем {list_name} уже существует!", user_id=user_id)
                    del auth_states[user_id]
                    await show_chat_lists_menu(event, user_id)
                else:
                    auth_states[user_id] = {'step': 'creating_chat_list_content', 'list_name': list_name}
                    await send_and_track(event, f"Отправьте список ссылок для списка {list_name}:\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("Отмена")]], user_id=user_id)
            
            elif state['step'] == 'creating_chat_list_content' and text != "Отмена":
                list_name = state['list_name']
                links = [l.strip() for l in text.split('\n') if l.strip()]
                if not links:
                    await send_and_track(event, "Пустой список", user_id=user_id)
                    return
                await send_and_track(event, f"Обрабатываю {len(links)} ссылок...", user_id=user_id)
                results, dups = await convert_links_to_ids(links)
                ok = [r for r in results if r['success']]
                bad = [r for r in results if not r['success']]
                if ok:
                    chat_ids = [r['id'] for r in ok]
                    chat_links = [r['link'] for r in ok]
                    save_chat_list(list_name, chat_ids, chat_links)
                    msg = f"Список {list_name} сохранён! Добавлено {len(ok)} чатов"
                    if bad:
                        msg += f"\nОшибок: {len(bad)}"
                    await send_and_track(event, msg, user_id=user_id)
                else:
                    await send_and_track(event, "Не удалось обработать ссылки", user_id=user_id)
                del auth_states[user_id]
                await show_chat_lists_menu(event, user_id)
            
            elif state['step'] == 'adding_links_to_list' and text != "Отмена":
                list_name = state['edit_list_name']
                links = [l.strip() for l in text.split('\n') if l.strip()]
                await send_and_track(event, f"Обрабатываю {len(links)} ссылок...", user_id=user_id)
                results, dups = await convert_links_to_ids(links)
                ok = [r for r in results if r['success']]
                if ok:
                    chat_ids, chat_links, _ = load_chat_list(list_name)
                    new_ids = chat_ids + [r['id'] for r in ok]
                    new_links = chat_links + [r['link'] for r in ok]
                    save_chat_list(list_name, new_ids, new_links)
                    await send_and_track(event, f"Добавлено {len(ok)} чатов в список {list_name}", user_id=user_id)
                else:
                    await send_and_track(event, "Не удалось обработать ссылки", user_id=user_id)
                del auth_states[user_id]
                await show_chat_lists_menu(event, user_id)
            
            elif state['step'] == 'overwrite_chat_list' and text != "Отмена":
                list_name = state['edit_list_name']
                links = [l.strip() for l in text.split('\n') if l.strip()]
                await send_and_track(event, f"Обрабатываю {len(links)} ссылок...", user_id=user_id)
                results, dups = await convert_links_to_ids(links)
                ok = [r for r in results if r['success']]
                if ok:
                    chat_ids = [r['id'] for r in ok]
                    chat_links = [r['link'] for r in ok]
                    save_chat_list(list_name, chat_ids, chat_links)
                    await send_and_track(event, f"Список {list_name} перезаписан! Сохранено {len(ok)} чатов", user_id=user_id)
                else:
                    await send_and_track(event, "Не удалось обработать ссылки", user_id=user_id)
                del auth_states[user_id]
                await show_chat_lists_menu(event, user_id)
            
            elif state['step'] == 'viewing_chat_list' and text != "Назад":
                list_name = state['list_name']
                chat_ids, chat_links, _ = load_chat_list(list_name)
                if text == "По ID":
                    if chat_ids:
                        msg = "ID чатов:\n\n" + "\n".join([str(cid) for cid in chat_ids])
                        if len(msg) > 4000:
                            msg = msg[:4000] + "\n\n... и ещё"
                        await send_and_track(event, msg, user_id=user_id)
                    else:
                        await send_and_track(event, "Список пуст", user_id=user_id)
                elif text == "По ссылкам":
                    if chat_links:
                        msg = "Ссылки на чаты:\n\n" + "\n".join(chat_links)
                        if len(msg) > 4000:
                            msg = msg[:4000] + "\n\n... и ещё"
                        await send_and_track(event, msg, user_id=user_id)
                    else:
                        await send_and_track(event, "Список пуст", user_id=user_id)
                del auth_states[user_id]
                await show_chat_lists_menu(event, user_id)
