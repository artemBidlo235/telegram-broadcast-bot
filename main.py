import asyncio
import sqlite3
import os
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.custom import Button
from telethon.sessions import StringSession
from flask import Flask
from threading import Thread

# ========== НАСТРОЙКИ ==========
API_ID = 36594021
API_HASH = '6dfedd148bf6bba5d4e67ed213178ebb'
BOT_TOKEN = '8779543002:AAEnnD2AeimtSQDptnmVh-OMXR64sLe5xDg'
MASTER_ADMIN_ID = 1031953955

# Настройки рассылки
DEFAULT_MESSAGE_TEXT = "qwerty"
DELAY_BETWEEN_MESSAGES = 5
# ==================================

# ========== FLASK ДЛЯ RAILWAY ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Бот работает!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

thread = Thread(target=run_flask, daemon=True)
thread.start()
print("🌐 Веб-сервер запущен")
# ==================================

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_admin BOOLEAN DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER,
            session_string TEXT NOT NULL,
            phone_number TEXT,
            first_name TEXT,
            is_active BOOLEAN DEFAULT 0,
            FOREIGN KEY (owner_user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            chat_title TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)', (MASTER_ADMIN_ID,))
    conn.commit()
    return conn

conn = init_db()
# ==================================

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
user_clients = {}
auth_states = {}
user_message_texts = {}
# ==================================

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ==========
def register_user(user_id):
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()

