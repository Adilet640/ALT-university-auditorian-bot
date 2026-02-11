from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os
import sys
from dotenv import load_dotenv
import traceback
from datetime import datetime
import re

# Добавляем корень проекта в путь, чтобы корректно импортировать google_sheets.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from google_sheets import GoogleSheetsDB

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("⚠️ ОШИБКА: API ключ OpenAI не найден в файле .env")
else:
    openai.api_key = api_key
    print("✅ OpenAI API ключ загружен")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    message: str


class BookingRequest(BaseModel):
    room_number: str
    teacher_name: str
    group_name: str
    date: str
    time_start: str
    time_end: str
    students_count: int
    equipment_needed: str = ""


# Инициализация работы с Google Sheets
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID")
if not SPREADSHEET_ID:
    print("⚠️ GOOGLE_SHEETS_ID не найден в .env — работа с таблицей будет недоступна")
    sheets_db = None
else:
    try:
        sheets_db = GoogleSheetsDB(SPREADSHEET_ID)
    except Exception as e:
        print(f"❌ Ошибка инициализации GoogleSheetsDB: {e}")
        sheets_db = None


def find_suitable_rooms(query: str):
    """Поиск аудиторий по запросу"""
    if sheets_db is None:
        print("⚠️ sheets_db не инициализирован, возвращаю пустой список аудиторий")
        return []

    query_lower = query.lower()
    rooms = sheets_db.read_rooms()  # список словарей из Google Sheets

    filtered = []

    for room in rooms:
        # Клонируем, чтобы добавить поля
        r = dict(room)

        # Тип аудитории по умолчанию определяем по наличию компьютеров
        if r.get("has_computers"):
            r["type"] = "Компьютерный класс"
        else:
            r["type"] = "Лекционная аудитория"

        # Фильтр по компьютерам
        if any(w in query_lower for w in ["компьютер", "пк", "компьютерный", "класс"]):
            if not r.get("has_computers"):
                continue

        # Фильтр по проектору / оборудованию
        if "проектор" in query_lower:
            if "проектор" not in str(r.get("equipment", "")).lower():
                continue

        # Фильтр по вместимости (берём первое число из запроса)
        numbers = re.findall(r"\d+", query)
        if numbers:
            capacity_needed = int(numbers[0])
            if int(r.get("capacity", 0)) < capacity_needed:
                continue

        # Фильтр по лаборатории
        if "лаборатор" in query_lower:
            if "лаборато" not in r["type"].lower() and "лаборато" not in str(r.get("equipment", "")).lower():
                continue

        filtered.append(r)

    # Добавляем искусственный id для фронтенда
    for idx, r in enumerate(filtered, start=1):
        r["id"] = idx

    return filtered


@app.get("/")
async def root():
    return {"message": "University FAQ Bot v2.0 is running! 🚀"}


