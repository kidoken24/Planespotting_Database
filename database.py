import sqlite3
from pathlib import Path

REPOSITORY_PATH = Path(__file__).resolve().parent
DATA_PATH = REPOSITORY_PATH / "data"
DATABASE_PATH = DATA_PATH / "planespotting.db"
PHOTOS_PATH = REPOSITORY_PATH / "photos"

def init_database():
    DATA_PATH.mkdir(parents=True ,exist_ok=True)
    (PHOTOS_PATH / "originals").mkdir(parents=True, exist_ok=True)
    (PHOTOS_PATH / "thumbnails").mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_type TEXT,
            registration TEXT,
            serial_number TEXT,
            airline TEXT,
            operator TEXT,
            airport TEXT,
            country TEXT,
            departure_airport TEXT,
            arrival_airport TEXT,
            flight_number TEXT,
            capture_date DATETIME NOT NULL,
            tags TEXT,
            filename TEXT NOT NULL,
            filepath TEXT UNIQUE NOT NULL,
            thumbnail_path TEXT
            );
    """)

    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_type ON photos (aircraft_type);""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_registration ON photos (registration);""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_airline ON photos (airline);""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_operator ON photos (operator);""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_airport ON photos (airport);""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_country ON photos (country);""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_capture_date ON photos (capture_date);""")

    connection.commit()
    connection.close()
    print(f"Database initialized at {DATABASE_PATH}")

def insert_data(aircraft_type, registration, serial_number, airline, operator, airport, country, departure_airport, arrival_airport, flight_number, capture_date, tags, filename, filepath, thumbnail_path):
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO photos (aircraft_type, registration, serial_number, airline, operator, airport, country, departure_airport, arrival_airport, flight_number, capture_date, tags, filename, filepath, thumbnail_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (aircraft_type, registration, serial_number, airline, operator, airport, country, departure_airport, arrival_airport, flight_number, capture_date, tags, filename, filepath, thumbnail_path)
    )

    connection.commit()
    connection.close()

if __name__ == "__main__":
    INITIALIZE_DATABASE = True  # Set to True to initialize the database and create tables

    if INITIALIZE_DATABASE:
        init_database()

    insert_data(
        aircraft_type="Airbus A320-200",
        registration="B-LPC",
        serial_number="05147",
        airline="Hong Kong Airlines",
        operator="Hong Kong Airlines",
        airport="Fukuoka Airport (FUK/RJFF)",
        country="Japan",
        departure_airport="Hong Kong International Airport (HKG/VHHH)",
        arrival_airport="Fukuoka Airport (FUK/RJFF)",
        flight_number="HX638",
        capture_date="2026-01-09 03:04:00Z",
        tags="Airbus, A320, Hong Kong Airlines, Fukuoka, Japan",
        filename="B-LPC_001.png",
        filepath="photos/originals/B-LPC_001.png",
        thumbnail_path="photos/thumbnails/B-LPC_001.jpg"
    )
