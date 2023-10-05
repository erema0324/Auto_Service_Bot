<!DOCTYPE html>
<html lang="en">
<head>

</head>
<body>
    <header>
        <h1>Auto Service Bot</h1>
    </header>
    <section>
        <h2>Overview</h2>
        <p>
            <strong>Auto Service Bot</strong> is a Telegram bot designed to streamline the management processes 
            of an auto service business. The bot provides functionality to interact with a client database, 
            manage appointments, track work orders, and more.
        </p>
    </section>
    <section>
        <h2>Features</h2>
        <ul>
            <li>Appointment Calendar and Scheduling: Manage scheduling and appointment booking for services.</li>
            <li>Client Management: Store and update client data in a database.</li>
            <li>Work Order Management: Create and track the status of work orders.</li>
            <li>Parts and Labor Logging: Keep track of parts used and mechanic labor time.</li>
            <li>Reporting: Generate work reports for completed services.</li>
            <li>Administrative Functions: Edit data, manage records, generate monthly reports.</li>
        </ul>
    </section>
    <section>
        <h2>Prerequisites</h2>
        <ul>
            <li>Python 3.6 or higher</li>
            <li>SQLite</li>
            <li>Telegram bot token</li>
        </ul>
    </section>
    <section>
        <h2>Installation</h2>
        <h3>Install Dependencies</h3>
        <pre><code>pip install -r requirements.txt</code></pre>
        <h3>Configuration</h3>
        <p>Configure your bot tokens by placing them in the <code>.env</code> file:</p>
        <pre><code>TELEGRAM_BOT_TOKEN=YOUR_MAIN_BOT_TOKEN
WORKER_BOT_TOKEN=YOUR_WORKER_BOT_TOKEN</code></pre>
        <p>Use the tokens in your code as follows:</p>
        <pre><code>from dotenv import load_dotenv
import os
load_dotenv()

token1 = os.getenv('TELEGRAM_BOT_TOKEN') 
token2 = os.getenv('WORKER_BOT_TOKEN')

# Initializing bots
bot1 = TeleBot(token1) 
bot2 = TeleBot(token2)</code></pre>
    </section>
    <section>
        <h2>Usage</h2>
        <p>
            After setting up the bot, users can interact with it using various commands and menus. 
            Examples of core functionalities include:
        </p>
        <ul>
            <li>Viewing the calendar and booking appointments</li>
            <li>Searching and viewing client information</li>
            <li>Managing work orders</li>
            <li>Generating and viewing reports</li>
        </ul>
    </section>
    <section>
        <h2>Deployment</h2>
        <p>
            The bot can be deployed to any server that supports Python. For instance, you might use Heroku, 
            PythonAnywhere, or AWS Lambda.
        </p>
    </section>
    <section>
        <h2>Resources</h2>
        <ul>
            <li><a href="https://github.com/eternnoir/pyTelegramBotAPI" target="_blank">Telebot Documentation</a></li>
            <li><a href="https://docs.python.org/3/library/sqlite3.html" target="_blank">SQLite in Python</a></li>
        </ul>
    </section>
    <footer>
        <p>&copy; 2023 Auto Service Bot. All rights reserved.</p>
    </footer>
</body>
</html>
