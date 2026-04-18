import asyncio
import os
from telethon import TelegramClient, events
from flask import Flask
from threading import Thread

# ========== НАСТРОЙКИ ==========
API_ID = 36594021
API_HASH = '6dfedd148bf6bba5d4e67ed213178ebb'
BOT_TOKEN = '8779543002:AAEnnD2AeimtSQDptnmVh-OMXR64sLe5xDg'
MASTER_ADMIN_ID = 1031953955
# ==================================

# ========== FLASK ДЛЯ RAILWAY ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Бот работает!", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Запускаем Flask в отдельном потоке
thread = Thread(target=run_flask, daemon=True)
thread.start()
print("🌐 Веб-сервер запущен")
# ==================================

# ========== ОСНОВНОЙ БОТ ==========
async def main():
    # Создаём клиент бота
    bot = await TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен и готов к работе!")
    
    # Обработчик всех сообщений
    @bot.on(events.NewMessage)
    async def handler(event):
        user_id = event.sender_id
        text = event.raw_text
        print(f"📩 Получено сообщение от {user_id}: {text}")
        
        # Ответ на любое сообщение
        await event.reply(f"✅ Бот работает! Вы написали: {text}")
    
    # Запускаем бота
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
