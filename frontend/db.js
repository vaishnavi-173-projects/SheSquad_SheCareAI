// ─────────────────────────────────────────────────────────────
// SheCare AI — Reusable Frontend Database Functions (db.js)
// Requires: config.js + supabaseClient.js loaded before this
// ─────────────────────────────────────────────────────────────

// ── saveHealthData ──────────────────────────────────────────
/**
 * Insert a new health record for the logged-in user.
 * @param {string} userId - Supabase auth UUID
 * @param {object} data   - All symptom + prediction fields
 * @returns {object}      - { data, error }
 */
async function saveHealthData(userId, data) {
  const sb = getSupabase();
  if (!sb) return { data: null, error: 'Supabase not ready' };

  const record = {
    user_id:           userId,
    cycle_length:      data.cycle_length,
    pain_level:        data.pain_level,
    irregular_periods: !!data.irregular_periods,
    weight_gain:       !!data.weight_gain,
    acne:              !!data.acne,
    hair_growth:       !!data.hair_growth,
    skin_darkening:    !!data.skin_darkening,
    fast_food:         !!data.fast_food,
    symptoms:          data,                  // full JSON snapshot
    risk:              data.risk,
    score:             data.score,
    risk_label:        data.risk_label,
    risk_percent:      data.risk_percent,
    reasons:           data.reasons || [],
    suggestion:        data.suggestion
  };

  try {
    const { data: result, error } = await sb
      .from('health_records')
      .insert([record])
      .select()
      .single();

    if (error) throw error;
    console.log('[DB] ✅ Health record saved:', result.id);
    return { data: result, error: null };
  } catch (e) {
    console.error('[DB] ❌ saveHealthData error:', e.message);
    return { data: null, error: e.message };
  }
}


// ── getHealthHistory ────────────────────────────────────────
/**
 * Fetch all health records for a user (newest first).
 * @param {string} userId
 * @returns {Array} - list of health records
 */
async function getHealthHistory(userId) {
  const sb = getSupabase();
  if (!sb) return [];

  try {
    const { data, error } = await sb
      .from('health_records')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  } catch (e) {
    console.error('[DB] ❌ getHealthHistory error:', e.message);
    return [];
  }
}


// ── getUserData ─────────────────────────────────────────────
/**
 * Fetch user profile from the users table.
 * @param {string} userId
 * @returns {object|null}
 */
async function getUserData(userId) {
  const sb = getSupabase();
  if (!sb) return null;

  try {
    const { data, error } = await sb
      .from('users')
      .select('*')
      .eq('id', userId)
      .single();

    if (error) throw error;
    return data;
  } catch (e) {
    console.error('[DB] ❌ getUserData error:', e.message);
    return null;
  }
}


// ── upsertUser ──────────────────────────────────────────────
/**
 * Insert or update user profile after login/signup.
 * Called automatically in auth state change.
 * @param {object} authUser - from supabase.auth.getUser()
 * @param {string} role     - 'patient' or 'doctor'
 */
async function upsertUser(authUser, role = 'patient') {
  const sb = getSupabase();
  if (!sb || !authUser) return;

  const profile = {
    id:    authUser.id,
    email: authUser.email,
    name:  authUser.user_metadata?.full_name || authUser.email.split('@')[0],
    role:  role
  };

  try {
    const { error } = await sb
      .from('users')
      .upsert([profile], { onConflict: 'id' });

    if (error) throw error;
    console.log('[DB] ✅ User upserted:', profile.email, '| role:', role);
  } catch (e) {
    console.error('[DB] ❌ upsertUser error:', e.message);
  }
}


// ── saveReport ──────────────────────────────────────────────
/**
 * Store a generated report record in the reports table.
 * @param {string} userId
 * @param {object} reportData - { risk_level, risk_score, summary, pdf_url }
 * @returns {object} - { data, error }
 */
