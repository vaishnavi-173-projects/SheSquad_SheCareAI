from flask import Flask, request, jsonify, send_file, session, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import os
import joblib
import requests as req
import json
import uuid
import numpy as np
from datetime import datetime
from fpdf import FPDF
import tempfile
import google.generativeai as genai

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "shecare_secret_2024")

# CORS setup
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.route("/health")
def health():
    return {"status": "ok"}

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ─────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("patient_dashboard.html")

@app.route("/doctor-dashboard")
def doctor_dashboard():
    return render_template("doctor_dashboard.html")

@app.route("/patient-dashboard")
def patient_dashboard():
    return render_template("patient_dashboard.html")

# Load ML model once at startup
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
model = None
if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print("ML model loaded successfully.")
    except Exception as e:
        print(f"Could not load model.pkl: {e}")
else:
    print("model.pkl not found -- using rule-based scoring only.")

# Gemini AI setup
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
gemini_model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        print("Gemini AI model ready.")
    except Exception as e:
        print(f"Gemini init failed: {e}")


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def ascii_safe(text):
    """Remove non-Latin characters that Helvetica cannot render (e.g. em-dashes)."""
    return ''.join(c if ord(c) < 256 else '-' for c in str(text))


def generate_ai_explanation(name, age, risk_label, score, reasons, symptoms):
    """
    Call Gemini to produce a short clinical-style narrative for the PDF report.
    Falls back gracefully if API unavailable.
    """
    if not gemini_model:
        return None
    try:
        sym_list = []
        if symptoms.get("irregular_periods"): sym_list.append("irregular menstrual cycles")
        if symptoms.get("pain_level", 0) > 6:  sym_list.append(f"pelvic pain rated {symptoms.get('pain_level')}/10")
        if symptoms.get("weight_gain"):         sym_list.append("unexplained weight gain")
        if symptoms.get("acne"):                sym_list.append("hormonal acne")
        if symptoms.get("hair_growth"):         sym_list.append("excessive hair growth")
        if symptoms.get("skin_darkening"):      sym_list.append("skin darkening")
        if symptoms.get("fast_food"):           sym_list.append("frequent fast food consumption")
        cycle = symptoms.get("cycle_length", 28)

        prompt = (
            f"You are a clinical assistant writing a brief, empathetic, non-alarmist health report section."
            f" Patient: {name}, Age: {age}."
            f" PCOS risk assessment result: {risk_label} (rule score {score}/13)."
            f" Reported symptoms: {', '.join(sym_list) if sym_list else 'none significant'}."
            f" Menstrual cycle length: {cycle} days."
            f" In 3-4 short sentences (plain English, no markdown, no bullet points, no em-dashes),"
            f" explain what these findings suggest, why early action matters, and one lifestyle tip."
            f" Keep it under 80 words."
        )
        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()
        return ascii_safe(raw)
    except Exception as e:
        print(f"[Gemini] Explanation failed: {e}")
        return None


def supabase_get(table, params=None):
    """GET rows from a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    response = req.get(url, headers=HEADERS, params=params)
    if response.status_code in (200, 206):
        return response.json()
    return []


def supabase_post(table, data):
    """INSERT a row into a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    response = req.post(url, headers=HEADERS, json=data)
    return response


