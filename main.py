import os
import time
import json
import uuid
import shutil
import subprocess
import requests
import qrcode
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ============ SECRETS ============
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
PAYMENT_CHANNEL = os.getenv("PAYMENT_CHANNEL")
# =================================

WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"
WGCF_BIN = "./wgcf"

FREE_USERS = "users.json"
VIP_USERS = "vip_users.json"

ENDPOINT_IP = "162.159.192.1"
ENDPOINT_PORT = 500

# ========== VIP JUNK ==========
VIP_JUNK = """
S1 = 0
S2 = 0
Jc = 4
Jmin = 40
Jmax = 70
H1 = 1
H2 = 2
H3 = 3
H4 = 4
MTU = 1280
PersistentKeepalive = 25
"""

# ---------- Utils ----------
def load_json(path):
    if not os.path.exists(path):
        return {}
    return json.load(open(path))

def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2)

def now_ts():
    return int(time.time())

def setup_wgcf():
    if not os.path.exists(WGCF_BIN):
        r = requests.get(WGCF_URL)
        open("wgcf", "wb").write(r.content)
        os.chmod("wgcf", 0o755)

def reset_wgcf():
    for f in ["wgcf-account.toml", "wgcf-profile.conf"]:
        if os.path.exists(f):
            os.remove(f)

def generate_conf(vip=False):
    reset_wgcf()
    subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
    subprocess.run([WGCF_BIN, "generate"], check=True)

    txt = open("wgcf-profile.conf").read()
    txt = txt.replace(
        "Endpoint =",
        f"Endpoint = {ENDPOINT_IP}:{ENDPOINT_PORT}"
    )

    if vip:
        txt += "\n" + VIP_JUNK

    name = f"WARP_{uuid.uuid4().hex[:6]}.conf"
    png = name.replace(".conf", ".png")

    open(name, "w").write(txt)
    qrcode.make(txt).save(png)

    return name, png

async def is_user_joined(bot, user_id):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return m.status in ("member", "administrator", "creator")
    except:
        return False

# ---------- UI ----------
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🆓 Free Generate", callback_data="free")],
        [InlineKeyboardButton("💎 VIP Generate", callback_data="vip")],
        [InlineKeyboardButton("📊 User Stats", callback_data="stats")]
    ])

def vip_request_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 ငွေလွှဲပြီး", callback_data="paid")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 WARP Generator Bot\n\n"
        "• Free / VIP Generate\n"
        "• Channel Join Required",
        reply_markup=main_keyboard()
    )

# ---------- Buttons ----------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = str(q.from_user.id)

    if not await is_user_joined(context.bot, q.from_user.id):
        await q.message.reply_text("⛔ Channel join လုပ်ပါ")
        return

    free_users = load_json(FREE_USERS)
    vip_users = load_json(VIP_USERS)
    is_vip = uid in vip_users
    is_admin = q.from_user.id == ADMIN_ID

    if q.data == "stats":
        await q.message.reply_text(
            f"🆔 {uid}\nVIP: {'YES' if is_vip else 'NO'}"
        )
        return

    if q.data == "vip" and not is_vip:
        await q.message.reply_text(
            "💎 VIP ဝင်ရန် ငွေလွှဲပါ",
            reply_markup=vip_request_keyboard()
        )
        return

    if q.data == "paid":
        await q.message.reply_text("📸 ငွေလွှဲပြီး ပုံပို့ပါ")
        return

    if q.data not in ("free", "vip"):
        return

    last = free_users.get(uid, 0)
    limit_days = 1 if is_vip else 10

    if not is_admin and now_ts() - last < limit_days * 86400:
        await q.message.reply_text("⏳ မကြာသေးပါ")
        return

    msg = await q.message.reply_text("⚙️ Generate...")
    conf, png = generate_conf(vip=(q.data == "vip"))

    await q.message.reply_document(open(conf, "rb"))
    await q.message.reply_photo(open(png, "rb"))

    free_users[uid] = now_ts()
    save_json(FREE_USERS, free_users)

    os.remove(conf)
    os.remove(png)
    await msg.delete()

# ---------- Payment Photo ----------
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.from_user.id
    caption = (
        f"User ID: {uid}\n"
        f"Username: @{update.from_user.username}\n"
        f"Time: {datetime.now()}"
    )
    await context.bot.send_photo(
        chat_id=f"@{PAYMENT_CHANNEL}",
        photo=update.message.photo[-1].file_id,
        caption=caption
    )
    await update.message.reply_text("✅ Admin စစ်ဆေးပါမယ်")

# ---------- Admin Approve ----------
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.from_user.id != ADMIN_ID:
        return
    try:
        uid = context.args[0]
        vip_users = load_json(VIP_USERS)
        vip_users[uid] = {"since": now_ts()}
        save_json(VIP_USERS, vip_users)
        await update.message.reply_text(f"✅ VIP Approved: {uid}")
    except:
        await update.message.reply_text("Usage: /approve USER_ID")

# ---------- Main ----------
if __name__ == "__main__":
    setup_wgcf()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))

    print("🤖 Bot Running...")
    app.run_polling()