async function saveReport(userId, reportData) {
  const sb = getSupabase();
  if (!sb) return { data: null, error: 'Supabase not ready' };

  const record = {
    user_id:    userId,
    risk_level: reportData.risk_level  || reportData.risk_label,
    risk_score: reportData.risk_score  || reportData.score,
    summary:    reportData.summary     || reportData.suggestion,
    pdf_url:    reportData.pdf_url     || null
  };

  try {
    const { data, error } = await sb
      .from('reports')
      .insert([record])
      .select()
      .single();

    if (error) throw error;
    console.log('[DB] ✅ Report saved:', data.id);
    return { data, error: null };
  } catch (e) {
    console.error('[DB] ❌ saveReport error:', e.message);
    return { data: null, error: e.message };
  }
}


// ── getReports ──────────────────────────────────────────────
/**
 * Fetch all reports for a user.
 * @param {string} userId
 * @returns {Array}
 */
async function getReports(userId) {
  const sb = getSupabase();
  if (!sb) return [];

  try {
    const { data, error } = await sb
      .from('reports')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  } catch (e) {
    console.error('[DB] ❌ getReports error:', e.message);
    return [];
  }
}


// ── getDoctors ──────────────────────────────────────────────
/**
 * Fetch doctors, optionally filtered by specialization.
 * @param {string} specialization - e.g. 'Gynecologist'
 * @returns {Array}
 */
async function getDoctors(specialization = null) {
  const sb = getSupabase();
  if (!sb) return [];

  try {
    let query = sb
      .from('doctors')
      .select('id, name, specialization, location, rating, bio, available')
      .eq('available', true)
      .order('rating', { ascending: false });

    if (specialization) {
      query = query.eq('specialization', specialization);
    }

    const { data, error } = await query;
    if (error) throw error;
    return data || [];
  } catch (e) {
    console.error('[DB] ❌ getDoctors error:', e.message);
    return [];
  }
}


// ── createConsultation ──────────────────────────────────────
/**
 * Patient requests a consultation with a doctor.
 * @param {string} patientId
 * @param {string} doctorId
 * @returns {object} - { data, error }
 */
async function createConsultation(patientId, doctorId) {
  const sb = getSupabase();
  if (!sb) return { data: null, error: 'Supabase not ready' };

  try {
    const { data, error } = await sb
      .from('consultations')
      .upsert([{ patient_id: patientId, doctor_id: doctorId, status: 'pending' }],
               { onConflict: 'patient_id,doctor_id' })
      .select()
      .single();

    if (error) throw error;
    console.log('[DB] ✅ Consultation created:', data.id);
    return { data, error: null };
  } catch (e) {
    console.error('[DB] ❌ createConsultation error:', e.message);
    return { data: null, error: e.message };
  }
}


// ── getPatientConsultation ──────────────────────────────────
/**
 * Get patient's active consultation (with doctor info).
 * @param {string} patientId
 * @returns {object|null}
 */
async function getPatientConsultation(patientId) {
  const sb = getSupabase();
  if (!sb) return null;

  try {
    const { data, error } = await sb
      .from('consultations')
      .select(`
        id, status, created_at,
        doctors ( id, name, specialization, location, rating )
      `)
      .eq('patient_id', patientId)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) throw error;
    return data;
  } catch (e) {
    console.error('[DB] ❌ getPatientConsultation error:', e.message);
    return null;
  }
}


// ── getDoctorConsultations ──────────────────────────────────
/**
 * Fetch all consultations for a doctor (with patient info).
 * @param {string} doctorId
 * @returns {Array}
 */
async function getDoctorConsultations(doctorId) {
  const sb = getSupabase();
  if (!sb) return [];

  try {
    const { data, error } = await sb
      .from('consultations')
      .select(`
        id, status, created_at, updated_at,
        users!consultations_patient_id_fkey ( id, name, email, age )
      `)
      .eq('doctor_id', doctorId)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  } catch (e) {
    console.error('[DB] ❌ getDoctorConsultations error:', e.message);
    return [];
  }
}


