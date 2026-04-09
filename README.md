# 🌸 SheCare AI — Smart Reproductive Health Assistant

> AI-powered system for early detection of PCOS & Endometriosis with doctor integration and real-time communication.

---

## 🚀 Key Features

- 🧠 **Explainable AI Risk Detection**: Transparent analysis of health factors.
- 📊 **Symptom Tracking**: Easy-to-use interface for monitoring reproductive health.
- 📄 **PDF Report Generation**: Professional AI-generated narratives combined with clinical logic.
- 👩‍⚕️ **Doctor Recommendation**: Direct connection to registered specialists.
- 🔗 **Consultation Pipeline**: Secure request-approve workflow for patients and doctors.
- 💬 **Real-Time Chat**: Web-socket based messaging with resilient polling fallbacks.
- 🔐 **Secure Data**: Industry-standard isolation using Supabase Row Level Security (RLS).
- 🧪 **E2E Testing**: Comprehensive automation suite using Playwright.

---

## 🧠 System Architecture

```text
[Frontend UI (HTML/JS)]
        ↓
[Flask Backend API]
        ↓
[Supabase DB + Auth + Storage]
        ↓
[Gemini AI (optional)]
```

### ⚙️ Workflow
1. **Login** → 2. **Track Symptoms** → 3. **AI Prediction** → 4. **Generate PDF** → 5. **Consult Doctor** → 6. **Live Chat**

---

## 🧰 Tech Stack

- **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+)
- **Backend**: Python (Flask)
- **Database**: Supabase (PostgreSQL)
- **AI/LLM**: Google Gemini 1.5 Flash (Narratives) + Scikit-learn (Risk Logic)
- **Storage**: Supabase Storage (PDF Bucket)
- **Realtime**: Supabase Realtime (WebSockets)
- **Testing**: Playwright (End-to-End Automation)

---

## 📁 Project Structure

```text
SheCareAI/
├── frontend/        # Web Interface (HTML/CSS/JS)
├── backend/         # Flask API & ML Logic
├── tests/           # Playwright E2E Test Suite
├── .gitignore       # Production exclusion rules
└── README.md        # Project Documentation
```

---

## ⚙️ Setup Instructions

### 1️⃣ Clone Repository
```bash
git clone https://github.com/vaishnavi-173-projects/SheSquad_SheCareAI.git
cd SheSquad_SheCareAI
```

### 2️⃣ Setup Environment-Variables
Create a `.env` file in the `backend/` directory:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_key
GEMINI_API_KEY=your_key
```

### 3️⃣ Install & Run Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
```
👉 API runs on: `http://localhost:5000`

### 4️⃣ Launch Frontend
Serve the `frontend/` directory using **Live Server** or any static host.
👉 UI runs on: `http://localhost:5500`

---

## 🧪 Run Automation Tests
```bash
npm install
npx playwright install chrome
npx playwright test tests/e2e/shecare_demo.spec.js --headed
```

---

## 🔐 Security & Compliance
- **RLS (Row Level Security)**: Patient data is strictly isolated; doctors can only see data for accepted consultations.
- **Credential Hygiene**: Zero local secrets; all sensitive keys are managed via environment variables.
- **Privacy**: No diagnostic claims made; focusing on communication and risk awareness.

---

## ⚠️ Disclaimer
**This system does NOT provide medical diagnosis.** It is designed for early risk detection and to facilitate efficient communication between patients and licensed medical professionals.

---

## 👩‍💻 Team
- **Vaishnavi V**
- **Sakshi Rajendra Kamble**
- **Saraswati Kulkarni**
- **Ramya B**

---

## 🌟 Project Impact
SheCare AI empowers women by reducing the time between symptom onset and clinical consultation, transforming unstructured health data into actionable medical insights.