@app.post("/api/query")
async def process_query(request: QueryRequest):
    try:
        print(f"\n📩 Получен запрос: {request.message}")

        suitable_rooms = find_suitable_rooms(request.message)
        print(f"🔍 Найдено аудиторий: {len(suitable_rooms)}")

        context = "База данных аудиторий университета:\n\n"
        if suitable_rooms:
            for room in suitable_rooms[:5]:
                context += f"Кабинет {room['number']} (корпус {room['building']}, этаж {room['floor']}):\n"
                context += f"- Вместимость: {room['capacity']} человек\n"
                context += f"- Тип: {room['type']}\n"
                context += f"- Оборудование: {room['equipment']}\n"
                if room['has_computers']:
                    context += f"- Компьютеров: {room['computer_count']} шт\n"
                context += "\n"
        else:
            context += "К сожалению, точно подходящих аудиторий не найдено.\n"

        print("🤖 Отправляю запрос в OpenAI...")

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """Ты - умный помощник университета энергетики.
                    Помогаешь находить подходящие аудитории.
                    Отвечай кратко и по делу. Рекомендуй лучший вариант.
                    Если несколько вариантов - укажи лучший и 1-2 альтернативы."""
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nЗапрос: {request.message}\n\nДай рекомендацию:"
                }
            ],
            temperature=0.7,
            max_tokens=300
        )

        answer = response["choices"][0]["message"]["content"]
        print("✅ Ответ от OpenAI получен успешно!\n")

        return {
            "success": True,
            "answer": answer,
            "rooms": suitable_rooms[:5]
        }

    except Exception as e:
        print(f"\n❌ ОШИБКА: {type(e).__name__}")
        print(f"❌ Детали: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.post("/api/book")
async def create_booking(booking: BookingRequest):
    """Создание бронирования"""
    try:
        if sheets_db is None:
            return {
                "success": False,
                "message": "❌ Google Sheets недоступен (нет GOOGLE_SHEETS_ID или ошибка инициализации)"
            }

        # Проверяем конфликты через Google Sheets
        if sheets_db.check_conflict(
            room_number=booking.room_number,
            date=booking.date,
            time_start=booking.time_start,
            time_end=booking.time_end,
        ):
            return {
                "success": False,
                "message": f"❌ Аудитория {booking.room_number} занята в это время!"
            }

        # Создаем бронирование в листе "Бронирования"
        result = sheets_db.add_booking(
            room_number=booking.room_number,
            date=booking.date,
            time_start=booking.time_start,
            time_end=booking.time_end,
            teacher=booking.teacher_name,
            group=booking.group_name,
            students_count=booking.students_count,
        )

        if not result.get("success"):
            return result

        # Находим информацию об аудитории по номеру
        rooms = sheets_db.read_rooms()
        room = next((r for r in rooms if r["number"] == booking.room_number), None)

        return {
            "success": True,
            "message": result.get("message", "✅ Бронирование создано!"),
            "booking_room_number": booking.room_number,
            "room": room
        }

    except Exception as e:
        print(f"Ошибка создания брони: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bookings")
async def get_bookings(date: str = None):
    """Получить бронирования"""
    if sheets_db is None:
        return {"bookings": []}

    # Читаем бронирования (с фильтром по дате, если указан)
    bookings = sheets_db.read_bookings(date=date)

    # Чтобы показать корпус, подгружаем аудитории
    rooms = sheets_db.read_rooms()
    rooms_by_number = {r["number"]: r for r in rooms}

    result = []
    for b in bookings:
        room = rooms_by_number.get(b["room_number"], {})
        result.append(
            {
                "number": b["room_number"],
                "building": room.get("building", ""),
                "teacher_name": b.get("teacher", ""),
                "group_name": b.get("group", ""),
                "date": b.get("date", ""),
                "time_start": b.get("time_start", ""),
                "time_end": b.get("time_end", ""),
                "students_count": int(b.get("students", 0) or 0),
            }
        )

    # Можно ограничить количество, но пока отдаем все
    return {"bookings": result}


@app.get("/api/rooms")
async def get_all_rooms(
    building: str | None = None,
    floor: int | None = None,
    type: str | None = None,
    capacity: int | None = None,
    equipment: str | None = None,
):
    """Получить аудитории (для ручного поиска) из Google Sheets"""
    if sheets_db is None:
        return {"rooms": []}

    rooms = sheets_db.read_rooms()
    filtered = []

    for room in rooms:
        r = dict(room)

        # Тип аудитории — как и в find_suitable_rooms
        if r.get("has_computers"):
            r["type"] = "Компьютерный класс"
        else:
            r["type"] = "Лекционная аудитория"

        if building and str(r.get("building")) != str(building):
            continue
        if floor is not None and int(r.get("floor", 0)) != int(floor):
            continue
        if capacity is not None and int(r.get("capacity", 0)) < int(capacity):
            continue
        if equipment and equipment.lower() not in str(r.get("equipment", "")).lower():
            continue
        if type:
            t = type.lower()
            if "компьютер" in t and not r.get("has_computers"):
                continue
            # для других типов пока простой фильтр по подстроке
            if "компьютер" not in t and t not in r["type"].lower():
                continue

        filtered.append(r)

    # Добавляем id для фронтенда
    for idx, r in enumerate(filtered, start=1):
        r["id"] = idx

    return {"rooms": filtered}


if __name__ == "__main__":
    import uvicorn

    print("\n🚀 Запускаю сервер v2.0 на http://localhost:8000")
    print("📝 Открой frontend/index.html в браузере\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)