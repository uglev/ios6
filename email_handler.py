import os
import asyncio
import re
import email
import html
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime
from aioimaplib import aioimaplib
from aiosmtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

class EmailHandler:
    def __init__(self):
        self.imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.yandex.ru')
        self.imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))
        self.smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.yandex.ru')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 465))
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.messages = []
        
    def strip_html(self, html):
        if not html:
            return ""

        # 1. Заменяем <br>, <div>, <p> и подобные на переносы строк
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</(div|p|li|tr|td|th)>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<(div|p|li|tr|td|th)[^>]*>', '', html, flags=re.IGNORECASE)

        # 2. Удаляем все остальные теги
        html = re.sub(r'<[^>]+>', '', html)

        # 3. Декодируем HTML‑сущности
        try:
            # Python 3.4+: используем html.unescape()
            html = html.unescape(html)
        except AttributeError:
            # Для старых версий Python: эмулируем unescape через замену сущностей
            html = self._unescape_html_entities(html)

        # 4. Удаляем оставшиеся сущности, которые не удалось декодировать (на всякий случай)
        html = re.sub(r'&\w+;', ' ', html)  # например, &nbsp;, &quot;
        html = re.sub(r'&#\d+;', ' ', html)   # числовые сущности, например, &#160;

        # 5. Нормализуем пробелы и переносы
        html = re.sub(r'\s+', ' ', html).strip()        # множественные пробелы → один пробел
        html = re.sub(r' *\n *', '\n', html)           # пробелы вокруг \n → чистый \n
        html = re.sub(r'\n+', '\n', html).strip()       # множественные \n → один \n

        return html


    def _unescape_html_entities(self, text):
        """Ручная замена HTML-сущностей для старых версий Python."""
        # Словарь базовых сущностей
        entity_map = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&nbsp;': ' ',
            '&copy;': '©',
            '&reg;': '®',
            '&euro;': '€',
            '&pound;': '£',
            '&yen;': '¥',
            '&cent;': '¢',
            '&sect;': '§',
            '&para;': '¶',
            '&deg;': '°',
            '&plusmn;': '±',
            '&times;': '×',
            '&divide;': '÷',
            '&frac12;': '½',
            '&frac14;': '¼',
            '&frac34;': '¾',
            '&hellip;': '…',
            '&ndash;': '–',
            '&mdash;': '—',
            '&lsquo;': '‘',
            '&rsquo;': '’',
            '&ldquo;': '“',
            '&rdquo;': '”',
            '&bull;': '•',
            '&trade;': '™',
            '&rarr;': '→',
            '&larr;': '←',
            '&uarr;': '↑',
            '&darr;': '↓',
        }

        for entity, char in entity_map.items():
            text = text.replace(entity, char)

        # Обрабатываем числовые сущности (&#160;)
        import re
        def replace_numeric(match):
            code = int(match.group(1))
            return chr(code) if 0 <= code <= 0x10FFFF else ' '

        text = re.sub(r'&#(\d+);', replace_numeric, text)

        return text


    def decode_subject(self, subject):
        if subject is None:
            return "No Subject"
        try:
            decoded_parts = decode_header(subject)
            decoded_subject = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_subject += part.decode(encoding or 'utf-8', errors='replace')
                else:
                    decoded_subject += str(part)
            return decoded_subject
        except Exception as e:
            print(f"[ERROR] Decoding subject: {e}")
            return str(subject)

    def get_email_body(self, msg):
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", "")).lower()

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode('utf-8', errors='ignore')
                        else:
                            body = str(payload)
                        break
                    except Exception as e:
                        print(f"[ERROR] Decoding part: {e}")
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    body = payload.decode('utf-8', errors='ignore')
                else:
                    body = str(payload)
            except Exception as e:
                print(f"[ERROR] Getting payload: {e}")
                body = str(msg.get_payload())
        return body.strip()

    async def fetch_messages(self, limit=10):
        if not self.email_address or not self.email_password:
            print("WARNING: Email credentials not configured. Skipping email integration.")
            return []

        try:
            imap_client = aioimaplib.IMAP4_SSL(host=self.imap_server, port=self.imap_port)
            await imap_client.wait_hello_from_server()
            await imap_client.login(self.email_address, self.email_password)
            await imap_client.select('INBOX')

            # Ищем только непрочитанные письма
            status, data = await imap_client.search('UNSEEN')
            if status != 'OK':
                print(f"[ERROR] IMAP search failed: {data}")
                await imap_client.logout()
                return []

            email_ids = data[0].decode().split() if data[0] else []
            print(f"[INFO] Found {len(email_ids)} unread emails")

            messages = []

            for email_id in email_ids[-limit:]:
                try:
                    # 1. Проверяем текущие флаги (опционально)
                    status, flags_data = await imap_client.fetch(email_id, '(FLAGS)')
                    if status == 'OK':
                        flags = flags_data[0].decode()
                        if '\\Seen' in flags:
                            print(f"[SKIP] Email {email_id} already read, skipping")
                            continue

                    # 2. Запрашиваем только заголовки и размер (безопаснее)
                    status, msg_data = await imap_client.fetch(
                        email_id,
                        '(BODY.PEEK[HEADER.FIELDS (From To Cc Subject Date)] RFC822.SIZE)'
                    )
                    if status != 'OK':
                        print(f"[SKIP] Fetch headers failed for ID {email_id}: {msg_data}")
                        continue

                    # Извлекаем заголовки (надёжная версия)
                    headers = None
                    for part in msg_data:
                        if isinstance(part, bytearray):
                            if b'BODY[' in part or any(header_key in part for header_key in [b'From:', b'To:', b'Subject:', b'Date:']):
                                headers = part
                                break

                    if not headers:
                        print(f"[SKIP] No headers found for ID {email_id}")
                        continue

                    # Парсим заголовки
                    try:
                        msg = email.message_from_bytes(headers, policy=email.policy.default)
                    except Exception as e:
                        print(f"[ERROR] Failed to parse headers for ID {email_id}: {e}")
                        continue

                    subject = self.decode_subject(msg.get('Subject', 'No Subject'))
                    from_addr = parseaddr(msg.get('From'))[1] or 'Unknown'
                    date_str = msg.get('Date', '')


                    # Парсим дату
                    try:
                        date_obj = parsedate_to_datetime(date_str)
                        if date_obj is None:
                            date_obj = datetime.now()
                        timestamp = date_obj.timestamp()
                        date_iso = date_obj.isoformat()
                    except (ValueError, TypeError, OverflowError) as e:
                        print(f"[ERROR] Parsing date '{date_str}': {e}")
                        date_obj = datetime.now()
                        timestamp = date_obj.timestamp()
                        date_iso = date_obj.isoformat()

                    # 3. Если нужно тело — запрашиваем отдельно (менее агрессивно)
                    body = ""
                    status, body_data = await imap_client.fetch(email_id, '(BODY.PEEK[])')
                    if status == 'OK':
                        for part in body_data:
                            if isinstance(part, bytearray):
                                raw_body = bytes(part)
                                msg_body = email.message_from_bytes(raw_body, policy=email.policy.default)
                                raw_body = self.get_email_body(msg_body)
                                body = self.strip_html(raw_body)
                                break

                    messages.append({
                        'id': f"email_msg_{email_id}",
                        'source': 'Email',
                        'source_name': from_addr,
                        'sender': from_addr,
                        'text': f"{subject}\n\n{body}",
                        'date': date_iso,
                        'email_id': email_id,
                        'subject': subject,
                        'timestamp': timestamp
                    })

                except Exception as e:
                    print(f"[ERROR] Processing email {email_id}: {e}")
                    continue

            await imap_client.logout()
            messages.sort(key=lambda x: x['timestamp'], reverse=True)
            self.messages = messages[:limit]
            return self.messages

        except Exception as e:
            print(f"[CRITICAL] Error fetching email messages: {e}")
            import traceback
            traceback.print_exc()
            return []


    async def send_email(self, to_address, subject, body, in_reply_to=None):
        if not self.email_address or not self.email_password:
            print("[ERROR] Email credentials missing")
            return False

        try:
            message = MIMEMultipart()
            message['From'] = self.email_address
            message['To'] = to_address
            message['Subject'] = f"Re: {subject}" if in_reply_to else subject

            if in_reply_to:
                message['In-Reply-To'] = in_reply_to


            message.attach(MIMEText(body, 'plain', 'utf-8'))

            smtp_client = SMTP(
                hostname=self.smtp_server,
                port=self.smtp_port,
                timeout=120,
                use_tls=(self.smtp_port == 465),
                start_tls=(self.smtp_port == 587)
            )

            await smtp_client.connect()

            if self.smtp_port == 587:
                await smtp_client.starttls()

            await smtp_client.login(self.email_address, self.email_password)
            await smtp_client.send_message(message)
            await smtp_client.quit()

            print(f"[INFO] Email sent successfully to {to_address}")
            return True

        except Exception as e:
            print(f"[ERROR] Error sending email to {to_address}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def close(self):
        """Безопасное завершение работы (если нужно вызвать извне)."""
        pass  # В текущем коде соединения закрываются автоматически
