import logging
import aiosqlite
import datetime
import random
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ----------------- Render-এর জন্য হেলথ চেক ওয়েব সার্ভার -----------------
class SimpleHealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"<h1>MD MARUF HOSSAIN Trade Hub Bot is Running 24/7!</h1>")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHealthCheckHandler)
    server.serve_forever()

# ----------------- কনফিগারেশন ও ক্রেডেনশিয়াল -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9258333117:AAG6uXbLsFrpfflK9vr327W-xW7RGLdq_zw")
ADMIN_ID = 6087200623
DB_NAME = "trade_hub_production.db"

FORCE_CHANNEL_1 = "@instant_profit_airdrup_bot"
FORCE_CHANNEL_2 = "@MH_Official_Payment_Proofs"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ----------------- ডাটাবেজ আর্কিটেকচার -----------------
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            network TEXT,
            address TEXT,
            rate TEXT,
            guideline TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            lang TEXT DEFAULT 'bn',
            referrer_id INTEGER,
            ref_balance REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            status TEXT DEFAULT 'PENDING',
            amount REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            asset_name TEXT,
            amount_paid REAL,
            currency TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        defaults = {
            'status': 'online',
            'force_join': 'on',
            'ref_percent': '1.5',
            'channel_link': 'https://t.me/instant_profit_airdrup_bot',
            'group_link': 'https://t.me/Crypto_Earning_2025',
            'proof_channel': '@MH_Official_Payment_Proofs',
            'video_link': 'https://t.me/fullGuideVideo',
            
            'welcome_bn': "🔥 <b>আমাদের সেবাসমূহ:</b>\n🟢 ফ্রি এয়ারড্রপ আপডেট\n🟢 মাইনিং প্রজেক্ট গাইড\n🟢 ইনস্ট্যান্ট টোকেন বাই-সেল ডিল 💰 ⚡\n\n💬 <b>টোকেন বিক্রি করতে বা কোনো প্রবলেমে:</b> সরাসরি এই চ্যাটে আপনার মেসেজটি লিখুন! সাপোর্ট টিম দ্রুত উত্তর দেবে। ✉️\n\n👇 <b>নিচের অপশনসমূহ ব্যবহার করুন:</b>",
            'welcome_en': "🔥 <b>Our Services:</b>\n🟢 Free Airdrop Updates\n🟢 Mining Project Guides\n🟢 Instant Token Buy-Sell Deals 💰 ⚡\n\n💬 <b>To sell tokens or face any issues:</b> Write your message directly in this chat! Support team will reply quickly. ✉️\n\n👇 <b>Use the options below:</b>",
            'welcome_ng': "🔥 <b>Ayyukan Mu:</b>\n🟢 Sabunta Airdrop na Kyauta\n🟢 Jagororin Aikin Ma'adinai\n🟢 Sayar da Token Nan Take 💰 ⚡\n\n💬 <b>Don sayar da tokens ko matsala:</b> Rubuta sakon ku kai tsaye a nan! Taimako zai zo da sauri. ✉️\n\n👇 <b>Yi amfani da zabuka na kasa:</b>",

            'faq_msg': "❓ <b>সচরাচর জিজ্ঞাসিত প্রশ্নাবলী (FAQs):</b>\n\nটোকেন বা ডলার বিক্রি করতে মেনু থেকে 'Sell Tokens & Rates' এ গিয়ে ডিপোজিট এড্রেসে পাঠিয়ে স্ক্রিনশট ও পেমেন্ট নম্বর চ্যাটে দিন। ৫-১০ মিনিটে পেমেন্ট পাবেন।",
            'security_msg': "🛡️ <b>নিরাপত্তা ও স্ক্যাম সতর্কতা:</b>\n১. এডমিন কখনো আগে ইনবক্সে মেসেজ দেবে না।\n২. বটের বাইরে লেনদেন করবেন না।",
            'calc_msg': "🧮 <b>রেট ক্যালকুলেটর:</b>\nবর্তমান বেস রেট: ১ USDT = ১২০ BDT।"
        }
        for k, v in defaults.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        toks = [
            ('Very Coin', 'BNB Smart Chain (BEP-20)', '0x077d0d342f56bC...d362c0', '1 Very = $0.05', 'Step 1: ডিপোজিট এড্রেসে টোকেন পাঠান।\nStep 2: স্ক্রিনশট ও পেমেন্ট নম্বর চ্যাটে দিন।'),
            ('Very NFT', 'BNB Smart Chain (BEP-20)', '0x077d0d342f56bC...d362c0', '1 NFT = $12.00', 'Step 1: এনএফটি ট্রান্সফার করুন।\nStep 2: স্ক্রিনশট ও পেমেন্ট ডিটেইলস দিন।'),
            ('Sidra Bank', 'Sidra Chain', '0x57ce60158597c5...c5961a', '1 Sidra = 15 BDT', 'Step 1: সিদ্রা এড্রেসে টোকেন সেন্ড করুন।\nStep 2: বিকাশ বা নগদ নম্বর চ্যাটে দিন।')
        ]
        for t in toks:
            await db.execute("INSERT OR IGNORE INTO tokens (name, network, address, rate, guideline) VALUES (?, ?, ?, ?, ?)", t)
        await db.commit()

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as c:
            r = await c.fetchone()
            return r[0] if r else ""

