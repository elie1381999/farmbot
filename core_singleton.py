# core_singleton.py
"""
Singleton holder for FarmCore. The module exposes:
- farm_core: set to None initially, will hold FarmCore instance after init_farm_core()
- init_farm_core(supabase_url, supabase_key): initialize farm_core once
"""

from typing import Optional
from farmcore import FarmCore

farm_core: Optional[FarmCore] = None

def init_farm_core(supabase_url: str, supabase_key: str) -> None:
    global farm_core
    if farm_core is None:
        farm_core = FarmCore(supabase_url=supabase_url, supabase_key=supabase_key)
