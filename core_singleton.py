# core_singleton.py
# Single shared FarmCore instance to avoid multiple Supabase clients and to keep usage consistent.
from farmcore import FarmCore

farm_core = FarmCore()
