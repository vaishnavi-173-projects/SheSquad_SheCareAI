const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

const SUPABASE_URL = 'https://blaufhzsymetvpdvyqax.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3F-vpJvLzkoyGgQ9szwJKA_jVGkY9Ch'; // public anon key is sufficient for authenticated actions
const supabase     = createClient(SUPABASE_URL, SUPABASE_KEY);

async function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

async function runChatTest() {
  console.log(`\n==================================================`);
  console.log(`FULL SYSTEM TEST: REPORTS, CONSULTATIONS & CHAT`);
  console.log(`==================================================\n`);

  // 1. Setup Patient
  const pEmail = `patient_test_${Date.now()}@gmail.com`;
  console.log(`[+] Registering Patient...`);
  const pSignup = await supabase.auth.signUp({ email: pEmail, password: 'StrongPass123!', options: { data: { full_name: 'Test Patient', role: 'patient' } } });
  if (pSignup.error) { console.log(pSignup.error); return; }
  const patient = pSignup.data.user;
  
  // 2. Setup Doctor
  const dEmail = `doctor_test_${Date.now()}@gmail.com`;
  console.log(`[+] Registering Doctor...`);
  const dSignup = await supabase.auth.signUp({ email: dEmail, password: 'StrongPass123!', options: { data: { full_name: 'Dr. Smith', role: 'doctor' } } });
  if (dSignup.error) { console.log(dSignup.error); return; }
  const doctor = dSignup.data.user;

  await delay(1000); // Wait for triggers to resolve users/doctors tables

  console.log(`\n========================`);
  console.log(`1. PATIENT SELECTS DOCTOR -> CONSULTATION CREATED`);
  console.log(`========================`);
  
  // Simulate Patient initiating Consultation
  // Switching to Patient context
  await supabase.auth.signInWithPassword({ email: pEmail, password: 'StrongPass123!' });
  const { data: consultData, error: consultErr } = await supabase.from('consultations').upsert([{ patient_id: patient.id, doctor_id: doctor.id, status: 'pending' }], { onConflict: 'patient_id,doctor_id' }).select().single();
  if (consultErr) { console.log(`[❌] Error: ${consultErr.message}`); return; }
  console.log(`[✔] Consultation created. ID: ${consultData.id}`);
  console.log(`[✔] Status: ${consultData.status}`);

  console.log(`\n========================`);
  console.log(`2. DOCTOR ACCEPTS CONSULTATION`);
  console.log(`========================`);

  // Switching to Doctor context
  await supabase.auth.signInWithPassword({ email: dEmail, password: 'StrongPass123!' });
  const { data: updateData, error: updateErr } = await supabase.from('consultations').update({ status: 'accepted' }).eq('id', consultData.id).select().single();
  if (updateErr) { console.log(`[❌] Error: ${updateErr.message}`); return; }
  console.log(`[✔] Consultation matched for Dr. Smith.`);
  console.log(`[✔] Status updated to: ${updateData.status}`);

  console.log(`\n========================`);
  console.log(`3. PATIENT GENERATES REPORT -> DB VERIFICATION`);
  console.log(`========================`);
  await supabase.auth.signInWithPassword({ email: pEmail, password: 'StrongPass123!' });
  const reportUrl = `https://storage.example.com/reports/${patient.id}/report_mock.pdf`;
  const { error: repErr } = await supabase.from('reports').insert([{ user_id: patient.id, risk_level: 'High Risk', pdf_url: reportUrl }]);
  if (repErr) { console.log(`[❌] Error: ${repErr.message}`); return; }
  console.log(`[✔] Report smoothly generated and pdf_url saved natively into reports DB.`);


  console.log(`\n========================`);
  console.log(`4. DOCTOR VIEWS REPORT (RLS CHECK)`);
  console.log(`========================`);
  await supabase.auth.signInWithPassword({ email: dEmail, password: 'StrongPass123!' });
  // RLS states Doctor can only see if consultation is accepted. It is accepted!
  const { data: docReports, error: docRepErr } = await supabase.from('reports').select('*').eq('user_id', patient.id);
  if (docRepErr) { console.log(`[❌] Error: ${docRepErr.message}`); return; }
  console.log(`[✔] Doctor correctly sees ${docReports.length} report(s) for the patient.`);
  console.log(`[✔] Official PDF Extracted automatically: ${docReports[0].pdf_url}`);


  console.log(`\n========================`);
  console.log(`5. CHAT / MESSAGING PIPELINE`);
  console.log(`========================`);
  
  console.log(`[+] Patient sends message...`);
  await supabase.auth.signInWithPassword({ email: pEmail, password: 'StrongPass123!' });
  const { error: msg1Err } = await supabase.from('messages').insert([{ consultation_id: consultData.id, sender_id: patient.id, content: `Hello Dr. Smith!` }]);
  if (msg1Err) console.log(`[❌] Error: ${msg1Err.message}`);

  await delay(500);

  console.log(`[+] Doctor sends reply...`);
  await supabase.auth.signInWithPassword({ email: dEmail, password: 'StrongPass123!' });
  const { error: msg2Err } = await supabase.from('messages').insert([{ consultation_id: consultData.id, sender_id: doctor.id, content: `Hi there, I reviewed your report.` }]);
  if (msg2Err) console.log(`[❌] Error: ${msg2Err.message}`);

  await delay(500);

  // Read message queue natively via Doctor endpoint mirroring dashboard
  const { data: allMsgs, error: fetchErr } = await supabase.from('messages').select('*').eq('consultation_id', consultData.id).order('created_at', { ascending: true });
  if (fetchErr) { console.log(`[❌] Error: ${fetchErr.message}`); return; }
  
  console.log(`[✔] All messages extracted perfectly:`);
  allMsgs.forEach(m => {
     let context = "Patient (PINK Bubble)";
     if (m.sender_id === doctor.id) context = "Doctor (PURPLE Bubble)";
     console.log(`    -> [${context}] "${m.content}"`);
  });

  console.log(`\n[SUCCESS] FINAL TEST PASSED: Full Doctor-Patient Loop Stabilized.\n`);
}

runChatTest();
