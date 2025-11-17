import os
import asyncio
from telethon.tl.types import User
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import Message, User
from dotenv import load_dotenv

load_dotenv()

class TelegramHandler:
    def __init__(self):
        api_id_str = os.getenv('TELEGRAM_API_ID')
        self.api_id = int(api_id_str) if api_id_str else None
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone = os.getenv('TELEGRAM_PHONE')
        self.session_name = os.getenv('TELEGRAM_SESSION_NAME', 'message_aggregator')
        self.client = None
        self.messages = []
        self.last_check = None

    async def start(self):
        if not self.api_id or not self.api_hash or not self.phone:
            print("WARNING: Telegram credentials not configured. Skipping Telegram integration.")
            return False

        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            print("Telegram client started successfully")
            return True
        except Exception as e:
            print(f"Error starting Telegram client: {e}")
            return False

    async def fetch_messages(self, limit=10):
        if not self.client or not self.client.is_connected():
            return []
        
        try:
            messages = []
            # Получаем только личные диалоги
            async for dialog in self.client.iter_dialogs():
                if isinstance(dialog.entity, User):
                    # Проверяем наличие непрочитанных сообщений в диалоге
                    if dialog.unread_count > 0:
                        try:
                            # Берём только первые непрочитанные сообщения
                            async for message in self.client.iter_messages(dialog, limit=dialog.unread_count):
                                if message.text:
                                    messages.append({
                                        'id': f"tg_{dialog.id}_{message.id}",
                                        'source': 'Telegram',
                                        'source_name': dialog.name or 'Unknown',
                                        'sender': message.sender_id,
                                        'text': message.text,
                                        'date': message.date.isoformat() if message.date else datetime.now().isoformat(),
                                        'chat_id': dialog.id,
                                        'message_id': message.id,
                                        'timestamp': message.date.timestamp() if message.date else datetime.now().timestamp()
                                    })
                        except Exception as e:
                            print(f"Error fetching messages from dialog {dialog.id}: {e}")
                            continue
            
            messages.sort(key=lambda x: x['timestamp'], reverse=True)
            self.messages = messages[:limit]
            return self.messages
        
        except Exception as e:
            print(f"Error fetching Telegram messages: {e}")
            return []

    async def send_message(self, chat_id, message_id, text):
        if not self.client or not self.client.is_connected():
            return False

        try:
            await self.client.send_message(int(chat_id), text, reply_to=int(message_id))
            return True
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False

    async def save_to_favorites(self, text):
        if not self.client or not self.client.is_connected():
            return False

        try:
            await self.client.send_message('me', text)
            return True
        except Exception as e:
            print(f"Error saving to Telegram favorites: {e}")
            return False

    async def stop(self):
        if self.client:
            await self.client.disconnect()
