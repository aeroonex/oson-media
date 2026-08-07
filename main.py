import os
import sys
import asyncio
import json
import re
import time
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True,
    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, InlineQuery,
    InlineQueryResultAudio, InlineQueryResultCachedVideo
)
import subprocess
import base64
import aiohttp as aiohttp_lib
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '07b97d5194mshc33621b0b0c3f00p13b0fbjsn1d48ef3ccd07')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
FILE_CACHE_FILE = os.path.join(BASE_DIR, 'file_cache.json')
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')

video_storage_cache = {}
download_executor = ThreadPoolExecutor(max_workers=20)
download_semaphore = asyncio.Semaphore(15)

async def run_with_semaphore(func, *args):
    async with download_semaphore:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(download_executor, func, *args)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(auto_clean_videos())
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    await dp.stop_polling()
    polling_task.cancel()

app = FastAPI(lifespan=lifespan)
session = AiohttpSession(timeout=120)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()
async def shazam_recognize(audio_path: str) -> dict:
    with open(audio_path, 'rb') as f:
        audio_data = base64.b64encode(f.read()).decode('utf-8')
    url = "https://shazam.p.rapidapi.com/songs/detect"
    headers = {
        "content-type": "text/plain",
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "shazam.p.rapidapi.com"
    }
    async with aiohttp_lib.ClientSession() as session_http:
        async with session_http.post(url, headers=headers, data=audio_data, timeout=aiohttp_lib.ClientTimeout(total=30)) as resp:
            return await resp.json()

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

search_cache = {}
admin_state = {}
user_states = {}


async def live_type(message: types.Message, text: str, chunk_size=3, delay=0.15, parse_mode="HTML"):
    chat_id = message.chat.id
    draft_id = message.message_id

    try:
        await bot.send_message_draft(chat_id=chat_id, draft_id=draft_id, text="")
        await asyncio.sleep(0.3)
    except:
        pass

    import re as _re
    plain_text = _re.sub(r'<[^>]+>', '', text)
    words = plain_text.split()
    current = ""
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        current += (" " if current else "") + chunk
        i += chunk_size
        try:
            await bot.send_message_draft(chat_id=chat_id, draft_id=draft_id, text=current)
        except Exception as e:
            if "Flood control" in str(e) or "Too Many Requests" in str(e):
                await asyncio.sleep(2)
            else:
                break
        await asyncio.sleep(delay)

    await asyncio.sleep(0.2)
    msg = await message.answer(text, parse_mode=parse_mode)
    return msg


# === YORDAMCHI FUNKSIYALAR ===

async def auto_clean_videos():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for f in os.listdir(BASE_DIR):
            if not any(f.startswith(p) for p in ('insta_', 'shazam_', 'direct_vid_', 'voice_', 'sc_')):
                continue
            if not any(f.endswith(ext) for ext in ('.mp4', '.mp3', '.ogg', '.m4a', '.webm', '.raw', '.opus')):
                continue
            fp = os.path.join(BASE_DIR, f)
            try:
                if now - os.path.getmtime(fp) > 120:
                    os.remove(fp)
            except:
                pass
        video_storage_cache.clear()


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_user(user_id, full_name, username, inviter_id=None):
    users = load_users()
    str_id = str(user_id)
    new_user = False

    if str_id not in users:
        users[str_id] = {
            'name': full_name or "Noma'lum",
            'username': f"@{username}" if username else "Mavjud emas",
            'balance': 0,
            'invited_by': None,
            'refs': 0,
            'favorites': []
        }
        new_user = True

    if inviter_id and str_id in users and not users[str_id].get('invited_by'):
        if str_id != str(inviter_id) and str_id != str(ADMIN_ID):
            users[str_id]['invited_by'] = inviter_id
            str_inviter = str(inviter_id)
            if str_inviter in users:
                users[str_inviter]['balance'] += 500
                users[str_inviter]['refs'] += 1
                asyncio.create_task(notify_user(int(inviter_id), "🎉 <b>Yangi do'st qo'shildi!</b>\nSizga 500 so'm hisoblandi."))
                inviter_name = users[str_inviter].get('name', "Noma'lum")
                asyncio.create_task(notify_user(ADMIN_ID,
                    f"🤝 <b>Yangi Referal!</b>\n"
                    f"👤 Kim qo'shildi: {escape_html(full_name)} (ID: <code>{user_id}</code>)\n"
                    f"🗣 Kim taklif qildi: {escape_html(inviter_name)} (ID: <code>{inviter_id}</code>)"
                ))
                new_user = True

    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)
    return new_user


