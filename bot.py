import requests
import asyncio
import json
from datetime import datetime, timezone, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackContext

# === 🔹 Ваш TELEGRAM BOT TOKEN ===
TELEGRAM_BOT_TOKEN = "7982547314:AAGIdBosICi3u1_cY-rusmvpOjN0EyWOd7s"

# === 🔹 API USGS ===
USGS_API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# === 🔹 Границы Узбекистана ===
UZBEKISTAN_BOUNDS = {
    "min_lat": 37.0, "max_lat": 45.5,
    "min_lon": 55.0, "max_lon": 73.0
}

# === 🔹 Часовой пояс Ташкента (UTC+5) ===
TASHKENT_TZ = timezone(timedelta(hours=5))

# === 🔹 Инициализация бота ===
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# === 🔹 Файл для хранения chat_id ===
CHAT_IDS_FILE = "chat_ids.json"


# === 🔹 Функция загрузки chat_id из файла ===
def load_chat_ids():
    try:
        with open(CHAT_IDS_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))  # Загружаем список и преобразуем в set
    except (FileNotFoundError, json.JSONDecodeError):
        return set()  # Если файл не найден, создаем пустой список


# === 🔹 Функция сохранения chat_id ===
def save_chat_ids(chat_ids):
    with open(CHAT_IDS_FILE, "w", encoding="utf-8") as file:
        json.dump(list(chat_ids), file, ensure_ascii=False, indent=4)


# === 🔹 Загружаем chat_id при старте бота ===
chat_ids = load_chat_ids()


# === 🔹 Функция проверки землетрясений ===
async def check_earthquakes():
    last_checked = datetime.now(timezone.utc) - timedelta(seconds=30)

    while True:
        new_quakes = []
        now_utc = datetime.now(timezone.utc)

        try:
            params_usgs = {
                "format": "geojson",
                "starttime": (now_utc - timedelta(minutes=1)).isoformat(),
                "endtime": now_utc.isoformat(),
                "minmagnitude": 3.5,
                "maxlatitude": UZBEKISTAN_BOUNDS["max_lat"],
                "minlatitude": UZBEKISTAN_BOUNDS["min_lat"],
                "maxlongitude": UZBEKISTAN_BOUNDS["max_lon"],
                "minlongitude": UZBEKISTAN_BOUNDS["min_lon"],
                "limit": 5
            }
            response_usgs = requests.get(USGS_API_URL, params=params_usgs)
            if response_usgs.status_code == 200:
                data_usgs = response_usgs.json()
                for quake in data_usgs.get("features", []):
                    quake_time = datetime.fromtimestamp(quake["properties"]["time"] / 1000, timezone.utc)
                    if quake_time > last_checked:
                        new_quakes.append({
                            "time": quake["properties"]["time"],
                            "place": quake["properties"]["place"],
                            "magnitude": quake["properties"]["mag"],
                            "coordinates": quake["geometry"]["coordinates"][:2]
                        })
            else:
                print(f"❌ Ошибка USGS: {response_usgs.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"⚠ Ошибка сети: {e}")

        if new_quakes:
            for quake in new_quakes:
                await send_alert(quake)

        last_checked = now_utc
        await asyncio.sleep(30)  # Проверка каждые 30 секунд


# === 🔹 Функция отправки уведомлений в Telegram ===
async def send_alert(quake):
    quake_time_utc = datetime.fromtimestamp(quake["time"] / 1000, timezone.utc)
    quake_time_tashkent = quake_time_utc.astimezone(TASHKENT_TZ)
    formatted_time = quake_time_tashkent.strftime("%Y-%m-%d %H:%M:%S")

    message = (
        f"🚨 *Землетрясение только что!*\n"
        f"📍 *Место:* {quake['place']}\n"
        f"💪 *Магнитуда:* {quake['magnitude']} M\n"
        f"📅 *Время:* {formatted_time} (Ташкент)\n"
        f"🌍 *Координаты:* {quake['coordinates'][1]}, {quake['coordinates'][0]}\n"
        f"🔗 [Подробнее](https://earthquake.usgs.gov/earthquakes/eventpage)"
    )

    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения: {e}")


# === 🔹 Команда /start ===
async def start(update: Update, context: CallbackContext):
    global chat_ids
    chat_id = update.message.chat_id

    if chat_id not in chat_ids:
        chat_ids.add(chat_id)
        save_chat_ids(chat_ids)  # Сохраняем в JSON
        await update.message.reply_text("✅ Ваш Chat ID сохранен! Теперь вы будете получать уведомления о землетрясениях.")
    else:
        await update.message.reply_text("🔔 Вы уже подписаны на уведомления о землетрясениях!")


# === 🔹 Запуск бота ===
if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавляем команду /start
    application.add_handler(CommandHandler("start", start))

    # Запуск асинхронного цикла
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(check_earthquakes())

    # Запуск бота
    application.run_polling()
