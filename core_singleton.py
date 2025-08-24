'''
from typing import Optional
from farmcore import FarmCore

farm_core: Optional[FarmCore] = None

def init_farm_core(supabase_url: str, supabase_key: str) -> None:
    global farm_core
    if farm_core is None:
        farm_core = FarmCore(supabase_url=supabase_url, supabase_key=supabase_key)

'''