async def notify_user(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except:
        pass


def update_user_favorites(user_id, music_data):
    users = load_users()
    str_id = str(user_id)
    if str_id in users:
        if 'favorites' not in users[str_id]:
            users[str_id]['favorites'] = []
        if not any(f['title'] == music_data['title'] for f in users[str_id]['favorites']):
            users[str_id]['favorites'].append(music_data)
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
            return True
    return False


def load_file_cache():
    if not os.path.exists(FILE_CACHE_FILE):
        return {}
    try:
        with open(FILE_CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_file_to_cache(key, file_id, file_type, extra_data=None):
    cache = load_file_cache()
    cache[key] = {
        'file_id': file_id,
        'type': file_type,
        'data': extra_data or {}
    }
    with open(FILE_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)


def escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# === KLAVIATURALAR ===

def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text="🎵 Musiqa qidirish"), KeyboardButton(text="🤫 Anonim Xabar")],
        [KeyboardButton(text="💰 Pul ishlash"), KeyboardButton(text="❤️ Sevimlilar (/my)")],
        [KeyboardButton(text="💳 Kabinet")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_keyboard():
    keyboard = [
        [KeyboardButton(text="📝 Foydalanuvchilarga xabar yuborish")],
        [KeyboardButton(text="👥 Foydalanuvchilar ro'yxati"), KeyboardButton(text="📊 Umumiy soni")],
        [KeyboardButton(text="🔙 Oddiy foydalanuvchi rejimiga qaytish")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_marketing_caption(title, artist):
    return (
        f"🎵 <b>Nomi:</b> {escape_html(title)}\n"
        f"👤 <b>Artist/Kanal:</b> {escape_html(artist)}\n\n"
        f"🚀 <i>Istagan musiqangizni tez va oson toping!</i>\n"
        f"🤖 <b>Botimiz:</b> @oson_mediabot"
    )


def get_clean_caption(title, artist):
    return (
        f"🎵 <b>Nomi:</b> {escape_html(title)}\n"
        f"👤 <b>Artist/Kanal:</b> {escape_html(artist)}"
    )


def get_share_keyboard(music_title, index=None, share_id=None):
    keyboard_layout = []
    if index is not None:
        keyboard_layout.append([
            InlineKeyboardButton(text="❤️ Sevimlilarga qo'shish", callback_data=f"like_{index}")
        ])
    if share_id:
        keyboard_layout.append([
            InlineKeyboardButton(text="🔗 Do'stlarga ulashish", switch_inline_query=share_id)
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_layout)


# === OBUNA TEKSHIRISH ===

async def check_subscription(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return True


async def send_sub_alert(message: types.Message):
    sub_text = "⚠️ Botdan to'liq foydalanish uchun kanalimizga a'zo bo'lishingiz shart!"
    channel_url = f"https://t.me/{CHANNEL_ID.replace('@', '')}" if CHANNEL_ID else "#"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=channel_url)],
        [InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")]
    ])
    await live_type(message, sub_text)
    await message.answer("⬇️", reply_markup=keyboard)


@dp.callback_query(F.data == "check_sub")
async def handle_check_sub(callback_query: types.CallbackQuery):
    if await check_subscription(callback_query.from_user.id):
        await callback_query.answer("✅ Obuna tasdiqlandi!", show_alert=True)
        await callback_query.message.delete()
    else:
        await callback_query.answer("❌ Siz hali kanalga a'zo bo'lmagansiz!", show_alert=True)


# === SOUNDCLOUD QIDIRUV ===

def search_soundcloud_multi(query: str, limit=10):
    ydl_opts = {'quiet': True, 'noplaylist': True, 'skip_download': True, 'source_address': '0.0.0.0'}
    results = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    results.append({
                        'title': entry.get('title', "Noma'lum nom"),
                        'url': entry.get('url') or entry.get('webpage_url'),
                        'uploader': entry.get('uploader') or "Noma'lum Artist"
                    })
        except:
            pass
    return results


def download_by_url(url: str, output_path: str):
    ydl_opts = {
        'format': 'bestaudio[abr<=128]/bestaudio/best',
        'outtmpl': output_path + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'noplaylist': True,
        'source_address': '0.0.0.0',
        'concurrent_fragment_downloads': 16,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def get_url_cache_key(url: str) -> str:
    import hashlib
    return f"url_{hashlib.md5(url.encode()).hexdigest()[:16]}"


# === /START ===

@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    admin_state.pop(user_id, None)
    user_states.pop(user_id, None)

    full_name = message.from_user.full_name
    username = message.from_user.username
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("anonim_"):
        target_id = int(args[1].split("_")[1])
        if target_id == user_id:
            await message.reply("😅 O'zingizga anonim xabar yozolmaysiz.")
            return
        user_states[user_id] = f"sending_anonim_{target_id}"
        await message.reply("🤫 <b>Ushbu foydalanuvchiga yubormoqchi bo'lgan anonim xabaringizni yozing:</b>\nIsmingiz sir saqlanadi.", parse_mode="HTML")
        return

    inviter_id = None
    if len(args) > 1 and args[1].isdigit():
        inviter_id = int(args[1])

    is_new = save_user(user_id, full_name, username, inviter_id)

    if is_new and not inviter_id and user_id != ADMIN_ID:
        asyncio.create_task(notify_user(ADMIN_ID,
            f"👤 <b>Yangi foydalanuvchi!</b>\nNomi: {escape_html(full_name)}\nID: <code>{user_id}</code>"))

    if user_id == ADMIN_ID:
        await live_type(message, "👋 <b>Salom Admin! Boshqaruv paneliga xush kelibsiz!</b>")
        await message.answer("⬇️ Admin panel:", reply_markup=get_admin_keyboard())
        return

    welcome_text = (
        f"👋 <b>Salom, {escape_html(full_name)}! Botimizga xush kelibsiz!</b>\n\n"
        f"👉 <b>Musiqa topish uchun</b> shunchaki qo'shiq nomini yozib yuboring yoki ovozli xabar (voice)/video tashlang!\n"
        f"👉 <b>Instagram Reels/Post yuklash uchun</b> link tashlang!"
    )
    await live_type(message, welcome_text)
    await message.answer("⬇️ Quyidagi tugmalardan foydalaning:", reply_markup=get_main_keyboard())


# === ASOSIY TEXT HANDLER ===

@dp.message(F.text)
async def handle_all_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if text == "❌ Bekor qilish" and user_states.get(user_id) == "waiting_card_details":
        user_states.pop(user_id, None)
        await message.reply("❌ Pul yechib olish so'rovi bekor qilindi.", reply_markup=get_main_keyboard())
        return

    # Admin panel
    if user_id == ADMIN_ID:
        if text == "📝 Foydalanuvchilarga xabar yuborish":
            admin_state[ADMIN_ID] = "waiting_for_post"
            cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
            await message.reply("📨 Menga yuboriladigan xabarni (text, rasm yoki video) tashlang:", reply_markup=cancel_kb)
            return
        elif text == "❌ Bekor qilish" and admin_state.get(ADMIN_ID) == "waiting_for_post":
            admin_state.pop(ADMIN_ID, None)
            await message.reply("❌ Xabar yuborish bekor qilindi.", reply_markup=get_admin_keyboard())
            return
        elif text == "📊 Umumiy soni":
            users = load_users()
            await message.reply(f"📈 <b>Foydalanuvchilar soni:</b> {len(users)} ta", parse_mode="HTML")
            return
        elif text == "👥 Foydalanuvchilar ro'yxati":
            users = load_users()
            txt = "👥 <b>Oxirgi 15 ta foydalanuvchi:</b>\n\n"
            count = 0
            for uid, data in list(users.items())[-15:]:
                txt += f"👤 <b>Nomi:</b> {escape_html(data['name'])}\n🆔 ID: <code>{uid}</code>\n\n"
                count += 1
            if count == 0:
                txt = "Foydalanuvchilar mavjud emas."
            await message.reply(txt, parse_mode="HTML")
            return
        elif text == "🔙 Oddiy foydalanuvchi rejimiga qaytish":
            admin_state.pop(ADMIN_ID, None)
            await message.reply("Oddiy foydalanuvchi rejimiga qaytdingiz.", reply_markup=get_main_keyboard())
            return
        elif admin_state.get(ADMIN_ID) == "waiting_for_post":
            admin_state.pop(ADMIN_ID, None)
            users = load_users()
            await message.reply("🚀 Xabar barcha foydalanuvchilarga yuborilmoqda...", reply_markup=get_admin_keyboard())

            async def send_broadcast():
                success, fail = 0, 0
                for uid in users.keys():
                    try:
                        await message.copy_to(chat_id=int(uid))
                        success += 1
                        await asyncio.sleep(0.1)
                    except:
                        fail += 1
                try:
                    await bot.send_message(ADMIN_ID,
                        f"🏁 <b>Yetkazildi:</b> {success}\n❌ <b>Bloklaganlar:</b> {fail}", parse_mode="HTML")
                except:
                    pass
            asyncio.create_task(send_broadcast())
            return

    # Anonim xabar
    if user_states.get(user_id, "").startswith("sending_anonim_"):
        target_id = int(user_states[user_id].split("_")[2])
        user_states.pop(user_id, None)
        try:
            await bot.send_message(chat_id=target_id,
                text=f"🤫 <b>Sizga yangi anonim xabar keldi:</b>\n\n{escape_html(text)}", parse_mode="HTML")
            await message.reply("✅ Anonim xabaringiz yuborildi.")
        except:
            await message.reply("😔 Xabar yuborishda xatolik. Foydalanuvchi botni bloklagan bo'lishi mumkin.")
        return

    # Pul yechish karta ma'lumotlari
    if user_states.get(user_id) == "waiting_card_details":
        user_states.pop(user_id, None)
        users = load_users()
        str_id = str(user_id)
        user_balance = users.get(str_id, {}).get('balance', 0)

        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_yes_{user_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay_no_{user_id}")
            ]
        ])
        admin_text = (
            f"💸 <b>Pul yechishga so'rov!</b>\n\n"
            f"👤 Foydalanuvchi: {escape_html(message.from_user.full_name)}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Yechiladigan summa: <b>{user_balance} so'm</b>\n"
            f"💳 Karta/Hisob: <code>{escape_html(text)}</code>\n\nTanlang:"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_kb, parse_mode="HTML")
        await message.reply("✅ <b>So'rovingiz adminga yuborildi!</b>\nAdmin tasdiqlaganidan so'ng mablag'ingiz yechiladi.",
            reply_markup=get_main_keyboard(), parse_mode="HTML")
        return

    # Tugma handlerlar
    if text == "🎵 Musiqa qidirish":
        await live_type(message, "🎹 Musiqa qidirish uchun:\nShunchaki qo'shiq nomini yozib yuboring.\n\nMasalan: Konsta - Havo")
        return
    elif "Anonim Xabar" in text:
        anonim_link = f"https://t.me/oson_mediabot?start=anonim_{user_id}"
        await live_type(message, f"🤫 Sizning anonim xabar qabul qilish havolangiz:\n\n{anonim_link}\n\nUshbu linkni storiesingizga qo'ying.")
        return
    elif "Pul ishlash" in text:
        ref_link = f"https://t.me/oson_mediabot?start={user_id}"
        pul_text = (
            f"💰 Pul ishlash tizimi!\n\n"
            f"Havolani do'stlaringizga tarqating. Har bir yangi odam uchun 500 so'm olasiz!\n\n"
            f"🔗 Sizning referal havolangiz:\n{ref_link}"
        )
        await live_type(message, pul_text)
        return
    elif "Kabinet" in text:
        users = load_users()
        str_id = str(user_id)
        if str_id not in users:
            return
        user_data = users[str_id]
        text_kabinet = (
            f"👤 <b>Sizning shaxsiy kabinetingiz</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📊 Takliflar: <b>{user_data.get('refs', 0)} ta</b>\n"
            f"💰 Balans: <b>{user_data.get('balance', 0)} so'm</b>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Pulni yechib olish", callback_data="payout")]
        ])
        await live_type(message, text_kabinet)
        await message.answer("⬇️", reply_markup=kb)
        return
    elif "Sevimlilar" in text or text == "/my":
        users = load_users()
        str_id = str(user_id)
        if str_id not in users or 'favorites' not in users[str_id] or not users[str_id]['favorites']:
            await live_type(message, "😔 Sevimlilar ro'yxatingiz bo'sh. Qo'shiqlarni ❤️ tugmasi orqali saqlang.")
            return
        favs = users[str_id]['favorites']
        txt = "❤️ <b>Sizning sevimlilar ro'yxatingiz:</b>\n\n"
        btns = []
        current_row = []
        for i, music in enumerate(favs[:20]):
            txt += f"<b>{i+1}.</b> {escape_html(music['title'])} — {escape_html(music['uploader'])}\n"
            current_row.append(InlineKeyboardButton(text=f"{i+1}", callback_data=f"myfav_{i}"))
            if len(current_row) == 4:
                btns.append(current_row)
                current_row = []
        if current_row:
            btns.append(current_row)
        txt += "\n📥 Qaysi birini yuklashni tanlaysiz?"
        await live_type(message, txt)
        await message.answer("⬇️ Tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
        return

    # Instagram link
    if re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[\w-]+)', text):
        if not await check_subscription(user_id):
            await send_sub_alert(message)
            return
        try:
            await bot.send_message_draft(chat_id=message.from_user.id, draft_id=message.message_id, text="⏳")
        except:
            pass
        await handle_instagram_video(message, None)
        return

    # Musiqa qidirish (oddiy matn)
    if not await check_subscription(user_id):
        await send_sub_alert(message)
        return
    status_msg = await message.reply(f"🔍 <b>'{escape_html(text)}' qidirilyapti...</b>", parse_mode="HTML")
    await process_text_search_with_custom_ui(message, text, status_msg, user_id)


