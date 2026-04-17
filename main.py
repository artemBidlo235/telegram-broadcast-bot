import asyncio
import os
import glob
import signal
import sys
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.custom import Button

# ========== ВАШИ ДАННЫЕ ==========
API_ID = 36594021
API_HASH = '6dfedd148bf6bba5d4e67ed213178ebb'
BOT_TOKEN = '8297380746:AAHChWZNlbT-_pc70Nr3zUydC6BebI-ao9Q'
ADMIN_ID = 1031953955

# Настройки рассылки
MESSAGE_TEXT = "qwerty"
DELAY_BETWEEN_MESSAGES = 5

# Папка для хранения сессий
SESSIONS_DIR = "sessions"
ACTIVE_SESSION_FILE = os.path.join(SESSIONS_DIR, "active_session.txt")
# ==================================

os.makedirs(SESSIONS_DIR, exist_ok=True)

user_client = None
is_broadcasting = False
target_chat_ids = []
auth_states = {}


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
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def load_active_session():
    try:
        with open(ACTIVE_SESSION_FILE, 'r', encoding='utf-8') as f:
            session_name = f.read().strip()
            session_path = os.path.join(SESSIONS_DIR, session_name)
            if session_name and os.path.exists(session_path):
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
        except:
            pass


async def switch_to_session(session_name, event=None):
    global user_client
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
            return True, msg
        else:
            await new_client.disconnect()
            msg = f"❌ Сессия {session_name} не авторизована"
            if event:
                await event.reply(msg)
            return False, msg
    except Exception as e:
        msg = f"❌ Ошибка: {e}"
        if event:
            await event.reply(msg)
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


async def send_broadcast(chat_ids, event):
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


