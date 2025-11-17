import os
import asyncio
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from telegram import TelegramHandler
from email_handler import EmailHandler
import threading

messages_lock = threading.Lock()
all_messages = []
load_dotenv()

app = Flask(__name__)

telegram_handler = TelegramHandler()
email_handler = EmailHandler()

poll_interval_minutes = int(os.getenv('POLL_INTERVAL_MINUTES', '10'))
max_messages_display = int(os.getenv('MAX_MESSAGES_DISPLAY', '15'))
message_preview_length = int(os.getenv('MESSAGE_PREVIEW_LENGTH', '500'))

async def poll_messages():
    while True:
        try:
            # Увеличиваем лимит выборки: берём в 2 раза больше, чем нужно для отображения
            telegram_messages = await telegram_handler.fetch_messages(limit=max_messages_display * 2)
            email_messages = await email_handler.fetch_messages(limit=max_messages_display * 2)

            # Объединяем и сортируем по timestamp (новые сверху)
            combined = sorted(
                telegram_messages + email_messages,
                key=lambda x: x['timestamp'],
                reverse=True
            )

            # Отладка: выводим источники первых 10 сообщений
            print(f"[DEBUG] Top 10 message sources: {[m['source'] for m in combined[:10]]}")


            with messages_lock:
                all_messages[:] = combined[:max_messages_display]

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Fetched {len(telegram_messages)} Telegram and {len(email_messages)} email messages "
                  f"(total in all_messages: {len(all_messages)})")

        except Exception as e:
            print(f"Error polling messages: {e}")

        await asyncio.sleep(poll_interval_minutes * 60)



def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

async def init_handlers():
    await telegram_handler.start()
    print("Handlers initialized")
    asyncio.create_task(poll_messages())

def initialize_async():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=start_background_loop, args=(loop,), daemon=True)
    thread.start()
    
    asyncio.run_coroutine_threadsafe(init_handlers(), loop)
    return loop

event_loop = initialize_async()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/messages', methods=['GET'])
def get_messages():
    with messages_lock:
        print(f"[API] Returning {len(all_messages)} messages")  # логирование
        preview_messages = []
        for msg in all_messages:
            preview_msg = msg.copy()
            if len(preview_msg['text']) > message_preview_length:
                preview_msg['text'] = preview_msg['text'][:message_preview_length] + '...'
            preview_messages.append(preview_msg)
    return jsonify({
        'messages': preview_messages,
        'count': len(preview_messages)
    })


@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.json or {}
    text = data.get('text', '')
    reply_to = data.get('reply_to')
    
    if not text:
        return jsonify({'success': False, 'error': 'No text provided'}), 400
    
    async def send():
        if reply_to:
            original_msg = next((m for m in all_messages if m['id'] == reply_to), None)
            if not original_msg:
                return False
            
            if original_msg['source'] == 'Telegram':
                return await telegram_handler.send_message(
                    original_msg['chat_id'],
                    original_msg['message_id'],
                    text
                )
            elif original_msg['source'] == 'Email':
                return await email_handler.send_email(
                    original_msg['sender'],
                    original_msg.get('subject', 'No Subject'),
                    text,
                    in_reply_to=original_msg['email_id']
                )
        else:
            return await telegram_handler.save_to_favorites(text)
    
    try:
        future = asyncio.run_coroutine_threadsafe(send(), event_loop)
        success = future.result(timeout=10)
        
        if success:
            return jsonify({'success': True, 'message': 'Message sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send message'}), 500
    except Exception as e:
        print(f"Error sending message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', '5000'))
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    app.run(host=host, port=port, debug=False)
