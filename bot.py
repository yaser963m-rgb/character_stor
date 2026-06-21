#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
October SMS Bot - أكتوبر SMS
بوت أرقام وهمية مجانية من عدة مواقع
"""

import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# التوكن
TOKEN = "8275448704:AAEoC1btNOg7AJcXWoeOie9gKVjY9yIcyr4"

# المواقع المجانية
SITES = {
    'yallasms': {
        'name': 'YallaSMS',
        'url': 'https://yallasms.com',
        'flag': '🇸🇦'
    },
    'receivesms': {
        'name': 'ReceiveSMS',
        'url': 'https://receivesms.cc',
        'flag': '🇺🇸'
    },
    'freephonenum': {
        'name': 'FreePhoneNum',
        'url': 'https://freephonenum.com',
        'flag': '🇬🇧'
    },
    'smsreceivefree': {
        'name': 'SMSReceiveFree',
        'url': 'https://smsreceivefree.com',
        'flag': '🇨🇦'
    }
}

def scrape_numbers(site_url):
    """يجلب الأرقام من الموقع"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(site_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        numbers = []
        # البحث عن أرقام في الصفحة
        for element in soup.find_all(text=True):
            text = element.strip().replace(' ', '').replace('-', '')
            if text.startswith('+') and len(text) > 10 and len(text) < 20:
                if text not in numbers:
                    numbers.append(text)

        # البحث في الروابط
        for link in soup.find_all('a', href=True):
            text = link.text.strip().replace(' ', '').replace('-', '')
            if text.startswith('+') and len(text) > 10 and len(text) < 20:
                if text not in numbers:
                    numbers.append(text)

        return numbers[:10]  # أقصى 10 أرقام
    except Exception as e:
        logger.error(f"Error scraping {site_url}: {e}")
        return []

def get_country_flag(number):
    """يحدد الدولة من الرقم"""
    if number.startswith('+1'):
        return '🇺🇸'
    elif number.startswith('+7'):
        return '🇷🇺'
    elif number.startswith('+44'):
        return '🇬🇧'
    elif number.startswith('+49'):
        return '🇩🇪'
    elif number.startswith('+33'):
        return '🇫🇷'
    elif number.startswith('+39'):
        return '🇮🇹'
    elif number.startswith('+34'):
        return '🇪🇸'
    elif number.startswith('+90'):
        return '🇹🇷'
    elif number.startswith('+66'):
        return '🇹🇭'
    elif number.startswith('+62'):
        return '🇮🇩'
    elif number.startswith('+60'):
        return '🇲🇾'
    elif number.startswith('+65'):
        return '🇸🇬'
    elif number.startswith('+84'):
        return '🇻🇳'
    elif number.startswith('+63'):
        return '🇵🇭'
    elif number.startswith('+81'):
        return '🇯🇵'
    elif number.startswith('+82'):
        return '🇰🇷'
    elif number.startswith('+86'):
        return '🇨🇳'
    elif number.startswith('+91'):
        return '🇮🇳'
    elif number.startswith('+92'):
        return '🇵🇰'
    elif number.startswith('+966'):
        return '🇸🇦'
    elif number.startswith('+971'):
        return '🇦🇪'
    elif number.startswith('+20'):
        return '🇪🇬'
    elif number.startswith('+212'):
        return '🇲🇦'
    elif number.startswith('+216'):
        return '🇹🇳'
    elif number.startswith('+218'):
        return '🇱🇾'
    elif number.startswith('+249'):
        return '🇸🇩'
    elif number.startswith('+251'):
        return '🇪🇹'
    elif number.startswith('+254'):
        return '🇰🇪'
    elif number.startswith('+255'):
        return '🇹🇿'
    elif number.startswith('+256'):
        return '🇺🇬'
    elif number.startswith('+260'):
        return '🇿🇲'
    elif number.startswith('+27'):
        return '🇿🇦'
    else:
        return '🌍'

