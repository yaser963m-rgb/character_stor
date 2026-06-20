#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
October Store - Advanced Virtual Numbers Platform
===============================================
- SaaS متكامل لبيع الأرقام الوهمية
- نظام رصيد (Credits)
- نظام اشتراكات (Subscriptions)
- API للعملاء
- نظام فواتير
- لوحة تحكم للمشرف
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import uuid
from datetime import datetime, timedelta, date
from urllib.parse import urljoin
import os
import hashlib
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# ======================
# إعدادات iVasms
# ======================
IVASMS_CONFIG = {
    "login_url": "https://ivas.tempnum.qzz.io/login",
    "base_url": "https://ivas.tempnum.qzz.io",
    "sms_api_endpoint": "https://ivas.tempnum.qzz.io/portal/sms/received/getsms",
    "username": os.environ.get("IVASMS_USERNAME", "y41942934@gmail.com"),
    "password": os.environ.get("IVASMS_PASSWORD", "yaser1234"),
    "session": requests.Session(),
    "is_logged_in": False,
    "csrf_token": None,
    "last_login": 0
}

# ======================
# قاعدة البيانات
# ======================
DB_PATH = "october_store.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # المستخدمين
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            subscription_type TEXT DEFAULT 'free',
            subscription_expiry DATE,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # الأرقام المتاحة
    c.execute("""
        CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            country_code TEXT NOT NULL,
            country_name TEXT,
            service TEXT DEFAULT 'any',
            price REAL DEFAULT 0.0,
            status TEXT DEFAULT 'available',
            purchased_by INTEGER,
            purchased_at TIMESTAMP,
            expires_at TIMESTAMP,
            otp_code TEXT,
            otp_message TEXT,
            FOREIGN KEY (purchased_by) REFERENCES users(id)
        )
    """)

    # المعاملات (الفواتير)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # API Keys
    c.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # إنشاء admin افتراضي
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute("""
        INSERT OR IGNORE INTO users (username, email, password_hash, is_admin, balance)
        VALUES (?, ?, ?, ?, ?)
    """, ("admin", "admin@october.store", admin_hash, 1, 999999.0))

    conn.commit()
    conn.close()

init_db()

# ======================
# دوال مساعدة
# ======================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_api_key():
    return "oct_" + uuid.uuid4().hex[:32]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        conn = get_db()
        user = conn.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()
        if not user or not user['is_admin']:
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ======================
# iVasms - تسجيل الدخول وجلب الرسائل
# ======================
def login_to_ivasms():
    try:
        dash = IVASMS_CONFIG
        session = dash["session"]

        if time.time() - dash["last_login"] > 1800:
            dash["session"] = requests.Session()
            session = dash["session"]

        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive"
        })

        login_page = session.get(dash["login_url"], timeout=30)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        csrf_token = token_input['value'] if token_input else None

        login_data = {
            'email': dash["username"],
            'password': dash["password"]
        }
        if csrf_token:
            login_data['_token'] = csrf_token

        login_resp = session.post(dash["login_url"], data=login_data, allow_redirects=True, timeout=30)

        if "/portal" in login_resp.url or "dashboard" in login_resp.url:
            dash['is_logged_in'] = True
            dash['last_login'] = time.time()

            soup = BeautifulSoup(login_resp.text, 'html.parser')
            meta_csrf = soup.find('meta', {'name': 'csrf-token'})
            if meta_csrf:
                dash['csrf_token'] = meta_csrf.get('content')
            else:
                token_input = soup.find('input', {'name': '_token'})
                dash['csrf_token'] = token_input['value'] if token_input else None

            return True
        return False
    except Exception as e:
        print(f"[iVasms] Login error: {e}")
        return False

