from db.supabase_client import supabase


def get_account():
    res = supabase.table("account").select("*").eq("id", 1).execute()
    if not res.data:
        raise RuntimeError("Account id=1 not found.")
    return res.data[0]


def update_cash(new_cash: float):
    supabase.table("account").update({"cash": float(new_cash)}).eq("id", 1).execute()
