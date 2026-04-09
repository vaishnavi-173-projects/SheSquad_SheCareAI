// ─────────────────────────────────────────────────────────────
// SheCare AI — Supabase Configuration
// ─────────────────────────────────────────────────────────────
// ⚠️  PASTE YOUR REAL SUPABASE_ANON_KEY below.
//    Get it from: Supabase Dashboard → Project Settings → API → anon/public
// ─────────────────────────────────────────────────────────────

window.SHECARE_CONFIG = {
  supabaseUrl:  'https://nmelswteuphdmhwxxxl.supabase.co',
  supabaseKey:  'YOUR_SUPABASE_ANON_KEY_HERE',   // ← Replace this!
  apiBase:      'http://localhost:5000',          // Flask backend URL
  redirectBase: window.location.origin           // Auto-detects http://localhost:5500
};
