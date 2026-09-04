from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
import sqlite3
import shutil
import uuid
from pathlib import Path

REPOSITORY_PATH = Path(__file__).resolve().parent
DATA_PATH = REPOSITORY_PATH / "data"
DATABASE_PATH = DATA_PATH / "planespotting.db"
PHOTOS_PATH = REPOSITORY_PATH / "photos"

app = FastAPI()



app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/photos", StaticFiles(directory=PHOTOS_PATH), name="photos")

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

#API ENDPOINTS

@app.get("/api/photos")
def get_all_photos():
    connection = get_db_connection()
    cursor = connection.execute("SELECT * FROM photos ORDER BY capture_date ASC")
    photos = [dict(photo) for photo in cursor.fetchall()]
    connection.close()
    return photos

@app.post("/api/photos")
async def upload_photo(
    file: UploadFile = File(...),
    aircraft_type: str = Form(...),
    registration: str = Form(...),
    serial_number: str = Form(...),
    airline: str = Form(...),
    operator: str = Form(...),
    airport: str = Form(...),
    country: str = Form(...),
    departure_airport: str = Form(...),
    arrival_airport: str = Form(...),
    flight_number: str = Form(...),
    capture_date: str = Form(...)):

    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    original_path = PHOTOS_PATH / "originals" / unique_filename
    thumbnail_path = PHOTOS_PATH / "thumbnails" / f"thumbnail_{unique_filename}"

    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    with Image.open(original_path) as img:
        img.thumbnail((400, 400))
        img.save(thumbnail_path)

    connection = get_db_connection()
    connection.execute("""
        INSERT INTO photos (aircraft_type, registration, serial_number, airline, operator, airport, country, departure_airport, arrival_airport, flight_number, capture_date, filename, filepath, thumbnail_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (aircraft_type, registration, serial_number, airline, operator, airport, country, departure_airport, arrival_airport, flight_number, capture_date, file.filename, f"photos/originals/{unique_filename}", f"photos/thumbnails/thumbnail_{unique_filename}")
    )
    connection.commit()
    connection.close()

    return {"status": "success", "message": "Photo uploaded successfully."}