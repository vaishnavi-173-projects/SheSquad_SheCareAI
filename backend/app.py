from flask import Flask, request, jsonify, send_file, session
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

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "shecare_secret_2024")
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Load ML model once at startup
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
model = None
if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print("ML model loaded successfully.")
    except Exception as e:
        print(f"Could not load model.pkl: {e}")
        model = None
else:
    print("model.pkl not found — using rule-based scoring only.")


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# PREDICTION ENGINE
# ─────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict():
    """
    Hybrid PCOS risk prediction using rule-based scoring + ML model.
    Required fields: user_id, cycle_length, pain_level, irregular_periods,
                     weight_gain, acne, hair_growth, skin_darkening, fast_food
    """
    try:
        data = request.json
        user_id = data.get("user_id", "anonymous")

        cycle_length = int(data.get("cycle_length", 28))
        pain_level = int(data.get("pain_level", 1))
        irregular_periods = int(data.get("irregular_periods", 0))
        weight_gain = int(data.get("weight_gain", 0))
        acne = int(data.get("acne", 0))
        hair_growth = int(data.get("hair_growth", 0))
        skin_darkening = int(data.get("skin_darkening", 0))
        fast_food = int(data.get("fast_food", 0))

        # ── Step 1: Rule-based scoring ──
        score = 0
        reasons = []

        if cycle_length > 35:
            score += 2
            reasons.append("Irregular cycle detected")

        if pain_level > 6:
            score += 2
            reasons.append("High pain level observed")

        if weight_gain == 1:
            score += 1
            reasons.append("Weight gain pattern noticed")

        if acne == 1:
            score += 1
            reasons.append("Hormonal symptoms observed")

        if hair_growth == 1:
            score += 1
            reasons.append("Hormonal symptoms observed")

        if score >= 5:
            rule_risk = 2
        elif score >= 3:
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

        # ── Step 3: Final risk (take the worse of the two) ──
        risk = max(rule_risk, model_risk)

        # ── Step 4: Suggestion ──
        if risk == 0:
            suggestion = "Maintain healthy lifestyle"
        elif risk == 1:
            suggestion = "Monitor symptoms and consult doctor"
        else:
            suggestion = "Immediate gynecologist consultation recommended"

        # ── Step 5: Save to health_records (only if user_id is real uuid) ──
        if not str(user_id).startswith("demo-"):
            record = {
                "user_id": user_id,
                "cycle_length": cycle_length,
                "pain_level": pain_level,
                "irregular_periods": irregular_periods,
                "weight_gain": weight_gain,
                "acne": acne,
                "hair_growth": hair_growth,
                "skin_darkening": skin_darkening,
                "fast_food": fast_food,
                "risk": risk,
                "score": score
            }
            supabase_post("health_records", record)

        risk_labels = {0: "Low Risk", 1: "Moderate Risk", 2: "High Risk"}
        risk_percent_map = {0: 20, 1: 62, 2: 85}

        # Deduplicate reasons
        unique_reasons = list(dict.fromkeys(reasons))

        return jsonify({
            "risk": risk,
            "score": score,
            "reasons": unique_reasons,
            "suggestion": suggestion,
            "risk_label": risk_labels[risk],
            "risk_percent": risk_percent_map[risk]
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
            "order": "created_at.desc"
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
    """Return all users with role='doctor'."""
    try:
        params = {"role": "eq.doctor", "select": "id,name,email"}
        doctors = supabase_get("users", params)
        return jsonify(doctors)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# REQUESTS
# ─────────────────────────────────────────────

@app.route("/request-doctor", methods=["POST"])
def request_doctor():
    """Patient sends a consultation request to a doctor."""
    try:
        data = request.json
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")
        if not patient_id or not doctor_id:
            return jsonify({"error": "patient_id and doctor_id required"}), 400

        record = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "status": "pending"
        }
        resp = supabase_post("requests", record)
        if resp.status_code in (200, 201):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to create request", "detail": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/doctor/requests", methods=["GET"])
def doctor_requests():
    """Fetch all consultation requests for a doctor with patient details."""
    try:
        doctor_id = request.args.get("doctor_id")
        if not doctor_id:
            return jsonify({"error": "doctor_id required"}), 400

        params = {
            "doctor_id": f"eq.{doctor_id}",
            "select": "id,patient_id,status,created_at",
            "order": "created_at.desc"
        }
        requests_data = supabase_get("requests", params)

        # Enrich with patient info
        enriched = []
        for r in requests_data:
            patient_params = {
                "id": f"eq.{r['patient_id']}",
                "select": "id,name,email,age"
            }
            patients = supabase_get("users", patient_params)
            patient = patients[0] if patients else {"name": "Unknown", "email": "", "age": ""}
            enriched.append({
                "id": r["id"],
                "patient_id": r["patient_id"],
                "patient_name": patient.get("name", "Unknown"),
                "patient_email": patient.get("email", ""),
                "patient_age": patient.get("age", ""),
                "status": r["status"],
                "created_at": r["created_at"]
            })

        return jsonify(enriched)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/doctor/respond", methods=["POST"])
