const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = 'https://blaufhzsymetvpdvyqax.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3F-vpJvLzkoyGgQ9szwJKA_jVGkY9Ch';
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

const testEmail = `auth_tester_${Date.now()}@gmail.com`;
const testPassword = `StrongPass123!`;

async function runTests() {
  console.log(`TEST AFTER IMPLEMENTATION`);
  console.log(`========================\n`);

  let authUserId = null;

  // 1. Signup Test
  console.log(`1. Signup test:`);
  console.log(`- Query: Creating user ${testEmail}...`);
  const signupRes = await supabase.auth.signUp({ 
    email: testEmail, 
    password: testPassword,
    options: {
        data: { full_name: 'Auth Tester', role: 'patient' }
    }
  });
  
  if (signupRes.error) {
    console.log(`- Response: Error (${signupRes.error.message})`);
    return;
  }
  
  authUserId = signupRes.data.user.id;
  console.log(`- Response: SUCCESS. User ID created: ${authUserId}\n`);

  // Explicitly sign out before login test to ensure a clean login
  await supabase.auth.signOut();

  // 2. Login Test
  console.log(`2. Login test:`);
  console.log(`- Query: Logging in with same user...`);
  const loginRes = await supabase.auth.signInWithPassword({ 
    email: testEmail, 
    password: testPassword 
  });

  if (loginRes.error) {
    console.log(`- Response: Error (${loginRes.error.message})`);
    return;
  }
  
  console.log(`- Response: SUCCESS. Logged in successfully.`);
  console.log(`- Session token sample: ${loginRes.data.session.access_token.substring(0, 30)}...`);
  console.log(`- Expires in: ${loginRes.data.session.expires_in} seconds\n`);

  // Wait briefly for the DB trigger to handle the insert
  await new Promise(r => setTimeout(r, 1000));

  // 3. DB Test (Does auth match users table?)
  console.log(`3. DB test:`);
  console.log(`- Query: Checking if ID exists in public.users table...`);
  const dbRes = await supabase.from('users').select('*').eq('id', authUserId).single();

  if (dbRes.error) {
     console.log(`- Response: Error fetching from users table (${dbRes.error.message})`);
  } else if (dbRes.data) {
     console.log(`- Response: SUCCESS. User confirmed successfully inserted into DB.`);
     console.log(`- DB Row Data:\n`, JSON.stringify(dbRes.data, null, 2));
  } else {
     console.log(`- Response: FAIL. User was not found in the users table.`);
  }
}

runTests();