# === PUL YECHIB OLISH ===

@dp.callback_query(F.data == "payout")
async def handle_payout_request(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    users = load_users()
    str_id = str(user_id)
    if str_id not in users:
        return
    user_balance = users[str_id].get('balance', 0)
    if user_balance < 1000:
        await callback_query.answer(
            f"😔 Minimal pul yechish summasi 1,000 so'm. Sizning balansingiz: {user_balance} so'm", show_alert=True)
        return
    user_states[user_id] = "waiting_card_details"
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    await bot.send_message(chat_id=user_id,
        text="💳 <b>Pul o'tkaziladigan karta raqami yoki click raqamingizni yuboring:</b>\nMasalan: <code>8600 1234 5678 9012</code>",
        reply_markup=cancel_kb, parse_mode="HTML")
    await callback_query.answer()


# === ADMIN TO'LOV TASDIQLASH ===

@dp.callback_query(F.data.startswith("pay_"))
async def handle_admin_payment_decision(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Siz admin emassiz!")
        return
    parts = callback_query.data.split("_")
    action = parts[1]
    target_user_id = parts[2]
    users = load_users()
    if target_user_id not in users:
        await callback_query.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    user_balance = users[target_user_id].get('balance', 0)

    if action == "yes":
        users[target_user_id]['balance'] = 0
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        await bot.send_message(chat_id=int(target_user_id),
            text=f"🎉 <b>Sizning pul yechish so'rovingiz tasdiqlandi!</b>\n<b>{user_balance} so'm</b> o'tkazildi.",
            parse_mode="HTML")
        await callback_query.message.edit_text(
            f"✅ Ushbu foydalanuvchiga <b>{user_balance} so'm</b> yechildi va tasdiqlandi.", parse_mode="HTML")
        await callback_query.answer("To'lov tasdiqlandi.")
    elif action == "no":
        await bot.send_message(chat_id=int(target_user_id),
            text="❌ <b>Sizning pul yechish so'rovingiz admin tomonidan rad etildi!</b>\nHisobingizdagi pul saqlanib qoldi.",
            parse_mode="HTML")
        await callback_query.message.edit_text("❌ So'rov rad etildi. Foydalanuvchining puli hisobida qoldi.", parse_mode="HTML")
        await callback_query.answer("To'lov rad etildi.")


# === INSTAGRAM YUKLASH ===

async def handle_instagram_video(message: types.Message, status_msg: types.Message):
    chat_id = message.from_user.id
    draft_id = message.message_id
    url = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[\w-]+)', message.text).group(1)

    local_file = os.path.join(BASE_DIR, f"insta_{message.message_id}.mp4")

    ydl_opts = {
        'format': 'best',
        'outtmpl': local_file,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'format_sort': ['res', 'br'],
        'concurrent_fragment_downloads': 16,
        'source_address': '0.0.0.0',
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
        'socket_timeout': 15,
        'retries': 3,
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
    }

    try:
        def extract_and_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        loop = asyncio.get_event_loop()

        await loop.run_in_executor(download_executor, extract_and_download)

        if os.path.exists(local_file):
            file_size = os.path.getsize(local_file)
            file_mb = round(file_size / 1024 / 1024, 1)

            if file_size > 49 * 1024 * 1024:
                compressed = local_file.replace('.mp4', '_c.mp4')
                target_bitrate = int(49 * 8 * 1024 / max(1, file_size / 1024 / 1024) * 1024)
                await loop.run_in_executor(download_executor, lambda: subprocess.run(
                    f'ffmpeg -i "{local_file}" -c:v libx264 -b:v {target_bitrate}k -maxrate {target_bitrate}k -bufsize {target_bitrate*2}k -preset fast -c:a aac -b:a 128k "{compressed}" -y',
                    shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                ))
                os.remove(local_file)
                os.rename(compressed, local_file)

            caption = get_marketing_caption("Instagram", "Post")
            msg = await bot.send_video(chat_id=chat_id, video=FSInputFile(local_file), caption=caption, parse_mode="HTML")
            if status_msg:
                try:
                    await status_msg.delete()
                except:
                    pass
            video_storage_cache[local_file] = time.time()

            cache_key = f"vid_{message.message_id}"
            save_file_to_cache(cache_key, msg.video.file_id, "video", {"title": "Instagram Video", "uploader": "Oson Media Bot"})

            video_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", switch_inline_query=cache_key)]
            ])
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg.message_id, reply_markup=video_kb)
        else:
            raise Exception("Video fayli topilmadi.")

    except Exception as e:
        print(f"Instagram Yuklash Xatosi: {e}")
        await bot.send_message(chat_id=chat_id,
            text="😔 Videoni yuklab bo'lmadi. Kuki fayli eskirgan yoki havola xato.")
        if status_msg:
            try:
                await status_msg.delete()
            except:
                pass
        if os.path.exists(local_file):
            try:
                os.remove(local_file)
            except:
                pass


