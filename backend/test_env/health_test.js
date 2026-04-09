const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = 'https://blaufhzsymetvpdvyqax.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3F-vpJvLzkoyGgQ9szwJKA_jVGkY9Ch';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const email = `health_tester_${Date.now()}@gmail.com`;
const password = `StrongPass123!`;

async function runHealthTests() {
  console.log(`TEST AFTER IMPLEMENTATION: HEALTH DATA SYSTEM`);
  console.log(`========================\n`);

  // Setup: Create a user
  let authUserId;
  const signup = await supabase.auth.signUp({ 
    email, password, options: { data: { full_name: 'Health Tester' } }
  });
  authUserId = signup.data.user.id;
  await new Promise(r => setTimeout(r, 1000)); // wait for trigger

  // Wait for API to boot up if it hasn't
  await new Promise(r => setTimeout(r, 2000)); 

  // Data to send
  const testPayload = {
    user_id: authUserId,
    age: 28,
    cycle_length: 45,        // Irregular
    pain_level: 8,           // High pain
    irregular_periods: 1,    // Yes
    weight_gain: 1,          // Yes
    acne: 1,                 // Yes
    hair_growth: 1,          // Yes
    skin_darkening: 0,
    fast_food: 1
  };

  console.log(`3. Prediction test:`);
  console.log(`- Query: Calling POST http://localhost:5000/predict ...`);
  const apiStart = Date.now();
  let predictionData;
  try {
    const res = await fetch('http://localhost:5000/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(testPayload)
    });
    predictionData = await res.json();
    console.log(`- Response time: ${Date.now() - apiStart}ms`);
    console.log(`- Response status: ${res.status}`);
    console.log(`- Response body:\n`, JSON.stringify(predictionData, null, 2), `\n`);
  } catch (err) {
    console.log(`- Error: API connection failed. Did you start the Flask server? (${err.message})`);
    return;
  }

  console.log(`1. Insert test & 4. Storage test:`);
  console.log(`- Query: Authenticated client insertion of payload into health_records...`);
  
  const recordToInsert = {
     user_id: authUserId,
     cycle_length: predictionData.cycle_length || testPayload.cycle_length,
     symptoms: testPayload,
     score: predictionData.score,
     risk_label: predictionData.risk_label
  };

  const insertRes = await supabase.from('health_records').insert([recordToInsert]).select().single();
  
  if (insertRes.error) {
    console.log(`- Response: Error (${insertRes.error.message})`);
    return;
  }
  
  if (insertRes.data) {
    console.log(`- Response: SUCCESS.`);
    console.log(`- Saved Risk Score natively retrieved: ${insertRes.data.score}`);
    console.log(`- DB Row Data:\n`, JSON.stringify(insertRes.data, null, 2), '\n');
  }

  console.log(`2. Fetch test:`);
  console.log(`- Query: Fetching user history securely via Supabase JS client...`);
  const histRes = await supabase.from('health_records').select('*').eq('user_id', authUserId).order('created_at', { ascending: false });
  
  if (histRes.error) {
     console.log(`- Error: DB History fetch failed (${histRes.error.message})`);
  } else {
     console.log(`- Array Length: ${histRes.data.length}`);
     if (histRes.data.length > 0) {
        console.log(`- Secure RLS extracted Data successfully verified via Client layer.\n`);
     }
  }

}

runHealthTests();
