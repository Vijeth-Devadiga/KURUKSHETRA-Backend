# app.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import errorcode
from dotenv import load_dotenv

# Load local .env if present (development)
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "fest_registration")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")  # set to your Vercel origin in production

app = Flask(__name__)

# Configure CORS properly
if CORS_ORIGINS.strip() == "*":
    CORS(app)
else:
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    # flask-cors accepts 'origins' parameter
    CORS(app, origins=origins)

def get_db_connection():
    try:
        cnx = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset='utf8mb4'
        )
        return cnx
    except mysql.connector.Error as err:
        app.logger.error("DB connection error: %s", err)
        raise

# Event field definitions (order preserved)
EVENT_FIELDS = [
    *[("dance{}".format(i), "Dance") for i in range(1, 8)],      # dance1..dance7
    ("mockPress", "Mock Press"),
    ("quiz1", "Quiz"), ("quiz2", "Quiz"),
    ("treasureHunt", "Treasure Hunt"),
    *[("madAd{}".format(i), "Mad Ad") for i in range(1, 7)],    # madAd1..madAd6
    ("marketing1", "Marketing"), ("marketing2", "Marketing"),
    ("bottleArt", "Bottle Art"),
    ("motorMouth", "Motor Mouth"),
    ("bestManager", "Best Manager"),
    ("sharkTank1", "Shark Tank"), ("sharkTank2", "Shark Tank"),
    ("mockCid1", "Mock CID"), ("mockCid2", "Mock CID"),
    ("reelsMaking", "Reels Making")
]

def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    p = phone.strip()
    return p.isdigit() and len(p) == 10

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/register", methods=["POST"])
def register():
    # Ensure request has JSON
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    college_name = str(data.get("collegeName", "")).strip()
    coordinator_name = str(data.get("coordinatorName", "")).strip()
    coordinator_contact = str(data.get("coordinatorContact", "")).strip()

    errors = []
    if not college_name:
        errors.append("collegeName is required")
    if not coordinator_name:
        errors.append("coordinatorName is required")
    if not is_valid_phone(coordinator_contact):
        errors.append("coordinatorContact must be a valid 10-digit number")

    # Collect participant entries
    participants = []  # list of tuples: (event_name, participant_name)
    dance_count = 0
    madad_count = 0

    for field_key, event_name in EVENT_FIELDS:
        raw = data.get(field_key)
        if raw is None:
            # treat missing as empty
            name = ""
        else:
            name = str(raw).strip()
        if name:
            participants.append((event_name, name))
            if field_key.startswith("dance"):
                dance_count += 1
            if field_key.startswith("madAd"):
                madad_count += 1

    # Validate counts for events (clear messages)
    if not (5 <= dance_count <= 7):
        errors.append(f"Dance must have between 5 and 7 participants (got {dance_count})")
    if madad_count != 6:
        errors.append(f"Mad Ad must have exactly 6 participants (got {madad_count})")
    # Single/dual events
    counts = {
        "Mock Press": sum(1 for e, _ in participants if e == "Mock Press"),
        "Quiz": sum(1 for e, _ in participants if e == "Quiz"),
        "Treasure Hunt": sum(1 for e, _ in participants if e == "Treasure Hunt"),
        "Marketing": sum(1 for e, _ in participants if e == "Marketing"),
        "Bottle Art": sum(1 for e, _ in participants if e == "Bottle Art"),
        "Motor Mouth": sum(1 for e, _ in participants if e == "Motor Mouth"),
        "Best Manager": sum(1 for e, _ in participants if e == "Best Manager"),
        "Shark Tank": sum(1 for e, _ in participants if e == "Shark Tank"),
        "Mock CID": sum(1 for e, _ in participants if e == "Mock CID"),
        "Reels Making": sum(1 for e, _ in participants if e == "Reels Making"),
    }

    # enforce exact counts for these events
    if counts["Mock Press"] != 1:
        errors.append(f"Mock Press must have exactly 1 participant (got {counts['Mock Press']})")
    if counts["Quiz"] != 2:
        errors.append(f"Quiz must have exactly 2 participants (got {counts['Quiz']})")
    if counts["Treasure Hunt"] != 1:
        errors.append(f"Treasure Hunt must have exactly 1 participant (got {counts['Treasure Hunt']})")
    if counts["Marketing"] != 2:
        errors.append(f"Marketing must have exactly 2 participants (got {counts['Marketing']})")
    if counts["Bottle Art"] != 1:
        errors.append(f"Bottle Art must have exactly 1 participant (got {counts['Bottle Art']})")
    if counts["Motor Mouth"] != 1:
        errors.append(f"Motor Mouth must have exactly 1 participant (got {counts['Motor Mouth']})")
    if counts["Best Manager"] != 1:
        errors.append(f"Best Manager must have exactly 1 participant (got {counts['Best Manager']})")
    if counts["Shark Tank"] != 2:
        errors.append(f"Shark Tank must have exactly 2 participants (got {counts['Shark Tank']})")
    if counts["Mock CID"] != 2:
        errors.append(f"Mock CID must have exactly 2 participants (got {counts['Mock CID']})")
    if counts["Reels Making"] != 1:
        errors.append(f"Reels Making must have exactly 1 participant (got {counts['Reels Making']})")

    if errors:
        return jsonify({"errors": errors}), 400

    # Insert into DB with safe cleanup
    cnx = None
    cursor = None
    try:
        cnx = get_db_connection()
        cursor = cnx.cursor()

        insert_college = """
            INSERT INTO colleges (college_name, coordinator_name, coordinator_contact)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_college, (college_name, coordinator_name, coordinator_contact))
        cnx.commit()
        college_id = cursor.lastrowid

        insert_participant = """
            INSERT INTO participants (college_id, event_name, participant_name)
            VALUES (%s, %s, %s)
        """
        for event_name, participant_name in participants:
            cursor.execute(insert_participant, (college_id, event_name, participant_name))
        cnx.commit()
        participants_count = len(participants)

        return jsonify({
            "message": "Registration submitted successfully!",
            "college_id": college_id,
            "participants_count": participants_count
        }), 201

    except mysql.connector.Error as db_err:
        app.logger.exception("Database error while saving registration")
        return jsonify({"error": "Database error", "details": str(db_err)}), 500
    except Exception as e:
        app.logger.exception("Unexpected error while saving registration")
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if cnx:
                cnx.close()
        except Exception:
            pass

if __name__ == "__main__":
    # For local dev only; on PythonAnywhere WSGI will import 'app' as application
    # app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
    app.run()