# ios6
Telegram/mail client for older versions of iPhone 4s (iOS 6)

Вы фанат стареньких iPhone, в частности, iPhone 4s на iOS 6.1.3? Уже давно не работает Telegram и почта, а вы всё хотите им пользоваться? Тогда проект для Вас. Для работы нужен старенький Safari без https, свой хостинг для размещения проекта и домен (или его подпапка).
Итак, что он может. Вы заходите на свой сайт - например http://yoursite.com (http!), и читаете все свежие новости с почты и Телеграмма и даже отвечаете на них! А если не отвечаете, тогда сообщение сразу отправляется в папку "Избранное" Телеграмма.

<img width="660" height="832" alt="Screenshot 2025-11-17 213900" src="https://github.com/user-attachments/assets/4fb3dd37-ce11-4fbb-afaa-a36d940f5d7f" />


Требования:
- сервер Unix, в данном случае использовалась конфигурация python 3.12/FreeBSD 14.3 (и любой домен)
- права для администрирования Apache (опционально, если нет - можно запускать http://domain.ext:5000)
- опыт в установке расширений python

Порядок выполнения:
- заполнить по примеру данные в .env. Нужно знать параметры Телеграмм (https://my.telegram.org/auth?to=apps) и собственного почтового ящика (внимание, здесь отправка на порт 465 SSL/TLS, обычный пароль)
- загрузить на сервер
- создать окружение Python, посредством python, pip, source, activate/deactivate и установить зависимости requirements.txt
- запустить Python из окружения и файл app.py по прямому пути и убедиться, что всё создаётся и сервис работает
- прописать постоянную работу, например, с помощью supervisor, либо запускать в screen
- по умолчанию работает по адресу http://domain.ext:5000 (не https!), но можно посредством apache/nginx настроить на обычный порт 80. Изменение требует разных ip в конфигурационных файлах - по умолчанию 0.0.0.0, а посредством Apache - 127.0.0.1
- по желанию можно настроить и Apache:
<VirtualHost *:80>
    ServerAdmin test@test.com
    ServerName test.ru

    ProxyPass / http://127.0.0.1:5000
    ProxyPassReverse / http://127.0.0.1:5000

</VirtualHost>
Не забудьте защитить публичный домен паролем, поскольку он предназначен только для личного использования.
---
Are you a fan of older iPhones, particularly the iPhone 4s running iOS 6.1.3? Telegram and email have been down for a while, but you still want to use them? Then this project is for you.

So, what can it do? You visit the website and read all the latest news from email and Telegram, and even reply to them! If you don't reply, the message is immediately sent to your Telegram "Favorites" folder.

Requirements:
- Unix server; in this case, Python 3.12/FreeBSD 14.3 was used.
- Apache administration rights (optional; if not, you can run http://domain.ext:5000).
- Experience installing Python extensions.

How to:
- Fill in the .env data as shown. You'll need to know your Telegram settings (https://my.telegram.org/auth?to=apps) and your email address (note: this sends to port 465 SSL/TLS, using a standard password).
- Upload to the server
- Create a Python environment using python, pip, source, activate/deactivate, and install the dependencies (requirements.txt)
- Run Python from the environment and the app.py file directly and ensure everything is created and the service is running
- Set it to run continuously, for example, using supervisor, or run it in screen
- By default, it runs at http://domain.ext:5000 (not https!), but you can configure it to use the standard port 80 via Apache/nginx. Changing this requires different IP addresses in the configuration files: 0.0.0.0 by default, and 127.0.0.1 via Apache.
- Optionally, you can configure Apache.
