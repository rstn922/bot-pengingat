import logging
import datetime
import re
import asyncio
import os
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import dateparser.search

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kirim pesan saat perintah /start digunakan."""
    await update.message.reply_text(
        'Halo! Saya bot pengingat. ⏰\n\n'
        'Cukup ketik pesan seperti:\n'
        '• "ingatkan aku membeli sabun jam 2 siang"\n'
        '• "ingetin meeting besok jam 9 pagi"\n'
        '• "tolong ingetin aku untuk cek email 10 menit lagi"'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani pesan pengguna dan mengekstrak waktu/tugas."""
    text = update.message.text
    
    settings = {
        'PREFER_DATES_FROM': 'future',
        'TIMEZONE': 'Asia/Jakarta', 
        'RETURN_AS_TIMEZONE_AWARE': True,
    }
    
    text_normalized = re.sub(r'(jam|pukul)?\s*(\d{1,2})\.(\d{2})', r'\1 \2:\3', text, flags=re.IGNORECASE).strip()
    
    try:
        extracted_dates = dateparser.search.search_dates(
            text_normalized, 
            languages=['id', 'en'], 
            settings=settings
        )
    except Exception as e:
        logging.error(f"Dateparser error: {e}")
        extracted_dates = None
    
    if not extracted_dates:
        await update.message.reply_text('Maaf, saya tidak dapat mendeteksi waktu. Coba gunakan format seperti "jam 15:17", "10 menit lagi", atau "besok jam 08:00".')
        return

    time_str, dt = extracted_dates[0]
    
    # --- PERBAIKAN AKURASI DETIK ---
    if "lagi" not in text_normalized.lower():
        dt = dt.replace(second=0, microsecond=0)
    
    now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
    delay = (dt - now).total_seconds()
    
    if delay <= 0:
        await update.message.reply_text(
            f'Waktu yang terdeteksi adalah: {dt.strftime("%d %b %Y %H:%M:%S")}\n'
            f'Sepertinya waktu ini sudah lewat. Pastikan Anda memasukkan waktu di masa depan!'
        )
        return
        
    # --- PROSES EKSTRAKSI TUGAS ---
    task = text_normalized.replace(time_str, '').strip()
    pattern = r'(?i)^(tolong\s+)?(ingatkan|ingetin|remind)(\s+aku|\s+saya|me)?(\s+untuk|\s+supaya|\s+agar|\s+buat|to)?\s*'
    task = re.sub(pattern, '', task).strip()
    task = re.sub(r'(?i)^(di|pada|jam|pukul)\s+', '', task).strip()
    
    if not task:
        task = "Sesuatu yang Anda jadwalkan"
        
    chat_id = update.effective_message.chat_id
    asyncio.create_task(delayed_reminder(context.bot, chat_id, dt, task))
    
    formatted_time = dt.strftime("%d %B %Y - Pukul %H:%M:%S")
    await update.message.reply_text(f'✨ Siap!\n\nSaya akan mengingatkan Anda untuk:\n👉 "{task}"\n\n⏰ Pada:\n{formatted_time}')

async def delayed_reminder(bot, chat_id, target_dt, task_text) -> None:
    """Pemantau waktu yang 100% akurat terhadap jam dunia nyata."""
    while True:
        now = datetime.datetime.now(target_dt.tzinfo) if target_dt.tzinfo else datetime.datetime.now()
        remaining = (target_dt - now).total_seconds()
        
        if remaining <= 0:
            break
            
        if remaining > 60:
            await asyncio.sleep(10)
        elif remaining > 5:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(remaining)

    try:
        await bot.send_message(
            chat_id, 
            text=f'🚨 **PENGINGAT** 🚨\n\nWaktunya untuk:\n👉 {task_text}'
        )
    except Exception as e:
        logging.error(f"Gagal mengirim pesan pengingat: {e}")

# ==============================================================================
# --- FUNGSI SERVER WEB PALSU (UNTUK MENGAKALI RENDER.COM & UPTIMEROBOT) ---
# ==============================================================================
async def web_handler(request):
    """Merespons pinger UptimeRobot agar bot disangka website yang aktif."""
    return web.Response(text="Bot is running and healthy!")

async def start_webserver(application: Application):
    """Memulai server web di latar belakang."""
    app = web.Application()
    app.router.add_get('/', web_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render memberikan port secara otomatis
    port = int(os.environ.get("PORT", 7860))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Server web penyamaran berjalan di port {port}")
# ==============================================================================

def main() -> None:
    """Menjalankan bot."""
    TOKEN = "8222875265:AAHiGudrPhJzkPm2Z9mUg5G2Dfr5g7gcHwI"

    # Tambahkan webserver ke proses startup bot
    application = Application.builder().token(TOKEN).post_init(start_webserver).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot sedang berjalan dengan dukungan Server Web Render...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
