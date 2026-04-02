import os
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

# Determine if we are running in a CI or test environment
IS_TESTING = os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("GITHUB_ACTIONS")

if not SUPABASE_URL or not SUPABASE_KEY:
    if IS_TESTING:
        # Provide dummy credentials for testing/CI purposes to allow module collection
        _URL = "https://placeholder.supabase.co"
        _KEY = "placeholder-key"
    else:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY. Check your .env file.")
else:
    _URL = SUPABASE_URL
    _KEY = SUPABASE_KEY

supabase = create_client(_URL, _KEY)
