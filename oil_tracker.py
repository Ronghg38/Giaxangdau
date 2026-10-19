import os
import time
from datetime import datetime
import sqlite3
import json
import requests
from bs4 import BeautifulSoup

URL = "https://webgia.com/gia-xang-dau/petrolimex/"
DB_NAME = "oil_prices.db"
JSON_NAME = "prices.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(telegram_url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            product_name TEXT,
            price_str TEXT
        )
    ''')
    conn.commit()
    conn.close()

def fetch_fuel_prices():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        if not table:
            return None

        prices_data = {}
        rows = table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all(['th', 'td'])
            if len(cols) >= 2:
                product_name = cols[0].text.strip()
                price_vung1 = cols[1].text.strip()
                prices_data[product_name] = price_vung1
        return prices_data
    except Exception as e:
        print(f"❌ Lỗi cào dữ liệu: {e}")
        return None

def clean_price_to_number(price_str):
    try:
        clean_str = ''.join(filter(str.isdigit, price_str))
        return int(clean_str)
    except:
        return 0

def get_last_saved_prices():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT product_name, price_str FROM price_history 
        WHERE timestamp = (SELECT MAX(timestamp) FROM price_history)
    ''')
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def save_to_db_and_json(current_time, prices_data):
    # Lưu vào SQLite
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for product, price in prices_data.items():
        cursor.execute('''
            INSERT INTO price_history (timestamp, product_name, price_str)
            VALUES (?, ?, ?)
        ''', (current_time, product, price))
    conn.commit()
    conn.close()

    # Xuất ra file prices.json cho trang web đọc
    json_data = {
        "update_time": current_time,
        "prices": prices_data
    }
    with open(JSON_NAME, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

def monitor_oil_prices():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_prices = fetch_fuel_prices()
    if not current_prices:
        return

    old_prices = get_last_saved_prices()
    report_lines = [f"⛽ *CẬP NHẬT GIÁ XĂNG DẦU* ⛽\n🕒 _{current_time}_\n"]

    for product, price_str in current_prices.items():
        line = f"• *{product}*: `{price_str}`"
        if product in old_prices:
            old_price_str = old_prices[product]
            old_val = clean_price_to_number(old_price_str)
            new_val = clean_price_to_number(price_str)
            if old_val > 0 and new_val > 0:
                diff = new_val - old_val
                if diff > 0:
                    line += f" (📈 `+{diff:,} VNĐ`)"
                elif diff < 0:
                    line += f" (📉 `{diff:,} VNĐ`)"
                else:
                    line += " (➖ Không đổi)"
        else:
            line += " (🆕 Mới cập nhật)"
        report_lines.append(line)

    save_to_db_and_json(current_time, current_prices)
    send_telegram_message("\n".join(report_lines))

if __name__ == "__main__":
    init_db()
    monitor_oil_prices()