def fetch_ivasms_messages():
    if not IVASMS_CONFIG.get('is_logged_in', False):
        if not login_to_ivasms():
            return []

    try:
        sess = IVASMS_CONFIG['session']
        base_url = IVASMS_CONFIG['base_url']
        csrf_token = IVASMS_CONFIG.get('csrf_token')

        if not csrf_token:
            IVASMS_CONFIG['is_logged_in'] = False
            return []

        headers = {
            'Referer': f"{base_url}/portal/sms/received",
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        now = datetime.utcnow()
        start_date = (now - timedelta(hours=24)).strftime('%m/%d/%Y %H:%M')
        end_date = now.strftime('%m/%d/%Y %H:%M')

        summary_payload = {'from': start_date, 'to': end_date, '_token': csrf_token}
        summary_resp = sess.post(IVASMS_CONFIG["sms_api_endpoint"], headers=headers, data=summary_payload, timeout=30)
        summary_soup = BeautifulSoup(summary_resp.text, 'html.parser')

        country_groups = summary_soup.find_all('div', onclick=re.compile(r"getDetials\('(.+?)'\)"))
        if not country_groups:
            return []

        group_ids = []
        for group in country_groups:
            onclick = group.get('onclick', '')
            match = re.search(r"getDetials\('(.+?)'\)", onclick)
            if match:
                group_ids.append(match.group(1))

        all_messages = []
        numbers_url = urljoin(base_url, "portal/sms/received/getsms/number")
        sms_details_url = urljoin(base_url, "portal/sms/received/getsms/number/sms")

        for group_id in group_ids:
            numbers_payload = {'start': start_date, 'end': end_date, 'range': group_id, '_token': csrf_token}
            numbers_resp = sess.post(numbers_url, headers=headers, data=numbers_payload, timeout=30)
            numbers_soup = BeautifulSoup(numbers_resp.text, 'html.parser')

            number_elements = numbers_soup.select("div[onclick*='getDetialsNumber']")
            phone_numbers = [el.text.strip() for el in number_elements]

            for phone in phone_numbers:
                sms_payload = {'start': start_date, 'end': end_date, 'Number': phone, 'Range': group_id, '_token': csrf_token}
                sms_resp = sess.post(sms_details_url, headers=headers, data=sms_payload, timeout=30)
                sms_soup = BeautifulSoup(sms_resp.text, 'html.parser')

                sms_cards = sms_soup.find_all('div', class_='card-body')
                for card in sms_cards:
                    sms_text_p = card.find('p', class_='mb-0')
                    if sms_text_p:
                        sms_text = sms_text_p.get_text(separator='\n').strip()
                        all_messages.append({
                            'number': phone,
                            'text': sms_text,
                            'country': group_id.strip(),
                            'timestamp': datetime.utcnow().isoformat()
                        })

        return all_messages
    except Exception as e:
        print(f"[iVasms] Fetch error: {e}")
        IVASMS_CONFIG['is_logged_in'] = False
        return []

def extract_otp(message):
    patterns = [
        r'(?:code|verification|otp|pin)[:\s]+(\d{3,8})',
        r'\b(\d{4,8})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    all_numbers = re.findall(r'\d{4,8}', message)
    if all_numbers:
        return all_numbers[0]
    return "N/A"

def get_country_name(code):
    countries = {
        '1': 'USA', '7': 'Russia', '20': 'Egypt', '27': 'South Africa',
        '30': 'Greece', '31': 'Netherlands', '32': 'Belgium', '33': 'France',
        '34': 'Spain', '39': 'Italy', '40': 'Romania', '41': 'Switzerland',
        '44': 'UK', '45': 'Denmark', '46': 'Sweden', '47': 'Norway',
        '48': 'Poland', '49': 'Germany', '60': 'Malaysia', '61': 'Australia',
        '62': 'Indonesia', '63': 'Philippines', '65': 'Singapore', '66': 'Thailand',
        '81': 'Japan', '82': 'South Korea', '84': 'Vietnam', '86': 'China',
        '90': 'Turkey', '91': 'India', '92': 'Pakistan', '966': 'Saudi Arabia',
        '971': 'UAE', '972': 'Israel', '974': 'Qatar', '212': 'Morocco',
        '213': 'Algeria', '216': 'Tunisia', '218': 'Libya', '234': 'Nigeria',
        '254': 'Kenya', '255': 'Tanzania', '256': 'Uganda', '260': 'Zambia',
        '351': 'Portugal', '380': 'Ukraine'
    }
    return countries.get(code, f"Country {code}")

# ======================
# Routes
# ======================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password_hash = ?",
            (email, hash_password(password))
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']

            conn = get_db()
            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'redirect': '/dashboard'})

        return jsonify({'success': False, 'message': 'Invalid credentials'})

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? OR username = ?",
            (email, username)
        ).fetchone()

        if existing:
            conn.close()
            return jsonify({'success': False, 'message': 'Email or username already exists'})

        conn.execute(
            "INSERT INTO users (username, email, password_hash, balance) VALUES (?, ?, ?, ?)",
            (username, email, hash_password(password), 0.0)
        )
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Account created successfully'})

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    stats = {
        'balance': user['balance'],
        'subscription': user['subscription_type'],
        'subscription_expiry': user['subscription_expiry']
    }

    transactions = conn.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (session['user_id'],)
    ).fetchall()

    api_keys = conn.execute(
        "SELECT * FROM api_keys WHERE user_id = ? AND is_active = 1",
        (session['user_id'],)
    ).fetchall()

    conn.close()

    return render_template('dashboard.html', user=user, stats=stats, 
                         transactions=transactions, api_keys=api_keys)