def supabase_patch(table, match_field, match_value, data):
    """UPDATE rows in a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {match_field: f"eq.{match_value}"}
    response = req.patch(url, headers=HEADERS, params=params, json=data)
    return response


def upload_to_supabase_storage(file_path, bucket, storage_path):
    """Upload a file to Supabase Storage and return the public URL."""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{storage_path}"
    upload_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/pdf"
    }
    with open(file_path, "rb") as f:
        response = req.post(url, headers=upload_headers, data=f)
    if response.status_code in (200, 201):
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{storage_path}"
        return public_url
    return None


# ─────────────────────────────────────────────
# USER UPSERT (called after auth)
# ─────────────────────────────────────────────

@app.route("/user/upsert", methods=["POST"])
def user_upsert():
    """
    Store or update user in the users table after login/signup.
    Required: user_id, email
    Optional: name, age, role
    """
    try:
        data = request.json
        user_id = data.get("user_id")
        email   = data.get("email")

        if not user_id or not email:
            return jsonify({"error": "user_id and email required"}), 400

        record = {
            "id":    user_id,
            "email": email,
            "name":  data.get("name", email.split("@")[0]),
            "age":   data.get("age"),
            "role":  data.get("role", "patient")
        }

        url = f"{SUPABASE_URL}/rest/v1/users"
        upsert_headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
        response = req.post(url, headers=upsert_headers, json=record)

        if response.status_code in (200, 201):
            return jsonify({"success": True, "user": response.json()})
        return jsonify({"error": "Failed to upsert user", "detail": response.text}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# PREDICTION ENGINE
# ─────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict():
    """
    Hybrid PCOS risk prediction: rule-based + ML model.

    Input JSON:
    {
      "user_id": "...",
      "cycle_length": 35,
      "pain_level": 7,
      "irregular_periods": 1,
      "weight_gain": 1,
      "acne": 1,
      "hair_growth": 0,
      "skin_darkening": 0,
      "fast_food": 1
    }

    Output:
    {
      "risk": 0|1|2,
      "risk_label": "Low/Moderate/High Risk",
      "risk_percent": 20|62|85,
      "score": int,
      "reasons": [...],
      "suggestion": "...",
      "explanation": [{"factor": "...", "contribution": pct%}]
    }
    """
    try:
        data = request.json
        user_id = data.get("user_id", "anonymous")

        cycle_length      = int(data.get("cycle_length", 28))
        pain_level        = int(data.get("pain_level", 1))
        irregular_periods = int(data.get("irregular_periods", 0))
        weight_gain       = int(data.get("weight_gain", 0))
        acne              = int(data.get("acne", 0))
        hair_growth       = int(data.get("hair_growth", 0))
        skin_darkening    = int(data.get("skin_darkening", 0))
        fast_food         = int(data.get("fast_food", 0))

        # ── Step 1: Rule-based scoring ──
        score   = 0
        factors = []

        if cycle_length > 35:
            score += 2
            factors.append({"factor": "Irregular cycle (>35 days)", "weight": 2, "reason": "Irregular cycle detected"})

        if pain_level > 6:
            score += 2
            factors.append({"factor": "High pain level", "weight": 2, "reason": "High pain level observed"})

        if irregular_periods == 1:
            score += 3
            factors.append({"factor": "Irregular periods", "weight": 3, "reason": "Irregular periods reported"})

        if weight_gain == 1:
            score += 2
            factors.append({"factor": "Weight gain", "weight": 2, "reason": "Weight gain pattern noticed"})

        if acne == 1:
            score += 2
            factors.append({"factor": "Acne (hormonal)", "weight": 2, "reason": "Hormonal acne observed"})

        if hair_growth == 1:
            score += 1
            factors.append({"factor": "Excessive hair growth", "weight": 1, "reason": "Hormonal hair growth noted"})

        if skin_darkening == 1:
            score += 1
            factors.append({"factor": "Skin darkening", "weight": 1, "reason": "Skin darkening (hormonal marker)"})

        if fast_food == 1:
            score += 1
            factors.append({"factor": "Regular fast food", "weight": 1, "reason": "Diet pattern may affect hormones"})

        if score >= 7:
            rule_risk = 2
        elif score >= 4:
            rule_risk = 1
        else:
            rule_risk = 0

        # ── Step 2: ML model prediction ──
        features = np.array([[
            cycle_length, pain_level, irregular_periods,
            weight_gain, acne, hair_growth, skin_darkening, fast_food
        ]])

        if model is not None:
            try:
                model_risk = int(model.predict(features)[0])
            except Exception:
                model_risk = rule_risk
        else:
            model_risk = rule_risk

        # ── Step 3: Final risk ──
        risk = max(rule_risk, model_risk)

        # ── Step 4: Suggestion ──
        if risk == 0:
            suggestion = "Maintain a healthy lifestyle with regular exercise and a balanced diet."
        elif risk == 1:
            suggestion = "Monitor your symptoms closely and consider consulting a gynecologist soon."
        else:
            suggestion = "Immediate gynecologist consultation strongly recommended. High PCOS risk detected."

        # ── Step 5: Build explanation with contribution % ──
        total_weight = sum(f["weight"] for f in factors) or 1
        explanation = [
            {
                "factor": f["factor"],
                "contribution": round((f["weight"] / total_weight) * 100)
            }
            for f in factors
        ]
        reasons = list(dict.fromkeys(f["reason"] for f in factors))

        # ── Step 6: Save to health_records ──
        if not str(user_id).startswith("demo-"):
            record = {
                "user_id":          user_id,
                "cycle_length":     cycle_length,
                "pain_level":       pain_level,
                "irregular_periods": bool(irregular_periods),
                "weight_gain":      bool(weight_gain),
                "acne":             bool(acne),
                "hair_growth":      bool(hair_growth),
                "skin_darkening":   bool(skin_darkening),
                "fast_food":        bool(fast_food),
                "risk":             risk,
                "score":            score,
                "risk_label":       ["Low Risk", "Moderate Risk", "High Risk"][risk],
                "risk_percent":     [20, 62, 85][risk],
                "reasons":          reasons,
                "suggestion":       suggestion,
                "symptoms": {
                    "cycle_length":      cycle_length,
                    "pain_level":        pain_level,
                    "irregular_periods": irregular_periods,
                    "weight_gain":       weight_gain,
                    "acne":              acne,
                    "hair_growth":       hair_growth,
                    "skin_darkening":    skin_darkening,
                    "fast_food":         fast_food
                }
            }
            supabase_post("health_records", record)

        risk_labels      = {0: "Low Risk", 1: "Moderate Risk", 2: "High Risk"}
        risk_percent_map = {0: 20, 1: 62, 2: 85}

        return jsonify({
            "risk":         risk,
            "risk_label":   risk_labels[risk],
            "risk_percent": risk_percent_map[risk],
            "score":        score,
            "reasons":      reasons,
            "suggestion":   suggestion,
            "explanation":  explanation
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# HEALTH HISTORY
# ─────────────────────────────────────────────

@app.route("/health/history", methods=["GET"])
def health_history():
    """Fetch all health records for a given user_id."""
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    try:
        params = {
            "user_id": f"eq.{user_id}",
            "order":   "created_at.desc"
        }
        records = supabase_get("health_records", params)
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health/add", methods=["POST"])
def health_add():
    """Manually add a health record."""
    try:
        data = request.json
        resp = supabase_post("health_records", data)
        if resp.status_code in (200, 201):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to insert record"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# DOCTORS
# ─────────────────────────────────────────────

@app.route("/doctors", methods=["GET"])
def get_doctors():
    """
    Return doctors from the doctors table.
    Optional query param: specialization (e.g. Gynecologist)
    """
    try:
        specialization = request.args.get("specialization")
        params = {
            "select": "id,name,specialization,location,rating,bio,available",
            "available": "eq.true",
            "order": "rating.desc"
        }
        if specialization:
            params["specialization"] = f"eq.{specialization}"

        doctors = supabase_get("doctors", params)

        # Fallback: if doctors table empty, try users table
        if not doctors:
            user_params = {"role": "eq.doctor", "select": "id,name,email"}
            doctors = supabase_get("users", user_params)
            # Normalize shape
            doctors = [{
                "id":             d.get("id"),
                "name":           d.get("name", "Doctor"),
                "specialization": "Gynecologist",
                "location":       "Available Online",
                "rating":         4.5,
                "bio":            "Specialist in reproductive health",
                "available":      True
            } for d in doctors]

        return jsonify(doctors)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# CONSULTATIONS (replaces requests table)
# ─────────────────────────────────────────────

@app.route("/request-doctor", methods=["POST"])
def request_doctor():
    """Patient sends a consultation request to a doctor."""
    try:
        data       = request.json
        patient_id = data.get("patient_id")
        doctor_id  = data.get("doctor_id")

        if not patient_id or not doctor_id:
            return jsonify({"error": "patient_id and doctor_id required"}), 400

        record = {
            "patient_id": patient_id,
            "doctor_id":  doctor_id,
            "status":     "pending"
        }

        # Try consultations table first, fall back to requests
        resp = supabase_post("consultations", record)
        if resp.status_code not in (200, 201):
            resp = supabase_post("requests", record)

        if resp.status_code in (200, 201):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to create consultation", "detail": resp.text}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/patient/consultation", methods=["GET"])
def patient_consultation():
    """Get the patient's most recent consultation with doctor info."""
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400

    try:
        params = {
            "patient_id": f"eq.{patient_id}",
            "select":     "id,doctor_id,status,created_at",
            "order":      "created_at.desc",
            "limit":      "1"
        }
        consultations = supabase_get("consultations", params)
        if not consultations:
            return jsonify(None)

        c = consultations[0]
        # Get doctor info
        doc_params = {"id": f"eq.{c['doctor_id']}", "select": "id,name,specialization,location,rating"}
        doctors    = supabase_get("doctors", doc_params)
        if not doctors:
            doctors = supabase_get("users", {"id": f"eq.{c['doctor_id']}", "select": "id,name,email"})

        c["doctor"] = doctors[0] if doctors else None
        return jsonify(c)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/doctor/requests", methods=["GET"])
