# core_singleton.py
import logging
from typing import Optional
from farmcore import FarmCore

logger = logging.getLogger("core_singleton")

farm_core: Optional[FarmCore] = None

def init_farm_core(supabase_url: str = None, supabase_key: str = None) -> FarmCore:
    """
    Lazily initialize and return the global FarmCore instance.
    If FarmCore construction fails, this function will raise the underlying exception.
    """
    global farm_core
    if farm_core is not None:
        return farm_core

    try:
        farm_core = FarmCore(supabase_url=supabase_url, supabase_key=supabase_key)
        logger.info("core_singleton: FarmCore instance created")
        return farm_core
    except Exception:
        logger.exception("core_singleton: Failed to initialize FarmCore")
        farm_core = None
        raise

def get_farm_core() -> FarmCore:
    """
    Return the initialized FarmCore instance.
    Raises RuntimeError if it is not yet initialized.
    Use this from other modules instead of importing farm_core directly.
    """
    if farm_core is None:
        raise RuntimeError("FarmCore is not initialized yet. Call init_farm_core() first (usually in main.on_startup).")
    return farm_core












'''# core_singleton.py
import logging
from typing import Optional
from farmcore import FarmCore

logger = logging.getLogger("core_singleton")

farm_core: Optional[FarmCore] = None

def init_farm_core(supabase_url: str = None, supabase_key: str = None) -> FarmCore:
    """
    Lazily initialize and return the global FarmCore instance.
    If FarmCore construction fails, this function will raise the underlying exception.
    """
    global farm_core
    if farm_core is not None:
        return farm_core

    try:
        # FarmCore will raise ValueError if the credentials are missing
        farm_core = FarmCore(supabase_url=supabase_url, supabase_key=supabase_key)
        logger.info("core_singleton: FarmCore instance created")
        return farm_core
    except Exception as e:
        logger.exception("core_singleton: Failed to initialize FarmCore")
        # keep farm_core as None and re-raise to let caller handle it
        farm_core = None
        raise'''