async def set_setting(key: str, val: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, val))
        await db.commit()

async def get_user_lang(user_id: int) -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)) as c:
            r = await c.fetchone()
            return r[0] if r else 'bn'

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)) as c:
            r = await c.fetchone()
            return bool(r[0]) if r else False

async def is_user_joined(bot, user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    fj = await get_setting('force_join')
    if fj != 'on':
        return True

    for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True

def get_force_join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Official Channel", url="https://t.me/instant_profit_airdrup_bot")],
        [InlineKeyboardButton("🧾 Join Proof Channel", url="https://t.me/MH_Official_Payment_Proofs")],
        [InlineKeyboardButton("🔄 ভেরিফাই করুন (Check Join)", callback_data="check_join")]
    ])

# স্ক্রিনশটের হুবহু স্টাইলে সাজানো ইনলাইন বাটন লেআউট
def get_main_inline_keyboard(lang='bn'):
    if lang == 'en':
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Select Language", callback_data="open_lang")],
            [InlineKeyboardButton("📈 Official Channel", url="https://t.me/instant_profit_airdrup_bot"), InlineKeyboardButton("👥 Official Group", url="https://t.me/Crypto_Earning_2025")],
            [InlineKeyboardButton("🧾 Users Payment Proof", url="https://t.me/MH_Official_Payment_Proofs"), InlineKeyboardButton("🎥 Video Guide", url="https://t.me/fullGuideVideo")],
            [InlineKeyboardButton("🛒 Sell Tokens & Rates", callback_data="menu_sell"), InlineKeyboardButton("👥 Invite & Earn", callback_data="menu_invite")],
            [InlineKeyboardButton("🧮 Rate Calculator", callback_data="menu_calc"), InlineKeyboardButton("❓ FAQs", callback_data="menu_faq")],
            [InlineKeyboardButton("🛡️ Security Rules", callback_data="menu_sec"), InlineKeyboardButton("🌐 Social Links", callback_data="menu_social")],
            [InlineKeyboardButton("💬 Live Support", callback_data="menu_support")]
        ])
    elif lang == 'ng':
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Zabi Harshe (Select Language)", callback_data="open_lang")],
            [InlineKeyboardButton("📈 Tashar Hukum", url="https://t.me/instant_profit_airdrup_bot"), InlineKeyboardButton("👥 Rukunin Tattaunawa", url="https://t.me/Crypto_Earning_2025")],
            [InlineKeyboardButton("🧾 Hujjojin Biya", url="https://t.me/MH_Official_Payment_Proofs"), InlineKeyboardButton("🎥 Bidiyo Na Musamman", url="https://t.me/fullGuideVideo")],
            [InlineKeyboardButton("🛒 Sayar da Token", callback_data="menu_sell"), InlineKeyboardButton("👥 Gayyata da Samun Kudi", callback_data="menu_invite")],
            [InlineKeyboardButton("🧮 Lissafin Rate", callback_data="menu_calc"), InlineKeyboardButton("❓ Tambayoyi", callback_data="menu_faq")],
            [InlineKeyboardButton("🛡️ Dokokin Tsaro", callback_data="menu_sec"), InlineKeyboardButton("🌐 Shafukan Sadarwa", callback_data="menu_social")],
            [InlineKeyboardButton("💬 Taimako Na Kai Tsaye", callback_data="menu_support")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Select Language", callback_data="open_lang")],
            [InlineKeyboardButton("📈 Official Channel", url="https://t.me/instant_profit_airdrup_bot"), InlineKeyboardButton("👥 Official Group", url="https://t.me/Crypto_Earning_2025")],
            [InlineKeyboardButton("🧾 Users Payment Proof", url="https://t.me/MH_Official_Payment_Proofs"), InlineKeyboardButton("🎥 Video Guide", url="https://t.me/fullGuideVideo")],
            [InlineKeyboardButton("🛒 Sell Tokens & Rates", callback_data="menu_sell"), InlineKeyboardButton("👥 Invite & Earn", callback_data="menu_invite")],
            [InlineKeyboardButton("🧮 Rate Calculator", callback_data="menu_calc"), InlineKeyboardButton("❓ FAQs", callback_data="menu_faq")],
            [InlineKeyboardButton("🛡️ Security Rules", callback_data="menu_sec"), InlineKeyboardButton("🌐 Social Links", callback_data="menu_social")],
            [InlineKeyboardButton("💬 Live Support", callback_data="menu_support")]
        ])