def doctor_requests():
    """Fetch all consultations for a doctor with patient details."""
    try:
        doctor_id = request.args.get("doctor_id")
        if not doctor_id:
            return jsonify({"error": "doctor_id required"}), 400

        params = {
            "doctor_id": f"eq.{doctor_id}",
            "select":    "id,patient_id,status,created_at",
            "order":     "created_at.desc"
        }
        consultations = supabase_get("consultations", params)

        # Fallback to requests table
        if not consultations:
            consultations = supabase_get("requests", params)

        enriched = []
        for r in consultations:
            patient_params = {"id": f"eq.{r['patient_id']}", "select": "id,name,email,age"}
            patients       = supabase_get("users", patient_params)
            patient        = patients[0] if patients else {"name": "Unknown", "email": "", "age": ""}
            enriched.append({
                "id":           r["id"],
                "patient_id":   r["patient_id"],
                "patient_name": patient.get("name", "Unknown"),
                "patient_email":patient.get("email", ""),
                "patient_age":  patient.get("age", ""),
                "status":       r["status"],
                "created_at":   r["created_at"]
            })

        return jsonify(enriched)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/doctor/respond", methods=["POST"])
def doctor_respond():
    """Doctor accepts or rejects a consultation request."""
    try:
        data       = request.json
        request_id = data.get("request_id")
        status     = data.get("status")

        if not request_id or status not in ("accepted", "rejected"):
            return jsonify({"error": "request_id and valid status required"}), 400

        # Try consultations first, then requests
        resp = supabase_patch("consultations", "id", request_id, {"status": status})
        if resp.status_code not in (200, 204):
            resp = supabase_patch("requests", "id", request_id, {"status": status})

        if resp.status_code in (200, 204):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to update", "detail": resp.text}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# MESSAGES
