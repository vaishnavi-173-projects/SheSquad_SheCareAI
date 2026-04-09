-- ═══════════════════════════════════════════════════════════════
-- SheCare AI — Full Supabase Database Schema
-- Run this entire script in: Supabase Dashboard → SQL Editor → Run
-- ═══════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────
-- 1. USERS (mirrors auth.users)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name        TEXT,
  email       TEXT UNIQUE,
  role        TEXT NOT NULL DEFAULT 'patient' CHECK (role IN ('patient', 'doctor')),
  age         INTEGER,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON public.users(role);

-- Auto-create user profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.users (id, name, email, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'role', 'patient')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ─────────────────────────────────────────────
-- 2. DOCTORS (extended profile for doctor role)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.doctors (
  id              UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  specialization  TEXT NOT NULL DEFAULT 'Gynecologist',
  location        TEXT,
  rating          NUMERIC(3,1) DEFAULT 4.5 CHECK (rating >= 0 AND rating <= 5),
  bio             TEXT,
  available       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doctors_specialization ON public.doctors(specialization);
CREATE INDEX IF NOT EXISTS idx_doctors_rating ON public.doctors(rating DESC);

-- Seed demo doctors (safe to re-run — uses ON CONFLICT DO NOTHING)
-- NOTE: These will be inserted after real auth users exist.
-- You can insert demo doctors manually from the Supabase Table Editor.


-- ─────────────────────────────────────────────
-- 3. HEALTH_RECORDS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.health_records (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  cycle_length       INTEGER,
  pain_level         INTEGER CHECK (pain_level BETWEEN 1 AND 10),
  irregular_periods  BOOLEAN DEFAULT FALSE,
  weight_gain        BOOLEAN DEFAULT FALSE,
  acne               BOOLEAN DEFAULT FALSE,
  hair_growth        BOOLEAN DEFAULT FALSE,
  skin_darkening     BOOLEAN DEFAULT FALSE,
  fast_food          BOOLEAN DEFAULT FALSE,
  symptoms           JSONB,         -- full raw input stored as JSON
  risk               INTEGER CHECK (risk IN (0, 1, 2)),
  score              INTEGER,
  risk_label         TEXT,
  risk_percent       INTEGER,
  reasons            TEXT[],
  suggestion         TEXT,
  created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_records_user_id    ON public.health_records(user_id);
CREATE INDEX IF NOT EXISTS idx_health_records_created_at ON public.health_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_records_risk       ON public.health_records(risk);


-- ─────────────────────────────────────────────
-- 4. REPORTS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.reports (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  risk_level  TEXT,
  risk_score  INTEGER,
  summary     TEXT,
  pdf_url     TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user_id    ON public.reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON public.reports(created_at DESC);


-- ─────────────────────────────────────────────
-- 5. CONSULTATIONS (patient ↔ doctor)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.consultations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id  UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  doctor_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'completed')),
  notes       TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (patient_id, doctor_id)  -- one active consultation per pair
);

CREATE INDEX IF NOT EXISTS idx_consultations_patient_id ON public.consultations(patient_id);
CREATE INDEX IF NOT EXISTS idx_consultations_doctor_id  ON public.consultations(doctor_id);
CREATE INDEX IF NOT EXISTS idx_consultations_status     ON public.consultations(status);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS set_consultations_updated_at ON public.consultations;
CREATE TRIGGER set_consultations_updated_at
  BEFORE UPDATE ON public.consultations
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ─────────────────────────────────────────────
-- 6. MESSAGES
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.messages (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consultation_id  UUID NOT NULL REFERENCES public.consultations(id) ON DELETE CASCADE,
  sender_id        UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  content          TEXT NOT NULL,
  read             BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_consultation_id ON public.messages(consultation_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id       ON public.messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at      ON public.messages(created_at ASC);


-- ═══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ═══════════════════════════════════════════════════════════════

-- Enable RLS on all tables
ALTER TABLE public.users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctors        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages       ENABLE ROW LEVEL SECURITY;


-- ── USERS ──
DROP POLICY IF EXISTS "Users can view own profile"    ON public.users;
DROP POLICY IF EXISTS "Users can update own profile"  ON public.users;
DROP POLICY IF EXISTS "Doctors visible to all users"  ON public.users;

CREATE POLICY "Users can view own profile"
  ON public.users FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON public.users FOR UPDATE
  USING (auth.uid() = id);

-- Patients can see doctors (for listing)
CREATE POLICY "Doctors visible to all users"
  ON public.users FOR SELECT
  USING (role = 'doctor' OR auth.uid() = id);


-- ── DOCTORS ──
DROP POLICY IF EXISTS "Doctors table visible to all authenticated users" ON public.doctors;
DROP POLICY IF EXISTS "Doctors can edit their own profile" ON public.doctors;

CREATE POLICY "Doctors table visible to all authenticated users"
  ON public.doctors FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Doctors can edit their own profile"
  ON public.doctors FOR UPDATE
  USING (auth.uid() = id);


-- ── HEALTH_RECORDS ──
DROP POLICY IF EXISTS "Patients see only their own records"    ON public.health_records;
DROP POLICY IF EXISTS "Patients can insert their own records"  ON public.health_records;
DROP POLICY IF EXISTS "Doctors see records of their patients"  ON public.health_records;

CREATE POLICY "Patients see only their own records"
  ON public.health_records FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Patients can insert their own records"
  ON public.health_records FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Doctors see records of patients in accepted consultations
CREATE POLICY "Doctors see records of their patients"
  ON public.health_records FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.consultations c
      WHERE c.doctor_id  = auth.uid()
        AND c.patient_id = health_records.user_id
        AND c.status     = 'accepted'
    )
  );


