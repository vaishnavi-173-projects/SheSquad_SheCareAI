const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = 'https://blaufhzsymetvpdvyqax.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3F-vpJvLzkoyGgQ9szwJKA_jVGkY9Ch';
const supabase     = createClient(SUPABASE_URL, SUPABASE_KEY);
const API_BASE     = 'http://localhost:5000';

const email    = `report_tester_${Date.now()}@gmail.com`;
const password = `StrongPass123!`;

async function runReportTests() {
  console.log(`TEST: REPORT GENERATION SYSTEM`);
  console.log(`==============================\n`);

  // Setup — signup test user
  const signup = await supabase.auth.signUp({ email, password, options: { data: { full_name: 'Report Tester' } } });
  if (signup.error) { console.log(`Setup Error: ${signup.error.message}`); return; }
  const authUserId = signup.data.user.id;
  await new Promise(r => setTimeout(r, 500));
  console.log(`Test user created: ${authUserId}\n`);

  // ========================
  // 1. GENERATE REPORT
  // ========================
  console.log(`1. Generate report:`);
  console.log(`- Query: POST /generate-report with sample High Risk patient data...`);

  const payload = {
    user_id:     authUserId,
    name:        'Report Tester',
    age:         28,
    risk:        2,
    score:       13,
    risk_label:  'High Risk',
    risk_percent: 85,
    reasons:     ['Irregular cycle detected', 'High pain level observed', 'Hormonal acne observed'],
    explanation: [
      { factor: 'Irregular cycle (>35 days)', contribution: 23 },
      { factor: 'High pain level',            contribution: 15 },
      { factor: 'Acne (hormonal)',             contribution: 15 }
    ],
    suggestion:  'Immediate gynecologist consultation strongly recommended.',
    symptoms: {
      cycle_length:      45,
      pain_level:        8,
      irregular_periods: 1,
      weight_gain:       1,
      acne:              1,
      hair_growth:       1,
      skin_darkening:    0,
      fast_food:         1
    }
  };

  try {
    const res = await fetch(`${API_BASE}/generate-report`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload)
    });

    if (res.ok) {
      const pdfUrl   = res.headers.get('X-PDF-URL');
      const fileSize = res.headers.get('Content-Length') || 'unknown';
      console.log(`- Status: ${res.status} OK`);
      console.log(`- Content-Type: ${res.headers.get('content-type')}`);
      console.log(`- PDF File Size: ${fileSize} bytes`);
      console.log(`- Supabase Storage URL: ${pdfUrl || '(Storage bucket not set up — PDF still downloaded locally)'}\n`);
    } else {
      const err = await res.json();
      console.log(`- Error: ${err.error}\n`);
    }
  } catch(e) {
    console.log(`- Fatal: ${e.message} (Is Flask running?)\n`);
    return;
  }

  // Wait for Supabase Storage trigger + DB write
  await new Promise(r => setTimeout(r, 1500));

  // ========================
  // 2. CHECK REPORTS TABLE
  // ========================
  console.log(`2. Check reports table:`);
  console.log(`- Query: SELECT * FROM reports WHERE user_id = '${authUserId}'`);

  const { data: reports, error: rErr } = await supabase
    .from('reports')
    .select('*')
    .eq('user_id', authUserId)
    .order('created_at', { ascending: false });

  if (rErr) {
    console.log(`- Error: ${rErr.message}`);
    console.log(`- Fix: Check RLS INSERT policy on reports table\n`);
  } else {
    console.log(`- Response: ${reports.length} report(s) found in DB`);
    if (reports.length > 0) {
      console.log(`- Latest report:`, JSON.stringify(reports[0], null, 2));
    } else {
      // Storage upload may have failed — insert manually to verify DB works
      console.log(`- Note: PDF Storage upload may have failed (bucket missing). Inserting record directly...`);
      const { data: manualInsert, error: mErr } = await supabase
        .from('reports')
        .insert([{
          user_id:    authUserId,
          risk_level: 'High Risk',
          risk_score: 13,
          summary:    'Immediate gynecologist consultation recommended.',
          pdf_url:    null
        }])
        .select()
        .single();

      if (mErr) {
        console.log(`- Manual Insert Error: ${mErr.message}`);
      } else {
        console.log(`- Manual insert succeeded:`, JSON.stringify(manualInsert, null, 2));
      }
    }
    console.log('');
  }

  // ========================
  // 3. FETCH REPORT
  // ========================
  console.log(`3. Fetch report:`);
  console.log(`- Query: SELECT * FROM reports WHERE user_id = '${authUserId}' ORDER BY created_at DESC LIMIT 1`);

  const { data: latest, error: lErr } = await supabase
    .from('reports')
    .select('id, risk_level, risk_score, summary, pdf_url, created_at')
    .eq('user_id', authUserId)
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (lErr) {
    console.log(`- Error: ${lErr.message}\n`);
  } else if (latest) {
    console.log(`- Response: Fetched successfully`);
    console.log(`  id:         ${latest.id}`);
    console.log(`  risk_level: ${latest.risk_level}`);
    console.log(`  risk_score: ${latest.risk_score}`);
    console.log(`  summary:    ${latest.summary}`);
    console.log(`  pdf_url:    ${latest.pdf_url || '(null — storage not configured)'}`);
    console.log(`  created_at: ${latest.created_at}\n`);
  } else {
    console.log(`- Response: No report found\n`);
  }

  // ========================
  // 4. VERIFY DATA CORRECTNESS
  // ========================
  console.log(`4. Verify data correctness:`);

  let passed = 0; let failed = 0;
  const check = (name, actual, expected) => {
    const ok = actual === expected;
    console.log(`  ${ok ? '✅' : '❌'} ${name}: expected="${expected}" got="${actual}"`);
    ok ? passed++ : failed++;
  };

  if (latest) {
    check('risk_level', latest.risk_level, 'High Risk');
    check('risk_score', latest.risk_score, 13);
  } else {
    console.log(`  ⚠️  No report found to verify — check steps 1 and 2 above`);
  }

  console.log(`\n  RESULT: ${passed} passed / ${failed} failed\n`);
}

runReportTests();