# ====================
# أوامر البوت
# ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    keyboard = [
        [InlineKeyboardButton("📱 جلب أرقام من جميع المواقع", callback_data='all_numbers')],
        [InlineKeyboardButton("🇸🇦 YallaSMS", callback_data='site_yallasms'),
         InlineKeyboardButton("🇺🇸 ReceiveSMS", callback_data='site_receivesms')],
        [InlineKeyboardButton("🇬🇧 FreePhoneNum", callback_data='site_freephonenum'),
         InlineKeyboardButton("🇨🇦 SMSReceiveFree", callback_data='site_smsreceivefree')],
        [InlineKeyboardButton("❓ كيف أستخدم البوت؟", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎃 *أكتوبر SMS* - October SMS

"
        "بوت الأرقام الوهمية المجانية
"
        "جلب أرقام من عدة مواقع عالمية

"
        "اختر الموقع أو اضغط 'جلب أرقام من جميع المواقع'",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def all_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جلب من جميع المواقع"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("⏳ جاري جلب الأرقام من جميع المواقع...")

    all_numbers = []
    for site_id, site_info in SITES.items():
        numbers = scrape_numbers(site_info['url'])
        for num in numbers:
            all_numbers.append({
                'number': num,
                'site': site_info['name'],
                'flag': site_info['flag']
            })

    if all_numbers:
        message = "📱 *أرقام متاحة من جميع المواقع:*

"
        for i, item in enumerate(all_numbers[:15], 1):
            flag = get_country_flag(item['number'])
            message += f"{i}. {flag} `{item['number']}`
"
            message += f"   📍 من: {item['site']}

"

        message += "⚠️ *تنبيه:* هذه أرقام عامة (الكل يشوف الرسائل)
"
        message += "💡 *نصيحة:* اضغط على الرقم لنسخه"
    else:
        message = "❌ لا توجد أرقام حالياً.
"
        message += "جرب لاحقاً أو اختر موقع محدد."

    # زر العودة
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def site_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جلب من موقع محدد"""
    query = update.callback_query
    await query.answer()

    site_id = query.data.replace('site_', '')
    site_info = SITES.get(site_id)

    if not site_info:
        await query.edit_message_text("❌ خطأ في الموقع")
        return

    await query.edit_message_text(f"⏳ جاري جلب أرقام من {site_info['name']}...")

    numbers = scrape_numbers(site_info['url'])

    if numbers:
        message = f"📱 *أرقام من {site_info['flag']} {site_info['name']}:*

"
        for i, num in enumerate(numbers[:10], 1):
            flag = get_country_flag(num)
            message += f"{i}. {flag} `{num}`

"

        message += "⚠️ *تنبيه:* رقم عام (الكل يشوف الرسائل)"
    else:
        message = f"❌ لا توجد أرقام في {site_info['name']} حالياً.
"
        message += "جرب موقع آخر أو لاحقاً."

    keyboard = [
        [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data=f'site_{site_id}')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المساعدة"""
    query = update.callback_query
    await query.answer()

    message = (
        "❓ *كيف أستخدم أكتوبر SMS؟*

"
        "1️⃣ اضغط 'جلب أرقام من جميع المواقع'
"
        "2️⃣ اختر رقم من القائمة
"
        "3️⃣ اضغط على الرقم لنسخه
"
        "4️⃣ استخدم الرقم في التطبيق اللي تبيه
"
        "5️⃣ ارجع للبوت واضغط على الرقم لشوف الرسائل

"
        "⚠️ *تنبيه مهم:*
"
        "• الأرقام عامة (الكل يشوفها)
"
        "• الرسائل تظهر للجميع
"
        "• استخدم بسرعة قبل غيرك

"
        "💡 *نصيحة:*
"
        "لو تبي رقم خاص، استخدم مواقع مدفوعة مثل 5sim أو sms-activate"
    )

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📱 جلب أرقام من جميع المواقع", callback_data='all_numbers')],
        [InlineKeyboardButton("🇸🇦 YallaSMS", callback_data='site_yallasms'),
         InlineKeyboardButton("🇺🇸 ReceiveSMS", callback_data='site_receivesms')],
        [InlineKeyboardButton("🇬🇧 FreePhoneNum", callback_data='site_freephonenum'),
         InlineKeyboardButton("🇨🇦 SMSReceiveFree", callback_data='site_smsreceivefree')],
        [InlineKeyboardButton("❓ كيف أستخدم البوت؟", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎃 *أكتوبر SMS* - October SMS

"
        "بوت الأرقام الوهمية المجانية
"
        "جلب أرقام من عدة مواقع عالمية

"
        "اختر الموقع أو اضغط 'جلب أرقام من جميع المواقع'",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ====================
# تشغيل البوت
# ====================

def main():
    application = Application.builder().token(TOKEN).build()

    # الأوامر
    application.add_handler(CommandHandler("start", start))

    # الأزرار
    application.add_handler(CallbackQueryHandler(all_numbers, pattern='^all_numbers$'))
    application.add_handler(CallbackQueryHandler(site_numbers, pattern='^site_'))
    application.add_handler(CallbackQueryHandler(help_command, pattern='^help$'))
    application.add_handler(CallbackQueryHandler(back_start, pattern='^back_start$'))

    print("🚀 أكتوبر SMS يشتغل...")
    print("📱 البوت: @OctoberSMS_Bot")
    application.run_polling()

if __name__ == '__main__':
    main()
