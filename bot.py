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
BOT_TOKEN = "9258333117:AAHayp7MMKpyk9lChaFtypJ_l2VbMKr4OPs"
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
            'welcome_msg': "👋 স্বাগতম <b>MD MARUF HOSSAIN (Official Hub)</b>-এ!\n\nএখানে আপনি ১০০% বিশ্বস্ততার সাথে যেকোনো ক্রিপ্টো টোকেন বা ডলার সেরা রেটে ক্যাশ/বিকাশ/নগদে সেল (Sell) করতে পারবেন।",
            'faq_msg': (
                "❓ <b>সচরাচর জিজ্ঞাসিত প্রশ্নাবলী (FAQs):</b>\n\n"
                "<b>প্রশ্ন:</b> আমি কীভাবে টোকেন বা ডলার বিক্রি করব?\n"
                "<b>উত্তর:</b> মেনু থেকে 🛒 Sell Tokens & Rates-এ গিয়ে আপনার টোকেন সিলেক্ট করে ডিপোজিট এড্রেসে পাঠিয়ে দিন। তারপর স্ক্রিনশট ও আপনার বিকাশ/নগদ/USDT এড্রেস চ্যাটে দিন。\n\n"
                "<b>প্রশ্ন:</b> পেমেন্ট পেতে কত সময় লাগে?\n"
                "<b>উত্তর:</b> প্রুফ দেওয়ার ৫ থেকে ১০ মিনিটের মধ্যে ভেরিফাই করে সফলভাবে পেমেন্ট পাঠিয়ে দেওয়া হয়。\n\n"
                "<b>প্রশ্ন:</b> বর্তমান USDT রেট কত?\n"
                "<b>উত্তর:</b> আমাদের লাইভ রেট ১ USDT = ১২৫ BDT।"
            ),
            'security_msg': (
                "🛡️ <b>নিরাপত্তা ও স্ক্যাম সতর্কতা:</b>\n"
                "১. এডমিন কখনো আগে আপনাকে ইনবক্সে মেসেজ দেবে না।\n"
                "২. বটের বাইরে কারো সাথে লেনদেন করবেন না।\n"
                "৩. টোকেন পাঠানোর পূর্বে ডিপোজিট এড্রেস চেক করে নেবেন।"
            ),
            'calc_msg': "🧮 <b>রেট ক্যালকুলেটর:</b>\nআমাদের বর্তমান বেস USDT রেট: ১ USDT = ১২৫ BDT। লাইভ টোকেন ভ্যালু জানতে এডমিন সাপোর্টে নক দিন।"
        }
        for k, v in defaults.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        toks = [
            ('Very Coin', 'BNB Smart Chain (BEP-20)', '0x077d0d342f56bC...d362c0', '1 Very = $0.05', 'Step 1: ডিপোজিট এড্রেসে টোকেন পাঠান।\nStep 2: স্ক্রিনশট ও পেমেন্ট নম্বর দিন।\nStep 3: ৫-১০ মিনিটে পেমেন্ট বুঝে নিন।'),
            ('Very NFT', 'BNB Smart Chain (BEP-20)', '0x077d0d342f56bC...d362c0', '1 NFT = $12.00', 'Step 1: ডিপোজিট এড্রেসে এনএফটি ট্রান্সফার করুন।\nStep 2: স্ক্রিনশট ও এড্রেস দিন।'),
            ('Sidra Bank', 'Sidra Chain', '0x57ce60158597c5...c5961a', '1 Sidra = 15 BDT', 'Step 1: সিদ্রা এড্রেসে টোকেন সেন্ড করুন।\nStep 2: বিকাশ বা নগদ নম্বর চ্যাটে সেন্ড করুন।'),
            ('Rubi Network', 'Rubi Core', 'rubi_wallet_addr_here', '1 Rubi = 25 BDT', 'Step 1: রুবি ওয়ালেটে টোকেন পাঠান।\nStep 2: আপনার পেমেন্ট ডিটেইলস চ্যাটে দিন।')
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

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)) as c:
            r = await c.fetchone()
            return bool(r[0]) if r else False

