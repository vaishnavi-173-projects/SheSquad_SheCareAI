# SheCare AI – Reproductive Health Assistant

SheCare AI is a comprehensive, full-stack predictive healthcare application designed to assess the risk of Polycystic Ovary Syndrome (PCOS) and other related reproductive health disorders. It combines a dynamic and visually rich user interface with robust machine-learning-backed prediction capabilities to equip patients with actionable insights, whilst facilitating seamless connections with healthcare providers.

## Features ✨

### 👩 For Patients:
- **Instant Health Analysis:** Enter symptoms and cycle details to receive a risk assessment score (Low, Moderate, High).
- **Hybrid AI Model:** Uses both clinical rules and an ML Model (`sklearn` Gradient Boosting Classifier) for robust predictions.
- **Detailed PDF Reports:** Download your symptom history and predictive risk securely as a PDF report.
- **Doctor Consultation:** Ask for reviews and expert second opinions by messaging doctors on the platform.

### 🩺 For Doctors:
- **Centralized Dashboard:** Manage accepted and pending patient requests.
- **View Patient Records:** See an in-depth view of a patient’s historical records and specific PCOS symptoms.
- **Secure Messaging:** Discuss symptoms or recommend tests with your patients.
- **Generate Diagnoses:** Accept or reject appointments to prioritize urgent patients.

## Technology Stack 💻

- **Frontend:** HTML5, CSS3 (Vanilla + Tailwind-like custom variables framework), Vanilla JavaScript 
- **Backend:** Python, Flask, Flask-CORS 
- **Database:** Supabase (PostgreSQL) REST APIs
- **Machine Learning:** `scikit-learn` for generating predictive risk models
- **PDF Generation:** `fpdf2` 

## Project Structure 📁

```text
shecares/
├── backend/
│   ├── .env                 # Environment variables (Supabase URL/Key)
│   ├── app.py               # Main Flask application and REST endpoints
│   ├── train_model.py       # ML Model generation script
│   ├── requirements.txt     # Python dependencies
│   └── model.pkl            # Pre-compiled ML gradient boosting model
└── frontend/
    ├── index.html           # Landing & Authentication Page
    ├── dashboard.html       # Patient Portal
    ├── doctor.html          # Healthcare Provider Portal
    └── styles.css           # Global custom styles and theming
```

## Setup & Running the Application 🚀

### 1. Configure the Database
The application relies on Supabase. To utilize this:
1. Create a project on [Supabase](https://supabase.com).
2. Grab your `SUPABASE_URL` and `SUPABASE_KEY` (Anon/Public key).
3. Insert them into `backend/.env`.
4. Create the required tables in Supabase (or use the REST endpoint auto-generation if configuring locally). You will need these tables:
   - `users`, `health_records`, `requests`, `messages`

### 2. Setup the Backend
Navigate to the `backend/` directory:
```bash
cd backend
pip install -r requirements.txt
python train_model.py  # (Optional) Generate the model.pkl
python app.py
```
*The backend will boot up at http://localhost:5000*

### 3. Setup the Frontend
Since the frontend uses standard HTML/JS, simply serve the directory or run it using a local live server.
```bash
# E.g. using python
cd frontend
python -m http.server 3000
```
*Open your browser and navigate to http://localhost:3000/index.html*

---

## 🎨 Design System
SheCare AI uses a meticulously crafted **Pink/Purple design terminology** focusing on an elegant, soothing, and trustworthy visual aura (inspired by `Glassmorphism` interactions and micro-animations).

## 🔒 Privacy & Safety
The predictions generated are exclusively for **informational purposes**. SheCare natively prompts users categorized as "High-Risk" to consult with an onboarded specialist prior to accepting absolute prognosis.
