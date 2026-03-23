// ===== SUPABASE CLIENT INITIALIZATION =====
// Import from CDN — used across all pages
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export default supabase;
