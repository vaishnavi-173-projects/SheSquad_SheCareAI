const { createClient } = require('@supabase/supabase-js');

// Config exactly as provided
const SUPABASE_URL = 'https://blaufhzsymetvpdvyqax.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3F-vpJvLzkoyGgQ9szwJKA_jVGkY9Ch';

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const email = `testuser${Date.now()}@gmail.com`;
const password = `Pass1234!!`;
let authUserId = null;
let doctorId = null;
let consultId = null;

async function logResult(stepName, queryDesc, response, error) {
  console.log(`\n========================`);
  console.log(`${stepName}`);
  console.log(`========================`);
  console.log(`- Query: ${queryDesc}`);
  if (error) {
    console.log(`- Error:`, JSON.stringify(error, null, 2));
    console.log(`- Fix:`);
    if (error.code === '42P01') console.log(`  Table is missing. Make sure you pasted the exact SQL script in the Supabase SQL editor.`);
    if (error.code === 'PGRST116' || error.message.includes('RLS')) console.log(`  Row Level Security (RLS) is blocking the query. Check the policies on the table.`);
    if (error.status === 401 || error.message.includes('Invalid API key')) console.log(`  Invalid or missing API key. Verify SUPABASE_ANON_KEY.`);
    if (error.message.includes('Auth session')) console.log(`  User is not authenticated properly for this action.`);
  } else {
    console.log(`- Response:`, JSON.stringify(response, null, 2));
  }
  return error;
}