# ─────────────────────────────────────────────

@app.route("/messages/send", methods=["POST"])
def send_message():
    """Send a message. Supports both consultation_id and sender/receiver model."""
    try:
        data            = request.json
        sender_id       = data.get("sender_id")
        receiver_id     = data.get("receiver_id")
        content         = data.get("content", "").strip()
        consultation_id = data.get("consultation_id")

        if not sender_id or not content:
            return jsonify({"error": "sender_id and content required"}), 400

        record = {
            "sender_id":  sender_id,
            "content":    content
        }
        if consultation_id:
            record["consultation_id"] = consultation_id
        if receiver_id:
            record["receiver_id"] = receiver_id

        resp = supabase_post("messages", record)
        if resp.status_code in (200, 201):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to send message", "detail": resp.text}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/messages", methods=["GET"])
def get_messages():
    """Fetch conversation between two users or by consultation_id."""
    try:
        consultation_id = request.args.get("consultation_id")
        user1           = request.args.get("user1")
        user2           = request.args.get("user2")

        if consultation_id:
            params = {
                "consultation_id": f"eq.{consultation_id}",
                "order":           "created_at.asc",
                "select":          "id,sender_id,content,read,created_at"
            }
        elif user1 and user2:
            params = {
                "or":    f"(and(sender_id.eq.{user1},receiver_id.eq.{user2}),and(sender_id.eq.{user2},receiver_id.eq.{user1}))",
                "order": "created_at.asc",
                "select":"id,sender_id,receiver_id,content,created_at"
            }
        else:
            return jsonify({"error": "consultation_id or user1+user2 required"}), 400

        messages = supabase_get("messages", params)
        return jsonify(messages)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# REPORT GENERATION (PDF → Supabase Storage)
