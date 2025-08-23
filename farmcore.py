import os
from supabase import create_client, Client
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables if running locally
load_dotenv()

class FarmCore:
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase URL and Key must be set in environment variables or passed to FarmCore()"
            )
        # create_client returns a sync client from supabase library
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
        return bool(response.data)

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

    def get_weekly_summary(self, farmer_id: str) -> Dict[str, Any]:
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        harvests_response = (
            self.supabase.table("harvests")
            .select("*, crops!inner(*)")
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

        harvests_data = harvests_response.data if harvests_response.data else []
        expenses_data = expenses_response.data if expenses_response.data else []

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
