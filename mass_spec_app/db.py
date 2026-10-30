import sqlite3
import os
import uuid
import json
from datetime import datetime

# Local SQLite Configuration (Default)
DB_PATH = os.environ.get("DB_PATH", "mass_spec_data.db")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")

# Cloudflare D1 Configuration (For Cloudflare Serverless Deployment)
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
CF_D1_DATABASE_ID = os.environ.get("CF_D1_DATABASE_ID")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")

USE_CLOUDFLARE_D1 = bool(CF_ACCOUNT_ID and CF_D1_DATABASE_ID and CF_API_TOKEN)


def _execute_cf_d1(sql, params=None):
    """Execute SQL query against Cloudflare D1 via Cloudflare REST API."""
    import urllib.request
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{CF_D1_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({"sql": sql, "params": params or []}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if not res.get("success"):
            raise RuntimeError(f"Cloudflare D1 Error: {res.get('errors')}")
        results = res.get("result", [{}])[0].get("results", [])
        return results


def init_db():
    """Initialize database tables and schema migrations (SQLite local or Cloudflare D1)."""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    create_users_table = '''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT,
            organization TEXT,
            auth_provider TEXT,
            picture TEXT,
            created_at DATETIME
        )
    '''

    create_submissions_table = '''
        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            timestamp DATETIME,
            target_gas TEXT,
            conc_pct REAL,
            ref_gas TEXT,
            brand_model TEXT,
            serial_id TEXT,
            detector_mode TEXT,
            vac_pressure REAL,
            emission_current REAL,
            air_scan_path TEXT,
            cal_scan_path TEXT,
            spec_file_path TEXT,
            user_id TEXT,
            user_name TEXT,
            user_email TEXT,
            organization TEXT
        )
    '''

    create_predictions_table = '''
        CREATE TABLE IF NOT EXISTS predictions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            user_name TEXT,
            user_email TEXT,
            organization TEXT,
            timestamp DATETIME,
            gas TEXT,
            conc TEXT,
            overall_accuracy REAL,
            download_file_id TEXT,
            download_filename TEXT,
            baseline_pressure REAL,
            n2_amps REAL,
            ar_amps REAL
        )
    '''

    if USE_CLOUDFLARE_D1:
        try:
            _execute_cf_d1(create_users_table)
            _execute_cf_d1(create_submissions_table)
            _execute_cf_d1(create_predictions_table)
            print("[db] Cloudflare D1 tables initialized successfully.")
            return
        except Exception as e:
            print(f"[db] Cloudflare D1 init failed ({e}), falling back to local SQLite.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(create_users_table)
    cursor.execute(create_submissions_table)
    cursor.execute(create_predictions_table)

    # Check and migrate submissions table columns if they do not exist
    cursor.execute("PRAGMA table_info(submissions)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    new_cols = [
        ("user_id", "TEXT"),
        ("user_name", "TEXT"),
        ("user_email", "TEXT"),
        ("organization", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col_name} {col_type}")

    # Check and migrate users table for password_hash
    cursor.execute("PRAGMA table_info(users)")
    existing_user_cols = [col[1] for col in cursor.fetchall()]
    if "password_hash" not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    conn.commit()
    conn.close()


import hashlib
import hmac

AUTH_SALT = "kth_mass_spec_auth_salt_2026"

def hash_password(password: str) -> str:
    """Hash password with application salt."""
    return hashlib.sha256((password + AUTH_SALT).encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify raw password against stored hash."""
    if not hashed:
        return False
    return hmac.compare_digest(hash_password(password), hashed)


def register_user(name: str, email: str, organization: str, password: str):
    """Register a new user account with password."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Valid email is required.")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    pwd_hash = hash_password(password)
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        if existing["password_hash"]:
            conn.close()
            raise ValueError("An account with this email already exists. Please sign in.")
        user_id = existing["id"]
        cursor.execute('''
            UPDATE users SET name = ?, organization = ?, password_hash = ?
            WHERE id = ?
        ''', (name or existing["name"], organization or existing["organization"], pwd_hash, user_id))
    else:
        user_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO users (id, email, name, organization, auth_provider, picture, created_at, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, name, organization, "password", "", now, pwd_hash))

    conn.commit()
    cursor.execute("SELECT id, email, name, organization, auth_provider, picture, created_at FROM users WHERE id = ?", (user_id,))
    user = dict(cursor.fetchone())
    conn.close()
    return user


def authenticate_user_password(email: str, password: str):
    """Authenticate existing user with email and password."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Valid email is required.")
    if not password:
        raise ValueError("Password is required.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        raise ValueError("No account found with this email. Please create an account.")

    stored_hash = user_row["password_hash"]
    if not stored_hash:
        # User created previously without password, link password now
        new_hash = hash_password(password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_row["id"]))
        conn.commit()
    else:
        if not verify_password(password, stored_hash):
            conn.close()
            raise ValueError("Incorrect password. Please try again.")

    user_dict = {
        "id": user_row["id"],
        "email": user_row["email"],
        "name": user_row["name"],
        "organization": user_row["organization"],
        "auth_provider": user_row["auth_provider"],
        "picture": user_row["picture"],
        "created_at": user_row["created_at"]
    }
    conn.close()
    return user_dict


def upsert_user(user_data):
    """Insert or update user record by email."""
    email = user_data.get("email", "").strip().lower()
    if not email:
        raise ValueError("User email is required.")

    name = user_data.get("name") or email.split("@")[0]
    organization = user_data.get("organization") or "Independent Researcher"
    auth_provider = user_data.get("auth_provider") or "organization"
    picture = user_data.get("picture") or ""
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        user_id = existing["id"]
        cursor.execute('''
            UPDATE users SET name = ?, organization = ?, picture = ?
            WHERE id = ?
        ''', (name, organization, picture, user_id))
    else:
        user_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO users (id, email, name, organization, auth_provider, picture, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, name, organization, auth_provider, picture, now))

    conn.commit()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(cursor.fetchone())
    conn.close()
    return user


def get_user_by_id(user_id):
    """Retrieve user record by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_uploaded_file(file_data, original_filename="scan.csv", prefix=""):
    """
    Saves file bytes or UploadFile object to UPLOAD_DIR.
    Returns the saved file path.
    """
    if file_data is None:
        return None

    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(original_filename)[1] or ".csv"
    unique_filename = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    if isinstance(file_data, bytes):
        with open(file_path, "wb") as f:
            f.write(file_data)
    elif hasattr(file_data, "getbuffer"):
        with open(file_path, "wb") as f:
            f.write(file_data.getbuffer())
    elif hasattr(file_data, "read"):
        with open(file_path, "wb") as f:
            data = file_data.read()
            if isinstance(data, str):
                data = data.encode('utf-8')
            f.write(data)
    else:
        return None

    return file_path


def insert_submission(data_dict):
    """Insert a new contributor submission into database."""
    sub_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    params = [
        sub_id, timestamp, data_dict.get('target_gas'), data_dict.get('conc_pct'),
        data_dict.get('ref_gas'), data_dict.get('brand_model'), data_dict.get('serial_id'),
        data_dict.get('detector_mode'), data_dict.get('vac_pressure'), data_dict.get('emission_current'),
        data_dict.get('air_scan_path'), data_dict.get('cal_scan_path'), data_dict.get('spec_file_path'),
        data_dict.get('user_id'), data_dict.get('user_name'), data_dict.get('user_email'),
        data_dict.get('organization')
    ]

    sql = '''
        INSERT INTO submissions (
            id, timestamp, target_gas, conc_pct, ref_gas, 
            brand_model, serial_id, detector_mode, vac_pressure, 
            emission_current, air_scan_path, cal_scan_path, spec_file_path,
            user_id, user_name, user_email, organization
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''

    if USE_CLOUDFLARE_D1:
        try:
            _execute_cf_d1(sql, params)
            return sub_id
        except Exception as e:
            print(f"[db] Cloudflare D1 insert failed ({e}), falling back to local SQLite.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()
    return sub_id


def get_all_submissions(user_id=None):
    """Retrieve all submissions ordered by newest first, optionally filtered by user."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM submissions WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM submissions ORDER BY timestamp DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def insert_prediction(data_dict):
    """Log a consumer AI prediction into the database."""
    pred_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    params = [
        pred_id, data_dict.get('user_id'), data_dict.get('user_name'),
        data_dict.get('user_email'), data_dict.get('organization'), timestamp,
        data_dict.get('gas'), data_dict.get('conc'), data_dict.get('overall_accuracy'),
        data_dict.get('download_file_id'), data_dict.get('download_filename'),
        data_dict.get('baseline_pressure'), data_dict.get('n2_amps'), data_dict.get('ar_amps')
    ]

    sql = '''
        INSERT INTO predictions (
            id, user_id, user_name, user_email, organization, timestamp,
            gas, conc, overall_accuracy, download_file_id, download_filename,
            baseline_pressure, n2_amps, ar_amps
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()
    return pred_id


def get_predictions(user_id=None):
    """Retrieve tracked predictions, optionally filtered by user."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM predictions WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM predictions ORDER BY timestamp DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
