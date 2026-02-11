import sqlite3
import random
from datetime import datetime, timedelta


def create_database():
    """Создание БД с таблицами"""
    conn = sqlite3.connect("university.db")
    cursor = conn.cursor()

    # Таблица аудиторий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            building TEXT NOT NULL,
            floor INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            type TEXT NOT NULL,
            equipment TEXT,
            has_computers BOOLEAN DEFAULT 0,
            computer_count INTEGER DEFAULT 0
        )
    ''')

    # Таблица бронирований
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            teacher_name TEXT NOT NULL,
            group_name TEXT,
            date TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            students_count INTEGER,
            equipment_needed TEXT,
            status TEXT DEFAULT 'approved',
            created_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id),
            UNIQUE(room_id, date, time_start)
        )
    ''')

    conn.commit()
    print("✅ Таблицы созданы!")
    return conn


def generate_rooms():
    """Генерация демо-аудиторий"""
    conn = sqlite3.connect("university.db")
    cursor = conn.cursor()

    # Очищаем старые данные
    cursor.execute("DELETE FROM rooms")

    rooms = []

    # Типы оборудования для энергетики
    energy_equipment = [
        "Стенды ТЭЦ, измерительные приборы",
        "Турбины (макеты), котельное оборудование",
        "Солнечные панели (макеты), инверторы",
        "Ветрогенераторы (макеты), контроллеры",
        "Осциллографы, генераторы сигналов",
        "Стенды электроснабжения",
        "Трансформаторы (учебные), мультиметры"
    ]

    # Корпуса 1-4 (0-5 этажи)
    for building in ['1', '2', '3', '4']:
        for floor in range(0, 6):
            for num in range(1, random.randint(6, 12)):
                number = f"{building}{floor}{num:02d}"
                capacity = random.choice([15, 20, 25, 30, 40, 50])

                # Выбираем тип аудитории
                rand = random.random()
                if rand < 0.3:  # 30% компьютерные классы
                    room_type = "Компьютерный класс"
                    equipment = "Проектор, доска, кондиционер"
                    has_comp = 1
                    comp_count = random.randint(15, min(capacity, 30))
                elif rand < 0.5:  # 20% лаборатории
                    room_type = "Лаборатория энергетики"
                    equipment = random.choice(energy_equipment)
                    has_comp = 0
                    comp_count = 0
                else:  # 50% обычные
                    room_type = "Лекционная аудитория"
                    equipment = "Проектор, доска"
                    has_comp = 0
                    comp_count = 0

                rooms.append((number, building, floor, capacity, room_type,
                              equipment, has_comp, comp_count))

    # Корпус В (0-8 этажи)
    for floor in range(0, 9):
        for num in range(1, random.randint(8, 15)):
            number = f"В{floor}{num:02d}"
            capacity = random.choice([20, 25, 30, 40, 50, 80, 100])

            rand = random.random()
            if rand < 0.25:
                room_type = "Компьютерный класс"
                equipment = "Проектор, доска, кондиционер, WiFi"
                has_comp = 1
                comp_count = random.randint(20, min(capacity, 40))
            elif rand < 0.35:
                room_type = "Лаборатория теплоэнергетики"
                equipment = random.choice(energy_equipment)
                has_comp = 0
                comp_count = 0
            elif rand < 0.4:
                room_type = "Конференц-зал"
                equipment = "Проектор, микрофоны, акустика"
                has_comp = 0
                comp_count = 0
            else:
                room_type = "Лекционная аудитория"
                equipment = "Проектор, доска, микрофоны"
                has_comp = 0
                comp_count = 0

            rooms.append((number, "В", floor, capacity, room_type,
                          equipment, has_comp, comp_count))

    # Корпус О (5-й корпус, 0-8 этажи)
    for floor in range(0, 9):
        for num in range(1, random.randint(6, 10)):
            number = f"О{floor}{num:02d}"
            capacity = random.choice([15, 20, 25, 30, 35, 40])

            rand = random.random()
            if rand < 0.3:
                room_type = "Компьютерный класс"
                equipment = "Проектор, доска, кондиционер"
                has_comp = 1
                comp_count = random.randint(15, min(capacity, 25))
            elif rand < 0.5:
                room_type = "Лаборатория ВИЭ"
                equipment = random.choice(energy_equipment)
                has_comp = 0
                comp_count = 0
            else:
                room_type = "Лекционная аудитория"
                equipment = "Проектор, доска"
                has_comp = 0
                comp_count = 0

            rooms.append((number, "О", floor, capacity, room_type,
                          equipment, has_comp, comp_count))

    # Вставляем данные
    cursor.executemany('''
        INSERT INTO rooms (number, building, floor, capacity, type, 
                         equipment, has_computers, computer_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', rooms)

    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    print(f"✅ Создано {count} аудиторий!")

    # Добавляем несколько демо-бронирований
    today = datetime.now().date()
    demo_bookings = []

    for i in range(10):
        room_id = random.randint(1, min(50, count))
        date = (today + timedelta(days=random.randint(0, 7))).strftime("%Y-%m-%d")
        hour = random.randint(8, 16)
        time_start = f"{hour:02d}:00"
        time_end = f"{hour + 2:02d}:00"

        demo_bookings.append((
            room_id,
            f"Преподаватель {i + 1}",
            f"ГрÑƒпpa-{random.randint(1, 5)}",
            date,
            time_start,
            time_end,
            random.randint(15, 40),
            "Проектор",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    try:
        cursor.executemany('''
            INSERT INTO bookings (room_id, teacher_name, group_name, date, 
                                time_start, time_end, students_count, 
                                equipment_needed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', demo_bookings)
        conn.commit()
        print(f"✅ Создано {len(demo_bookings)} демо-бронирований!")
    except:
        pass

    conn.close()


if __name__ == "__main__":
    print("🗄️ Создание демо базы данных...")
    create_database()
    generate_rooms()
    print("✅ База данных готова! Файл: university.db")