# === VIDEO/VOICE SHAZAM ===

async def auto_recognize_and_download(message, status_msg, source_file, source_type="video"):
    user_id = message.from_user.id
    draft_id = message.message_id
    local_audio = source_file.rsplit('.', 1)[0] + '_shazam.raw'

    try:
        loop = asyncio.get_event_loop()

        try:
            await bot.send_message_draft(chat_id=user_id, draft_id=draft_id, text="⏳")
        except:
            pass

        await loop.run_in_executor(download_executor, lambda: subprocess.run(
            f'ffmpeg -i "{source_file}" -vn -ss 3 -t 5 -ar 44100 -ac 1 -f s16le "{local_audio}" -y',
            shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ))

        result = await shazam_recognize(local_audio)
        logger.info(f"Shazam natija: {json.dumps(result, ensure_ascii=False)[:500]}")

        if not result.get('track'):
            logger.info("Shazam: musiqa topilmadi")
            await message.answer("😔 Afsuski, musiqa aniqlay olmadim.", parse_mode="HTML")
            return

        track = result['track']
        title = track.get('title', 'Unknown')
        artist = track.get('subtitle', 'Unknown')
        query = f"{artist} - {title}"

        await message.answer(f"🎵 <b>Topildi:</b> {escape_html(query)}\n⏳ <b>Yuklab olinyapti...</b>", parse_mode="HTML")

        # Keshda bormi tekshirish
        results = await loop.run_in_executor(download_executor, search_soundcloud_multi, query, 3)
        if not results:
            await message.answer(
                f"🎵 <b>Topildi:</b> {escape_html(query)}\n\n"
                "😔 Afsuski, yuklab olish uchun manba topilmadi.",
                parse_mode="HTML")
            return

        selected = results[0]

        # URL keshda bormi
        url_key = get_url_cache_key(selected['url'])
        file_cache = load_file_cache()
        if url_key in file_cache and file_cache[url_key].get('file_id'):
            audio_msg = await bot.send_audio(
                chat_id=user_id,
                audio=file_cache[url_key]['file_id'],
                title=title,
                performer=artist,
                caption=get_marketing_caption(title, artist),
                parse_mode="HTML"
            )
            keyboard = get_share_keyboard(title, share_id=f"aud_{audio_msg.audio.file_id[:15]}")
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=audio_msg.message_id, reply_markup=keyboard)
            return

        # Yangi yuklab olish
        music_path = os.path.join(BASE_DIR, f"shazam_{message.message_id}")
        await loop.run_in_executor(download_executor, download_by_url, selected['url'], music_path)

        downloaded_file = None
        for f in os.listdir(BASE_DIR):
            if f.startswith(f"shazam_{message.message_id}"):
                downloaded_file = os.path.join(BASE_DIR, f)
                break

        if not downloaded_file:
            await message.answer(
                f"🎵 <b>Topildi:</b> {escape_html(query)}\n\n😔 Yuklab bo'lmadi.",
                parse_mode="HTML")
            return

        audio_msg = await bot.send_audio(
            chat_id=user_id,
            audio=FSInputFile(downloaded_file),
            title=title,
            performer=artist,
            caption=get_marketing_caption(title, artist),
            parse_mode="HTML"
        )

        save_file_to_cache(url_key, audio_msg.audio.file_id, "audio",
            {"title": title, "uploader": artist})
        cache_key = f"aud_{audio_msg.audio.file_id[:15]}"
        save_file_to_cache(cache_key, audio_msg.audio.file_id, "audio",
            {"title": title, "uploader": artist})

        keyboard = get_share_keyboard(title, share_id=cache_key)
        await bot.edit_message_reply_markup(chat_id=user_id, message_id=audio_msg.message_id, reply_markup=keyboard)

        os.remove(downloaded_file)

    except Exception as e:
        print(f"Shazam xatosi: {e}")
        try:
            await message.answer("😔 Tahlil jarayonida xatolik yuz berdi.", parse_mode="HTML")
        except:
            pass
    finally:
        if os.path.exists(local_audio): os.remove(local_audio)
        if os.path.exists(source_file): os.remove(source_file)