def doctor_respond():
    """Doctor accepts or rejects a patient request."""
    try:
        data = request.json
        request_id = data.get("request_id")
        status = data.get("status")

        if not request_id or status not in ("accepted", "rejected"):
            return jsonify({"error": "request_id and valid status required"}), 400

        resp = supabase_patch("requests", "id", request_id, {"status": status})
        if resp.status_code in (200, 204):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to update request", "detail": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# MESSAGES
# ─────────────────────────────────────────────

@app.route("/messages/send", methods=["POST"])
def send_message():
    """Send a message between user and doctor."""
    try:
        data = request.json
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        content = data.get("content", "").strip()

        if not sender_id or not receiver_id or not content:
            return jsonify({"error": "sender_id, receiver_id, content required"}), 400

        record = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content
        }
        resp = supabase_post("messages", record)
        if resp.status_code in (200, 201):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to send message", "detail": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/messages", methods=["GET"])
def get_messages():
    """Fetch conversation between two users."""
    try:
        user1 = request.args.get("user1")
        user2 = request.args.get("user2")
        if not user1 or not user2:
            return jsonify({"error": "user1 and user2 required"}), 400

        # Fetch all messages involving both users
        params = {
            "or": f"(and(sender_id.eq.{user1},receiver_id.eq.{user2}),and(sender_id.eq.{user2},receiver_id.eq.{user1}))",
            "order": "created_at.asc",
            "select": "id,sender_id,receiver_id,content,created_at"
        }
        messages = supabase_get("messages", params)
        return jsonify(messages)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# REPORT GENERATION (PDF)
# ─────────────────────────────────────────────

@app.route("/generate-report", methods=["POST"])
def generate_report():
    """Generate a downloadable PDF health report using FPDF."""
    try:
        data = request.json
        user_id = data.get("user_id", "user")
        name = data.get("name", "Patient")
        age = data.get("age", "N/A")
        risk = int(data.get("risk", 0))
        score = data.get("score", 0)
        reasons = data.get("reasons", [])
        suggestion = data.get("suggestion", "Maintain healthy lifestyle")
        symptoms = data.get("symptoms", {})

        risk_labels = {0: "Low Risk", 1: "Moderate Risk", 2: "High Risk"}
        risk_label = risk_labels.get(risk, "Unknown")
        risk_percent_map = {0: 20, 1: 62, 2: 85}
        risk_percent = risk_percent_map.get(risk, 20)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ── Header band ──
        pdf.set_fill_color(201, 75, 106)
        pdf.rect(0, 0, 210, 32, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_y(8)
        pdf.cell(0, 10, "SheCare AI  -  Health Report", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "Reproductive Health Assessment | Confidential", align="C", new_x="LMARGIN", new_y="NEXT")

        # ── Patient Details ──
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

        # ── Risk Assessment ──
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
        pdf.cell(0, 7, f"Rule-Based Score: {score} / 10", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"Risk Percentage: {risk_percent}%", new_x="LMARGIN", new_y="NEXT")

        # ── Symptoms Summary ──
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
            "fast_food": "Regular Fast Food Consumption"
        }
        for key, label in symptom_labels.items():
            val = symptoms.get(key, "N/A")
            if key in ("cycle_length", "pain_level"):
                display = str(val)
            else:
                display = "Yes" if val == 1 else ("No" if val == 0 else str(val))
            pdf.cell(0, 7, f"  {label}: {display}", new_x="LMARGIN", new_y="NEXT")

        # ── AI Analysis ──
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "AI Analysis — Key Findings", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        if reasons:
            for reason in reasons:
                pdf.cell(0, 7, f"  \u2022  {reason}", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 7, "  No significant risk factors detected.", new_x="LMARGIN", new_y="NEXT")

        # ── Doctor Recommendation ──
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Doctor's Recommendation", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, f"  {suggestion}")

        # ── Disclaimer ──
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

        # ── Footer ──
        pdf.set_y(-18)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(150, 100, 130)
        pdf.cell(
            0, 10,
            "Generated by SheCare AI  |  Confidential  |  For medical reference only",
            align="C"
        )

        # Save to temp file
        tmp_dir = tempfile.gettempdir()
        safe_id = str(user_id).replace("-", "_")[:20]
        path = os.path.join(tmp_dir, f"shecare_report_{safe_id}.pdf")
        pdf.output(path)

        safe_name = name.replace(" ", "_")
        return send_file(
            path,
            as_attachment=True,
            download_name=f"shecare_report_{safe_name}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "app": "SheCare AI Backend",
        "model_loaded": model is not None
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
