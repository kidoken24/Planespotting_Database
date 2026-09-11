from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
import sqlite3
import shutil
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone

REPOSITORY_PATH = Path(__file__).resolve().parent
DATA_PATH = REPOSITORY_PATH / "data"
DATABASE_PATH = DATA_PATH / "planespotting.db"
PHOTOS_PATH = REPOSITORY_PATH / "photos"

# --- SECURITY CONFIGURATION ---
# Change this to whatever master password you want!
MASTER_PASSWORD = "admin" 

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/photos", StaticFiles(directory=PHOTOS_PATH), name="photos")

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

# --- SECURITY DEPENDENCY ---
# This checks if the React frontend sent the correct password token
def verify_token(authorization: str = Header(None)):
    if authorization != f"Bearer {MASTER_PASSWORD}":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

class LoginRequest(BaseModel):
    password: str

@app.post("/api/login")
def login(request: LoginRequest):
    if request.password == MASTER_PASSWORD:
        return {"token": MASTER_PASSWORD}
    raise HTTPException(status_code=401, detail="Invalid Password")

# --- PROTECTED API ENDPOINTS ---
# Notice we added `dependencies=[Depends(verify_token)]` to lock these down!

@app.get("/api/photos", dependencies=[Depends(verify_token)])
def get_all_photos():
    connection = get_db_connection()
    cursor = connection.execute("SELECT * FROM photos ORDER BY capture_date ASC")
    photos = [dict(photo) for photo in cursor.fetchall()]
    connection.close()
    return photos

@app.post("/api/photos", dependencies=[Depends(verify_token)])
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
    capture_date: str = Form(None)
):
    # (Your exact upload logic remains completely unchanged here)
    safe_airline = re.sub(r'[\\/*?:"<>|]', "", airline.strip()) or "Unknown_Airline"
    safe_reg = re.sub(r'[\\/*?:"<>|]', "", registration.strip()) or "Unknown_Registration"

    original_dir = PHOTOS_PATH / "originals" / safe_airline / safe_reg
    thumbnail_dir = PHOTOS_PATH / "thumbnails" / safe_airline / safe_reg

    original_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_dir.mkdir(parents=True, exist_ok=True)

    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    original_path = original_dir / unique_filename
    thumbnail_path = thumbnail_dir / f"thumbnail_{unique_filename}"

    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    utc_now = datetime.now(timezone.utc)
    final_capture_date_iso = utc_now.isoformat()

    with Image.open(original_path) as img:
        img.thumbnail((400, 400))
        img.save(thumbnail_path)

        exif = img.getexif()
        if exif and 36867 in exif:
            dt_str = exif[36867]
            try:
                dt_obj = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                dt_utc = dt_obj.replace(tzinfo=timezone.utc)
                final_capture_date_iso = dt_utc.isoformat()
            except ValueError:
                pass

    if capture_date:
        final_capture_date_iso = capture_date

    db_original_path = f"photos/originals/{safe_airline}/{safe_reg}/{unique_filename}"
    db_thumbnail_path = f"photos/thumbnails/{safe_airline}/{safe_reg}/thumbnail_{unique_filename}"

    connection = get_db_connection()
    connection.execute("""
        INSERT INTO photos (
            aircraft_type, registration, serial_number, airline, operator, 
            airport, country, departure_airport, arrival_airport, flight_number, 
            capture_date, filename, filepath, thumbnail_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            aircraft_type, registration, serial_number, airline, operator, 
            airport, country, departure_airport, arrival_airport, flight_number, 
            final_capture_date_iso, file.filename, db_original_path, db_thumbnail_path
        )
    )
    connection.commit()
    connection.close()

    return {"status": "success", "message": "Photo uploaded successfully."}

@app.delete("/api/photos/{photo_id}", dependencies=[Depends(verify_token)])
def delete_photo(photo_id: int):
    connection = get_db_connection()
    cursor = connection.execute("SELECT filepath, thumbnail_path FROM photos WHERE id = ?", (photo_id,))
    photo = cursor.fetchone()
    
    if photo:
        connection.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        connection.commit()
        try:
            original_file = REPOSITORY_PATH / photo["filepath"]
            thumbnail_file = REPOSITORY_PATH / photo["thumbnail_path"]
            if original_file.exists(): original_file.unlink()
            if thumbnail_file.exists(): thumbnail_file.unlink()
        except Exception as e:
            print(f"Error deleting physical files: {e}")
            
    connection.close()
    return {"status": "success", "message": "Photo deleted"}