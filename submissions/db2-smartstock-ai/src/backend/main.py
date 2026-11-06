"""
FastAPI Backend for SmartStock AI.
Serves RESTful APIs for Inventory, Movements, Suppliers, Users, ML Waste Predictions,
Demand Forecasting, Recipe RAG, Purchasing Assistant, Multi-Agent Coordination, and AI Chatbot.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.db2_client import db_client
from backend.services.inventory_service import InventoryService
from backend.services.waste_service import WasteService
from backend.services.demand_service import DemandService
from backend.services.recipe_service import RecipeService
from backend.services.purchasing_service import PurchasingService
from backend.services.analytics_service import AnalyticsService
from backend.services.whatif_service import WhatIfService
from backend.services.movement_service import MovementService
from backend.services.supplier_service import SupplierService
from backend.services.user_service import UserService
from agents.chatbot import chatbot
from agents.multi_agent_system import crew

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartstock.api")

app = FastAPI(
    title="SmartStock AI - Backend API",
    description="Intelligent Food Waste & Inventory Optimizer powered by IBM Db2, ML, and Multi-Agent AI",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------
# Pydantic Schemas
# -----------------
class BatchCreateRequest(BaseModel):
    ingredient_id: str
    quantity: float
    initial_quantity: Optional[float] = None
    expiry_date: str
    purchase_date: Optional[str] = None
    unit_price: float
    storage_location: Optional[str] = "Refrigerator"
    supplier_id: Optional[str] = "SUP001"

class ConsumeRequest(BaseModel):
    ingredient_id: str
    quantity: float
    dish_name: Optional[str] = "Daily Service"
    notes: Optional[str] = ""

class StockAdjustRequest(BaseModel):
    inventory_id: str
    new_quantity: float
    reason: str

class DiscardWasteRequest(BaseModel):
    ingredient_id: str
    batch_number: str
    quantity: float
    reason: Optional[str] = "Expired"

class WhatIfRequest(BaseModel):
    percentage_change: float = 30.0
    horizon_days: int = 7

class ChatRequest(BaseModel):
    message: str

class PurchaseOrderCreateRequest(BaseModel):
    ingredient_id: str
    supplier_id: str
    quantity: float
    unit_price: float

class SupplierCreateRequest(BaseModel):
    supplier_name: str
    contact: Optional[str] = ""
    lead_time_days: int = 2
    rating: float = 4.5
    min_order_qty: float = 5.0

class UserCreateRequest(BaseModel):
    username: str
    full_name: str
    role: str
    email: Optional[str] = ""

# -----------------
# API Endpoints
# -----------------

@app.get("/health")
def health_check():
    db_status = db_client.health_check()
    return {
        "status": "healthy",
        "service": "SmartStock AI Backend",
        "ibm_db2": db_status
    }

# --- Inventory & Movements ---
@app.get("/api/inventory")
def list_ingredients():
    return InventoryService.get_all_ingredients()

@app.get("/api/inventory/batches")
def list_batches(ingredient_id: Optional[str] = None):
    return InventoryService.get_inventory_batches(ingredient_id=ingredient_id)

@app.post("/api/inventory/batch")
def add_batch(req: BatchCreateRequest):
    success = InventoryService.add_inventory_batch(req.dict())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add batch to IBM Db2")
    return {"message": "Inventory batch added successfully"}

@app.post("/api/inventory/consume")
def consume_inventory(req: ConsumeRequest):
    res = InventoryService.consume_ingredient(
        ingredient_id=req.ingredient_id,
        quantity=req.quantity,
        dish_name=req.dish_name,
        notes=req.notes
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/api/inventory/adjust")
def adjust_inventory_stock(req: StockAdjustRequest):
    success = InventoryService.adjust_stock(
        inventory_id=req.inventory_id,
        new_quantity=req.new_quantity,
        reason=req.reason
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to adjust stock")
    return {"message": "Stock adjusted successfully"}

@app.get("/api/inventory/low-stock")
def get_low_stock():
    return InventoryService.get_low_stock_alerts()

@app.get("/api/movements")
def get_stock_movements(limit: int = 100):
    return MovementService.get_all_movements(limit=limit)

# --- Suppliers ---
@app.get("/api/suppliers")
def list_suppliers():
    return SupplierService.get_all_suppliers()

@app.post("/api/suppliers")
def create_supplier(req: SupplierCreateRequest):
    success = SupplierService.add_supplier(req.dict())
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add supplier")
    return {"message": "Supplier created successfully"}

@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str):
    success = SupplierService.delete_supplier(supplier_id)
    return {"success": success}

# --- Users ---
@app.get("/api/users")
def list_users():
    return UserService.get_all_users()

@app.post("/api/users")
def create_user(req: UserCreateRequest):
    success = UserService.add_user(req.dict())
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create user")
    return {"message": "User created successfully"}

@app.put("/api/users/{user_id}/role")
def update_user_role(user_id: str, payload: Dict[str, str]):
    new_role = payload.get("role", "")
    if not new_role:
        raise HTTPException(status_code=400, detail="Role is required")
    success = UserService.update_user_role(user_id, new_role)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update role in Db2")
    return {"message": "Role updated successfully"}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: str):
    success = UserService.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete user from Db2")
    return {"message": "User deleted successfully"}

# --- Waste Prediction & Discard ---
@app.get("/api/waste/predictions")
def get_waste_predictions():
    return WasteService.get_waste_predictions()

@app.get("/api/waste/history")
def get_waste_history():
    return WasteService.get_historical_waste_summary()

@app.post("/api/waste/discard")
def record_waste_discard(req: DiscardWasteRequest):
    success = WasteService.record_waste_discard(
        ingredient_id=req.ingredient_id,
        batch_number=req.batch_number,
        quantity=req.quantity,
        reason=req.reason or "Expired"
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to record waste discard")
    return {"message": "Waste discard recorded successfully"}

# --- Demand Forecasting ---
@app.get("/api/demand/forecasts")
def get_demand_forecasts(horizon_days: int = 7, multiplier: float = 1.0):
    return DemandService.get_demand_forecasts(horizon_days=horizon_days, demand_multiplier=multiplier)

# --- Recipes ---
@app.get("/api/recipes")
def get_all_recipes():
    return RecipeService.get_all_recipes()

@app.get("/api/recipes/recommendations")
def get_recommended_recipes():
    return RecipeService.get_recommended_recipes_for_expiring_stock()

@app.post("/api/recipes/search")
def search_recipes(payload: Dict[str, str]):
    q = payload.get("query", "")
    return RecipeService.search_recipes_rag(q)

@app.post("/api/recipes/cook/{recipe_id}")
def cook_recipe(recipe_id: str):
    res = RecipeService.cook_recipe(recipe_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to cook recipe"))
    return res

@app.post("/api/recipes/add")
def add_recipe(payload: Dict[str, Any]):
    success = RecipeService.add_recipe(payload)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add recipe to Db2")
    return {"success": True, "message": "Recipe added successfully"}

@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: str):
    success = RecipeService.delete_recipe(recipe_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete recipe from Db2")
    return {"success": True, "message": "Recipe deleted successfully"}

@app.post("/api/recipes/ai-suggest")
def ai_suggest_recipe(payload: Dict[str, str]):
    theme = payload.get("theme", "")
    return RecipeService.suggest_recipe_with_ai(theme)

# --- Purchasing ---
@app.get("/api/purchasing/recommendations")
def get_purchasing_recommendations(horizon_days: int = 7):
    return PurchasingService.get_purchase_recommendations(horizon_days=horizon_days)

@app.get("/api/purchasing/orders")
def get_purchase_orders():
    return PurchasingService.get_purchase_orders()

@app.post("/api/purchasing/orders")
def create_purchase_order(req: PurchaseOrderCreateRequest):
    oid = PurchasingService.create_purchase_order(req.dict())
    return {"order_id": oid, "status": "Suggested"}

@app.post("/api/purchasing/approve/{order_id}")
def approve_order(order_id: str):
    success = PurchasingService.approve_purchase_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found or update failed")
    return {"message": "Order approved successfully", "order_id": order_id}

@app.post("/api/purchasing/reject/{order_id}")
def reject_order(order_id: str):
    success = PurchasingService.reject_purchase_order(order_id)
    return {"message": "Order rejected", "order_id": order_id}

# --- Analytics, What-If, Reports ---
@app.get("/api/analytics/summary")
def get_analytics_summary():
    return AnalyticsService.get_executive_summary()

@app.get("/api/analytics/trends")
def get_analytics_trends():
    return AnalyticsService.get_consumption_vs_waste_trends()

@app.get("/api/analytics/reports")
def get_report(period: str = "Weekly"):
    return AnalyticsService.generate_report(period=period)

@app.post("/api/simulation/what-if")
def simulate_what_if(req: WhatIfRequest):
    return WhatIfService.simulate_demand_surge(
        percentage_change=req.percentage_change,
        horizon_days=req.horizon_days
    )

# --- AI Assistant & Crew ---
@app.post("/api/chat")
def chat_with_assistant(req: ChatRequest):
    return chatbot.process_query(req.message)

@app.post("/api/agents/run")
def run_agents():
    return crew.run_crew()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
