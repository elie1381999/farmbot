# core_singleton.py
from typing import Optional
from threading import Lock

# import FarmCore lazily (module present in your repo)
from farmcore import FarmCore

class _FarmCoreProxy:
    """
    A thread-safe lazy-initialized proxy for FarmCore.
    Importing this module is safe (no network activity).
    Call init_farm_core(...) during FastAPI startup to initialize.
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

# exported singleton-like proxy
farm_core = _FarmCoreProxy()

def init_farm_core(supabase_url: str, supabase_key: str):
    """Helper used by main.py to initialize farm_core during startup."""
    farm_core.init(supabase_url=supabase_url, supabase_key=supabase_key)