@app.route('/numbers')
@login_required
def numbers_page():
    conn = get_db()
    numbers = conn.execute(
        "SELECT * FROM numbers WHERE status = 'available' ORDER BY country_name, phone_number"
    ).fetchall()

    countries = conn.execute(
        "SELECT DISTINCT country_code, country_name FROM numbers WHERE status = 'available' ORDER BY country_name"
    ).fetchall()

    conn.close()
    return render_template('numbers.html', numbers=numbers, countries=countries)

@app.route('/buy-number', methods=['POST'])
@login_required
def buy_number():
    number_id = request.json.get('number_id')

    conn = get_db()
    number = conn.execute("SELECT * FROM numbers WHERE id = ? AND status = 'available'", (number_id,)).fetchone()
    if not number:
        conn.close()
        return jsonify({'success': False, 'message': 'Number not available'})

    user = conn.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if user['balance'] < number['price']:
        conn.close()
        return jsonify({'success': False, 'message': 'Insufficient balance'})

    conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (number['price'], session['user_id']))
    expires = datetime.now() + timedelta(hours=24)
    conn.execute(
        "UPDATE numbers SET status = 'purchased', purchased_by = ?, purchased_at = CURRENT_TIMESTAMP, expires_at = ? WHERE id = ?",
        (session['user_id'], expires, number_id)
    )
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
        (session['user_id'], 'purchase', -number['price'], f"Purchase number {number['phone_number']}")
    )

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Number purchased successfully'})

@app.route('/my-numbers')
@login_required
def my_numbers():
    conn = get_db()
    numbers = conn.execute(
        "SELECT * FROM numbers WHERE purchased_by = ? ORDER BY purchased_at DESC",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('my_numbers.html', numbers=numbers)

@app.route('/wallet')
@login_required
def wallet():
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    transactions = conn.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('wallet.html', balance=user['balance'], transactions=transactions)

@app.route('/api')
@login_required
def api_page():
    conn = get_db()
    api_keys = conn.execute(
        "SELECT * FROM api_keys WHERE user_id = ?",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('api.html', api_keys=api_keys)

@app.route('/generate-api-key', methods=['POST'])
@login_required
def generate_api_key_route():
    name = request.json.get('name', 'Default')
    api_key = generate_api_key()

    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (user_id, api_key, name) VALUES (?, ?, ?)",
        (session['user_id'], api_key, name)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'api_key': api_key})

# ======================
# Admin Routes
# ======================

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()

    stats = {
        'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_numbers': conn.execute("SELECT COUNT(*) FROM numbers").fetchone()[0],
        'available_numbers': conn.execute("SELECT COUNT(*) FROM numbers WHERE status = 'available'").fetchone()[0],
        'sold_numbers': conn.execute("SELECT COUNT(*) FROM numbers WHERE status = 'purchased'").fetchone()[0],
        'total_revenue': abs(conn.execute("SELECT SUM(amount) FROM transactions WHERE type = 'purchase'").fetchone()[0] or 0),
        'total_balance': conn.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
    }

    recent_transactions = conn.execute(
        "SELECT t.*, u.username FROM transactions t JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC LIMIT 20"
    ).fetchall()

    conn.close()
    return render_template('admin/dashboard.html', stats=stats, transactions=recent_transactions)

@app.route('/admin/numbers')
@admin_required
def admin_numbers():
    conn = get_db()
    numbers = conn.execute("SELECT n.*, u.username FROM numbers n LEFT JOIN users u ON n.purchased_by = u.id ORDER BY n.id DESC").fetchall()
    conn.close()
    return render_template('admin/numbers.html', numbers=numbers)

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/add-balance', methods=['POST'])
@admin_required
def admin_add_balance():
    user_id = request.json.get('user_id')
    amount = float(request.json.get('amount', 0))

    conn = get_db()
    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
        (user_id, 'deposit', amount, 'Admin balance addition')
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'Added {amount} to user'})