async def main():
    global user_client, MESSAGE_TEXT
    
    bot_client = await TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен")
    
    main_menu_buttons = [
        [Button.text("📋 Запустить рассылку")],
        [Button.text("🔄 Поменять базу чатов")],
        [Button.text("📝 Сменить текст"), Button.text("⏹️ Остановить")],
        [Button.text("📊 Статус"), Button.text("🔑 Логин")],
        [Button.text("📁 Управление сессиями")]
    ]
    
    last_session = load_active_session()
    if last_session:
        await switch_to_session(last_session)
    
    # ЕДИНЫЙ ОБРАБОТЧИК (без дублей)
    @bot_client.on(events.NewMessage(from_users=ADMIN_ID))
    async def unified_handler(event):
        global target_chat_ids, is_broadcasting, MESSAGE_TEXT, user_client
        text = event.raw_text
        
        # Основное меню
        if text == "📋 Запустить рассылку":
            if not user_client or not user_client.is_connected():
                await event.reply("❌ Авторизуйтесь: 🔑 Логин", buttons=main_menu_buttons)
                return
            chat_ids = load_chat_ids_from_file()
            if not chat_ids:
                await event.reply("❌ Нет чатов", buttons=main_menu_buttons)
                return
            await send_broadcast(chat_ids, event)
        
        elif text == "🔄 Поменять базу чатов":
            if not user_client or not user_client.is_connected():
                await event.reply("❌ Сначала авторизуйтесь", buttons=main_menu_buttons)
                return
            auth_states[ADMIN_ID] = {'step': 'awaiting_chat_links'}
            await event.reply("📋 Отправьте список ссылок (по одной на строку)", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📝 Сменить текст":
            auth_states[ADMIN_ID] = {'step': 'awaiting_new_text'}
            await event.reply(f"📝 Текущий текст:\n{MESSAGE_TEXT}\n\nОтправьте новый текст", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "⏹️ Остановить":
            if is_broadcasting:
                is_broadcasting = False
                await event.reply("⏸️ Остановлено", buttons=main_menu_buttons)
            else:
                await event.reply("ℹ️ Рассылка не активна", buttons=main_menu_buttons)
        
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
            await event.reply(f"👤 {acc}\n📁 {get_current_session_name() or 'Нет'}\n📝 {MESSAGE_TEXT[:50]}\n📋 {len(chat_ids)} чатов", buttons=main_menu_buttons)
        
        elif text == "🔑 Логин":
            auth_states[ADMIN_ID] = {'step': 'awaiting_phone'}
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
        
        elif text == "◀️ Назад":
            await event.reply("🔙 Главное меню", buttons=main_menu_buttons)
        
        elif text.startswith("🔑 "):
            session_name = text[2:]
            success, msg = await switch_to_session(session_name, event)
            if success:
                await event.reply("🔙 Возврат в главное меню", buttons=main_menu_buttons)
        
        elif text.startswith("🗑️ "):
            session_name = text[2:]
            await delete_session(session_name, event)
        
        elif text == "❌ Отмена":
            if ADMIN_ID in auth_states:
                del auth_states[ADMIN_ID]
            await event.reply("❌ Отменено", buttons=main_menu_buttons)
        
        elif text == "✅ Да":
            chat_ids = load_chat_ids_from_file()
            if chat_ids:
                await send_broadcast(chat_ids, event)
            else:
                await event.reply("❌ Нет чатов", buttons=main_menu_buttons)
        
        elif text == "❌ Нет":
            await event.reply("✅ База сохранена", buttons=main_menu_buttons)
        
        elif ADMIN_ID in auth_states:
            state = auth_states[ADMIN_ID]
            
            if state['step'] == 'awaiting_phone' and text.startswith('+'):
                phone = text
                state['phone'] = phone
                state['step'] = 'awaiting_code'
                temp_path = os.path.join(SESSIONS_DIR, f'temp_{ADMIN_ID}')
                temp = TelegramClient(temp_path, API_ID, API_HASH)
                await temp.connect()
                state['temp'] = temp
                try:
                    result = await temp.send_code_request(phone)
                    state['hash'] = result.phone_code_hash
                    await event.reply("🔑 Введите код из Telegram", buttons=[[Button.text("❌ Отмена")]])
                except Exception as e:
                    await event.reply(f"❌ {e}", buttons=main_menu_buttons)
                    del auth_states[ADMIN_ID]
            
            elif state['step'] == 'awaiting_code' and text.isdigit() and len(text) == 5:
                code = text
                temp = state['temp']
                try:
                    await temp.sign_in(phone=state['phone'], code=code, phone_code_hash=state['hash'])
                    user_client = temp
                    me = await user_client.get_me()
                    session_name = f"{me.first_name}_{state['phone'][-5:]}.session"
                    session_path = os.path.join(SESSIONS_DIR, session_name)
                    temp_path = os.path.join(SESSIONS_DIR, f'temp_{ADMIN_ID}.session')
                    if os.path.exists(session_path):
                        await user_client.disconnect()
                        os.remove(temp_path)
                        await switch_to_session(session_name)
                        await event.reply(f"✅ Вход выполнен: {me.first_name}", buttons=main_menu_buttons)
                    else:
                        await user_client.disconnect()
                        await asyncio.sleep(0.5)
                        os.rename(temp_path, session_path)
                        await switch_to_session(session_name)
                        await event.reply(f"✅ Авторизован: {me.first_name}", buttons=main_menu_buttons)
                    del auth_states[ADMIN_ID]
                except Exception as e:
                    await event.reply(f"❌ Ошибка: {e}", buttons=main_menu_buttons)
                    del auth_states[ADMIN_ID]
            
            elif state['step'] == 'awaiting_chat_links' and text != "❌ Отмена":
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
                    del auth_states[ADMIN_ID]
                    await event.reply(msg, buttons=[[Button.text("✅ Да"), Button.text("❌ Нет")]])
                else:
                    await event.reply("❌ Не удалось обработать ссылки", buttons=main_menu_buttons)
                    del auth_states[ADMIN_ID]
            
            elif state['step'] == 'awaiting_new_text' and text != "❌ Отмена":
                MESSAGE_TEXT = text
                await event.reply(f"✅ Текст изменён", buttons=main_menu_buttons)
                del auth_states[ADMIN_ID]
    
    await bot_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