# ----------------- Force Join চেকার -----------------
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

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 Sell Tokens & Rates"), KeyboardButton("🧮 Rate Calculator")],
        [KeyboardButton("📢 Official Channel"), KeyboardButton("👥 Official Group")],
        [KeyboardButton("🧾 Users payment proof"), KeyboardButton("🎥 Video Guide")],
        [KeyboardButton("👥 Invite & Earn"), KeyboardButton("❓ FAQs")],
        [KeyboardButton("💬 Live Support"), KeyboardButton("🛡️ Security Rules")],
        [KeyboardButton("🌐 Social Links"), KeyboardButton("🌐 Select Language")]
    ], resize_keyboard=True)

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

    welcome = await get_setting('welcome_msg')
    await update.message.reply_text(welcome, reply_markup=get_main_keyboard(), parse_mode="HTML")

# ----------------- ইউজার মেনু বাটন হ্যান্ডলার -----------------
async def handle_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_banned(user_id):
        return

    if not await is_user_joined(context.bot, user_id):
        await update.message.reply_text("⚠️ অনুগ্রহ করে প্রথমে অফিশিয়াল চ্যানেলগুলোতে জয়েন করুন!", reply_markup=get_force_join_keyboard(), parse_mode="HTML")
        return

    text = update.message.text
    status = await get_setting('status')
    if status == 'offline' and user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ এডমিন বর্তমানে অফলাইনে/ব্যস্ত আছেন। অনুগ্রহ করে কিছুক্ষণ পর যোগাযোগ করুন।")
        return

    if text == "🛒 Sell Tokens & Rates":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, name FROM tokens") as c:
                tokens = await c.fetchall()
        if not tokens:
            await update.message.reply_text("বর্তমানে কোনো টোকেন লিস্টেড নেই।")
            return
        kb = [[InlineKeyboardButton(f"🔹 {t[1]}", callback_data=f"viewtok_{t[0]}")] for t in tokens]
        await update.message.reply_text("🛒 <b>যে টোকেনটি সেল করতে চান সিলেক্ট করুন:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif text == "🧮 Rate Calculator":
        await update.message.reply_text(await get_setting('calc_msg'), parse_mode="HTML")

    elif text == "📢 Official Channel":
        kb = [[InlineKeyboardButton("📢 Join Channel", url=await get_setting('channel_link'))]]
        await update.message.reply_text("আমাদের অফিসিয়াল চ্যানেলে যুক্ত থাকুন:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "👥 Official Group":
        kb = [[InlineKeyboardButton("👥 Join Group", url=await get_setting('group_link'))]]
        await update.message.reply_text("আমাদের অফিশিয়াল ট্রেডিং গ্রুপ লিংক:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🧾 Users payment proof":
        ch = (await get_setting('proof_channel')).replace('@', '')
        kb = [[InlineKeyboardButton("🧾 View Proofs", url=f"https://t.me/{ch}")]]
        await update.message.reply_text("লাইভ পেমেন্ট প্রুফ চ্যানেল:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "🎥 Video Guide":
        kb = [[InlineKeyboardButton("🎥 Watch Video Guide", url=await get_setting('video_link'))]]
        await update.message.reply_text("ভিডিও টিউটোরিয়াল গাইডলাইন:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "❓ FAQs":
        await update.message.reply_text(await get_setting('faq_msg'), parse_mode="HTML")

    elif text == "🛡️ Security Rules":
        await update.message.reply_text(await get_setting('security_msg'), parse_mode="HTML")

    elif text == "🌐 Social Links":
        kb = [
            [InlineKeyboardButton("📢 Official Channel", url=await get_setting('channel_link'))],
            [InlineKeyboardButton("👥 Community Group", url=await get_setting('group_link'))],
            [InlineKeyboardButton("🎥 Video Guide", url=await get_setting('video_link'))]
        ]
        await update.message.reply_text("🌐 <b>আমাদের অফিসিয়াল সোশ্যাল লিঙ্কসমূহ:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif text == "👥 Invite & Earn":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,)) as c:
                row = await c.fetchone()
                bal = row[0] if row else 0.0

        ref_pct = await get_setting('ref_percent')
        msg = (
            f"👥 <b>রেফারেল প্রোগ্রাম (Invite & Earn):</b>\n\n"
            f"আপনার বন্ধুদের ইনভাইট করে তাদের প্রতিটি সফল সেল থেকে <b>{ref_pct}% অটো-কমিশন</b> পান!\n\n"
            f"🔗 <b>আপনার রেফারেল লিংক:</b>\n<code>{ref_link}</code>\n\n"
            f"💰 <b>বর্তমান রেফারেল ব্যালেন্স:</b> <code>{bal:.2f} USDT</code>"
        )
        kb = [[InlineKeyboardButton("💸 Request Withdrawal", callback_data="req_withdraw")]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif text == "🌐 Select Language":
        kb = [
            [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇳🇬 Nigeria", callback_data="lang_ng")]
        ]
        await update.message.reply_text("🌐 Select Language:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "💬 Live Support":
        await update.message.reply_text("💬 <b>লাইভ সাপোর্ট সক্রিয় আছে!</b>\nআপনার যেকোনো মেসেজ, টোকেন পাঠানোর স্ক্রিনশট ও পেমেন্ট রিসিভিং এড্রেস/নম্বর চ্যাটে লিখে পাঠিয়ে দিন।")

# ----------------- /admin কন্ট্রোল প্যানেল -----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    st = await get_setting('status')
    fj = await get_setting('force_join')
    kb = [
        [InlineKeyboardButton(f"⏯️ Status: {st.upper()}", callback_data="adm_toggle_status"),
         InlineKeyboardButton(f"🔒 Force Join: {fj.upper()}", callback_data="adm_toggle_fj")],
        [InlineKeyboardButton("🪙 টোকেন কন্ট্রোল হাব (Add/Edit/Delete)", callback_data="adm_tok_hub")],
        [InlineKeyboardButton("📝 টেক্সট ও কনটেন্ট এডিটর", callback_data="adm_txt_hub")],
        [InlineKeyboardButton("🔗 সোশ্যাল ও চ্যানেল লিংক এডিটর", callback_data="adm_lnk_hub")],
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
            welcome = await get_setting('welcome_msg')
            await query.message.reply_text(f"✅ <b>ভেরিফিকেশন সফল হয়েছে!</b>\n\n{welcome}", reply_markup=get_main_keyboard(), parse_mode="HTML")
        else:
            await query.message.reply_text("❌ আপনি এখনো উভয় চ্যানেলে যুক্ত হননি! অনুগ্রহ করে জয়েন করে পুনরায় ভেরিফাই চাপুন।", reply_markup=get_force_join_keyboard())

    elif data.startswith("viewtok_"):
        tok_id = int(data.split("_")[1])
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT name, network, address, rate, guideline FROM tokens WHERE id = ?", (tok_id,)) as c:
                tok = await c.fetchone()
        if tok:
            msg = (
                f"🪙 <b>Sell Hub: {tok[0]}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <b>Network:</b> <code>{tok[1]}</code>\n"
                f"💵 <b>Current Rate:</b> <code>{tok[3]}</code>\n\n"
                f"📥 <b>Official Deposit Address:</b>\n<code>{tok[2]}</code> (ট্যাপ করে কপি করুন)\n\n"
                f"📋 <b>ট্রেডিং গাইডলাইন:</b>\n{tok[4]}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <i>টোকেন সেন্ড করার পর স্ক্রিনশট ও পেমেন্ট রিসিভিং এড্রেস/নম্বর চ্যাটে সেন্ড করুন।</i>"
            )
            await query.message.reply_text(msg, parse_mode="HTML")

    elif data.startswith("lang_"):
        await query.message.reply_text("✅ Language updated successfully!")

    elif data == "req_withdraw":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT ref_balance FROM users WHERE user_id = ?", (user_id,)) as c:
                bal = (await c.fetchone())[0]
        if bal < 5.0:
            await query.message.reply_text("⚠️ সর্বনিম্ন উইথড্র লিমিট 5.00 USDT!")
        else:
            await context.bot.send_message(ADMIN_ID, f"🚨 <b>Withdraw Request:</b>\nUser: @{query.from_user.username} (<code>{user_id}</code>)\nAmount: {bal} USDT", parse_mode="HTML")
            await query.message.reply_text("✅ আপনার উইথড্রল রিকোয়েস্ট এডমিনের কাছে পাঠানো হয়েছে!")

    if user_id != ADMIN_ID:
        return

    if data == "adm_cancel":
        context.user_data.clear()
        await query.message.reply_text("✅ চলমান অপারেশন সফলভাবে ক্যান্সেল করা হয়েছে।")

    elif data == "adm_toggle_status":
        curr = await get_setting('status')
        new_st = 'offline' if curr == 'online' else 'online'
        await set_setting('status', new_st)
        await query.message.reply_text(f"✅ বট স্ট্যাটাস এখন: <b>{new_st.upper()}</b>", parse_mode="HTML")

    elif data == "adm_toggle_fj":
        curr = await get_setting('force_join')
        new_fj = 'off' if curr == 'on' else 'on'
        await set_setting('force_join', new_fj)
        await query.message.reply_text(f"✅ Force Join এখন: <b>{new_fj.upper()}</b>", parse_mode="HTML")

    elif data == "adm_stats":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*), SUM(amount_paid) FROM trades WHERE timestamp >= datetime('now', '-30 days')") as c:
                m_count, m_sum = await c.fetchone()
            async with db.execute("SELECT COUNT(*), SUM(amount_paid) FROM trades WHERE timestamp >= datetime('now', 'start of day')") as c:
                d_count, d_sum = await c.fetchone()
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                u_cnt = (await c.fetchone())[0]

        report = (
            f"📊 <b>ট্রেড স্ট্যাটিস্টিকস ও হিস্ট্রি রিপোর্ট</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 মোট মেম্বার: <code>{u_cnt}</code> জন\n\n"
            f"📅 <b>গত ৩০ দিনের লেনদেন:</b>\n"
            f"🔹 ট্রেড সংখ্যা: <code>{m_count or 0}</code> টি\n"
            f"🔹 ভলিউম: <code>${m_sum or 0.0:.2f}</code>\n\n"
            f"📆 <b>আজকের দিনের লেনদেন:</b>\n"
            f"🔹 ট্রেড সংখ্যা: <code>{d_count or 0}</code> টি\n"
            f"🔹 ভলিউম: <code>${d_sum or 0.0:.2f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.message.reply_text(report, parse_mode="HTML")

    elif data.startswith("appr_"):
        order_id = data.split("_")[1]
        context.user_data['order_to_approve'] = order_id
        context.user_data['state'] = 'WAIT_PAY_AMOUNT'
        await query.message.reply_text(f"💰 অর্ডার <code>#{order_id}</code>-এর জন্য কত USDT পেমেন্ট করেছেন তা লিখুন (যেমন: 50.00):", parse_mode="HTML")

    elif data.startswith("rej_"):
        order_id = data.split("_")[1]
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM orders WHERE order_id = ?", (order_id,)) as c:
                row = await c.fetchone()
            await db.execute("UPDATE orders SET status = 'REJECTED' WHERE order_id = ?", (order_id,))
            await db.commit()

        if row:
            try:
                await context.bot.send_message(row[0], f"❌ দুঃখিত, আপনার অর্ডার <code>#{order_id}</code> বাতিল করা হয়েছে। বিস্তারিত জানতে সাপোর্টে মেসেজ দিন।", parse_mode="HTML")
            except Exception:
                pass
        await query.message.reply_text(f"🔴 অর্ডার <code>#{order_id}</code> রিজেক্ট করা হয়েছে।", parse_mode="HTML")

    elif data.startswith("chat_"):
        t_uid = int(data.split("_")[1])
        context.user_data['chat_uid'] = t_uid
        context.user_data['state'] = 'SEND_CHAT'
        await query.message.reply_text(f"✍️ ইউজার <code>{t_uid}</code>-এর জন্য নির্দেশনা বা মেসেজ লিখুন:", parse_mode="HTML")

    elif data.startswith("ban_"):
        t_uid = int(data.split("_")[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (t_uid,))
            await db.commit()
        await query.message.reply_text(f"🚫 ইউজার <code>{t_uid}</code>-কে পার্মানেন্ট ব্যান করা হয়েছে!", parse_mode="HTML")

    elif data == "adm_unban_prompt":
        context.user_data['state'] = 'UNBAN_USER'
        await query.message.reply_text("আনব্যান করতে ইউজারের Telegram ID লিখুন:")

    elif data == "adm_tok_hub":
        kb = [
            [InlineKeyboardButton("➕ নতুন টোকেন যুক্ত করুন (Add)", callback_data="adm_tok_add")],
            [InlineKeyboardButton("📝 টোকেন রেট/এড্রেস এডিট (Edit)", callback_data="adm_tok_edit_list")],
            [InlineKeyboardButton("🗑️ টোকেন মুছে ফেলুন (Delete)", callback_data="adm_tok_del_list")]
        ]
        await query.message.reply_text("🪙 <b>টোকেন কন্ট্রোল প্যানেল:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif data == "adm_tok_add":
        context.user_data['state'] = 'ADD_NAME'
        await query.message.reply_text("নতুন টোকেনের নাম লিখুন (যেমন: Pi Network):")

    elif data == "adm_tok_edit_list":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, name FROM tokens") as c:
                toks = await c.fetchall()
        kb = [[InlineKeyboardButton(f"✏️ {t[1]}", callback_data=f"edtok_{t[0]}")] for t in toks]
        await query.message.reply_text("কোন টোকেনটি এডিট করতে চান?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("edtok_"):
        tok_id = int(data.split("_")[1])
        context.user_data['edit_tok_id'] = tok_id
        kb = [
            [InlineKeyboardButton("💵 নতুন রেট দিন (Rate)", callback_data="fld_rate")],
            [InlineKeyboardButton("📥 ডিপোজিট এড্রেস দিন (Address)", callback_data="fld_address")],
            [InlineKeyboardButton("📋 নির্দেশনা বদলান (Guideline)", callback_data="fld_guideline")]
        ]
        await query.message.reply_text("কোন তথ্যটি বদলাতে চান?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("fld_"):
        context.user_data['edit_field'] = data.split("_")[1]
        context.user_data['state'] = 'SET_EDIT_VAL'
        await query.message.reply_text("নতুন মানটি (Value) চ্যাটে লিখে পাঠান:")

    elif data == "adm_tok_del_list":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id, name FROM tokens") as c:
                toks = await c.fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ Delete {t[1]}", callback_data=f"deltok_{t[0]}")] for t in toks]
        await query.message.reply_text("কোন টোকেনটি মুছে ফেলতে চান?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("deltok_"):
        tok_id = int(data.split("_")[1])
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM tokens WHERE id = ?", (tok_id,))
            await db.commit()
        await query.message.reply_text("✅ টোকেন সফলভাবে ডিলিট হয়েছে!")

    elif data == "adm_txt_hub":
        kb = [
            [InlineKeyboardButton("📝 Edit Welcome", callback_data="stxt_welcome_msg")],
            [InlineKeyboardButton("📝 Edit FAQs", callback_data="stxt_faq_msg")],
            [InlineKeyboardButton("📝 Edit Security Rules", callback_data="stxt_security_msg")],
            [InlineKeyboardButton("📝 Edit Rate Calc", callback_data="stxt_calc_msg")]
        ]
        await query.message.reply_text("কোন কনটেন্টটি এডিট করবেন?", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("stxt_"):
        k = data.replace("stxt_", "")
        context.user_data['edit_key'] = k
        context.user_data['state'] = 'SET_TXT_VAL'
        val = await get_setting(k)
        await query.message.reply_text(f"বর্তমান কনটেন্ট:\n\n{val}\n\n<b>নতুন কনটেন্ট লিখে মেসেজ দিন:</b>", parse_mode="HTML")

    elif data == "adm_lnk_hub":
        kb = [
            [InlineKeyboardButton("🔗 Edit Channel Link", callback_data="stxt_channel_link")],
            [InlineKeyboardButton("🔗 Edit Group Link", callback_data="stxt_group_link")],
            [InlineKeyboardButton("🔗 Edit Proof Channel", callback_data="stxt_proof_channel")],
            [InlineKeyboardButton("🔗 Edit Video Guide Link", callback_data="stxt_video_link")]
        ]
        await query.message.reply_text("কোন লিংকটি পরিবর্তন করবেন?", reply_markup=InlineKeyboardMarkup(kb))

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

                    ref_msg = ""
                    if ref_id:
                        ref_pct = float(await get_setting('ref_percent'))
                        bonus = round((amt * ref_pct) / 100.0, 2)
                        await db.execute("UPDATE users SET ref_balance = ref_balance + ? WHERE user_id = ?", (bonus, ref_id))
                        ref_msg = f"\n🎉 রেফারারকে <b>{bonus} USDT</b> কমিশন দেওয়া হয়েছে!"
                        try:
                            await context.bot.send_message(
                                ref_id,
                                f"🎉 <b>অভিনন্দন!</b>\nআপনার রেফারেল ইউজারের সফল ট্রেড সম্পন্ন হওয়ায় আপনার একাউন্টে <b>+{bonus} USDT</b> কমিশন জমা হয়েছে!",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                    await db.commit()

                if target_user:
                    try:
                        await context.bot.send_message(
                            target_user,
                            f"🎉 <b>আপনার অর্ডার #{order_id} সফলভাবে সম্পন্ন হয়েছে!</b>\n"
                            f"💰 পেইড অ্যামাউন্ট: <code>{amt} USDT / সমমূল্য ক্যাশ</code>\n\n"
                            f"🤝 MD MARUF HOSSAIN-এর সাথে ট্রেড করার জন্য ধন্যবাদ!",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

                context.user_data.clear()
                await update.message.reply_text(f"✅ অর্ডার <code>#{order_id}</code> সফলভাবে কমপ্লিট করা হয়েছে!{ref_msg}", parse_mode="HTML")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ এরর: সঠিক সংখ্যা লিখুন। {e}")
                return

        elif state == 'UNBAN_USER':
            try:
                target_id = int(text.strip())
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
                    await db.commit()
                context.user_data.clear()
                await update.message.reply_text(f"✅ ইউজার <code>{target_id}</code> সফলভাবে আনব্যান হয়েছে!", parse_mode="HTML")
            except Exception:
                await update.message.reply_text("❌ সঠিক নিউমেরিক Telegram User ID লিখুন!")
            return

        elif state == 'SET_TXT_VAL':
            k = context.user_data['edit_key']
            await set_setting(k, text)
            context.user_data.clear()
            await update.message.reply_text(f"✅ <code>{k}</code> সফলভাবে আপডেট হয়েছে!", parse_mode="HTML")
            return

        elif state == 'BCAST_MSG':
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as c:
                    users = await c.fetchall()
            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(u[0], f"📢 <b>অফিসিয়াল নোটিশ:</b>\n\n{text}", parse_mode="HTML")
                    sent += 1
                except Exception:
                    pass
            context.user_data.clear()
            await update.message.reply_text(f"✅ মোট {sent} জনের কাছে নোটিশ পৌঁছে দেওয়া হয়েছে!")
            return

        elif state == 'SEND_CHAT':
            t_uid = context.user_data['chat_uid']
            reply = (
                f"🛡️ <b>Official Support Reply [VERIFIED]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{text}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤝 MD MARUF HOSSAIN (Official Hub)"
            )
            try:
                await context.bot.send_message(t_uid, reply, parse_mode="HTML")
                await update.message.reply_text("✅ মেসেজ ইউজারের কাছে সফলভাবে পৌঁছেছে!")
            except Exception as e:
                await update.message.reply_text(f"❌ সেন্ড ব্যর্থ: {e}")
            context.user_data.clear()
            return

        elif state == 'ADD_NAME':
            context.user_data['n_name'] = text
            context.user_data['state'] = 'ADD_NET'
            await update.message.reply_text("নেটওয়ার্ক লিখুন (যেমন: BNB Smart Chain BEP-20):")
            return

        elif state == 'ADD_NET':
            context.user_data['n_net'] = text
            context.user_data['state'] = 'ADD_ADDR'
            await update.message.reply_text("ডিপোজিট ওয়ালেট এড্রেস দিন:")
            return

        elif state == 'ADD_ADDR':
            context.user_data['n_addr'] = text
            context.user_data['state'] = 'ADD_RATE'
            await update.message.reply_text("বর্তমান রেট লিখুন (যেমন: 1 Token = 25 BDT):")
            return

        elif state == 'ADD_RATE':
            context.user_data['n_rate'] = text
            context.user_data['state'] = 'ADD_GUIDE'
            await update.message.reply_text("ট্রেডিং গাইডলাইন/নির্দেশনা লিখুন:")
            return

        elif state == 'ADD_GUIDE':
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("INSERT INTO tokens (name, network, address, rate, guideline) VALUES (?, ?, ?, ?, ?)",
                                 (context.user_data['n_name'], context.user_data['n_net'], context.user_data['n_addr'], context.user_data['n_rate'], text))
                await db.commit()
            context.user_data.clear()
            await update.message.reply_text("✅ নতুন টোকেন সফলভাবে লিস্টে যুক্ত হয়েছে!")
            return

        elif state == 'SET_EDIT_VAL':
            tok_id = context.user_data['edit_tok_id']
            fld = context.user_data['edit_field']
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(f"UPDATE tokens SET {fld} = ? WHERE id = ?", (text, tok_id))
                await db.commit()
            context.user_data.clear()
            await update.message.reply_text("✅ সফলভাবে এডিট সম্পন্ন হয়েছে!")
            return

    if user.id == ADMIN_ID and update.message.reply_to_message:
        orig = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
        if "🆔 User ID: " in orig:
            try:
                t_uid = int(orig.split("🆔 User ID: ")[1].split("\n")[0].strip())
                reply = (
                    f"🛡️ <b>Official Support Reply [VERIFIED]</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🤝 MD MARUF HOSSAIN (Official Hub)"
                )
                await context.bot.send_message(t_uid, reply, parse_mode="HTML")
                await update.message.reply_text("✅ রিপ্লাই ইউজারের কাছে পাঠানো হয়েছে!")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ এরর: {e}")

    if user.id != ADMIN_ID:
        if await is_banned(user.id):
            return

        if not await is_user_joined(context.bot, user.id):
            await update.message.reply_text("⚠️ অনুগ্রহ করে প্রথমে অফিশিয়াল চ্যানেলে যুক্ত হোন!", reply_markup=get_force_join_keyboard(), parse_mode="HTML")
            return

        menu_items = [
            "🛒 Sell Tokens & Rates", "🧮 Rate Calculator", "📢 Official Channel",
            "👥 Official Group", "🧾 Users payment proof", "🎥 Video Guide",
            "👥 Invite & Earn", "❓ FAQs", "💬 Live Support", "🛡️ Security Rules",
            "🌐 Social Links", "🌐 Select Language"
        ]
        if text in menu_items:
            await handle_user_menu(update, context)
            return

        order_id = f"MH-{random.randint(1000, 9999)}"
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT INTO orders (order_id, user_id) VALUES (?, ?)", (order_id, user.id))
            await db.commit()

        cap = (
            f"📩 <b>New Order / Sell Proof: #{order_id}</b>\n"
            f"👤 User: @{user.username or 'No Username'}\n"
            f"🆔 User ID: <code>{user.id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        kb = [
            [InlineKeyboardButton("✅ Approve & Pay", callback_data=f"appr_{order_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"rej_{order_id}")],
            [InlineKeyboardButton("✍️ চ্যাট / নোট", callback_data=f"chat_{user.id}"),
             InlineKeyboardButton("🚫 ব্যান করুন", callback_data=f"ban_{user.id}")]
        ]

        if update.message.photo:
            cap += f"📝 টেক্সট: {update.message.caption or 'None'}"
            await context.bot.send_photo(ADMIN_ID, photo=update.message.photo[-1].file_id, caption=cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        elif update.message.text:
            cap += f"💬 মেসেজ: {update.message.text}"
            await context.bot.send_message(ADMIN_ID, cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

        await update.message.reply_text(
            f"✅ <b>আপনার প্রুফ/মেসেজ এডমিনের কাছে পাঠানো হয়েছে!</b>\n\n"
            f"🎫 <b>আপনার অর্ডার আইডি:</b> <code>#{order_id}</code>\n"
            f"এডমিন ভেরিফাই করে ৫-১০ মিনিটের মধ্যে পেমেন্ট কমপ্লিট করবে।", parse_mode="HTML"
        )

# ----------------- অটো পেমেন্ট প্রুফ পোস্টিং সিস্টেম -----------------
async def proof_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw = update.message.text.replace("/proofcrypto", "").strip()
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 7:
            await update.message.reply_text(
                "⚠️ <b>সঠিক ফরম্যাট (পাইপ | দিয়ে লিখুন):</b>\n"
                "<code>/proofcrypto User | Asset | Network | From_Addr | To_Addr | TxHash | Amount</code>",
                parse_mode="HTML"
            )
            return

        u_name, asset, net, from_a, to_a, tx, amt = parts
        masked_from = f"{from_a[:8]}......{from_a[-6:]}" if len(from_a) > 14 else from_a
        masked_to = f"{to_a[:8]}......{to_a[-6:]}" if len(to_a) > 14 else to_a
        masked_tx = f"{tx[:12]}......{tx[-16:]}" if len(tx) > 28 else tx
        now = datetime.datetime.now().strftime("%d %b %Y | %I:%M %p")
        proof_ch = await get_setting('proof_channel')

        msg = (
            "💎 <b>OFFICIAL PAYMENT PROOF [VERIFIED]</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User: {u_name}\n"
            f"🪙 Sell Asset: {asset}\n"
            f"🟢 Status: PAID & COMPLETED\n"
            f"⏰ Date & Time: {now}\n"
            f"🌐 Network / Chain: {net}\n"
            f"📤 Sender (From): <code>{masked_from}</code> (Admin Wallet)\n"
            f"📥 Recipient (To): <code>{masked_to}</code> (User Wallet)\n"
            f"🎲 TxHash: <code>{masked_tx}</code>\n"
            f"💰 Amount Paid: {amt}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛡️ Verified & Executed by Bot Admin\n"
            "🤝 4+ Years Trusted Crypto Trading Service"
        )
        await context.bot.send_message(proof_ch, msg, parse_mode="HTML")
        await update.message.reply_text("✅ ক্রিপ্টো পেমেন্ট প্রুফ চ্যানেলে পোস্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ এরর: {e}")

async def proof_bkash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw = update.message.text.replace("/proofbkash", "").strip()
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 6:
            await update.message.reply_text(
                "⚠️ <b>সঠিক ফরম্যাট (পাইপ | দিয়ে লিখুন):</b>\n"
                "<code>/proofbkash User | Asset | Method | RecipientNumber | TrxID | Amount</code>",
                parse_mode="HTML"
            )
            return

        u_name, asset, method, num, trx, amt = parts
        masked_num = f"{num[:3]}****{num[-4:]}" if len(num) >= 11 else num
        masked_trx = f"{trx[:4]}...{trx[-2:]}" if len(trx) > 6 else trx
        now = datetime.datetime.now().strftime("%d %b %Y | %I:%M %p")
        proof_ch = await get_setting('proof_channel')

        msg = (
            "💎 <b>OFFICIAL PAYMENT PROOF [VERIFIED]</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User: {u_name}\n"
            f"🪙 Sell Asset: {asset}\n"
            f"🟢 Status: SUCCESSFUL\n"
            f"⏰ Date & Time: {now}\n"
            f"💳 Payment Method: {method}\n"
            f"📲 Recipient Number: <code>{masked_num}</code> (User Account)\n"
            f"🎫 TrxID: <code>{masked_trx}</code>\n"
            f"💰 Amount Paid: {amt}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛡️ Verified & Executed by Bot Admin\n"
            "🤝 4+ Years Trusted Crypto Trading Service"
        )
        await context.bot.send_message(proof_ch, msg, parse_mode="HTML")
        await update.message.reply_text("✅ বিকাশ/নগদ পেমেন্ট প্রুফ চ্যানেলে পোস্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ এরর: {e}")

# ----------------- ইনিশিয়ালাইজেশন ও মেইন রানার -----------------
async def on_startup(app: Application):
    await init_db()
    print("✅ All Features & Database Initialized Successfully!")

def main():
    # Render-এর জন্য ব্যাকগ্রাউন্ড ডামি সার্ভার চালু
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