-- ── REPORTS ──
DROP POLICY IF EXISTS "Patients see only their own reports"   ON public.reports;
DROP POLICY IF EXISTS "Patients can insert their own reports" ON public.reports;
DROP POLICY IF EXISTS "Doctors see reports of their patients" ON public.reports;

CREATE POLICY "Patients see only their own reports"
  ON public.reports FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Patients can insert their own reports"
  ON public.reports FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Doctors see reports of their patients"
  ON public.reports FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.consultations c
      WHERE c.doctor_id  = auth.uid()
        AND c.patient_id = reports.user_id
        AND c.status     = 'accepted'
    )
  );


-- ── CONSULTATIONS ──
DROP POLICY IF EXISTS "Patients see their own consultations"   ON public.consultations;
DROP POLICY IF EXISTS "Patients can create consultations"      ON public.consultations;
DROP POLICY IF EXISTS "Doctors see their own consultations"    ON public.consultations;
DROP POLICY IF EXISTS "Doctors can update consultation status" ON public.consultations;

CREATE POLICY "Patients see their own consultations"
  ON public.consultations FOR SELECT
  USING (auth.uid() = patient_id);

CREATE POLICY "Patients can create consultations"
  ON public.consultations FOR INSERT
  WITH CHECK (auth.uid() = patient_id);

CREATE POLICY "Doctors see their own consultations"
  ON public.consultations FOR SELECT
  USING (auth.uid() = doctor_id);

CREATE POLICY "Doctors can update consultation status"
  ON public.consultations FOR UPDATE
  USING (auth.uid() = doctor_id);


-- ── MESSAGES ──
DROP POLICY IF EXISTS "Chat participants can view messages"   ON public.messages;
DROP POLICY IF EXISTS "Chat participants can send messages"   ON public.messages;

-- Only participants in the consultation can read messages
CREATE POLICY "Chat participants can view messages"
  ON public.messages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.consultations c
      WHERE c.id = messages.consultation_id
        AND (c.patient_id = auth.uid() OR c.doctor_id = auth.uid())
    )
  );

-- Only participants can send messages
CREATE POLICY "Chat participants can send messages"
  ON public.messages FOR INSERT
  WITH CHECK (
    auth.uid() = sender_id AND
    EXISTS (
      SELECT 1 FROM public.consultations c
      WHERE c.id = consultation_id
        AND (c.patient_id = auth.uid() OR c.doctor_id = auth.uid())
        AND c.status = 'accepted'
    )
  );


-- ═══════════════════════════════════════════════════════════════
-- ENABLE REALTIME for Messages
-- ═══════════════════════════════════════════════════════════════
ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
ALTER PUBLICATION supabase_realtime ADD TABLE public.consultations;


-- ═══════════════════════════════════════════════════════════════
-- STORAGE BUCKET for PDFs
-- Run this in SQL Editor too
-- ═══════════════════════════════════════════════════════════════
INSERT INTO storage.buckets (id, name, public)
VALUES ('reports', 'reports', true)
ON CONFLICT (id) DO NOTHING;

-- Allow authenticated users to upload to their own folder
CREATE POLICY "Authenticated users can upload reports"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (bucket_id = 'reports' AND (storage.foldername(name))[1] = auth.uid()::text);

-- Anyone can read report PDFs (they have unique URLs)
CREATE POLICY "Public can read report PDFs"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'reports');
