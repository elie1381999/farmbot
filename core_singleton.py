# core_singleton.py
from typing import Optional
from threading import Lock

from farmcore import FarmCore

class _FarmCoreProxy:
    """
    Lazy-initialized FarmCore proxy. Safe to import at module import time.
    Call init_farm_core(supabase_url, supabase_key) during FastAPI startup.
    """
    def __init__(self):
        self._inst: Optional[FarmCore] = None
        self._lock = Lock()

    def init(self, supabase_url: str, supabase_key: str):
        if self._inst is None:
            with self._lock:
                if self._inst is None:
                    self._inst = FarmCore(supabase_url=supabase_url, supabase_key=supabase_key)

    def is_initialized(self) -> bool:
        return self._inst is not None

    def __getattr__(self, name):
        if self._inst is None:
            raise RuntimeError("FarmCore not initialized. Call init_farm_core(...) during app startup.")
        return getattr(self._inst, name)

farm_core = _FarmCoreProxy()

def init_farm_core(supabase_url: str, supabase_key: str):
    """Called by main.py at FastAPI startup to initialize the real FarmCore."""
    farm_core.init(supabase_url=supabase_url, supabase_key=supabase_key)
