# farmcore.py
import os
import json
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
import httpx

# Load .env in local dev if present
load_dotenv()

def _iso(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        return d.isoformat()
    return d.isoformat()

class FarmCore:
    """
    Minimal FarmCore backed by Supabase REST (PostgREST) via httpx.
    This avoids using the supabase/gotrue Python clients that caused compatibility issues.
    """

    def __init__(self, supabase_url: str | None = None, supabase_key: str | None = None, timeout: int = 10):
        if supabase_url is None:
            supabase_url = os.getenv("SUPABASE_URL")
        if supabase_key is None:
            supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required to initialize FarmCore")

        # Ensure we have no trailing slash for rest endpoint construction
        self.base_url = supabase_url.rstrip("/")
        self.rest_url = f"{self.base_url}/rest/v1"
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # sync client
        self.client = httpx.Client(timeout=timeout)

    # --- helpers ---
    def _url(self, table: str) -> str:
        return f"{self.rest_url}/{table}"

    def _get(self, path: str, params: dict = None) -> Optional[Any]:
        r = self.client.get(path, headers=self.headers, params=params)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return None

    def _post(self, path: str, body: dict) -> Optional[Any]:
        r = self.client.post(path, headers=self.headers, content=json.dumps(body))
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return None

    def _patch(self, path: str, body: dict, params: dict = None) -> Optional[Any]:
        r = self.client.patch(path, headers=self.headers, params=params, content=json.dumps(body))
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return None

    def _delete(self, path: str, params: dict = None) -> Optional[Any]:
        r = self.client.delete(path, headers=self.headers, params=params)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return None

    # --- public methods mirroring your previous FarmCore interface ---
    def get_farmer(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        path = self._url("farmers")
        params = {"telegram_id": f"eq.{telegram_id}", "select": "*"}
        resp = self._get(path, params=params)
        if isinstance(resp, list) and len(resp) > 0:
            return resp[0]
        return None

    def create_farmer(self, telegram_id: int, name: str, phone: str, village: str, language: str = "ar") -> Optional[Dict[str, Any]]:
        path = self._url("farmers")
        body = {"telegram_id": telegram_id, "name": name, "phone": phone, "village": village, "language": language}
        # Ask PostgREST to return the inserted row(s) by using Prefer header; but simplest is to POST and then query back:
        self._post(path, body)
        return self.get_farmer(telegram_id)

    def add_crop(self, farmer_id: str, name: str, planting_date: date, notes: str = None) -> Optional[Dict[str, Any]]:
        path = self._url("crops")
        body = {"farmer_id": farmer_id, "name": name, "planting_date": _iso(planting_date), "notes": notes}
        inserted = self._post(path, body)
        # PostgREST returns array of inserted rows if you set Prefer=return=representation; to keep simple, return last inserted by querying by farmer_id+name+planting_date
        params = {"farmer_id": f"eq.{farmer_id}", "name": f"eq.{name}", "planting_date": f"eq.{_iso(planting_date)}", "select": "*"}
        rows = self._get(path, params=params)
        if isinstance(rows, list) and rows:
            return rows[0]
        return inserted

    def get_farmer_crops(self, farmer_id: str) -> List[Dict[str, Any]]:
        path = self._url("crops")
        params = {"farmer_id": f"eq.{farmer_id}", "select": "*", "order": "planting_date.asc"}
        resp = self._get(path, params=params)
        return resp or []

    def update_crop(self, crop_id: str, **updates) -> Optional[Dict[str, Any]]:
        path = self._url("crops")
        params = {"id": f"eq.{crop_id}"}
        # patch returns [] by default; we'll patch then re-fetch
        if "planting_date" in updates:
            updates["planting_date"] = _iso(updates["planting_date"])
        self._patch(path, updates, params=params)
        # fetch updated row
        rows = self._get(path, params={"id": f"eq.{crop_id}", "select": "*"})
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    def delete_crop(self, crop_id: str) -> bool:
        path = self._url("crops")
        params = {"id": f"eq.{crop_id}"}
        # delete returns array of deleted rows only if configured; we check status code
        self._delete(path, params=params)
        # confirm deletion by trying to fetch
        rows = self._get(path, params={"id": f"eq.{crop_id}", "select": "*"})
        return not (rows and len(rows) > 0)

    def record_harvest(self, crop_id: str, harvest_date: date, quantity: float, unit: str = "kg", notes: str = None, status: str = "stored") -> Optional[Dict[str, Any]]:
        path = self._url("harvests")
        body = {"crop_id": crop_id, "harvest_date": _iso(harvest_date), "quantity": quantity, "unit": unit, "notes": notes, "status": status}
        self._post(path, body)
        # fetch by crop_id and date to return the created record
        rows = self._get(path, params={"crop_id": f"eq.{crop_id}", "harvest_date": f"eq.{_iso(harvest_date)}", "select": "*"})
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    def get_stored_harvests(self, farmer_id: str) -> List[Dict[str, Any]]:
        # this requires a join in PostgREST; PostgREST supports foreign table select syntax: harvests?select=*,crops(*)&crops.farmer_id=eq.<farmer_id>&status=eq.stored
        path = self._url("harvests")
        params = {"select": "*,crops(*)", "status": "eq.stored", "crops.farmer_id": f"eq.{farmer_id}"}
        resp = self._get(path, params=params)
        return resp or []

    def record_delivery(self, harvest_id: str, delivery_date: date, collector_name: str = None, market: str = None) -> Optional[Dict[str, Any]]:
        # update harvest status
        path_harvests = self._url("harvests")
        self._patch(path_harvests, {"status": "delivered"}, params={"id": f"eq.{harvest_id}"})
        # insert into deliveries
        path = self._url("deliveries")
        body = {"harvest_id": harvest_id, "delivery_date": _iso(delivery_date), "collector_name": collector_name, "market": market}
        self._post(path, body)
        # fetch inserted delivery
        rows = self._get(path, params={"harvest_id": f"eq.{harvest_id}", "delivery_date": f"eq.{_iso(delivery_date)}", "select": "*"})
        delivery = rows[0] if isinstance(rows, list) and rows else None
        if delivery:
            expected_date = (delivery_date + timedelta(days=7)).isoformat()
            pay_path = self._url("payments")
            pay_data = {"delivery_id": delivery["id"], "expected_date": expected_date, "status": "pending"}
            self._post(pay_path, pay_data)
        return delivery

    def get_pending_payments(self, farmer_id: str) -> List[Dict[str, Any]]:
        # We try to traverse: payments -> deliveries -> harvests -> crops -> farmer_id
        # PostgREST supports nested select: payments?select=*,deliveries(harvests(crops(*)))
        path = self._url("payments")
        params = {"select": "*,deliveries(harvests(crops(*)))", "status": "eq.pending"}
        resp = self._get(path, params=params)
        if not resp:
            return []
        # filter by farmer_id manually
        out = []
        for p in resp:
            try:
                if p.get("deliveries") and p["deliveries"].get("harvests") and p["deliveries"]["harvests"].get("crops"):
                    crop = p["deliveries"]["harvests"]["crops"]
                    if str(crop.get("farmer_id")) == str(farmer_id):
                        out.append(p)
            except Exception:
                continue
        return out

    def record_payment(self, payment_id: str, paid_amount: float, paid_date: date) -> Optional[Dict[str, Any]]:
        path = self._url("payments")
        body = {"paid_amount": paid_amount, "paid_date": _iso(paid_date), "status": "paid"}
        self._patch(path, body, params={"id": f"eq.{payment_id}"})
        rows = self._get(path, params={"id": f"eq.{payment_id}", "select": "*"})
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    def add_treatment(self, crop_id: str, treatment_date: date, product_name: str, cost: float = None, next_due_date: date = None, notes: str = None) -> Optional[Dict[str, Any]]:
        path = self._url("treatments")
        body = {
            "crop_id": crop_id,
            "treatment_date": _iso(treatment_date),
            "product_name": product_name,
            "cost": cost,
            "next_due_date": _iso(next_due_date),
            "notes": notes,
        }
        self._post(path, body)
        rows = self._get(path, params={"crop_id": f"eq.{crop_id}", "treatment_date": f"eq.{_iso(treatment_date)}", "select": "*"})
        return rows[0] if isinstance(rows, list) and rows else None

    def get_upcoming_treatments(self, farmer_id: str, days: int = 7) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        end_date = (date.today() + timedelta(days=days)).isoformat()
        path = self._url("treatments")
        params = {"select": "*,crops(*)", "crops.farmer_id": f"eq.{farmer_id}", "next_due_date": f"gte.{today}", "next_due_date": f"lte.{end_date}"}
        # Note: PostgREST handles multiple filters by & between them; since params is dict, httpx will produce multiple keys with same name can't here - fallback simpler:
        # Use raw param string:
        raw_params = f"select=*,crops(*)&crops.farmer_id=eq.{farmer_id}&next_due_date=gte.{today}&next_due_date=lte.{end_date}"
        r = self.client.get(self._url("treatments") + "?" + raw_params, headers=self.headers)
        r.raise_for_status()
        try:
            return r.json() or []
        except Exception:
            return []

    def add_expense(self, farmer_id: str, expense_date: date, category: str, amount: float, crop_id: str = None, notes: str = None) -> Optional[Dict[str, Any]]:
        path = self._url("expenses")
        body = {"farmer_id": farmer_id, "expense_date": _iso(expense_date), "category": category, "amount": amount, "crop_id": crop_id, "notes": notes}
        self._post(path, body)
        rows = self._get(path, params={"farmer_id": f"eq.{farmer_id}", "expense_date": f"eq.{_iso(expense_date)}", "select": "*"})
        return rows[0] if isinstance(rows, list) and rows else None

    def get_weekly_summary(self, farmer_id: str) -> Dict[str, Any]:
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()

        harvests = self._get(self._url("harvests"), params={"select": "*,crops(*)", "crops.farmer_id": f"eq.{farmer_id}", "harvest_date": f"gte.{start_date}"})
        expenses = self._get(self._url("expenses"), params={"select": "*", "farmer_id": f"eq.{farmer_id}", "expense_date": f"gte.{start_date}"})
        pending = self.get_pending_payments(farmer_id)

        harvests_list = harvests or []
        expenses_list = expenses or []

        total_harvest = sum(h.get("quantity", 0) for h in harvests_list)
        total_expenses = sum(e.get("amount", 0) for e in expenses_list)
        total_pending = sum(p.get("expected_amount", 0) for p in pending)

        return {
            "total_harvest": total_harvest,
            "total_expenses": total_expenses,
            "total_pending": total_pending,
            "harvests": harvests_list,
            "expenses": expenses_list,
            "pending_payments": pending,
        }

    def get_market_prices(self, crop_name: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        path = self._url("market_prices")
        params = {"select": "*", "order": "price_date.desc", "limit": str(limit)}
        if crop_name:
            params["crop_name"] = f"eq.{crop_name}"
        resp = self._get(path, params=params)
        return resp or []

    def add_market_price(self, crop_name: str, price_date: date, price_per_kg: float, source: str = "admin") -> Optional[Dict[str, Any]]:
        path = self._url("market_prices")
        body = {"crop_name": crop_name, "price_date": _iso(price_date), "price_per_kg": price_per_kg, "source": source}
        self._post(path, body)
        rows = self._get(path, params={"crop_name": f"eq.{crop_name}", "price_date": f"eq.{_iso(price_date)}", "select": "*"})
        return rows[0] if isinstance(rows, list) and rows else None
















'''# farmcore.py
import os
from supabase import create_client, Client
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FarmCore:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase URL and Key must be set in environment variables"
            )
        self.supabase: Client = create_client(supabase_url, supabase_key)

    def get_farmer(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        try:
            response = (
                self.supabase.table("farmers")
                .select("*")
                .eq("telegram_id", telegram_id)
                .single()
                .execute()
            )
            return response.data
        except Exception:
            return None

    def create_farmer(
        self,
        telegram_id: int,
        name: str,
        phone: str,
        village: str,
        language: str = "ar",
    ) -> Dict[str, Any]:
        farmer_data = {
            "telegram_id": telegram_id,
            "name": name,
            "phone": phone,
            "village": village,
            "language": language,
        }
        response = self.supabase.table("farmers").insert(farmer_data).execute()
        return response.data[0] if response.data else None

    def add_crop(
        self, farmer_id: str, name: str, planting_date: date, notes: str = None
    ) -> Dict[str, Any]:
        crop_data = {
            "farmer_id": farmer_id,
            "name": name,
            "planting_date": planting_date.isoformat() if isinstance(planting_date, (date,)) else planting_date,
            "notes": notes,
        }
        response = self.supabase.table("crops").insert(crop_data).execute()
        return response.data[0] if response.data else None

    def get_farmer_crops(self, farmer_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table("crops")
            .select("*")
            .eq("farmer_id", farmer_id)
            .order("planting_date", desc=False)
            .execute()
        )
        return response.data or []

    def update_crop(self, crop_id: str, **updates) -> Optional[Dict[str, Any]]:
        if not updates:
            return None
        # convert dates to isoformat if date objects passed
        if "planting_date" in updates and isinstance(updates["planting_date"], (date,)):
            updates["planting_date"] = updates["planting_date"].isoformat()
        response = (
            self.supabase.table("crops")
            .update(updates)
            .eq("id", crop_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def delete_crop(self, crop_id: str) -> bool:
        response = (
            self.supabase.table("crops")
            .delete()
            .eq("id", crop_id)
            .execute()
        )
        # supabase returns deleted rows in response.data typically
        return bool(response.data)

    # Existing methods below -- unchanged
    def record_harvest(
        self,
        crop_id: str,
        harvest_date: date,
        quantity: float,
        unit: str = "kg",
        notes: str = None,
        status: str = "stored",
    ) -> Dict[str, Any]:
        harvest_data = {
            "crop_id": crop_id,
            "harvest_date": harvest_date.isoformat(),
            "quantity": quantity,
            "unit": unit,
            "notes": notes,
            "status": status,
        }
        response = self.supabase.table("harvests").insert(harvest_data).execute()
        return response.data[0] if response.data else None

    def get_stored_harvests(self, farmer_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table("harvests")
            .select("*, crops!inner(*)")
            .eq("crops.farmer_id", farmer_id)
            .eq("status", "stored")
            .execute()
        )
        return response.data or []

    def record_delivery(
        self,
        harvest_id: str,
        delivery_date: date,
        collector_name: str = None,
        market: str = None,
    ) -> Dict[str, Any]:
        self.supabase.table("harvests").update({"status": "delivered"}).eq(
            "id", harvest_id
        ).execute()
        delivery_data = {
            "harvest_id": harvest_id,
            "delivery_date": delivery_date.isoformat(),
            "collector_name": collector_name,
            "market": market,
        }
        response = self.supabase.table("deliveries").insert(delivery_data).execute()
        delivery = response.data[0] if response.data else None
        if delivery:
            expected_date = delivery_date + timedelta(days=7)
            payment_data = {
                "delivery_id": delivery["id"],
                "expected_date": expected_date.isoformat(),
                "status": "pending",
            }
            self.supabase.table("payments").insert(payment_data).execute()
        return delivery

    def get_pending_payments(self, farmer_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table("payments")
            .select("*, deliveries!inner(harvests!inner(crops!inner(farmer_id)))")
            .eq("deliveries.harvests.crops.farmer_id", farmer_id)
            .eq("status", "pending")
            .execute()
        )
        return response.data or []

    def record_payment(
        self, payment_id: str, paid_amount: float, paid_date: date
    ) -> Dict[str, Any]:
        payment_data = {
            "paid_amount": paid_amount,
            "paid_date": paid_date.isoformat(),
            "status": "paid",
        }
        response = (
            self.supabase.table("payments")
            .update(payment_data)
            .eq("id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def add_treatment(
        self,
        crop_id: str,
        treatment_date: date,
        product_name: str,
        cost: float = None,
        next_due_date: date = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        treatment_data = {
            "crop_id": crop_id,
            "treatment_date": treatment_date.isoformat(),
            "product_name": product_name,
            "cost": cost,
            "next_due_date": next_due_date.isoformat() if next_due_date else None,
            "notes": notes,
        }
        response = self.supabase.table("treatments").insert(treatment_data).execute()
        return response.data[0] if response.data else None

    def get_upcoming_treatments(
        self, farmer_id: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        today = date.today()
        end_date = today + timedelta(days=days)
        response = (
            self.supabase.table("treatments")
            .select("*, crops!inner(*)")
            .eq("crops.farmer_id", farmer_id)
            .gte("next_due_date", today.isoformat())
            .lte("next_due_date", end_date.isoformat())
            .execute()
        )
        return response.data or []

    def add_expense(
        self,
        farmer_id: str,
        expense_date: date,
        category: str,
        amount: float,
        crop_id: str = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        expense_data = {
            "farmer_id": farmer_id,
            "expense_date": expense_date.isoformat(),
            "category": category,
            "amount": amount,
            "crop_id": crop_id,
            "notes": notes,
        }
        response = self.supabase.table("expenses").insert(expense_data).execute()
        return response.data[0] if response.data else None

   # farmcore.py - get_weekly_summary method
def get_weekly_summary(self, farmer_id: str) -> Dict[str, Any]:
    start_date = date.today() - timedelta(days=7)
    end_date = date.today()

    # Get harvests with crop information
    harvests_response = (
        self.supabase.table("harvests")
        .select("*, crops!inner(*)")  # Get all crop fields, not just farmer_id
        .eq("crops.farmer_id", farmer_id)
        .gte("harvest_date", start_date.isoformat())
        .lte("harvest_date", end_date.isoformat())
        .execute()
    )

    # Get expenses
    expenses_response = (
        self.supabase.table("expenses")
        .select("*")
        .eq("farmer_id", farmer_id)
        .gte("expense_date", start_date.isoformat())
        .lte("expense_date", end_date.isoformat())
        .execute()
    )

    # Get pending payments
    pending_payments = self.get_pending_payments(farmer_id)

    # Ensure we have lists even if response.data is None
    harvests_data = harvests_response.data if harvests_response.data else []
    expenses_data = expenses_response.data if expenses_response.data else []

    # Calculate totals
    total_harvest = sum(h.get("quantity", 0) for h in harvests_data)
    total_expenses = sum(e.get("amount", 0) for e in expenses_data)
    total_pending = sum(p.get("expected_amount", 0) for p in pending_payments)

    return {
        "total_harvest": total_harvest,
        "total_expenses": total_expenses,
        "total_pending": total_pending,
        "harvests": harvests_data,
        "expenses": expenses_data,
        "pending_payments": pending_payments,
    }

    def get_market_prices(
        self, crop_name: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        query = (
            self.supabase.table("market_prices")
            .select("*")
            .order("price_date", desc=True)
            .limit(limit)
        )
        if crop_name:
            query = query.eq("crop_name", crop_name)
        response = query.execute()
        return response.data or []

    def add_market_price(
        self,
        crop_name: str,
        price_date: date,
        price_per_kg: float,
        source: str = "admin",
    ) -> Dict[str, Any]:
        price_data = {
            "crop_name": crop_name,
            "price_date": price_date.isoformat(),
            "price_per_kg": price_per_kg,
            "source": source,
        }
        response = self.supabase.table("market_prices").insert(price_data).execute()
        return response.data[0] if response.data else None

'''










"""
import os
from supabase import create_client, Client
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class FarmCore:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase URL and Key must be set in environment variables"
            )
        self.supabase: Client = create_client(supabase_url, supabase_key)

    def get_farmer(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        try:
            response = (
                self.supabase.table("farmers")
                .select("*")
                .eq("telegram_id", telegram_id)
                .single()
                .execute()
            )
            return response.data
        except Exception:
            return None

    def create_farmer(
        self,
        telegram_id: int,
        name: str,
        phone: str,
        village: str,
        language: str = "ar",
    ) -> Dict[str, Any]:
        farmer_data = {
            "telegram_id": telegram_id,
            "name": name,
            "phone": phone,
            "village": village,
            "language": language,
        }
        response = self.supabase.table("farmers").insert(farmer_data).execute()
        return response.data[0] if response.data else None

    def add_crop(
        self, farmer_id: str, name: str, planting_date: date, notes: str = None
    ) -> Dict[str, Any]:
        crop_data = {
            "farmer_id": farmer_id,
            "name": name,
            "planting_date": planting_date.isoformat(),
            "notes": notes,
        }
        response = self.supabase.table("crops").insert(crop_data).execute()
        return response.data[0] if response.data else None

    def get_farmer_crops(self, farmer_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table("crops")
            .select("*")
            .eq("farmer_id", farmer_id)
            .execute()
        )
        return response.data

    def record_harvest(
        self,
        crop_id: str,
        harvest_date: date,
        quantity: float,
        unit: str = "kg",
        notes: str = None,
        status: str = "stored",
    ) -> Dict[str, Any]:
        harvest_data = {
            "crop_id": crop_id,
            "harvest_date": harvest_date.isoformat(),
            "quantity": quantity,
            "unit": unit,
            "notes": notes,
            "status": status,
        }
        response = self.supabase.table("harvests").insert(harvest_data).execute()
        return response.data[0] if response.data else None

    def get_stored_harvests(self, farmer_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table("harvests")
            .select("*, crops!inner(*)")
            .eq("crops.farmer_id", farmer_id)
            .eq("status", "stored")
            .execute()
        )
        return response.data

    def record_delivery(
        self,
        harvest_id: str,
        delivery_date: date,
        collector_name: str = None,
        market: str = None,
    ) -> Dict[str, Any]:
        self.supabase.table("harvests").update({"status": "delivered"}).eq(
            "id", harvest_id
        ).execute()
        delivery_data = {
            "harvest_id": harvest_id,
            "delivery_date": delivery_date.isoformat(),
            "collector_name": collector_name,
            "market": market,
        }
        response = self.supabase.table("deliveries").insert(delivery_data).execute()
        delivery = response.data[0] if response.data else None
        if delivery:
            expected_date = delivery_date + timedelta(days=7)
            payment_data = {
                "delivery_id": delivery["id"],
                "expected_date": expected_date.isoformat(),
                "status": "pending",
            }
            self.supabase.table("payments").insert(payment_data).execute()
        return delivery

    def get_pending_payments(self, farmer_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table("payments")
            .select("*, deliveries!inner(harvests!inner(crops!inner(farmer_id)))")
            .eq("deliveries.harvests.crops.farmer_id", farmer_id)
            .eq("status", "pending")
            .execute()
        )
        return response.data

    def record_payment(
        self, payment_id: str, paid_amount: float, paid_date: date
    ) -> Dict[str, Any]:
        payment_data = {
            "paid_amount": paid_amount,
            "paid_date": paid_date.isoformat(),
            "status": "paid",
        }
        response = (
            self.supabase.table("payments")
            .update(payment_data)
            .eq("id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def add_treatment(
        self,
        crop_id: str,
        treatment_date: date,
        product_name: str,
        cost: float = None,
        next_due_date: date = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        treatment_data = {
            "crop_id": crop_id,
            "treatment_date": treatment_date.isoformat(),
            "product_name": product_name,
            "cost": cost,
            "next_due_date": next_due_date.isoformat() if next_due_date else None,
            "notes": notes,
        }
        response = self.supabase.table("treatments").insert(treatment_data).execute()
        return response.data[0] if response.data else None

    def get_upcoming_treatments(
        self, farmer_id: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        today = date.today()
        end_date = today + timedelta(days=days)
        response = (
            self.supabase.table("treatments")
            .select("*, crops!inner(*)")
            .eq("crops.farmer_id", farmer_id)
            .gte("next_due_date", today.isoformat())
            .lte("next_due_date", end_date.isoformat())
            .execute()
        )
        return response.data

    def add_expense(
        self,
        farmer_id: str,
        expense_date: date,
        category: str,
        amount: float,
        crop_id: str = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        expense_data = {
            "farmer_id": farmer_id,
            "expense_date": expense_date.isoformat(),
            "category": category,
            "amount": amount,
            "crop_id": crop_id,
            "notes": notes,
        }
        response = self.supabase.table("expenses").insert(expense_data).execute()
        return response.data[0] if response.data else None

    def get_weekly_summary(self, farmer_id: str) -> Dict[str, Any]:
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        harvests_response = (
            self.supabase.table("harvests")
            .select("*, crops!inner(farmer_id)")
            .eq("crops.farmer_id", farmer_id)
            .gte("harvest_date", start_date.isoformat())
            .lte("harvest_date", end_date.isoformat())
            .execute()
        )
        expenses_response = (
            self.supabase.table("expenses")
            .select("*")
            .eq("farmer_id", farmer_id)
            .gte("expense_date", start_date.isoformat())
            .lte("expense_date", end_date.isoformat())
            .execute()
        )
        pending_payments = self.get_pending_payments(farmer_id)
        total_harvest = (
            sum(h["quantity"] for h in harvests_response.data)
            if harvests_response.data
            else 0
        )
        total_expenses = (
            sum(e["amount"] for e in expenses_response.data)
            if expenses_response.data
            else 0
        )
        total_pending = (
            sum(p.get("expected_amount", 0) for p in pending_payments)
            if pending_payments
            else 0
        )
        return {
            "total_harvest": total_harvest,
            "total_expenses": total_expenses,
            "total_pending": total_pending,
            "harvests": harvests_response.data,
            "expenses": expenses_response.data,
            "pending_payments": pending_payments,
        }

    def get_market_prices(
        self, crop_name: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        query = (
            self.supabase.table("market_prices")
            .select("*")
            .order("price_date", desc=True)
            .limit(limit)
        )
        if crop_name:
            query = query.eq("crop_name", crop_name)
        response = query.execute()
        return response.data

    def add_market_price(
        self,
        crop_name: str,
        price_date: date,
        price_per_kg: float,
        source: str = "admin",
    ) -> Dict[str, Any]:
        price_data = {
            "crop_name": crop_name,
            "price_date": price_date.isoformat(),
            "price_per_kg": price_per_kg,
            "source": source,
        }
        response = self.supabase.table("market_prices").insert(price_data).execute()
        return response.data[0] if response.data else None
"""


