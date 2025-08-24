# core_singleton.py
# Single shared FarmCore instance to avoid multiple Supabase clients and to keep usage consistent.
from typing import Optional
from farmcore import FarmCore

farm_core: Optional[FarmCore] = None

def init_farm_core() -> FarmCore:
    """
    Initialize the global FarmCore instance if not already initialized.
    Returns the FarmCore instance.
    """
    global farm_core
    if farm_core is None:
        # FarmCore's constructor reads SUPABASE_URL and SUPABASE_KEY from the environment
        farm_core = FarmCore()
    return farm_core
