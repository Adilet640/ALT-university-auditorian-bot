import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime


class GoogleSheetsDB:
    def __init__(self, spreadsheet_id):
        """Инициализация подключения к Google Sheets"""
        # ВАЖНО: убраны лишние пробелы в конце строки!
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

        creds_file = 'credentials.json'

        if not os.path.exists(creds_file):
            raise FileNotFoundError(
                "❌ Файл credentials.json не найден! "
                "Создай Service Account и скачай JSON ключ."
            )

        creds = service_account.Credentials.from_service_account_file(
            creds_file, scopes=SCOPES
        )

        self.service = build('sheets', 'v4', credentials=creds)
        self.spreadsheet_id = spreadsheet_id
        print(f"✅ Подключено к Google Sheets (ID: {spreadsheet_id})")

    def read_rooms(self):
        """Читает все аудитории из листа 'Аудитории'"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Аудитории!A2:F1000'
            ).execute()

            rows = result.get('values', [])

            rooms = []
            for row in rows:
                if len(row) >= 4:
                    rooms.append({
                        'number': row[0],
                        'building': row[1],
                        'floor': int(row[2]) if row[2].isdigit() else 0,
                        'capacity': int(row[3]) if row[3].isdigit() else 0,
                        'equipment': row[4] if len(row) > 4 else '',
                        'computer_count': int(row[5]) if len(row) > 5 and row[5].isdigit() else 0,
                        'has_computers': int(row[5]) > 0 if len(row) > 5 and row[5].isdigit() else False
                    })

            print(f"📊 Прочитано {len(rooms)} аудиторий")
            return rooms

        except Exception as e:
            print(f"❌ Ошибка чтения аудиторий: {e}")
            return []

    def read_bookings(self, room_number=None, date=None):
        """Читает бронирования из листа 'Бронирования'"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Бронирования!A2:G1000'
            ).execute()

            rows = result.get('values', [])

            bookings = []
            for row in rows:
                if len(row) >= 5:
                    booking = {
                        'room_number': row[0],
                        'date': row[1],
                        'time_start': row[2],
                        'time_end': row[3],
                        'teacher': row[4],
                        'group': row[5] if len(row) > 5 else '',
                        'students': row[6] if len(row) > 6 else '0'
                    }

                    if room_number and booking['room_number'] != room_number:
                        continue
                    if date and booking['date'] != date:
                        continue

                    bookings.append(booking)

            print(f"📅 Прочитано {len(bookings)} бронирований")
            return bookings

        except Exception as e:
            print(f"❌ Ошибка чтения бронирований: {e}")
            return []

    def check_conflict(self, room_number, date, time_start, time_end):
        """Проверяет конфликты ПЕРЕД бронированием"""
        bookings = self.read_bookings(room_number=room_number, date=date)

        def time_to_minutes(time_str):
            h, m = map(int, time_str.split(':'))
            return h * 60 + m

        new_start = time_to_minutes(time_start)
        new_end = time_to_minutes(time_end)

        for booking in bookings:
            existing_start = time_to_minutes(booking['time_start'])
            existing_end = time_to_minutes(booking['time_end'])

            if (new_start < existing_end and new_end > existing_start):
                print(f"⚠️ КОНФЛИКТ! {room_number} занята {date} {booking['time_start']}-{booking['time_end']}")
                return True

        return False

    def add_booking(self, room_number, date, time_start, time_end,
                    teacher, group, students_count):
        """Добавляет бронирование (с защитой от двойного бронирования)"""
        if self.check_conflict(room_number, date, time_start, time_end):
            return {
                'success': False,
                'message': f'❌ Аудитория {room_number} уже занята {date} в это время!'
            }

        try:
            values = [[
                room_number,
                date,
                time_start,
                time_end,
                teacher,
                group,
                str(students_count)
            ]]

            body = {'values': values}

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Бронирования!A:G',
                valueInputOption='RAW',
                body=body
            ).execute()

            print(f"✅ Бронь добавлена: {room_number} {date} {time_start}-{time_end}")

            return {
                'success': True,
                'message': f'✅ Аудитория {room_number} забронирована на {date} {time_start}-{time_end}',
                'range': result.get('updates', {}).get('updatedRange')
            }

        except Exception as e:
            print(f"❌ Ошибка бронирования: {e}")
            return {
                'success': False,
                'message': f'❌ Ошибка: {str(e)}'
            }

    def generate_demo_rooms(self):
        """Генерирует демо-аудитории"""
        import random

        rooms_data = []

        # Корпуса 1-4 (этажи 0-5)
        for building in ['1', '2', '3', '4']:
            for floor in range(0, 6):
                for num in range(1, random.randint(4, 8)):
                    number = f"{building}{floor}{num:02d}"
                    capacity = random.choice([15, 20, 25, 30, 40, 50])

                    if random.random() < 0.3:
                        equipment = "Проектор, доска, кондиционер"
                        computers = random.randint(15, min(capacity, 30))
                    else:
                        equipment = "Проектор, доска"
                        computers = 0

                    rooms_data.append([number, building, floor, capacity, equipment, computers])

        # Корпус В (этажи 0-8)
        for floor in range(0, 9):
            for num in range(1, random.randint(5, 10)):
                number = f"В{floor}{num:02d}"
                capacity = random.choice([20, 30, 40, 50, 80, 100])

                if random.random() < 0.25:
                    equipment = "Проектор, доска, кондиционер, WiFi"
                    computers = random.randint(20, 40)
                else:
                    equipment = "Проектор, микрофоны, доска"
                    computers = 0

                rooms_data.append([number, "В", floor, capacity, equipment, computers])

        # Корпус О (этажи 0-8)
        for floor in range(0, 9):
            for num in range(1, random.randint(4, 7)):
                number = f"О{floor}{num:02d}"
                capacity = random.choice([15, 20, 25, 30, 35, 40])

                if random.random() < 0.3:
                    equipment = "Проектор, доска, кондиционер"
                    computers = random.randint(15, 25)
                else:
                    equipment = "Проектор, доска"
                    computers = 0

                rooms_data.append([number, "О", floor, capacity, equipment, computers])

        try:
            body = {'values': rooms_data}

            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Аудитории!A2',
                valueInputOption='RAW',
                body=body
            ).execute()

            print(f"✅ Загружено {len(rooms_data)} аудиторий!")
            return True

        except Exception as e:
            print(f"❌ Ошибка записи: {e}")
            return False


# Тестирование
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    spreadsheet_id = os.getenv('GOOGLE_SHEETS_ID')

    if not spreadsheet_id:
        print("❌ Ошибка: GOOGLE_SHEETS_ID не найден в .env")
        print("Пример правильного формата:")
        print("GOOGLE_SHEETS_ID=1baT1DaGxUEY0YQENfGKHV3nthJ0S_M7ETOGF8cQ59KI")
        exit(1)

    sheets = GoogleSheetsDB(spreadsheet_id)

    # Раскомментируй для генерации демо-данных (запусти ОДИН РАЗ!)
    sheets.generate_demo_rooms()

    rooms = sheets.read_rooms()
    if rooms:
        print(f"\n✅ Первые 3 аудитории:")
        for room in rooms[:3]:
            print(f"  • {room['number']} ({room['building']} корпус, этаж {room['floor']}) — {room['capacity']} мест")
    else:
        print("\n⚠️ Аудитории не найдены. Запусти генерацию:")
        print("  1. Раскомментируй строку 'sheets.generate_demo_rooms()' в этом файле")
        print("  2. Запусти: py google_sheets.py")