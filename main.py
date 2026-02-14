# === imports ===
import os, json, time, uuid, shutil, subprocess, requests, qrcode
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# === Secrets ===
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL = os.getenv("CHANNEL_USERNAME")
PAY_CH = os.getenv("PAYMENT_CHANNEL")

# === Files ===
USERS = "users.json"
VIP_USERS = "vip_users.json"

# === WG ===
WG_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"
WG = "./wgcf"
ENDPOINT = "162.159.192.1:500"

# === VIP Junk ===
VIP_JUNK = """(အပေါ်မှာပေးထားတဲ့ VIP_JUNK အပြည့် ထည့်ပါ)"""

# === Utils ===
def load(f): return json.load(open(f)) if os.path.exists(f) else {}
def save(f,d): json.dump(d,open(f,"w"),indent=2)
def now(): return int(time.time())

def setup_wg():
    if not os.path.exists(WG):
        r=requests.get(WG_URL);open("wgcf","wb").write(r.content);os.chmod("wgcf",0o755)

def gen_conf(vip=False):
    for f in ["wgcf-account.toml","wgcf-profile.conf"]:
        if os.path.exists(f): os.remove(f)
    subprocess.run([WG,"register","--accept-tos"],check=True)
    subprocess.run([WG,"generate"],check=True)
    txt=open("wgcf-profile.conf").read()
    txt=txt.replace("Endpoint =","Endpoint = "+ENDPOINT)
    if vip: txt+="\n"+VIP_JUNK
    name=f"WARP_{uuid.uuid4().hex[:6]}.conf"
    open(name,"w").write(txt)
    img=name.replace(".conf",".png")
    q=qrcode.make(txt);q.save(img)
    return name,img

# === UI ===
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel",url=f"https://t.me/{CHANNEL}")],
        [InlineKeyboardButton("🆓 Free Generate",callback_data="free")],
        [InlineKeyboardButton("💎 VIP Generate",callback_data="vip")],
        [InlineKeyboardButton("📊 User Stats",callback_data="stats")]
    ])

# === Commands ===
async def start(u,c):
    await u.message.reply_text("WARP Generator Bot",reply_markup=menu())

# === Buttons ===
async def btn(u,c):
    q=u.callback_query;await q.answer()
    uid=str(q.from_user.id)
    users,vips=load(USERS),load(VIP_USERS)

    if q.data=="stats":
        vip="YES" if uid in vips else "NO"
        await q.message.reply_text(f"ID: {uid}\nVIP: {vip}")
        return

    if q.data=="vip" and uid not in vips:
        await q.message.reply_text("💎 VIP ဝင်ရန် ငွေလွှဲပြီး ပုံပို့ပါ")
        return

    is_vip = uid in vips
    last = users.get(uid,0)
    limit = 1 if is_vip else 10
    if now()-last < limit*86400 and uid!=str(ADMIN_ID):
        await q.message.reply_text("⏳ မကြာသေးပါ")
        return

    m=await q.message.reply_text("⚙️ Generate...")
    name,img=gen_conf(vip=(q.data=="vip"))
    await q.message.reply_document(open(name,"rb"))
    await q.message.reply_photo(open(img,"rb"))
    users[uid]=now();save(USERS,users)
    os.remove(name);os.remove(img)
    await m.delete()

# === Payment Photo ===
async def photo(u,c):
    cap=f"UserID: {u.from_user.id}\nUsername: @{u.from_user.username}\nTime: {datetime.now()}"
    await c.bot.send_photo(f"@{PAY_CH}",u.message.photo[-1].file_id,caption=cap)
    await u.message.reply_text("Admin စစ်ဆေးပါမယ်")

# === Main ===
if __name__=="__main__":
    setup_wg()
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.PHOTO,photo))
    app.run_polling()