def is_user_allowed(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

def is_user_admin(user_id):
    if user_id == MASTER_ADMIN_ID:
        return True
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    return row and row[0] == 1

def save_user_session(user_id, session_string, phone_number, first_name):
    cursor = conn.cursor()
    cursor.execute('UPDATE telegram_sessions SET is_active = 0 WHERE owner_user_id = ?', (user_id,))
    cursor.execute('''
        INSERT INTO telegram_sessions (owner_user_id, session_string, phone_number, first_name, is_active)
        VALUES (?, ?, ?, ?, 1)
    ''', (user_id, session_string, phone_number, first_name))
    conn.commit()

def get_active_session(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT id, session_string, phone_number, first_name FROM telegram_sessions WHERE owner_user_id = ? AND is_active = 1', (user_id,))
    return cursor.fetchone()

def get_user_sessions(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT id, session_string, phone_number, first_name, is_active FROM telegram_sessions WHERE owner_user_id = ?', (user_id,))
    return cursor.fetchall()

def delete_user_session(user_id, session_id):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM telegram_sessions WHERE id = ? AND owner_user_id = ?', (session_id, user_id))
    conn.commit()

def save_user_chats(user_id, chats):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_chats WHERE user_id = ?', (user_id,))
    for chat_id, chat_title in chats:
        cursor.execute('''
            INSERT INTO user_chats (user_id, chat_id, chat_title)
            VALUES (?, ?, ?)
        ''', (user_id, chat_id, chat_title))
    conn.commit()

def load_user_chats(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM user_chats WHERE user_id = ?', (user_id,))
    return [row[0] for row in cursor.fetchall()]

def get_user_chats_info(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, chat_title FROM user_chats WHERE user_id = ?', (user_id,))
    return cursor.fetchall()

def get_user_chats_count(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM user_chats WHERE user_id = ?', (user_id,))
    return cursor.fetchone()[0]
# ============================================

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С TELEGRAM ==========
async def get_user_client(user_id):
    if user_id in user_clients and user_clients[user_id].is_connected():
        return user_clients[user_id]
    
    session_data = get_active_session(user_id)
    if not session_data:
        return None
    
    session_id, session_string, phone, name = session_data
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            cursor = conn.cursor()
            cursor.execute('DELETE FROM telegram_sessions WHERE id = ?', (session_id,))
            conn.commit()
            return None
        user_clients[user_id] = client
        return client
    except Exception as e:
        print(f"Ошибка подключения для юзера {user_id}: {e}")
        return None

async def convert_links_to_ids(links, client):
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
            entity = await client.get_entity(link)
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Без названия')
            results.append({'link': link, 'id': entity.id, 'title': title, 'success': True})
        except Exception as e:
            results.append({'link': link, 'error': str(e), 'success': False})
    return results, duplicates

async def send_broadcast(user_id, chat_ids, event):
    client = await get_user_client(user_id)
    if not client:
        await event.reply("❌ Ваш аккаунт не авторизован. Используйте 🔑 Логин")
        return
    
    text = user_message_texts.get(user_id, DEFAULT_MESSAGE_TEXT)
    success_count = 0
    fail_count = 0
    
    status_msg = await event.reply(f"🚀 Рассылка в {len(chat_ids)} чатов...\n📝 Текст: {text[:50]}...")
    
    for i, chat_id in enumerate(chat_ids, 1):
        try:
            entity = await client.get_entity(chat_id)
            await client.send_message(entity, text)
            success_count += 1
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                entity = await client.get_entity(chat_id)
                await client.send_message(entity, text)
                success_count += 1
            except:
                fail_count += 1
        except Exception:
            fail_count += 1
        
        if i % 5 == 0 or i == len(chat_ids):
            try:
                await status_msg.edit(f"🚀 {i}/{len(chat_ids)}\n✅ {success_count}\n❌ {fail_count}")
            except:
                pass
        
        if i < len(chat_ids):
            await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
    
    await event.reply(f"✅ Завершено!\n✅ {success_count}\n❌ {fail_count}")
# ============================================

# ========== СОЗДАНИЕ КНОПОК МЕНЮ ==========
def get_main_menu(user_id):
    is_admin = is_user_admin(user_id)
    menu = [
        [Button.text("📋 Запустить рассылку", resize=True)],
        [Button.text("🔄 Поменять базу чатов", resize=True)],
        [Button.text("📝 Сменить текст", resize=True), Button.text("⏹️ Остановить", resize=True)],
        [Button.text("📊 Статус", resize=True), Button.text("🔑 Логин", resize=True)],
        [Button.text("📁 Мои сессии", resize=True), Button.text("📋 Мои чаты", resize=True)]
    ]
    if is_admin:
        menu.append([Button.text("👥 Добавить пользователя", resize=True)])
        menu.append([Button.text("📊 Общая статистика", resize=True)])
    return menu
# ============================================

# ========== ЗАПУСК БОТА ==========
async def main():
    # Создаём клиент бота
    bot = await TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен и готов к работе!")
    
    # Единый обработчик всех сообщений
    @bot.on(events.NewMessage)
    async def all_messages_handler(event):
        user_id = event.sender_id
        text = event.raw_text
        
        # Игнорируем сообщения от самого бота
        if user_id == (await bot.get_me()).id:
            return
        
        print(f"📩 Получено сообщение от {user_id}: {text[:50]}")
        
        # Регистрируем пользователя, если его нет
        register_user(user_id)
        
        if not is_user_allowed(user_id):
            await event.reply("⛔ У вас нет доступа. Обратитесь к администратору.")
            return
        
        # ========== ОБРАБОТКА КОМАНД И КНОПОК ==========
        
        # /start
        if text == '/start':
            await event.reply(
                "🤖 **Мульти-пользовательский бот рассыльщик**\n\n"
                "📌 **Возможности:**\n"
                "• Авторизуйте свой аккаунт через 🔑 Логин\n"
                "• Добавьте чаты через 🔄 Поменять базу чатов\n"
                "• Запустите рассылку через 📋 Запустить рассылку",
                buttons=get_main_menu(user_id)
            )
        
        # Запустить рассылку
        elif text == "📋 Запустить рассылку":
            client = await get_user_client(user_id)
            if not client:
                await event.reply("❌ Авторизуйтесь: 🔑 Логин", buttons=get_main_menu(user_id))
                return
            chat_ids = load_user_chats(user_id)
            if not chat_ids:
                await event.reply("❌ Нет чатов. Нажмите 🔄 Поменять базу", buttons=get_main_menu(user_id))
                return
            await send_broadcast(user_id, chat_ids, event)
        
        # Поменять базу чатов
        elif text == "🔄 Поменять базу чатов":
            client = await get_user_client(user_id)
            if not client:
                await event.reply("❌ Сначала авторизуйтесь: 🔑 Логин", buttons=get_main_menu(user_id))
                return
            auth_states[user_id] = {'step': 'awaiting_chat_links'}
            await event.reply(
                "📋 **Отправьте список ссылок для вашей базы чатов**\n\n"
                "Поддерживаются:\n"
                "- `@username`\n"
                "- `t.me/username`\n"
                "- `https://t.me/username`\n\n"
                "Отправьте /cancel для отмены.",
                buttons=[[Button.text("❌ Отмена")]]
            )
        
        # Сменить текст
        elif text == "📝 Сменить текст":
            auth_states[user_id] = {'step': 'awaiting_new_text'}
            current_text = user_message_texts.get(user_id, DEFAULT_MESSAGE_TEXT)
            await event.reply(
                f"📝 **Текущий текст:**\n`{current_text}`\n\n"
                "Отправьте новый текст.\n"
                "Отправьте /cancel для отмены.",
                buttons=[[Button.text("❌ Отмена")]]
            )
        
        # Статус
        elif text == "📊 Статус":
            client = await get_user_client(user_id)
            if client and client.is_connected():
                try:
                    me = await client.get_me()
                    acc = f"✅ {me.first_name}"
                except:
                    acc = "❌ Ошибка"
            else:
                acc = "❌ Не авторизован"
            chats_count = get_user_chats_count(user_id)
            current_text = user_message_texts.get(user_id, DEFAULT_MESSAGE_TEXT)
            await event.reply(
                f"📊 **Ваш статус:**\n\n"
                f"👤 Аккаунт: {acc}\n"
                f"📝 Текст: {current_text[:50]}\n"
                f"📋 Чатов: {chats_count}",
                buttons=get_main_menu(user_id)
            )
        
        # Логин
        elif text == "🔑 Логин":
            auth_states[user_id] = {'step': 'awaiting_phone'}
            await event.reply(
                "📱 **Введите номер телефона**\nПример: `+12399230271`\n\n"
                "Отправьте /cancel для отмены.",
                buttons=[[Button.text("❌ Отмена")]]
            )
        
        # Мои сессии
        elif text == "📁 Мои сессии":
            sessions = get_user_sessions(user_id)
            if not sessions:
                await event.reply("📁 Нет сохранённых сессий.\n\nИспользуйте 🔑 Логин", buttons=get_main_menu(user_id))
                return
            msg = "📁 **Ваши сессии:**\n\n"
            for sess_id, _, phone, name, is_active in sessions:
                status = "✅ (активна)" if is_active else "⏸️"
                msg += f"• {name} ({phone}) {status}\n"
            await event.reply(msg, buttons=get_main_menu(user_id))
        
        # Мои чаты
        elif text == "📋 Мои чаты":
            chats = get_user_chats_info(user_id)
            if not chats:
                await event.reply("📋 Нет сохранённых чатов.\n\nИспользуйте 🔄 Поменять базу", buttons=get_main_menu(user_id))
                return
            msg = "📋 **Ваши чаты:**\n\n"
            for chat_id, title in chats:
                msg += f"• {title}\n  `{chat_id}`\n\n"
            await event.reply(msg, buttons=get_main_menu(user_id))
        
        # Остановить
        elif text == "⏹️ Остановить":
            await event.reply("ℹ️ Для остановки рассылки перезапустите бота.", buttons=get_main_menu(user_id))
        
        # Отмена
        elif text == "❌ Отмена":
            if user_id in auth_states:
                del auth_states[user_id]
            await event.reply("❌ Отменено", buttons=get_main_menu(user_id))
        
        # Добавить пользователя (админ)
        elif text == "👥 Добавить пользователя" and is_user_admin(user_id):
            auth_states[user_id] = {'step': 'awaiting_new_user_id'}
            await event.reply(
                "➕ **Добавление пользователя**\n\n"
                "Введите Telegram ID пользователя.\n\n"
                "Отправьте /cancel для отмены.",
                buttons=[[Button.text("❌ Отмена")]]
            )
        
        # Общая статистика (админ)
        elif text == "📊 Общая статистика" and is_user_admin(user_id):
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            users_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM telegram_sessions')
            sessions_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM user_chats')
            chats_count = cursor.fetchone()[0]
            await event.reply(
                f"📊 **Общая статистика:**\n\n"
                f"👥 Пользователей: {users_count}\n"
                f"📁 Сессий: {sessions_count}\n"
                f"📋 Чатов в базах: {chats_count}",
                buttons=get_main_menu(user_id)
            )
        
        # Кнопки "Да" и "Нет" после сохранения чатов
        elif text == "✅ Да, запустить рассылку":
            chat_ids = load_user_chats(user_id)
            if chat_ids:
                await send_broadcast(user_id, chat_ids, event)
            else:
                await event.reply("❌ Нет чатов", buttons=get_main_menu(user_id))
        
        elif text == "❌ Нет, позже":
            await event.reply("✅ База сохранена", buttons=get_main_menu(user_id))
        
        # ========== ОБРАБОТКА СОСТОЯНИЙ (ввод номера, кода, ссылок) ==========
        elif user_id in auth_states:
            state = auth_states[user_id]
            
            # Ожидание номера телефона
            if state['step'] == 'awaiting_phone' and text.startswith('+'):
                phone = text
                state['phone'] = phone
                state['step'] = 'awaiting_code'
                temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
                await temp_client.connect()
                state['temp_client'] = temp_client
                try:
                    result = await temp_client.send_code_request(phone)
                    state['phone_code_hash'] = result.phone_code_hash
                    await event.reply("🔑 **Введите код из Telegram**", buttons=[[Button.text("❌ Отмена")]])
                except Exception as e:
                    await event.reply(f"❌ {e}", buttons=get_main_menu(user_id))
                    del auth_states[user_id]
            
            # Ожидание кода
            elif state['step'] == 'awaiting_code' and text.isdigit() and len(text) == 5:
                code = text
                temp_client = state['temp_client']
                try:
                    await temp_client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['phone_code_hash'])
                    me = await temp_client.get_me()
                    session_string = temp_client.session.save()
                    save_user_session(user_id, session_string, state['phone'], me.first_name)
                    user_clients[user_id] = temp_client
                    await event.reply(f"✅ **Авторизован:** {me.first_name}", buttons=get_main_menu(user_id))
                    del auth_states[user_id]
                except Exception as e:
                    await event.reply(f"❌ {e}", buttons=get_main_menu(user_id))
                    del auth_states[user_id]
            
            # Ожидание списка ссылок
            elif state['step'] == 'awaiting_chat_links' and text != "❌ Отмена":
                links = [l.strip() for l in text.split('\n') if l.strip()]
                if not links:
                    await event.reply("❌ Пустой список", buttons=[[Button.text("❌ Отмена")]])
                    return
                await event.reply(f"🔄 Обрабатываю {len(links)} ссылок...")
                client = await get_user_client(user_id)
                if not client:
                    await event.reply("❌ Аккаунт не авторизован", buttons=get_main_menu(user_id))
                    del auth_states[user_id]
                    return
                results, dups = await convert_links_to_ids(links, client)
                success_results = [r for r in results if r['success']]
                fail_results = [r for r in results if not r['success']]
                if success_results:
                    chats_to_save = [(r['id'], r['title']) for r in success_results]
                    save_user_chats(user_id, chats_to_save)
                    msg = f"✅ Сохранено {len(success_results)} чатов"
                    if dups:
                        msg += f"\n⚠️ Дублей: {len(dups)}"
                    if fail_results:
                        msg += f"\n❌ Ошибок: {len(fail_results)}"
                    msg += "\n\n🚀 Запустить рассылку?"
                    del auth_states[user_id]
                    await event.reply(msg, buttons=[[Button.text("✅ Да, запустить рассылку"), Button.text("❌ Нет, позже")]])
                else:
                    await event.reply("❌ Не удалось обработать ссылки", buttons=get_main_menu(user_id))
                    del auth_states[user_id]
            
            # Ожидание нового текста
            elif state['step'] == 'awaiting_new_text' and text != "❌ Отмена":
                user_message_texts[user_id] = text
                await event.reply(f"✅ Текст изменён", buttons=get_main_menu(user_id))
                del auth_states[user_id]
            
            # Ожидание ID нового пользователя
            elif state['step'] == 'awaiting_new_user_id' and text != "❌ Отмена":
                try:
                    new_user_id = int(text)
                    register_user(new_user_id)
                    await event.reply(f"✅ **Пользователь {new_user_id} добавлен!**", buttons=get_main_menu(user_id))
                except ValueError:
                    await event.reply(f"❌ Неверный формат ID.", buttons=get_main_menu(user_id))
                del auth_states[user_id]
    
    # Запускаем бота
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