@app.route('/admin/sync-numbers', methods=['POST'])
@admin_required
def admin_sync_numbers():
    messages = fetch_ivasms_messages()

    if not messages:
        return jsonify({'success': False, 'message': 'Failed to fetch from iVasms'})

    conn = get_db()
    added = 0

    for msg in messages:
        existing = conn.execute(
            "SELECT id FROM numbers WHERE phone_number = ? AND status = 'available'",
            (msg['number'],)
        ).fetchone()

        if not existing:
            country_code = msg['number'][:3] if msg['number'][:3].isdigit() else msg['number'][:2]
            country_name = get_country_name(country_code)

            conn.execute(
                "INSERT INTO numbers (phone_number, country_code, country_name, service, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                (msg['number'], country_code, country_name, 'any', 1.0, 'available')
            )
            added += 1

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'Added {added} new numbers'})

# ======================
# Public API
# ======================

@app.route('/api/v1/numbers')
def api_get_numbers():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API Key required'}), 401

    conn = get_db()
    key = conn.execute("SELECT user_id FROM api_keys WHERE api_key = ? AND is_active = 1", (api_key,)).fetchone()
    if not key:
        conn.close()
        return jsonify({'error': 'Invalid API Key'}), 401

    country = request.args.get('country')

    query = "SELECT * FROM numbers WHERE status = 'available'"
    params = []
    if country:
        query += " AND country_code = ?"
        params.append(country)
    query += " ORDER BY country_name, phone_number"

    numbers = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({
        'numbers': [dict(n) for n in numbers],
        'count': len(numbers)
    })

@app.route('/api/v1/buy', methods=['POST'])
def api_buy_number():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API Key required'}), 401

    conn = get_db()
    key = conn.execute("SELECT user_id FROM api_keys WHERE api_key = ? AND is_active = 1", (api_key,)).fetchone()
    if not key:
        conn.close()
        return jsonify({'error': 'Invalid API Key'}), 401

    user_id = key['user_id']
    number_id = request.json.get('number_id')

    number = conn.execute("SELECT * FROM numbers WHERE id = ? AND status = 'available'", (number_id,)).fetchone()
    if not number:
        conn.close()
        return jsonify({'error': 'Number not available'}), 400

    user = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    if user['balance'] < number['price']:
        conn.close()
        return jsonify({'error': 'Insufficient balance'}), 400

    conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (number['price'], user_id))
    expires = datetime.now() + timedelta(hours=24)
    conn.execute(
        "UPDATE numbers SET status = 'purchased', purchased_by = ?, purchased_at = CURRENT_TIMESTAMP, expires_at = ? WHERE id = ?",
        (user_id, expires, number_id)
    )
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
        (user_id, 'purchase', -number['price'], f"API purchase: {number['phone_number']}")
    )

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'number': number['phone_number'],
        'expires_at': expires.isoformat()
    })

@app.route('/api/v1/sms/<number_id>')
def api_get_sms(number_id):
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API Key required'}), 401

    conn = get_db()
    key = conn.execute("SELECT user_id FROM api_keys WHERE api_key = ? AND is_active = 1", (api_key,)).fetchone()
    if not key:
        conn.close()
        return jsonify({'error': 'Invalid API Key'}), 401

    number = conn.execute(
        "SELECT * FROM numbers WHERE id = ? AND purchased_by = ?",
        (number_id, key['user_id'])
    ).fetchone()
    conn.close()

    if not number:
        return jsonify({'error': 'Number not owned by you'}), 403

    messages = fetch_ivasms_messages()
    sms_list = [m for m in messages if m['number'] == number['phone_number']]

    return jsonify({
        'number': number['phone_number'],
        'sms': [{
            'otp': extract_otp(m['text']),
            'message': m['text'],
            'timestamp': m['timestamp']
        } for m in sms_list]
    })

# ======================
# Run
# ======================
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 October Store - Advanced Virtual Numbers Platform")
    print("=" * 60)
    print("Admin: admin@october.store / admin123")
    print("URL: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