async function runTests() {
  console.log("Starting End-to-End Supabase Verification...\n");

  // ========================
  // 1. DATABASE CONNECTION TEST
  // ========================
  let res = await supabase.from('users').select('*').limit(1);
  let hasError = await logResult('1. DATABASE CONNECTION TEST', 'SELECT * FROM users LIMIT 1', res.data, res.error);
  if (hasError) return;

  // ========================
  // 2. AUTHENTICATION TEST
  // ========================
  let authRes = await supabase.auth.signUp({ email, password });
  await logResult('2. AUTHENTICATION TEST (SignUp)', `supabase.auth.signUp({ email: "${email}" })`, authRes.data, authRes.error);
  
  if (!authRes.error) {
    let loginRes = await supabase.auth.signInWithPassword({ email, password });
    await logResult('2. AUTHENTICATION TEST (Login)', `supabase.auth.signInWithPassword`, loginRes.data, loginRes.error);
  }

  let userRes = await supabase.auth.getUser();
  if (!userRes.error && userRes.data.user) {
    authUserId = userRes.data.user.id;
    await logResult('2. AUTHENTICATION TEST (GetUser)', `supabase.auth.getUser()`, { id: authUserId, email: userRes.data.user.email }, null);
  } else {
    await logResult('2. AUTHENTICATION TEST (GetUser)', `supabase.auth.getUser()`, null, userRes.error);
    console.log("\nStopping tests early due to Auth failure. Cannot proceed without a logged-in user.");
    return;
  }

  // Waiting 1.5 seconds for the DB trigger (handle_new_user) to run asynchronously
  await new Promise(r => setTimeout(r, 1500)); 

  // ========================
  // 3. USER TABLE SYNC TEST
  // ========================
  res = await supabase.from('users').select('*').eq('id', authUserId).single();
  let syncError = await logResult('3. USER TABLE SYNC TEST', `SELECT * FROM users WHERE id = '${authUserId}'`, res.data, res.error);
  
  if (syncError && syncError.code === 'PGRST116') {
    // Manually insert
    console.log("\n- Trigger failed or delayed. Attempting manual insert into users table...");
    res = await supabase.from('users').upsert({ id: authUserId, email, role: 'patient', name: 'Test User' }).select().single();
    await logResult('3. USER TABLE SYNC TEST (Manual Insert)', `INSERT INTO users (id, email, role)`, res.data, res.error);
    if (res.error) return;
  }

  // ========================
  // 4. HEALTH DATA INSERT TEST
  // ========================
  const healthData = {
    user_id: authUserId,
    cycle_length: 40,
    symptoms: { irregular: true, acne: true },
    risk_label: "High Risk",
    score: 8
  };
  res = await supabase.from('health_records').insert(healthData).select().single();
  await logResult('4. HEALTH DATA INSERT TEST', `INSERT INTO health_records`, res.data, res.error);

  // ========================
  // 5. DATA FETCH TEST
  // ========================
  res = await supabase.from('health_records').select('*').eq('user_id', authUserId);
  await logResult('5. DATA FETCH TEST', `SELECT * FROM health_records WHERE user_id = '${authUserId}'`, res.data, res.error);

  // ========================
  // 6. REPORT INSERT + FETCH
  // ========================
  const reportData = {
    user_id: authUserId,
    risk_level: 'High Risk',
    summary: 'Dummy report summary',
    pdf_url: null
  };
  await supabase.from('reports').insert(reportData);
  res = await supabase.from('reports').select('*').eq('user_id', authUserId);
  await logResult('6. REPORT FETCH TEST', `SELECT * FROM reports WHERE user_id = '${authUserId}'`, res.data, res.error);

  // ========================
  // 7. DOCTOR QUERY TEST
  // ========================
  res = await supabase.from('doctors').select('*').limit(5);
  await logResult('7. DOCTOR QUERY TEST', `SELECT * FROM doctors LIMIT 5`, res.data, res.error);
  if (!res.error && res.data.length > 0) {
     doctorId = res.data[0].id;
  } else {
     // Because doctors might be empty, try fetching from users where role=doctor
     let udocs = await supabase.from('users').select('*').eq('role', 'doctor').limit(1);
     if (udocs.data && udocs.data.length > 0) {
        doctorId = udocs.data[0].id;
     } else {
        console.log("- Could not find a test doctor to use for checking consultations. Skipping to RLS test.");
     }
  }

  // ========================
  // 8. CONSULTATION TEST
  // ========================
  if (doctorId) {
    const consultParams = { patient_id: authUserId, doctor_id: doctorId, status: 'pending' };
    await supabase.from('consultations').insert(consultParams);
    res = await supabase.from('consultations').select('*').eq('patient_id', authUserId).eq('doctor_id', doctorId);
    await logResult('8. CONSULTATION TEST', `SELECT * FROM consultations`, res.data, res.error);
    
    if (res.data && res.data.length > 0) {
      consultId = res.data[0].id;

      // ========================
      // 9. CHAT SYSTEM TEST
      // ========================
      await supabase.from('messages').insert({ consultation_id: consultId, sender_id: authUserId, content: 'Test message here' });
      res = await supabase.from('messages').select('*').eq('consultation_id', consultId);
      await logResult('9. CHAT SYSTEM TEST', `SELECT * FROM messages WHERE consultation_id = '${consultId}'`, res.data, res.error);
    }
  }

  // ========================
  // 10. RLS DEBUG TEST
  // ========================
  console.log(`\n========================`);
  console.log(`10. RLS DEBUG TEST`);
  console.log(`========================`);
  console.log(`Verifying standard RLS behavior... fetching health_records anonymously should fail.`);
  
  // Create an anonymous client to test RLS blocks reads for unauthorized users
  const anonClient = createClient(SUPABASE_URL, SUPABASE_KEY);
  let anonRes = await anonClient.from('health_records').select('*');
  if (anonRes.data && anonRes.data.length === 0) {
      console.log(`- Query: select * from health_records (unauthenticated)`);
      console.log(`- Response: [] (RLS successfully prevented data leak)`);
  } else if (anonRes.error) {
      console.log(`- Query: select * from health_records (unauthenticated)`);
      console.log(`- Error: RLS blocked query as expected:`, anonRes.error.message);
  } else {
      console.log(`- ⚠️ WARNING: Anonymous user gained access to health records! RLS policy is missing!`);
  }

  console.log(`\nEnd-to-End Testing Completed!`);
}

runTests();
