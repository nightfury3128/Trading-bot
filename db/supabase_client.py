from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
from utils.logger import log

supabase = None

if not SUPABASE_URL or not SUPABASE_KEY:
    log.warning("Supabase keys not found. Supabase operations will fail!")
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
