// ─────────────────────────────────────────────────────────────
// SheCare AI — Supabase Client (shared singleton)
// Include AFTER config.js in every HTML page:
//   <script src="config.js"></script>
//   <script src="supabaseClient.js"></script>
// ─────────────────────────────────────────────────────────────

(function () {
  const cfg = window.SHECARE_CONFIG;
  if (!cfg || !cfg.supabaseUrl || cfg.supabaseKey === 'YOUR_SUPABASE_ANON_KEY_HERE') {
    console.error('[SheCare] ⚠️ Supabase key not configured. Open static/config.js and paste your ANON KEY.');
    window._supabaseReady = false;
    return;
  }

  try {
    window._supabase = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseKey, {
      auth: {
        autoRefreshToken:    true,
        persistSession:      true,
        detectSessionInUrl:  true,
        storageKey:          'shecare_session'
      }
    });
    window._supabaseReady = true;
    console.log('[SheCare] ✅ Supabase client ready');
  } catch (e) {
    console.error('[SheCare] Supabase init error:', e.message);
    window._supabaseReady = false;
  }
})();

// Helper: get the shared client safely
function getSupabase() {
  if (!window._supabaseReady) {
    console.warn('[SheCare] Supabase not ready — check config.js');
    return null;
  }
  return window._supabase;
}