// ── updateConsultationStatus ────────────────────────────────
/**
 * Doctor accepts or rejects a consultation.
 * @param {string} consultationId
 * @param {string} status - 'accepted' | 'rejected' | 'completed'
 * @returns {object} - { data, error }
 */
async function updateConsultationStatus(consultationId, status) {
  const sb = getSupabase();
  if (!sb) return { data: null, error: 'Supabase not ready' };

  try {
    const { data, error } = await sb
      .from('consultations')
      .update({ status })
      .eq('id', consultationId)
      .select()
      .single();

    if (error) throw error;
    return { data, error: null };
  } catch (e) {
    console.error('[DB] ❌ updateConsultationStatus error:', e.message);
    return { data: null, error: e.message };
  }
}


// ── sendMessage ─────────────────────────────────────────────
/**
 * Send a chat message within a consultation.
 * @param {string} consultationId
 * @param {string} senderId
 * @param {string} content
 * @returns {object} - { data, error }
 */
async function sendMessage(consultationId, senderId, content) {
  const sb = getSupabase();
  if (!sb) return { data: null, error: 'Supabase not ready' };

  try {
    const { data, error } = await sb
      .from('messages')
      .insert([{ consultation_id: consultationId, sender_id: senderId, content }])
      .select()
      .single();

    if (error) throw error;
    return { data, error: null };
  } catch (e) {
    console.error('[DB] ❌ sendMessage error:', e.message);
    return { data: null, error: e.message };
  }
}


// ── getMessages ─────────────────────────────────────────────
/**
 * Load all messages for a consultation.
 * @param {string} consultationId
 * @returns {Array}
 */
async function getMessages(consultationId) {
  const sb = getSupabase();
  if (!sb) return [];

  try {
    const { data, error } = await sb
      .from('messages')
      .select('id, sender_id, content, read, created_at')
      .eq('consultation_id', consultationId)
      .order('created_at', { ascending: true });

    if (error) throw error;
    return data || [];
  } catch (e) {
    console.error('[DB] ❌ getMessages error:', e.message);
    return [];
  }
}


// ── subscribeToMessages ─────────────────────────────────────
/**
 * Subscribe to realtime messages for a consultation.
 * @param {string} consultationId
 * @param {function} onMessage - callback(newMessage)
 * @returns {RealtimeChannel} - call .unsubscribe() to clean up
 */
function subscribeToMessages(consultationId, onMessage) {
  const sb = getSupabase();
  if (!sb) return null;

  const channel = sb
    .channel(`messages:${consultationId}`)
    .on(
      'postgres_changes',
      {
        event:  'INSERT',
        schema: 'public',
        table:  'messages',
        filter: `consultation_id=eq.${consultationId}`
      },
      (payload) => {
        console.log('[Realtime] 📨 New message:', payload.new);
        onMessage(payload.new);
      }
    )
    .subscribe((status) => {
      console.log('[Realtime] Channel status:', status);
    });

  return channel;
}


// ── subscribeToConsultations ────────────────────────────────
/**
 * Doctor: Subscribe to realtime consultation status changes.
 * @param {string} doctorId
 * @param {function} onChange - callback(updatedConsultation)
 * @returns {RealtimeChannel}
 */
function subscribeToConsultations(doctorId, onChange) {
  const sb = getSupabase();
  if (!sb) return null;

  const channel = sb
    .channel(`consultations:doctor:${doctorId}`)
    .on(
      'postgres_changes',
      {
        event:  '*',
        schema: 'public',
        table:  'consultations',
        filter: `doctor_id=eq.${doctorId}`
      },
      (payload) => {
        console.log('[Realtime] 🔔 Consultation update:', payload);
        onChange(payload.new || payload.old);
      }
    )
    .subscribe();

  return channel;
}
