from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
import sqlite3
import shutil
import uuid
import re
import os
import jwt # NEW
from dotenv import load_dotenv # NEW
from pathlib import Path
from datetime import datetime, timezone, timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler # NEW
from slowapi.util import get_remote_address # NEW
from slowapi.errors import RateLimitExceeded # NEW

# Load variables from the hidden .env file
load_dotenv()

REPOSITORY_PATH = Path(__file__).resolve().parent
DATA_PATH = REPOSITORY_PATH / "data"
DATABASE_PATH = DATA_PATH / "planespotting.db"
PHOTOS_PATH = REPOSITORY_PATH / "photos"

# --- SECURITY CONFIGURATION ---
# Read from .env instead of hardcoding!
MASTER_PASSWORD = os.getenv("MASTER_PASSWORD")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Setup Rate Limiter (tracks requests by the user's IP address)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

# Register the rate limiter with FastAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/photos", StaticFiles(directory=PHOTOS_PATH), name="photos")

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

# --- JWT LOGIC ---
def create_access_token():
    # Creates a cryptographically signed token that expires in 24 hours
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {"sub": "admin", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized Access")
    
    # Extract the token part from "Bearer <token>"
    token = authorization.split(" ")[1]
    
    try:
        # If the token is modified or expired, this will throw an error
        jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

class LoginRequest(BaseModel):
    password: str

@app.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, login_data: LoginRequest):
    if login_data.password == MASTER_PASSWORD:
        # Instead of returning the password, we return the secure, temporary JWT!
        token = create_access_token()
        return {"token": token}
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
    operator: str = Form(""),
    airport: str = Form(""),
    country: str = Form(""),
    departure_airport: str = Form(""),
    arrival_airport: str = Form(""),
    flight_number: str = Form(""),
    capture_date: str = Form(None)
):
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

    # Default to current UTC time if no EXIF exists
    utc_now = datetime.now(timezone.utc)
    final_capture_date_iso = utc_now.isoformat()

    with Image.open(original_path) as img:
        img.thumbnail((400, 400))
        img.save(thumbnail_path)

        # --- NEW ROBUST EXIF EXTRACTION ---
        try:
            exif_data = img.getexif()
            if exif_data:
                # 34665 is the specific tag for the Exif Sub-IFD where dates are stored
                exif_ifd = exif_data.get_ifd(34665)
                
                # 36867 is the DateTimeOriginal tag
                if 36867 in exif_ifd:
                    dt_str = exif_ifd[36867] # e.g. "2026:01:09 12:06:00"
                    
                    # 36881 is the OffsetTimeOriginal tag (e.g. "+09:00" for JST)
                    # We default to "+00:00" (UTC) if the camera didn't record a timezone
                    offset_str = exif_ifd.get(36881, "+00:00")
                    
                    # Parse the offset string into hours and minutes
                    sign = 1 if offset_str[0] == '+' else -1
                    hours = int(offset_str[1:3])
                    minutes = int(offset_str[4:6])
                    tz_offset = timezone(timedelta(hours=hours * sign, minutes=minutes * sign))
                    
                    # Convert the camera string into a Timezone-Aware Datetime object
                    dt_obj = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    dt_obj = dt_obj.replace(tzinfo=tz_offset)
                    
                    # Calibrate to absolute UTC and save as ISO string for the database
                    dt_utc = dt_obj.astimezone(timezone.utc)
                    final_capture_date_iso = dt_utc.isoformat()
        except Exception as e:
            print(f"EXIF parsing error: {e}")
            pass # Fails gracefully back to upload time if the image data is corrupted

    # Allow explicit frontend overrides
    if capture_date and capture_date != "undefined" and capture_date != "null":
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

@app.put("/api/photos/{photo_id}", dependencies=[Depends(verify_token)])
async def update_photo(
    photo_id: int,
    aircraft_type: str = Form(...),
    registration: str = Form(...),
    serial_number: str = Form(...),
    airline: str = Form(...),
    operator: str = Form(""),
    airport: str = Form(""),
    country: str = Form(""),
    departure_airport: str = Form(""),
    arrival_airport: str = Form(""),
    flight_number: str = Form("")
):
    connection = get_db_connection()
    connection.execute("""
        UPDATE photos SET 
            aircraft_type = ?, registration = ?, serial_number = ?, 
            airline = ?, operator = ?, airport = ?, country = ?, 
            departure_airport = ?, arrival_airport = ?, flight_number = ?
        WHERE id = ?
    """, (
        aircraft_type, registration, serial_number, airline, operator, 
        airport, country, departure_airport, arrival_airport, flight_number, 
        photo_id
    ))
    connection.commit()
    
    # Fetch the updated row to send back to React
    cursor = connection.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
    updated_photo = dict(cursor.fetchone())
    connection.close()
    
    return {"status": "success", "photo": updated_photo}