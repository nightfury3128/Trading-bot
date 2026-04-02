from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY. Check your .env file.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