# ─────────────────────────────────────────────

@app.route("/generate-report", methods=["POST"])
def generate_report():
    """Generate PDF report, upload to Supabase Storage, store URL in reports table."""
    try:
        data       = request.json
        user_id    = data.get("user_id", "user")
        name       = ascii_safe(data.get("name", "Patient"))
        age        = ascii_safe(data.get("age", "N/A"))
        risk       = int(data.get("risk", 0))
        score      = data.get("score", 0)
        reasons    = data.get("reasons", [])
        explanation= data.get("explanation", [])
        suggestion = ascii_safe(data.get("suggestion", "Maintain healthy lifestyle"))
        symptoms   = data.get("symptoms", {})

        risk_labels      = {0: "Low Risk", 1: "Moderate Risk", 2: "High Risk"}
        risk_label       = risk_labels.get(risk, "Unknown")
        risk_percent_map = {0: 20, 1: 62, 2: 85}
        risk_percent     = risk_percent_map.get(risk, 20)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Header
        pdf.set_fill_color(201, 75, 106)
        pdf.rect(0, 0, 210, 32, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_y(8)
        pdf.cell(0, 10, "SheCare AI  -  Health Report", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "Reproductive Health Assessment | Confidential", align="C", new_x="LMARGIN", new_y="NEXT")

        # Patient Details
        pdf.set_text_color(59, 26, 46)
        pdf.set_y(42)
        pdf.set_fill_color(255, 240, 243)
        pdf.rect(10, 40, 190, 38, "F")
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_x(14)
        pdf.cell(0, 8, "Patient Details", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_x(14)
        pdf.cell(0, 7, f"Name:         {name}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(14)
        pdf.cell(0, 7, f"Age:           {age} years", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(14)
        pdf.cell(0, 7, f"Report Date: {datetime.now().strftime('%B %d, %Y  %I:%M %p')}", new_x="LMARGIN", new_y="NEXT")

        # Risk Assessment
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Risk Assessment", new_x="LMARGIN", new_y="NEXT")
        risk_colors = {0: (22, 163, 74), 1: (201, 75, 106), 2: (220, 38, 38)}
        r_col = risk_colors.get(risk, (100, 100, 100))
        pdf.set_text_color(*r_col)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, f"Result: {risk_label}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(59, 26, 46)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"Rule-Based Score: {score} / 13", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"Risk Percentage:  {risk_percent}%", new_x="LMARGIN", new_y="NEXT")

        # Symptoms
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Symptoms Reported", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        symptom_labels = {
            "cycle_length": "Cycle Length (days)",
            "pain_level": "Pain Level (1-10)",
            "irregular_periods": "Irregular Periods",
            "weight_gain": "Weight Gain",
            "acne": "Acne",
            "hair_growth": "Excessive Hair Growth",
            "skin_darkening": "Skin Darkening",
            "fast_food": "Regular Fast Food"
        }
        for key, label in symptom_labels.items():
            val = symptoms.get(key, "N/A")
            if key in ("cycle_length", "pain_level"):
                display = str(val)
            else:
                display = "Yes" if val in (1, True, "1", "true") else ("No" if val in (0, False, "0", "false") else str(val))
            pdf.cell(0, 7, f"  {label}: {display}", new_x="LMARGIN", new_y="NEXT")

        # AI Explanation
        if explanation:
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, "AI Explainability - Factor Contributions", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            for item in explanation:
                pdf.cell(0, 7, ascii_safe(f"  * {item.get('factor', '')}: {item.get('contribution', 0)}%"), new_x="LMARGIN", new_y="NEXT")

        # AI Findings
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "AI Analysis - Key Findings", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        if reasons:
            for reason in reasons:
                pdf.cell(0, 7, ascii_safe(f"  * {reason}"), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 7, "  No significant risk factors detected.", new_x="LMARGIN", new_y="NEXT")

        # Gemini AI Narrative (new section)
        ai_narrative = generate_ai_explanation(name, age, risk_label, score, reasons, symptoms)
        if ai_narrative:
            pdf.ln(5)
            pdf.set_fill_color(255, 248, 250)
            pdf.rect(10, pdf.get_y(), 190, 1, "F")
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, "AI Clinical Narrative (Powered by Gemini)", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(59, 26, 46)
            pdf.multi_cell(0, 7, f"  {ai_narrative}")

        # Recommendation
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Recommendation", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, f"  {suggestion}")

        # Disclaimer
        pdf.ln(5)
        pdf.set_fill_color(255, 224, 233)
        pdf.rect(10, pdf.get_y(), 190, 18, "F")
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(139, 58, 98)
        pdf.set_x(14)
        pdf.multi_cell(182, 6, (
            "DISCLAIMER: This report is generated by an AI-powered system for "
            "informational purposes only. It is not a substitute for professional "
            "medical advice, diagnosis, or treatment. Always consult a qualified "
            "healthcare provider for medical decisions."
        ))

        # Footer
        pdf.set_y(-18)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 100, 130)
        pdf.cell(0, 10, "Generated by SheCare AI  |  Confidential  |  For medical reference only", align="C")

        # Save PDF to temp
        tmp_dir  = tempfile.gettempdir()
        safe_id  = str(user_id).replace("-", "_")[:20]
        filename = f"shecare_report_{safe_id}.pdf"
        path     = os.path.join(tmp_dir, filename)
        pdf.output(path)

        # ── Upload to Supabase Storage (optional) ──
        pdf_url = None
        if not str(user_id).startswith("demo-") and SUPABASE_KEY and "your_supabase" not in str(SUPABASE_KEY):
            try:
                storage_path = f"{user_id}/{filename}"
                pdf_url = upload_to_supabase_storage(path, "reports", storage_path)
            except Exception as se:
                print(f"[Storage] Upload failed (bucket may not exist): {se}")

        safe_name = name.replace(" ", "_")
        response  = send_file(
            path,
            as_attachment=True,
            download_name=f"shecare_report_{safe_name}.pdf",
            mimetype="application/pdf"
        )
        if pdf_url:
            response.headers["X-PDF-URL"] = pdf_url
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# DOCTOR DASHBOARD STATS
# ─────────────────────────────────────────────

@app.route("/doctor/stats", methods=["GET"])
def doctor_stats():
    """Return summary stats for doctor dashboard."""
    doctor_id = request.args.get("doctor_id")
    if not doctor_id:
        return jsonify({"error": "doctor_id required"}), 400

    try:
        # Total patients (accepted consultations)
        all_consultations = supabase_get("consultations", {"doctor_id": f"eq.{doctor_id}"})
        total_patients  = len([c for c in all_consultations if c.get("status") == "accepted"])
        pending_count   = len([c for c in all_consultations if c.get("status") == "pending"])
        total_requests  = len(all_consultations)

        return jsonify({
            "total_patients":  total_patients,
            "pending_requests": pending_count,
            "total_requests":  total_requests
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/doctor/patient-reports", methods=["GET"])
def doctor_patient_reports():
    """Doctor fetches reports of an assigned patient."""
    doctor_id  = request.args.get("doctor_id")
    patient_id = request.args.get("patient_id")

    if not doctor_id or not patient_id:
        return jsonify({"error": "doctor_id and patient_id required"}), 400

    try:
        # Verify this doctor has an accepted consultation with the patient
        check_params = {
            "doctor_id":  f"eq.{doctor_id}",
            "patient_id": f"eq.{patient_id}",
            "status":     "eq.accepted"
        }
        access = supabase_get("consultations", check_params)
        if not access:
            return jsonify({"error": "Not authorized to view this patient's reports"}), 403

        reports = supabase_get("reports", {
            "user_id": f"eq.{patient_id}",
            "order":   "created_at.desc"
        })
        return jsonify(reports)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
