from db.supabase_client import supabase


def get_account():
    res = supabase.table("account").select("*").eq("id", 1).execute()
    if not res.data:
        # Fallback if table doesn't have the new columns yet
        return {"cash_usd": 0.0, "cash_inr": 0.0}
    return res.data[0]


def update_cash(new_cash_usd: float, new_cash_inr: float):
    supabase.table("account").update({
        "cash_usd": float(new_cash_usd),
        "cash_inr": float(new_cash_inr)
    }).eq("id", 1).execute()