# ----------------- /start কমান্ড -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if await is_banned(user.id):
        await update.message.reply_text("🚫 আপনি এই বট থেকে নিষিদ্ধ (Banned) হয়েছেন।")
        return

    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user.id else None

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET username = ?''',
                         (user.id, user.username or user.first_name, ref_id, user.username or user.first_name))
        await db.commit()

    if not await is_user_joined(context.bot, user.id):
        await update.message.reply_text(
            "⚠️ <b>বটের সকল সুবিধা ও ট্রেডিং ফিচার আনলক করতে আমাদের অফিশিয়াল চ্যানেলগুলোতে যুক্ত থাকা বাধ্যতামূলক!</b>\n\n"
            "নিচের চ্যানেলগুলোতে জয়েন করে <b>'ভেরিফাই করুন'</b> বাটনে চাপ দিন:",
            reply_markup=get_force_join_keyboard(),
            parse_mode="HTML"
        )
        return

    lang = await get_user_lang(user.id)
    welcome_text = await get_setting(f'welcome_{lang}')
    await update.message.reply_text(welcome_text, reply_markup=get_main_inline_keyboard(lang), parse_mode="HTML")

# ----------------- /admin কন্ট্রোল প্যানেল -----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    st = await get_setting('status')
    fj = await get_setting('force_join')
    kb = [
        [InlineKeyboardButton(f"⏯️ Status: {st.upper()}", callback_data="adm_toggle_status"),
         InlineKeyboardButton(f"🔒 Force Join: {fj.upper()}", callback_data="adm_toggle_fj")],
        [InlineKeyboardButton("🪙 টোকেন ও গাইডলাইন কন্ট্রোল", callback_data="adm_tok_hub")],
        [InlineKeyboardButton("📝 টেক্সট ও ওয়েলকাম এডিটর", callback_data="adm_txt_hub")],
        [InlineKeyboardButton("📊 Trade Statistics (রিপোর্ট)", callback_data="adm_stats")],
        [InlineKeyboardButton("📢 Targeted Broadcast", callback_data="adm_bcast_init")],
        [InlineKeyboardButton("🔓 আনব্যান ইউজার (Unban)", callback_data="adm_unban_prompt")],
        [InlineKeyboardButton("❌ ক্যান্সেল কারেন্ট অপারেশন", callback_data="adm_cancel")]
    ]
    await update.message.reply_text("⚙️ <b>এডমিন সুপার কন্ট্রোল সেন্টার</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# ----------------- ইনলাইন কলব্যাক হ্যান্ডলার -----------------
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_join":
        if await is_user_joined(context.bot, user_id):
            await query.message.delete()
            lang = await get_user_lang(user_id)
            welcome_text = await get_setting(f'welcome_{lang}')
            await query.message.reply_text(welcome_text, reply_markup=get_main_inline_keyboard(lang), parse_mode="HTML")
        else:
            await query.message.reply_text("❌ আপনি এখনো উভয় চ্যানেলে যুক্ত হননি! অনুগ্রহ করে জয়েন করে পুনরায় ভেরিফাই চাপুন।", reply_markup=get_force_join_keyboard())

    elif data == "open_lang":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇳🇬 Nigeria (Pidgin)", callback_data="lang_ng")]
        ])
        await query.message.edit_text("🌐 <b>ভাষা সিলেক্ট করুন / Select Language / Zabi Harshe:</b>", reply_markup=kb, parse_mode="HTML")

    elif data.startswith("lang_"):
        new_lang = data.split("_")[1]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, user_id))
            await db.commit()
        
        welcome_text = await get_setting(f'welcome_{new_lang}')
        await query.message.edit_text(welcome_text, reply_markup=get_main_inline_keyboard(new_lang), parse_mode="HTML")

    elif data == "menu_sell":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, name FROM tokens") as c:
                tokens = await c.fetchall()
        if not tokens:
            await query.message.reply_text("বর্তমানে কোনো টোকেন লিস্টেড নেই।")
            return
        kb = [[InlineKeyboardButton(f"🔹 {t[1]}", callback_data=f"viewtok_{t[0]}")] for t in tokens]
        await query.message.reply_text("🛒 <b>যে টোকেন বা প্রজেক্ট সেল করতে চান সিলেক্ট করুন:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif data.startswith("viewtok_"):
        tok_id = int(data.split("_")[1])
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT name, network, address, rate, guideline FROM tokens WHERE id = ?", (tok_id,)) as c:
                tok = await c.fetchone()
        if tok:
            msg = (
                f"🪙 <b>Sell Hub: {tok[0]}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <b>Network / Chain:</b> <code>{tok[1]}</code>\n"
                f"💵 <b>Current Rate:</b> <code>{tok[3]}</code>\n\n"
                f"📥 <b>Deposit Address / Account:</b>\n<code>{tok[2]}</code>\n\n"
                f"📋 <b>নির্দেশনা ও গাইডলাইন:</b>\n{tok[4]}"
            )
            await query.message.reply_text(msg, parse_mode="HTML")

    elif data == "menu_calc":
        await query.message.reply_text(await get_setting('calc_msg'), parse_mode="HTML")

    elif data == "menu_faq":
        await query.message.reply_text(await get_setting('faq_msg'), parse_mode="HTML")

    elif data == "menu_sec":
        await query.message.reply_text(await get_setting('security_msg'), parse_mode="HTML")

    elif data == "menu_social":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Channel", url=await get_setting('channel_link'))],
            [InlineKeyboardButton("👥 Group", url=await get_setting('group_link'))]
        ])
        await query.message.reply_text("🌐 <b>সোশ্যাল লিঙ্কসমূহ:</b>", reply_markup=kb, parse_mode="HTML")

    elif data == "menu_invite":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,)) as c:
                row = await c.fetchone()
                bal = row[0] if row else 0.0
        msg = (
            f"👥 <b>রেফারেল প্রোগ্রাম (Invite & Earn):</b>\n\n"
            f"বন্ধুদের ইনভাইট করে কমিশন পান!\n"
            f"🔗 <b>আপনার লিংক:</b>\n<code>{ref_link}</code>\n\n"
            f"💰 <b>ব্যালেন্স:</b> <code>{bal:.2f} USDT</code>"
        )
        kb = [[InlineKeyboardButton("💸 Request Withdrawal", callback_data="req_withdraw")]]
        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif data == "req_withdraw":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,)) as c:
                bal = (await c.fetchone())[0]
        if bal < 5.0:
            await query.message.reply_text("⚠️ সর্বনিম্ন উইথড্র লিমিট 5.00 USDT!")
        else:
            await context.bot.send_message(ADMIN_ID, f"🚨 <b>Withdraw Request:</b>\nUser ID: <code>{user_id}</code>\nAmount: {bal} USDT", parse_mode="HTML")
            await query.message.reply_text("✅ আপনার উইথড্রল রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে!")

    elif data == "menu_support":
        await query.message.reply_text("💬 <b>লাইভ সাপোর্ট:</b> সরাসরি আপনার মেসেজ বা স্ক্রিনশট এই চ্যাটে পাঠিয়ে দিন।")

    # --- এডমিন কন্ট্রোল অপশনসমূহ ---
    if user_id != ADMIN_ID:
        return

    if data == "adm_cancel":
        context.user_data.clear()
        await query.message.reply_text("✅ অপারেশন ক্যান্সেল করা হয়েছে।")

    elif data == "adm_toggle_status":
        curr = await get_setting('status')
        new_st = 'offline' if curr == 'online' else 'online'
        await set_setting('status', new_st)
        await query.message.reply_text(f"✅ বট স্ট্যাটাস: <b>{new_st.upper()}</b>", parse_mode="HTML")

    elif data == "adm_toggle_fj":
        curr = await get_setting('force_join')
        new_fj = 'off' if curr == 'on' else 'on'
        await set_setting('force_join', new_fj)
        await query.message.reply_text(f"✅ Force Join: <b>{new_fj.upper()}</b>", parse_mode="HTML")

    elif data == "adm_stats":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*), SUM(amount_paid) FROM trades") as c:
                m_count, m_sum = await c.fetchone()
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                u_cnt = (await c.fetchone())[0]
        report = f"📊 <b>স্ট্যাটিস্টিকস</b>\nমোট মেম্বার: {u_cnt}\nট্রেড সংখ্যা: {m_count or 0}\nমোট ভলিউম: ${m_sum or 0.0}"
        await query.message.reply_text(report, parse_mode="HTML")

    elif data == "adm_txt_hub":
        kb = [
            [InlineKeyboardButton("📝 Edit Welcome (Bangla)", callback_data="stxt_welcome_bn")],
            [InlineKeyboardButton("📝 Edit Welcome (English)", callback_data="stxt_welcome_en")],
            [InlineKeyboardButton("📝 Edit Welcome (Nigeria)", callback_data="stxt_welcome_ng")],
            [InlineKeyboardButton("📝 Edit FAQs", callback_data="stxt_faq_msg")],
            [InlineKeyboardButton("📝 Edit Security Rules", callback_data="stxt_security_msg")],
            [InlineKeyboardButton("📝 Edit Calculator", callback_data="stxt_calc_msg")]
        ]
        await query.message.reply_text("📝 <b>কোন টেক্সট বা ওয়েলকাম মেসেজটি এডিট করতে চান সিলেক্ট করুন:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif data.startswith("stxt_"):
        k = data.replace("stxt_", "")
        context.user_data['edit_key'] = k
        context.user_data['state'] = 'SET_TXT_VAL'
        current_val = await get_setting(k)
        await query.message.reply_text(f"বর্তমান টেক্সট:\n\n<code>{current_val}</code>\n\n<b>নতুন টেক্সট লিখে চ্যাটে পাঠান:</b>", parse_mode="HTML")

    elif data == "adm_tok_hub":
        kb = [
            [InlineKeyboardButton("➕ নতুন টোকেন/এনএফটি/প্রজেক্ট যুক্ত করুন", callback_data="adm_tok_add")],
            [InlineKeyboardButton("✏️ টোকেন গাইডলাইন/এড্রেস এডিট করুন", callback_data="adm_tok_edit_list")],
            [InlineKeyboardButton("🗑️ টোকেন মুছুন", callback_data="adm_tok_del_list")]
        ]
        await query.message.reply_text("🪙 <b>টোকেন ও গাইডলাইন কন্ট্রোল হাব:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif data == "adm_tok_add":
        context.user_data['state'] = 'ADD_NAME'
        await query.message.reply_text("নতুন টোকেন, এনএফটি বা প্রজেক্টের নাম লিখুন:")

    elif data == "adm_tok_edit_list":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, name FROM tokens") as c:
                toks = await c.fetchall()
        kb = [[InlineKeyboardButton(f"✏️ {t[1]}", callback_data=f"edtok_{t[0]}")] for t in toks]
        await query.message.reply_text("কোন টোকেন বা প্রজেক্টের গাইডলাইন/তথ্য এডিট করতে চান?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("edtok_"):
        tok_id = int(data.split("_")[1])
        context.user_data['edit_tok_id'] = tok_id
        kb = [
            [InlineKeyboardButton("💵 রেট পরিবর্তন (Rate)", callback_data="fld_rate")],
            [InlineKeyboardButton("📥 এড্রেস পরিবর্তন (Address)", callback_data="fld_address")],
            [InlineKeyboardButton("📋 গাইডলাইন/নির্দেশনা এডিট (Guideline)", callback_data="fld_guideline")]
        ]
        await query.message.reply_text("কোন বিষয়টি পরিবর্তন করতে চান?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("fld_"):
        context.user_data['edit_field'] = data.split("_")[1]
        context.user_data['state'] = 'SET_TOKEN_EDIT_VAL'
        await query.message.reply_text("নতুন তথ্য বা গাইডলাইনটি চ্যাটে লিখে পাঠান:")

    elif data == "adm_tok_del_list":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, name FROM tokens") as c:
                toks = await c.fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ Delete {t[1]}", callback_data=f"deltok_{t[0]}")] for t in toks]
        await query.message.reply_text("কোন টোকেনটি মুছতে চান?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("deltok_"):
        tok_id = int(data.split("_")[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM tokens WHERE id = ?", (tok_id,))
            await db.commit()
        await query.message.reply_text("✅ টোকেন সফলভাবে ডিলিট করা হয়েছে!")

    elif data.startswith("appr_"):
        order_id = data.split("_")[1]
        context.user_data['order_to_approve'] = order_id
        context.user_data['state'] = 'WAIT_PAY_AMOUNT'
        await query.message.reply_text(f"💰 অর্ডার <code>#{order_id}</code>-এর জন্য কত USDT পেমেন্ট করেছেন তা লিখুন:", parse_mode="HTML")

    elif data.startswith("rej_"):
        order_id = data.split("_")[1]
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM orders WHERE order_id = ?", (order_id,)) as c:
                row = await c.fetchone()
            await db.execute("UPDATE orders SET status = 'REJECTED' WHERE order_id = ?", (order_id,))
            await db.commit()
        if row:
            try:
                await context.bot.send_message(row[0], f"❌ আপনার অর্ডার <code>#{order_id}</code> বাতিল করা হয়েছে।", parse_mode="HTML")
            except Exception:
                pass
        await query.message.reply_text(f"🔴 অর্ডার <code>#{order_id}</code> রিজেক্ট করা হয়েছে।", parse_mode="HTML")

    elif data.startswith("chat_"):
        t_uid = int(data.split("_")[1])
        context.user_data['chat_uid'] = t_uid
        context.user_data['state'] = 'SEND_CHAT'
        await query.message.reply_text(f"✍️ ইউজার <code>{t_uid}</code>-এর জন্য মেসেজ লিখুন:", parse_mode="HTML")

    elif data.startswith("ban_"):
        t_uid = int(data.split("_")[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (t_uid,))
            await db.commit()
        await query.message.reply_text(f"🚫 ইউজার <code>{t_uid}</code> ব্যান করা হয়েছে!", parse_mode="HTML")

    elif data == "adm_unban_prompt":
        context.user_data['state'] = 'UNBAN_USER'
        await query.message.reply_text("আনব্যান করতে ইউজারের Telegram ID লিখুন:")

    elif data == "adm_bcast_init":
        context.user_data['state'] = 'BCAST_MSG'
        await query.message.reply_text("📢 সকলের উদ্দেশ্যে ব্রডকাস্ট নোটিশটি লিখুন:")

# ----------------- মেসেজ ও স্টেট প্রসেসিং -----------------
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    state = context.user_data.get('state')

    if user.id == ADMIN_ID and state:
        if state == 'WAIT_PAY_AMOUNT':
            try:
                amt = float(''.join(c for c in text if c.isdigit() or c == '.'))
                order_id = context.user_data['order_to_approve']

                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("UPDATE orders SET status = 'COMPLETED', amount = ? WHERE order_id = ?", (amt, order_id))
                    async with db.execute("SELECT u.user_id, u.referrer_id FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.order_id = ?", (order_id,)) as c:
                        ord_data = await c.fetchone()
                    target_user, ref_id = ord_data if ord_data else (None, None)
                    await db.execute("INSERT INTO trades (user_id, asset_name, amount_paid, currency) VALUES (?, ?, ?, ?)",
                                     (target_user or ADMIN_ID, f"Order #{order_id}", amt, 'USDT'))
                    await db.commit()

                if target_user:
                    try:
                        await context.bot.send_message(target_user, f"🎉 আপনার অর্ডার #{order_id} সফল হয়েছে! অ্যামাউন্ট: {amt} USDT", parse_mode="HTML")
                    except Exception:
                        pass
                context.user_data.clear()
                await update.message.reply_text(f"✅ অর্ডার #{order_id} কমপ্লিট করা হয়েছে!")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ এরর: সঠিক সংখ্যা দিন। {e}")
                return

        elif state == 'SET_TXT_VAL':
            k = context.user_data['edit_key']
            await set_setting(k, text)
            context.user_data.clear()
            await update.message.reply_text(f"✅ সফলভাবে টেক্সট আপডেট করা হয়েছে!", parse_mode="HTML")
            return

        elif state == 'SET_TOKEN_EDIT_VAL':
            tok_id = context.user_data['edit_tok_id']
            fld = context.user_data['edit_field']
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(f"UPDATE tokens SET {fld} = ? WHERE id = ?", (text, tok_id))
                await db.commit()
            context.user_data.clear()
            await update.message.reply_text(f"✅ টোকেনের তথ্য সফলভাবে আপডেট করা হয়েছে!", parse_mode="HTML")
            return

        elif state == 'UNBAN_USER':
            try:
                target_id = int(text.strip())
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
                    await db.commit()
                context.user_data.clear()
                await update.message.reply_text(f"✅ ইউজার {target_id} আনব্যান হয়েছে!")
            except Exception:
                await update.message.reply_text("❌ সঠিক আইডি দিন!")
            return

        elif state == 'BCAST_MSG':
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as c:
                    users = await c.fetchall()
            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(u[0], f"📢 <b>নোটিশ:</b>\n\n{text}", parse_mode="HTML")
                    sent += 1
                except Exception:
                    pass
            context.user_data.clear()
            await update.message.reply_text(f"✅ মোট {sent} জনের কাছে নোটিশ গেছে!")
            return

        elif state == 'SEND_CHAT':
            t_uid = context.user_data['chat_uid']
            try:
                await context.bot.send_message(t_uid, f"🛡️ <b>Support Reply:</b>\n{text}", parse_mode="HTML")
                await update.message.reply_text("✅ মেসেজ পাঠানো হয়েছে!")
            except Exception as e:
                await update.message.reply_text(f"❌ ব্যর্থ: {e}")
            context.user_data.clear()
            return

        elif state == 'ADD_NAME':
            context.user_data['n_name'] = text
            context.user_data['state'] = 'ADD_NET'
            await update.message.reply_text("নেটওয়ার্ক বা চেইন লিখুন (যেমন: BNB Smart Chain বা Sidra Chain):")
            return
        elif state == 'ADD_NET':
            context.user_data['n_net'] = text
            context.user_data['state'] = 'ADD_ADDR'
            await update.message.reply_text("ডিপোজিট ওয়ালেট এড্রেস বা অ্যাকাউন্ট দিন:")
            return
        elif state == 'ADD_ADDR':
            context.user_data['n_addr'] = text
            context.user_data['state'] = 'ADD_RATE'
            await update.message.reply_text("রেট লিখুন (যেমন: 1 Token = $0.05):")
            return
        elif state == 'ADD_RATE':
            context.user_data['n_rate'] = text
            context.user_data['state'] = 'ADD_GUIDE'
            await update.message.reply_text("বিশেষ গাইডলাইন বা নির্দেশনা লিখুন (যেমন: ১. টোকেন পাঠান ২. স্ক্রিনশট দিন):")
            return
        elif state == 'ADD_GUIDE':
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("INSERT INTO tokens (name, network, address, rate, guideline) VALUES (?, ?, ?, ?, ?)",
                                 (context.user_data['n_name'], context.user_data['n_net'], context.user_data['n_addr'], context.user_data['n_rate'], text))
                await db.commit()
            context.user_data.clear()
            await update.message.reply_text("✅ নতুন টোকেন ও গাইডলাইন সফলভাবে যুক্ত হয়েছে!")
            return

    if user.id == ADMIN_ID:
        return

    if await is_banned(user.id):
        return

    if not await is_user_joined(context.bot, user.id):
        await update.message.reply_text("⚠️ অনুগ্রহ করে প্রথমে অফিশিয়াল চ্যানেলে যুক্ত হোন!", reply_markup=get_force_join_keyboard(), parse_mode="HTML")
        return

    # সাধারণ টেক্সট মেসেজ হলে সেটিকে আর ডাটাবেজে অর্ডার/টিকিট হিসেবে সেভ না করে শুধু এডমিনের কাছে ফরোয়ার্ড করা হবে
    if update.message.text and not update.message.photo:
        cap = (
            f"💬 <b>Live Support Message:</b>\n"
            f"👤 User: @{user.username or 'No Username'}\n"
            f"🆔 User ID: <code>{user.id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 {update.message.text}"
        )
        kb = [[InlineKeyboardButton("✍️ রিপ্লাই দিন", callback_data=f"chat_{user.id}"),
               InlineKeyboardButton("🚫 ব্যান করুন", callback_data=f"ban_{user.id}")]]
        await context.bot.send_message(ADMIN_ID, cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        await update.message.reply_text("✅ আপনার মেসেজটি লাইভ সাপোর্ট টিমের কাছে পাঠানো হয়েছে। খুব শীঘ্রই উত্তর দেওয়া হবে।")
        return

    # শুধুমাত্র ছবি (স্ক্রিনশট বা প্রুফ) পাঠালেই নতুন অর্ডার বা টিকিট তৈরি হবে
    if update.message.photo:
        order_id = f"MH-{random.randint(1000, 9999)}"
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT INTO orders (order_id, user_id) VALUES (?, ?)", (order_id, user.id))
            await db.commit()

        cap = (
            f"📩 <b>New Order / Sell Proof: #{order_id}</b>\n"
            f"👤 User: @{user.username or 'No Username'}\n"
            f"🆔 User ID: <code>{user.id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 ক্যাপশন/টেキスト: {update.message.caption or 'None'}"
        )
        kb = [
            [InlineKeyboardButton("✅ Approve & Pay", callback_data=f"appr_{order_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"rej_{order_id}")],
            [InlineKeyboardButton("✍️ চ্যাট / নোট", callback_data=f"chat_{user.id}"),
             InlineKeyboardButton("🚫 ব্যান করুন", callback_data=f"ban_{user.id}")]
        ]

        await context.bot.send_photo(ADMIN_ID, photo=update.message.photo[-1].file_id, caption=cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        await update.message.reply_text(
            f"✅ <b>আপনার প্রুফ/স্ক্রিনশট এডমিনের কাছে পাঠানো হয়েছে!</b>\n\n"
            f"🎫 <b>অর্ডার আইডি:</b> <code>#{order_id}</code>\n"
            f"এডমিন ভেরিফাই করে ৫-১০ মিনিটের মধ্যে পেমেন্ট কমপ্লিট করবে।", parse_mode="HTML"
        )

# ----------------- পেমেন্ট প্রুফ কমান্ডসমূহ -----------------
async def proof_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw = update.message.text.replace("/proofcrypto", "").strip()
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 7:
            await update.message.reply_text("⚠️ ফরম্যাট: <code>/proofcrypto User | Asset | Network | From | To | TxHash | Amount</code>", parse_mode="HTML")
            return
        u_name, asset, net, from_a, to_a, tx, amt = parts
        now = datetime.datetime.now().strftime("%d %b %Y | %I:%M %p")
        proof_ch = await get_setting('proof_channel')
        msg = f"💎 <b>OFFICIAL PAYMENT PROOF [VERIFIED]</b>\n👤 User: {u_name}\n🪙 Asset: {asset}\n🟢 Status: PAID\n⏰ Time: {now}\n🌐 Network: {net}\n💰 Amount: {amt}"
        await context.bot.send_message(proof_ch, msg, parse_mode="HTML")
        await update.message.reply_text("✅ প্রুফ পোস্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ এরর: {e}")

async def proof_bkash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw = update.message.text.replace("/proofbkash", "").strip()
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 6:
            await update.message.reply_text("⚠️ ফরম্যাট: <code>/proofbkash User | Asset | Method | Number | TrxID | Amount</code>", parse_mode="HTML")
            return
        u_name, asset, method, num, trx, amt = parts
        now = datetime.datetime.now().strftime("%d %b %Y | %I:%M %p")
        proof_ch = await get_setting('proof_channel')
        msg = f"💎 <b>OFFICIAL PAYMENT PROOF [VERIFIED]</b>\n👤 User: {u_name}\n🪙 Asset: {asset}\n💳 Method: {method}\n💰 Amount: {amt}"
        await context.bot.send_message(proof_ch, msg, parse_mode="HTML")
        await update.message.reply_text("✅ প্রুফ পোস্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ এরর: {e}")

# ----------------- মেইন রানার -----------------
async def on_startup(app: Application):
    await init_db()
    print("✅ All Features & Database Initialized Successfully!")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("proofcrypto", proof_crypto))
    app.add_handler(CommandHandler("proofbkash", proof_bkash))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), handle_messages))

    print("🚀 Bot is Polling and Ready for Render 24/7 Deployment!")
    app.run_polling()

if __name__ == '__main__':
    main()