@dp.message(F.video)
async def handle_user_sent_video(message: types.Message):
    logger.info(f"VIDEO RECEIVED from {message.from_user.id}, file_id={message.video.file_id}")
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        logger.info("User not subscribed")
        await send_sub_alert(message)
        return

    logger.info("User subscribed, starting shazam")
    try:
        await bot.send_message_draft(chat_id=message.from_user.id, draft_id=message.message_id, text="⏳")
    except:
        pass

    video_file = await bot.get_file(message.video.file_id)
    local_video = os.path.join(BASE_DIR, f"direct_vid_{message.message_id}.mp4")
    await bot.download_file(video_file.file_path, local_video)
    logger.info(f"Video downloaded: {local_video}")

    await auto_recognize_and_download(message, None, local_video, "video")


@dp.message(F.voice)
async def handle_user_sent_voice(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await send_sub_alert(message)
        return

    try:
        await bot.send_message_draft(chat_id=message.from_user.id, draft_id=message.message_id, text="⏳")
    except:
        pass

    voice_file = await bot.get_file(message.voice.file_id)
    local_voice = os.path.join(BASE_DIR, f"voice_{message.message_id}.ogg")
    await bot.download_file(voice_file.file_path, local_voice)

    await auto_recognize_and_download(message, None, local_voice, "ovoz")


# === MATNLI QIDIRUV VA NATIJALAR ===

async def process_text_search_with_custom_ui(message, query, status_msg, target_chat_id, limit=10):
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(download_executor, search_soundcloud_multi, query, limit)
    if not results:
        return await status_msg.edit_text("😔 Topilmadi.")
    search_cache[target_chat_id] = results

    txt = f"🎧 <b>Siz uchun topilgan musiqalar:</b>\n\n"
    for i, res in enumerate(results):
        txt += f"<b>{i+1}.</b> {escape_html(res['title'])} — {escape_html(res['uploader'])}\n"

    btns = []
    current_row = []
    for i in range(len(results)):
        current_row.append(InlineKeyboardButton(text=f"{i+1}", callback_data=f"dl_{i}"))
        if len(current_row) == 4:
            btns.append(current_row)
            current_row = []
    if current_row:
        btns.append(current_row)
    await status_msg.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")


# === YUKLAB OLISH ===

@dp.callback_query(F.data.startswith("dl_"))
async def handle_download_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    results = search_cache.get(user_id)
    if not results or index >= len(results):
        return
    selected = results[index]
    await callback_query.answer("⏳ Yuklanmoqda...")

    # Keshda bor bo'lsa — tezkor yuborish
    url_key = get_url_cache_key(selected['url'])
    file_cache = load_file_cache()
    if url_key in file_cache and file_cache[url_key].get('file_id'):
        try:
            cached = file_cache[url_key]
            audio_msg = await bot.send_audio(
                chat_id=user_id,
                audio=cached['file_id'],
                title=cached['data'].get('title', selected['title']),
                performer=cached['data'].get('uploader', selected['uploader']),
                caption=get_marketing_caption(selected['title'], selected['uploader']),
                parse_mode="HTML"
            )
            selected_key = f"sel_{user_id}_{index}"
            save_file_to_cache(selected_key, "none", "selected_info", selected)
            share_key = f"aud_{audio_msg.audio.file_id[:15]}"
            save_file_to_cache(share_key, audio_msg.audio.file_id, "audio",
                {"title": selected['title'], "uploader": selected['uploader']})
            keyboard = get_share_keyboard(selected['title'], index=index, share_id=share_key)
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=audio_msg.message_id, reply_markup=keyboard)
            return
        except:
            pass

    status_msg = await callback_query.message.answer("⏳ <b>Yuklanyapti...</b>", parse_mode="HTML")
    path = os.path.join(BASE_DIR, f"music_{callback_query.id}")

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(download_executor, download_by_url, selected['url'], path)
        downloaded_file = None
        for file in os.listdir(BASE_DIR):
            if file.startswith(f"music_{callback_query.id}"):
                downloaded_file = os.path.join(BASE_DIR, file)
                break

        if downloaded_file:
            audio_msg = await bot.send_audio(
                chat_id=user_id,
                audio=FSInputFile(downloaded_file),
                title=selected['title'],
                performer=selected['uploader'],
                caption=get_marketing_caption(selected['title'], selected['uploader']),
                parse_mode="HTML"
            )

            # URL bo'yicha keshga saqlash — keyingi safar 1 sekundda yuboriladi
            save_file_to_cache(url_key, audio_msg.audio.file_id, "audio",
                {"title": selected['title'], "uploader": selected['uploader']})

            cache_key = f"aud_{audio_msg.audio.file_id[:15]}"
            save_file_to_cache(cache_key, audio_msg.audio.file_id, "audio",
                {"title": selected['title'], "uploader": selected['uploader']})

            selected_key = f"sel_{user_id}_{index}"
            save_file_to_cache(selected_key, "none", "selected_info", selected)

            keyboard = get_share_keyboard(selected['title'], index=index, share_id=cache_key)
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=audio_msg.message_id, reply_markup=keyboard)

            await status_msg.delete()
            os.remove(downloaded_file)
        else:
            raise Exception("Fayl topilmadi")
    except:
        await status_msg.edit_text("😔 Yuklab bo'lmadi.")
        for file in os.listdir(BASE_DIR):
            if file.startswith(f"music_{callback_query.id}"):
                try:
                    os.remove(os.path.join(BASE_DIR, file))
                except:
                    pass


