                        await event.reply(f"✅ Авторизован: {me.first_name}", buttons=get_accounts_menu())
                    del auth_states[user_id]
                except Exception as e:
                    await event.reply(f"❌ Ошибка: {e}", buttons=get_accounts_menu())
                    del auth_states[user_id]
                return
            
            # Смена текста
            elif state.get('step') == 'awaiting_new_text' and text != "❌ Отмена":
                MESSAGE_TEXT = text
                await event.reply(f"✅ Текст изменён!\n\nНовый текст:\n{MESSAGE_TEXT}", buttons=get_settings_menu())
                del auth_states[user_id]
                return
            
            # Отмена
            elif text == "❌ Отмена":
                del auth_states[user_id]
                await event.reply("❌ Действие отменено", buttons=get_main_menu(user_id))
                return
        
        # ========== ОСНОВНОЕ МЕНЮ ==========
        
        # Главное меню
        if text == "⚙️ Настройки софта":
            await delete_previous_messages(event, 2)
            await event.reply("⚙️ **Настройки софта**\n\nВыберите раздел:", buttons=get_settings_menu())
        
        elif text == "📢 Рассылка":
            await delete_previous_messages(event, 2)
            await event.reply("📢 **Управление рассылкой**\n\nВыберите действие:", buttons=get_broadcast_menu())
        
        elif text == "👑 Admin панель":
            if not is_owner(user_id):
                await event.reply("❌ У вас нет доступа к admin панели!\nЭтот раздел доступен только владельцу бота.", buttons=get_main_menu(user_id))
                return
            await delete_previous_messages(event, 2)
            await event.reply("👑 **Admin панель**\n\nДобро пожаловать, Владелец!", buttons=get_admin_menu())
        
        elif text == "🔒 Admin панель":
            await event.reply("❌ У вас нет доступа к admin панели!\nЭтот раздел доступен только владельцу бота.", buttons=get_main_menu(user_id))
        
        # ========== НАСТРОЙКИ СОФТА ==========
        
        elif text == "📚 Настройка базы чатов":
            await delete_previous_messages(event, 2)
            await event.reply(f"📚 **Настройка базы чатов**\n\nАктивная база: {selected_chat_base}\nЧатов в базе: {len(target_chat_ids)}\n\nВыберите действие:", buttons=get_chat_base_menu())
        
        elif text == "✏️ Редактирование текста":
            await delete_previous_messages(event, 2)
            await event.reply(f"✏️ **Редактирование текста рассылки**\n\nТекущий текст:\n{MESSAGE_TEXT}\n\nОтправьте новый текст:", buttons=[[Button.text("❌ Отмена")]])
            auth_states[user_id] = {'step': 'awaiting_new_text'}
        
        elif text == "👤 Управление аккаунтами":
            await delete_previous_messages(event, 2)
            await event.reply("👤 **Управление аккаунтами**\n\nВыберите действие:", buttons=get_accounts_menu())
        
        # ========== УПРАВЛЕНИЕ АККАУНТАМИ ==========
        
        elif text == "🔑 Авторизация":
            await delete_previous_messages(event, 2)
            auth_states[user_id] = {'step': 'awaiting_phone'}
            await event.reply("📱 **Авторизация аккаунта**\n\nВведите номер телефона (пример: +79991234567):", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📁 Управление сессиями":
            await delete_previous_messages(event, 2)
            sessions = get_session_files()
            current = get_current_session_name()
            buttons = []
            for s in sessions:
                if s == current:
                    buttons.append([Button.text(f"✅ {s} (активна)")])
                else:
                    buttons.append([Button.text(f"🔑 {s}"), Button.text(f"🗑️ {s}")])
            if not sessions:
                await event.reply("📁 **Управление сессиями**\n\nСессии не найдены", buttons=[[Button.text("◀️ Назад")]])
                return
            buttons.append([Button.text("◀️ Назад")])
            await event.reply(f"📁 **Управление сессиями**\n\nТекущая: {current or 'Нет'}\nВсего: {len(sessions)}", buttons=buttons)
        
        # ========== РАБОТА С БАЗАМИ ЧАТОВ ==========
        
        elif text == "📋 Выбрать":
            await delete_previous_messages(event, 2)
            bases = get_all_chat_bases()
            if not bases:
                await event.reply("❌ Нет доступных баз чатов. Создайте новую.", buttons=get_chat_base_menu())
                return
            buttons = []
            for base in bases:
                buttons.append([Button.text(f"📁 {base}")])
            buttons.append([Button.text("◀️ Назад")])
            await event.reply("📋 **Выбор базы чатов**\n\nВыберите базу:", buttons=buttons)
        
        elif text.startswith("📁 "):
            base_name = text[2:]
            auth_states[user_id] = {'step': 'confirm_base_selection', 'base_name': base_name}
            buttons = [
                [Button.text("✅ Подтвердить")],
                [Button.text("👁️ Просмотреть список")],
                [Button.text("◀️ Назад")]
            ]
            await event.reply(f"📁 **База: {base_name}**\n\nВыберите действие:", buttons=buttons)
        
        elif text == "✅ Подтвердить" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection':
            base_name = auth_states[user_id]['base_name']
            success, msg = set_active_chat_base(base_name)
            await event.reply(msg, buttons=get_chat_base_menu())
            del auth_states[user_id]
        
        elif text == "👁️ Просмотреть список" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                buttons = [
                    [Button.text("📊 По ID")],
                    [Button.text("🔗 По ссылкам")],
                    [Button.text("◀️ Назад")]
                ]
                auth_states[user_id]['view_step'] = 'choose_format'
                await event.reply(f"👁️ **Просмотр базы '{base_name}'**\n\nВыберите формат отображения:", buttons=buttons)
            else:
                await event.reply("❌ База не найдена", buttons=get_chat_base_menu())
                del auth_states[user_id]
        
        elif text == "📊 По ID" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection' and auth_states[user_id].get('view_step') == 'choose_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                chats = base_data.get("chats", [])
                if chats:
                    chat_list = "📊 **Чаты по ID:**\n\n" + "\n".join([f"`{chat}`" for chat in chats[:50]])
                    if len(chats) > 50:
                        chat_list += f"\n\n... и ещё {len(chats) - 50} чатов"
                    await event.reply(chat_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_chat_base_menu())
                del auth_states[user_id]
        
        elif text == "🔗 По ссылкам" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection' and auth_states[user_id].get('view_step') == 'choose_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                links = base_data.get("links", [])
                if links:
                    link_list = "🔗 **Чаты по ссылкам:**\n\n" + "\n".join([link for link in links[:50]])
                    if len(links) > 50:
                        link_list += f"\n\n... и ещё {len(links) - 50} чатов"
                    await event.reply(link_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_chat_base_menu())
                del auth_states[user_id]
        
        elif text == "✏️ Редактировать":
            await delete_previous_messages(event, 2)
            bases = get_all_chat_bases()
            if not bases:
                await event.reply("❌ Нет доступных баз чатов.", buttons=get_chat_base_menu())
                return
            buttons = []
            for base in bases:
                buttons.append([Button.text(f"✏️ {base}")])
            buttons.append([Button.text("◀️ Назад")])
            await event.reply("✏️ **Редактирование базы чатов**\n\nВыберите базу для редактирования:", buttons=buttons)
        
        elif text.startswith("✏️ "):
            base_name = text[2:]
            auth_states[user_id] = {'step': 'editing_base', 'base_name': base_name}
            await event.reply(f"✏️ **Редактирование базы '{base_name}'**\n\nВыберите действие:", buttons=get_edit_base_menu())
        
        elif text == "👁️ Просмотреть список" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                buttons = [
                    [Button.text("📊 По ID")],
                    [Button.text("🔗 По ссылкам")],
                    [Button.text("◀️ Назад")]
                ]
                auth_states[user_id]['view_step'] = 'edit_format'
                await event.reply(f"👁️ **Просмотр базы '{base_name}'**\n\nВыберите формат отображения:", buttons=buttons)
            else:
                await event.reply("❌ База не найдена", buttons=get_edit_base_menu())
                del auth_states[user_id]
        
        elif text == "📊 По ID" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base' and auth_states[user_id].get('view_step') == 'edit_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                chats = base_data.get("chats", [])
                if chats:
                    chat_list = "📊 **Чаты по ID:**\n\n" + "\n".join([f"`{chat}`" for chat in chats[:50]])
                    if len(chats) > 50:
                        chat_list += f"\n\n... и ещё {len(chats) - 50} чатов"
                    await event.reply(chat_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_edit_base_menu())
                del auth_states[user_id]
        
        elif text == "🔗 По ссылкам" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base' and auth_states[user_id].get('view_step') == 'edit_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                links = base_data.get("links", [])
                if links:
                    link_list = "🔗 **Чаты по ссылкам:**\n\n" + "\n".join([link for link in links[:50]])
                    if len(links) > 50:
                        link_list += f"\n\n... и ещё {len(links) - 50} чатов"
                    await event.reply(link_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_edit_base_menu())
                del auth_states[user_id]
        
        elif text == "➕ Добавить ссылки" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base':
            base_name = auth_states[user_id]['base_name']
            auth_states[user_id]['step'] = 'adding_links_to_base'
            await event.reply(f"➕ **Добавление ссылок в базу '{base_name}'**\n\nОтправьте список ссылок (по одной на строку):\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "🔄 Перезаписать" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base':
            base_name = auth_states[user_id]['base_name']
            auth_states[user_id]['step'] = 'overwrite_base'
            await event.reply(f"🔄 **Перезапись базы '{base_name}'**\n\n⚠️ ВНИМАНИЕ! Текущий список будет полностью заменён!\n\nОтправьте новый список ссылок (по одной на строку):\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "➕ Создать":
            await delete_previous_messages(event, 2)
            auth_states[user_id] = {'step': 'creating_base'}
            await event.reply("➕ **Создание новой базы чатов**\n\nВведите название для новой базы:", buttons=[[Button.text("❌ Отмена")]])
        
        # ========== РАССЫЛКА ==========
        
        elif text == "▶️ Запуск":
            if not user_client or not user_client.is_connected():
                await event.reply("❌ Аккаунт не авторизован! Сначала авторизуйтесь в разделе 'Управление аккаунтами'", buttons=get_broadcast_menu())
                return
            chat_ids = load_chat_ids_from_file()
            if not chat_ids:
                await event.reply("❌ Нет чатов для рассылки. Сначала настройте базу чатов.", buttons=get_broadcast_menu())
                return
            await send_broadcast_to_chats(chat_ids, event)
        
        elif text == "⏹️ Стоп":
            if is_broadcasting:
                is_broadcasting = False
                await event.reply("⏸️ Рассылка остановлена", buttons=get_broadcast_menu())
            else:
                await event.reply("ℹ️ Рассылка не активна", buttons=get_broadcast_menu())
        
        elif text == "📊 Статус":
            if user_client and user_client.is_connected():
                try:
                    me = await user_client.get_me()
                    acc = f"✅ {me.first_name}"
                except:
                    acc = "❌ Ошибка"
            else:
                acc = "❌ Не авторизован"
            await event.reply(f"📊 **Статус рассылки**\n\n👤 Аккаунт: {acc}\n📁 Активная база: {selected_chat_base}\n📋 Чатов в базе: {len(target_chat_ids)}\n📝 Текст: {MESSAGE_TEXT[:50]}\n{'🔄 РАССЫЛКА АКТИВНА' if is_broadcasting else '⏸️ Рассылка не активна'}", buttons=get_broadcast_menu())
        
        # ========== ADMIN ПАНЕЛЬ ==========
        
        elif text == "👑 Управление админами":
            if not is_owner(user_id):
                await event.reply("❌ Только владелец может управлять администраторами!", buttons=get_admin_menu())
                return
            
            admins = get_admins_list()
            admin_list = "👑 **Список администраторов:**\n\n"
            for a in admins:
                admin_list += f"🆔 `{a['id']}` - {a['role']}\n"
                if a.get('username'):
                    admin_list += f"📝 @{a['username']}\n"
                admin_list += f"📅 Добавлен: {a['added_at'][:10]}\n\n"
            
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
            await event.reply("👑 **Добавление администратора**\n\nВведите ID пользователя:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "➖ Удалить админа":
            if not is_owner(user_id):
                return
            auth_states[user_id] = {'step': 'removing_admin'}
            await event.reply("👑 **Удаление администратора**\n\nВведите ID администратора для удаления:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "👥 Пользователи":
            users = load_users()
            if not users:
                await event.reply("📭 Нет зарегистрированных пользователей", buttons=get_admin_menu())
                return
            user_list = "👥 **Список пользователей:**\n\n"
            for uid, data in list(users.items())[:30]:
                user_list += f"🆔 ID: `{uid}`\n👤 {data.get('first_name', '?')}\n"
                if data.get('username'):
                    user_list += f"📝 @{data['username']}\n"
                user_list += f"📅 Зарегистрирован: {data.get('joined_at', '?')[:10]}\n\n"
            if len(users) > 30:
                user_list += f"\n... и ещё {len(users) - 30} пользователей"
            await event.reply(user_list, buttons=get_admin_menu())
        
        elif text == "📈 Статистика бота":
            stats = get_stats()
            users_count = len(load_users())
            admins_count = len(load_admins())
            bases_count = len(get_all_chat_bases())
            await event.reply(f"""
📊 **СТАТИСТИКА БОТА**

👥 Пользователей: {users_count}
👑 Администраторов: {admins_count}
📚 Баз чатов: {bases_count}
📨 Сообщений отправлено: {stats.get('messages_sent', 0)}
📢 Всего рассылок: {stats.get('broadcasts', 0)}

📁 Активная сессия: {get_current_session_name() or 'Нет'}
📋 Активная база: {selected_chat_base}
💬 Текст рассылки: {MESSAGE_TEXT[:30]}...

✅ Бот работает стабильно
""", buttons=get_admin_menu())
        
        elif text == "📢 Рассылка пользователям":
            users = load_users()
            if not users:
                await event.reply("❌ Нет зарегистрированных пользователей", buttons=get_admin_menu())
                return
            auth_states[user_id] = {'step': 'broadcast_to_users'}
            await event.reply(f"📢 **Рассылка пользователям**\n\nВсего пользователей: {len(users)}\n\nОтправьте сообщение для рассылки:", buttons=[[Button.text("❌ Отмена")]])
        
        # ========== ОБРАБОТКА СЕССИЙ ==========
        
        elif text.startswith("🔑 ") and not text.startswith("🔑 Авторизация"):
            session_name = text
                                await event.reply(f"✅ Авторизован: {me.first_name}", buttons=get_accounts_menu())
                    del auth_states[user_id]
                except Exception as e:
                    await event.reply(f"❌ Ошибка: {e}", buttons=get_accounts_menu())
                    del auth_states[user_id]
                return
            
            # Смена текста
            elif state.get('step') == 'awaiting_new_text' and text != "❌ Отмена":
                MESSAGE_TEXT = text
                await event.reply(f"✅ Текст изменён!\n\nНовый текст:\n{MESSAGE_TEXT}", buttons=get_settings_menu())
                del auth_states[user_id]
                return
            
            # Отмена
            elif text == "❌ Отмена":
                del auth_states[user_id]
                await event.reply("❌ Действие отменено", buttons=get_main_menu(user_id))
                return
        
        # ========== ОСНОВНОЕ МЕНЮ ==========
        
        # Главное меню
        if text == "⚙️ Настройки софта":
            await delete_previous_messages(event, 2)
            await event.reply("⚙️ **Настройки софта**\n\nВыберите раздел:", buttons=get_settings_menu())
        
        elif text == "📢 Рассылка":
            await delete_previous_messages(event, 2)
            await event.reply("📢 **Управление рассылкой**\n\nВыберите действие:", buttons=get_broadcast_menu())
        
        elif text == "👑 Admin панель":
            if not is_owner(user_id):
                await event.reply("❌ У вас нет доступа к admin панели!\nЭтот раздел доступен только владельцу бота.", buttons=get_main_menu(user_id))
                return
            await delete_previous_messages(event, 2)
            await event.reply("👑 **Admin панель**\n\nДобро пожаловать, Владелец!", buttons=get_admin_menu())
        
        elif text == "🔒 Admin панель":
            await event.reply("❌ У вас нет доступа к admin панели!\nЭтот раздел доступен только владельцу бота.", buttons=get_main_menu(user_id))
        
        # ========== НАСТРОЙКИ СОФТА ==========
        
        elif text == "📚 Настройка базы чатов":
            await delete_previous_messages(event, 2)
            await event.reply(f"📚 **Настройка базы чатов**\n\nАктивная база: {selected_chat_base}\nЧатов в базе: {len(target_chat_ids)}\n\nВыберите действие:", buttons=get_chat_base_menu())
        
        elif text == "✏️ Редактирование текста":
            await delete_previous_messages(event, 2)
            await event.reply(f"✏️ **Редактирование текста рассылки**\n\nТекущий текст:\n{MESSAGE_TEXT}\n\nОтправьте новый текст:", buttons=[[Button.text("❌ Отмена")]])
            auth_states[user_id] = {'step': 'awaiting_new_text'}
        
        elif text == "👤 Управление аккаунтами":
            await delete_previous_messages(event, 2)
            await event.reply("👤 **Управление аккаунтами**\n\nВыберите действие:", buttons=get_accounts_menu())
        
        # ========== УПРАВЛЕНИЕ АККАУНТАМИ ==========
        
        elif text == "🔑 Авторизация":
            await delete_previous_messages(event, 2)
            auth_states[user_id] = {'step': 'awaiting_phone'}
            await event.reply("📱 **Авторизация аккаунта**\n\nВведите номер телефона (пример: +79991234567):", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "📁 Управление сессиями":
            await delete_previous_messages(event, 2)
            sessions = get_session_files()
            current = get_current_session_name()
            buttons = []
            for s in sessions:
                if s == current:
                    buttons.append([Button.text(f"✅ {s} (активна)")])
                else:
                    buttons.append([Button.text(f"🔑 {s}"), Button.text(f"🗑️ {s}")])
            if not sessions:
                await event.reply("📁 **Управление сессиями**\n\nСессии не найдены", buttons=[[Button.text("◀️ Назад")]])
                return
            buttons.append([Button.text("◀️ Назад")])
            await event.reply(f"📁 **Управление сессиями**\n\nТекущая: {current or 'Нет'}\nВсего: {len(sessions)}", buttons=buttons)
        
        # ========== РАБОТА С БАЗАМИ ЧАТОВ ==========
        
        elif text == "📋 Выбрать":
            await delete_previous_messages(event, 2)
            bases = get_all_chat_bases()
            if not bases:
                await event.reply("❌ Нет доступных баз чатов. Создайте новую.", buttons=get_chat_base_menu())
                return
            buttons = []
            for base in bases:
                buttons.append([Button.text(f"📁 {base}")])
            buttons.append([Button.text("◀️ Назад")])
            await event.reply("📋 **Выбор базы чатов**\n\nВыберите базу:", buttons=buttons)
        
        elif text.startswith("📁 "):
            base_name = text[2:]
            auth_states[user_id] = {'step': 'confirm_base_selection', 'base_name': base_name}
            buttons = [
                [Button.text("✅ Подтвердить")],
                [Button.text("👁️ Просмотреть список")],
                [Button.text("◀️ Назад")]
            ]
            await event.reply(f"📁 **База: {base_name}**\n\nВыберите действие:", buttons=buttons)
        
        elif text == "✅ Подтвердить" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection':
            base_name = auth_states[user_id]['base_name']
            success, msg = set_active_chat_base(base_name)
            await event.reply(msg, buttons=get_chat_base_menu())
            del auth_states[user_id]
        
        elif text == "👁️ Просмотреть список" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                buttons = [
                    [Button.text("📊 По ID")],
                    [Button.text("🔗 По ссылкам")],
                    [Button.text("◀️ Назад")]
                ]
                auth_states[user_id]['view_step'] = 'choose_format'
                await event.reply(f"👁️ **Просмотр базы '{base_name}'**\n\nВыберите формат отображения:", buttons=buttons)
            else:
                await event.reply("❌ База не найдена", buttons=get_chat_base_menu())
                del auth_states[user_id]
        
        elif text == "📊 По ID" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection' and auth_states[user_id].get('view_step') == 'choose_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                chats = base_data.get("chats", [])
                if chats:
                    chat_list = "📊 **Чаты по ID:**\n\n" + "\n".join([f"`{chat}`" for chat in chats[:50]])
                    if len(chats) > 50:
                        chat_list += f"\n\n... и ещё {len(chats) - 50} чатов"
                    await event.reply(chat_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_chat_base_menu())
                del auth_states[user_id]
        
        elif text == "🔗 По ссылкам" and user_id in auth_states and auth_states[user_id].get('step') == 'confirm_base_selection' and auth_states[user_id].get('view_step') == 'choose_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                links = base_data.get("links", [])
                if links:
                    link_list = "🔗 **Чаты по ссылкам:**\n\n" + "\n".join([link for link in links[:50]])
                    if len(links) > 50:
                        link_list += f"\n\n... и ещё {len(links) - 50} чатов"
                    await event.reply(link_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_chat_base_menu())
                del auth_states[user_id]
        
        elif text == "✏️ Редактировать" and not text == "✏️ Редактирование текста":
            await delete_previous_messages(event, 2)
            bases = get_all_chat_bases()
            if not bases:
                await event.reply("❌ Нет доступных баз частов.", buttons=get_chat_base_menu())
                return
            buttons = []
            for base in bases:
                buttons.append([Button.text(f"✏️ {base}")])
            buttons.append([Button.text("◀️ Назад")])
            await event.reply("✏️ **Редактирование базы чатов**\n\nВыберите базу для редактирования:", buttons=buttons)
        
        elif text.startswith("✏️ ") and text != "✏️ Редактирование текста":
            base_name = text[2:]
            auth_states[user_id] = {'step': 'editing_base', 'base_name': base_name}
            await event.reply(f"✏️ **Редактирование базы '{base_name}'**\n\nВыберите действие:", buttons=get_edit_base_menu())
        
        elif text == "👁️ Просмотреть список" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                buttons = [
                    [Button.text("📊 По ID")],
                    [Button.text("🔗 По ссылкам")],
                    [Button.text("◀️ Назад")]
                ]
                auth_states[user_id]['view_step'] = 'edit_format'
                await event.reply(f"👁️ **Просмотр базы '{base_name}'**\n\nВыберите формат отображения:", buttons=buttons)
            else:
                await event.reply("❌ База не найдена", buttons=get_edit_base_menu())
                del auth_states[user_id]
        
        elif text == "📊 По ID" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base' and auth_states[user_id].get('view_step') == 'edit_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                chats = base_data.get("chats", [])
                if chats:
                    chat_list = "📊 **Чаты по ID:**\n\n" + "\n".join([f"`{chat}`" for chat in chats[:50]])
                    if len(chats) > 50:
                        chat_list += f"\n\n... и ещё {len(chats) - 50} чатов"
                    await event.reply(chat_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_edit_base_menu())
                del auth_states[user_id]
        
        elif text == "🔗 По ссылкам" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base' and auth_states[user_id].get('view_step') == 'edit_format':
            base_name = auth_states[user_id]['base_name']
            base_data = load_chat_base(base_name)
            if base_data:
                links = base_data.get("links", [])
                if links:
                    link_list = "🔗 **Чаты по ссылкам:**\n\n" + "\n".join([link for link in links[:50]])
                    if len(links) > 50:
                        link_list += f"\n\n... и ещё {len(links) - 50} чатов"
                    await event.reply(link_list, buttons=[[Button.text("◀️ Назад")]])
                else:
                    await event.reply("📭 База пуста", buttons=[[Button.text("◀️ Назад")]])
            else:
                await event.reply("❌ База не найдена", buttons=get_edit_base_menu())
                del auth_states[user_id]
        
        elif text == "➕ Добавить ссылки" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base':
            base_name = auth_states[user_id]['base_name']
            auth_states[user_id]['step'] = 'adding_links_to_base'
            await event.reply(f"➕ **Добавление ссылок в базу '{base_name}'**\n\nОтправьте список ссылок (по одной на строку):\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "🔄 Перезаписать" and user_id in auth_states and auth_states[user_id].get('step') == 'editing_base':
            base_name = auth_states[user_id]['base_name']
            auth_states[user_id]['step'] = 'overwrite_base'
            await event.reply(f"🔄 **Перезапись базы '{base_name}'**\n\n⚠️ ВНИМАНИЕ! Текущий список будет полностью заменён!\n\nОтправьте новый список ссылок (по одной на строку):\n\nПример:\n@chat1\nhttps://t.me/chat2", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "➕ Создать":
            await delete_previous_messages(event, 2)
            auth_states[user_id] = {'step': 'creating_base'}
            await event.reply("➕ **Создание новой базы чатов**\n\nВведите название для новой базы:", buttons=[[Button.text("❌ Отмена")]])
        
        # ========== РАССЫЛКА ==========
        
        elif text == "▶️ Запуск":
            if not user_client or not user_client.is_connected():
                await event.reply("❌ Аккаунт не авторизован! Сначала авторизуйтесь в разделе 'Управление аккаунтами'", buttons=get_broadcast_menu())
                return
            chat_ids = load_chat_ids_from_file()
            if not chat_ids:
                await event.reply("❌ Нет чатов для рассылки. Сначала настройте базу чатов.", buttons=get_broadcast_menu())
                return
            await send_broadcast_to_chats(chat_ids, event)
        
        elif text == "⏹️ Стоп":
            if is_broadcasting:
                is_broadcasting = False
                await event.reply("⏸️ Рассылка остановлена", buttons=get_broadcast_menu())
            else:
                await event.reply("ℹ️ Рассылка не активна", buttons=get_broadcast_menu())
        
        elif text == "📊 Статус":
            if user_client and user_client.is_connected():
                try:
                    me = await user_client.get_me()
                    acc = f"✅ {me.first_name}"
                except:
                    acc = "❌ Ошибка"
            else:
                acc = "❌ Не авторизован"
            await event.reply(f"📊 **Статус рассылки**\n\n👤 Аккаунт: {acc}\n📁 Активная база: {selected_chat_base}\n📋 Чатов в базе: {len(target_chat_ids)}\n📝 Текст: {MESSAGE_TEXT[:50]}\n{'🔄 РАССЫЛКА АКТИВНА' if is_broadcasting else '⏸️ Рассылка не активна'}", buttons=get_broadcast_menu())
        
        # ========== ADMIN ПАНЕЛЬ ==========
        
        elif text == "👑 Управление админами":
            if not is_owner(user_id):
                await event.reply("❌ Только владелец может управлять администраторами!", buttons=get_admin_menu())
                return
            
            admins = get_admins_list()
            admin_list = "👑 **Список администраторов:**\n\n"
            for a in admins:
                admin_list += f"🆔 `{a['id']}` - {a['role']}\n"
                if a.get('username'):
                    admin_list += f"📝 @{a['username']}\n"
                admin_list += f"📅 Добавлен: {a['added_at'][:10]}\n\n"
            
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
            await event.reply("👑 **Добавление администратора**\n\nВведите ID пользователя:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "➖ Удалить админа":
            if not is_owner(user_id):
                return
            auth_states[user_id] = {'step': 'removing_admin'}
            await event.reply("👑 **Удаление администратора**\n\nВведите ID администратора для удаления:", buttons=[[Button.text("❌ Отмена")]])
        
        elif text == "👥 Пользователи":
            users = load_users()
            if not users:
                await event.reply("📭 Нет зарегистрированных пользователей", buttons=get_admin_menu())
                return
            user_list = "👥 **Список пользователей:**\n\n"
            for uid, data in list(users.items())[:30]:
                user_list += f"🆔 ID: `{uid}`\n👤 {data.get('first_name', '?')}\n"
                if data.get('username'):
                    user_list += f"📝 @{data['username']}\n"
                user_list += f"📅 Зарегистрирован: {data.get('joined_at', '?')[:10]}\n\n"
            if len(users) > 30:
                user_list += f"\n... и ещё {len(users) - 30} пользователей"
            await event.reply(user_list, buttons=get_admin_menu())
        
        elif text == "📈 Статистика бота":
            stats = get_stats()
            users_count = len(load_users())
            admins_count = len(load_admins())
            bases_count = len(get_all_chat_bases())
            await event.reply(f"""
📊 **СТАТИСТИКА БОТА**

👥 Пользователей: {users_count}
👑 Администраторов: {admins_count}
📚 Баз чатов: {bases_count}
📨 Сообщений отправлено: {stats.get('messages_sent', 0)}
📢 Всего рассылок: {stats.get('broadcasts', 0)}

📁 Активная сессия: {get_current_session_name() or 'Нет'}
📋 Активная база: {selected_chat_base}
💬 Текст рассылки: {MESSAGE_TEXT[:30]}...

✅ Бот работает стабильно
""", buttons=get_admin_menu())
        
        elif text == "📢 Рассылка пользователям":
            users = load_users()
            if not users:
                await event.reply("❌ Нет зарегистрированных пользователей", buttons=get_admin_menu())
                return
            auth_states[user_id] = {'step': 'broadcast_to_users'}
            await event.reply(f"📢 **Рассылка пользователям**\n\nВсего пользователей: {len(users)}\n\nОтправьте сообщение для рассылки:", buttons=[[Button.text("❌ Отмена")]])
        
        # ========== ОБРАБОТКА СЕССИЙ ==========
        
        elif text.startswith("🔑 ") and text != "🔑 Авторизация":
            session_name = text[2:].replace(" (активна)", "")
            success, msg = await switch_to_session(session_name, event)
            if success:
                await event.reply("🔙 Возврат в управление аккаунтами", buttons=get_accounts_menu())
        
        elif text.startswith("🗑️ "):
            session_name = text[2:]
            await delete_session(session_name, event)
        
        # ========== КНОПКИ НАЗАД ==========
        
        elif text == "◀️ Назад":
            # Определяем откуда пришли и возвращаемся
            if current_user_state.get(user_id) == 'settings':
                await delete_previous_messages(event, 2)
                await event.reply("🔙 Главное меню", buttons=get_main_menu(user_id))
                current_user_state[user_id] = 'main'
            elif current_user_state.get(user_id) == 'admin':
                await delete_previous_messages(event, 2)
                await event.reply("🔙 Главное меню", buttons=get_main_menu(user_id))
                current_user_state[user_id] = 'main'
            elif current_user_state.get(user_id) == 'broadcast':
                await delete_previous_messages(event, 2)
                await event.reply("🔙 Главное меню", buttons=get_main_menu(user_id))
                current_user_state[user_id] = 'main'
            else:
                await delete_previous_messages(event, 2)
                await event.reply("🔙 Главное меню", buttons=get_main_menu(user_id))
                current_user_state[user_id] = 'main'
        
        else:
            # Если ничего не подошло, показываем главное меню
            if text not in ["/start"]:
                await event.reply("❌ Неизвестная команда. Используйте кнопки меню.", buttons=get_main_menu(user_id))
    
    print("🔵 6. Все обработчики зарегистрированы")
    print("🟢 Бот запущен и готов к работе!")
    print(f"👥 Администраторы: {list(load_admins().keys())}")
    print(f"📚 Доступные базы чатов: {get_all_chat_bases()}")
    
    await bot_client.run_until_disconnected()
    
    # Бесконечное ожидание
    while True:
        await asyncio.sleep(60)
        print("💓 Бот жив")


if __name__ == "__main__":
    print("!!! ЗАПУСКАЮ MAIN !!!")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