# === SEVIMLILARGA QO'SHISH ===

@dp.callback_query(F.data.startswith("like_"))
async def process_favorites_like(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    selected_key = f"sel_{user_id}_{index}"
    cache = load_file_cache()

    if selected_key in cache:
        music_data = cache[selected_key]['data']
        res = update_user_favorites(user_id, music_data)
        if res:
            await callback_query.answer("❤️ Sevimlilar ro'yxatiga qo'shildi!", show_alert=True)
        else:
            await callback_query.answer("Bu musiqa allaqachon sevimlilaringizda bor.", show_alert=True)
    else:
        await callback_query.answer("Xatolik! Iltimos, musiqani qayta qidirib ko'ring.", show_alert=True)


@dp.callback_query(F.data.startswith("myfav_"))
async def handle_myfav_click(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    users = load_users()
    str_id = str(user_id)
    if str_id not in users or 'favorites' not in users[str_id]:
        return
    favs = users[str_id]['favorites']
    if index >= len(favs):
        return
    selected = favs[index]

    # Keshda bor bo'lsa tezkor yuborish
    url_key = get_url_cache_key(selected['url'])
    file_cache = load_file_cache()
    if url_key in file_cache and file_cache[url_key].get('file_id'):
        try:
            await bot.send_audio(
                chat_id=user_id,
                audio=file_cache[url_key]['file_id'],
                title=selected['title'],
                performer=selected['uploader'],
                caption=get_marketing_caption(selected['title'], selected['uploader']),
                parse_mode="HTML"
            )
            await callback_query.answer()
            return
        except:
            pass

    status_msg = await callback_query.message.answer("⏳ <b>Sevimlilardan yuklanyapti...</b>", parse_mode="HTML")
    path = os.path.join(BASE_DIR, f"music_fav_{callback_query.id}")

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(download_executor, download_by_url, selected['url'], path)
        downloaded_file = None
        for file in os.listdir(BASE_DIR):
            if file.startswith(f"music_fav_{callback_query.id}"):
                downloaded_file = os.path.join(BASE_DIR, file)
                break
        if downloaded_file:
            audio_msg = await bot.send_audio(
                chat_id=user_id,
                audio=FSInputFile(downloaded_file),
                title=selected['title'],
                performer=selected['uploader'],
                caption=get_marketing_caption(selected['title'], selected['uploader']),
                parse_mode="HTML"
            )
            save_file_to_cache(url_key, audio_msg.audio.file_id, "audio",
                {"title": selected['title'], "uploader": selected['uploader']})
            await status_msg.delete()
            os.remove(downloaded_file)
    except:
        await status_msg.edit_text("😔 Yuklab bo'lmadi.")
        for file in os.listdir(BASE_DIR):
            if file.startswith(f"music_fav_{callback_query.id}"):
                try:
                    os.remove(os.path.join(BASE_DIR, file))
                except:
                    pass


# === INLINE QUERY ===

@dp.inline_query()
async def inline_share_handler(inline_query: InlineQuery):
    query = inline_query.query
    results = []
    cache = load_file_cache()

    if query in cache:
        item = cache[query]
        file_id = item['file_id']
        file_type = item['type']

        if file_type == "audio":
            results.append(
                InlineQueryResultAudio(
                    id=query,
                    audio_file_id=file_id,
                    title=item['data'].get('title', 'Musiqa'),
                    caption=get_clean_caption(item['data'].get('title', 'Musiqa'), item['data'].get('uploader', 'Artist')),
                    parse_mode="HTML"
                )
            )
        elif file_type == "video":
            results.append(
                InlineQueryResultCachedVideo(
                    id=query,
                    video_file_id=file_id,
                    title="Instagram Video",
                    description="Oson Media orqali yuklangan video",
                    caption=get_clean_caption("Instagram", "Post"),
                    parse_mode="HTML"
                )
            )

    await inline_query.answer(results, cache_time=1)


@app.get('/')
async def home():
    return {"status": "Bot faol!", "bot": "@oson_mediabot"}
