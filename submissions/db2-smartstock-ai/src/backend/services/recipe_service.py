"""
AI Recipe Recommendation Service.
Implements RAG and smart recipe matching from IBM Db2.
Prioritizes recipes that consume ingredients expiring soonest.
Provides recipe creation, deletion, and preparation execution.
"""

import uuid
from typing import List, Dict, Any
from db.db2_client import db_client
from backend.services.inventory_service import InventoryService

class RecipeService:
    @staticmethod
    def get_all_recipes() -> List[Dict[str, Any]]:
        sql = "SELECT recipe_id, recipe_name, category, prep_time, servings, instructions, estimated_cost FROM RECIPES ORDER BY recipe_name"
        recipes = db_client.query(sql)

        ri_sql = """
        SELECT ri.recipe_id, ri.ingredient_id, i.ingredient_name, i.category,
               ri.required_quantity, ri.unit, i.unit_price
        FROM RECIPE_INGREDIENTS ri
        JOIN INGREDIENTS i ON ri.ingredient_id = i.ingredient_id
        """
        ri_rows = db_client.query(ri_sql)

        recipe_map = {}
        for r in recipes:
            r['estimated_cost'] = float(r.get('estimated_cost', 0) or 0)
            r['prep_time'] = int(r.get('prep_time', 30) or 30)
            r['servings'] = int(r.get('servings', 4) or 4)
            r['ingredients'] = []
            recipe_map[r['recipe_id']] = r

        for row in ri_rows:
            rec_id = row['recipe_id']
            if rec_id in recipe_map:
                recipe_map[rec_id]['ingredients'].append({
                    "ingredient_id": row['ingredient_id'],
                    "ingredient_name": row['ingredient_name'],
                    "category": row['category'],
                    "required_quantity": float(row.get('required_quantity', 0) or 0),
                    "unit": row['unit'],
                    "unit_price": float(row.get('unit_price', 0) or 0)
                })

        return list(recipe_map.values())

    @staticmethod
    def get_recommended_recipes_for_expiring_stock() -> List[Dict[str, Any]]:
        recipes = RecipeService.get_all_recipes()
        ingredients = {i['ingredient_id']: i for i in InventoryService.get_all_ingredients()}
        batches = InventoryService.get_inventory_batches()

        urgency_weights = {}
        for b in batches:
            ing_id = b['ingredient_id']
            days = b['days_until_expiry']
            if days <= 1:
                weight = 10.0
            elif days <= 3:
                weight = 6.0
            elif days <= 5:
                weight = 3.0
            else:
                weight = 1.0

            if ing_id not in urgency_weights or weight > urgency_weights[ing_id]:
                urgency_weights[ing_id] = weight

        scored_recipes = []
        for rec in recipes:
            score = 0.0
            expiring_ingredients_used = []
            can_cook = True
            missing_ingredients = []

            for ing in rec['ingredients']:
                ing_id = ing['ingredient_id']
                req_qty = float(ing['required_quantity'])
                avail_stock = float(ingredients.get(ing_id, {}).get('current_stock', 0.0) or 0.0)

                if avail_stock < req_qty:
                    can_cook = False
                    missing_ingredients.append({
                        "name": ing['ingredient_name'],
                        "required": req_qty,
                        "available": avail_stock,
                        "unit": ing['unit']
                    })

                if ing_id in urgency_weights:
                    u_weight = urgency_weights[ing_id]
                    score += u_weight * req_qty
                    if u_weight >= 6.0:
                        expiring_ingredients_used.append(ing['ingredient_name'])

            rec_copy = dict(rec)
            rec_copy['estimated_cost'] = float(rec_copy.get('estimated_cost', 0) or 0)
            rec_copy['expiry_utilization_score'] = round(score, 1)
            rec_copy['expiring_ingredients_used'] = expiring_ingredients_used
            rec_copy['can_cook'] = can_cook
            rec_copy['missing_ingredients'] = missing_ingredients
            rec_copy['consumption_impact'] = f"Utilizes {len(expiring_ingredients_used)} critical ingredient(s) approaching expiration."
            scored_recipes.append(rec_copy)

        scored_recipes.sort(key=lambda x: x['expiry_utilization_score'], reverse=True)
        return scored_recipes

    @staticmethod
    def cook_recipe(recipe_id: str, user: str = "Head Chef") -> Dict[str, Any]:
        """Consumes the required quantities for this recipe via FEFO."""
        recipes = RecipeService.get_all_recipes()
        matched = [r for r in recipes if r['recipe_id'] == recipe_id]
        if not matched:
            return {"success": False, "error": "Recipe not found"}

        rec = matched[0]
        results = []
        for ing in rec['ingredients']:
            res = InventoryService.consume_ingredient(
                ingredient_id=ing['ingredient_id'],
                quantity=ing['required_quantity'],
                dish_name=rec['recipe_name'],
                notes=f"Cooked recipe {rec['recipe_name']}",
                user=user
            )
            results.append({"ingredient": ing['ingredient_name'], "result": res})

        return {"success": True, "recipe_name": rec['recipe_name'], "details": results}

    @staticmethod
    def add_recipe(data: Dict[str, Any]) -> bool:
        rid = data.get("recipe_id") or f"REC_{uuid.uuid4().hex[:6].upper()}"
        sql = """
        INSERT INTO RECIPES (recipe_id, recipe_name, category, prep_time, servings, instructions, estimated_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        success = db_client.execute(sql, [
            rid,
            data['recipe_name'],
            data.get('category', 'Main Course'),
            int(data.get('prep_time', 30)),
            int(data.get('servings', 4)),
            data.get('instructions', ''),
            float(data.get('estimated_cost', 150.0))
        ])

        if success and "ingredients" in data:
            for ing in data["ingredients"]:
                ri_sql = "INSERT INTO RECIPE_INGREDIENTS (recipe_id, ingredient_id, required_quantity, unit) VALUES (?, ?, ?, ?)"
                db_client.execute(ri_sql, [rid, ing['ingredient_id'], float(ing['required_quantity']), ing['unit']])

        return success

    @staticmethod
    def delete_recipe(recipe_id: str) -> bool:
        """Deletes a recipe and its ingredients associations from IBM Db2."""
        db_client.execute("DELETE FROM RECIPE_INGREDIENTS WHERE recipe_id = ?", [recipe_id])
        success = db_client.execute("DELETE FROM RECIPES WHERE recipe_id = ?", [recipe_id])
        return success

    @staticmethod
    def suggest_recipe_with_ai(user_theme: str = "") -> Dict[str, Any]:
        """
        Uses LM Studio AI with live IBM Db2 inventory data to recommend and generate
        a tailored recipe designed to consume ingredients nearing expiration.
        """
        import json
        import requests
        from config import DEFAULT_LLM_MODEL, LMSTUDIO_URL
        
        ingredients = InventoryService.get_all_ingredients()
        batches = InventoryService.get_inventory_batches()
        
        # Identify top expiring batches
        expiring = [b for b in batches if b.get('days_until_expiry', 10) <= 3]
        if not expiring:
            expiring = batches[:4]
            
        exp_summary = ", ".join([f"{b['ingredient_name']} ({b['quantity']} {b['unit']} left, expires in {b['days_until_expiry']}d)" for b in expiring[:6]])
        avail_summary = ", ".join([f"{i['ingredient_name']} ({i['current_stock']} {i['unit']})" for i in ingredients[:10]])
        
        prompt = (
            f"You are an executive chef. Design a restaurant recipe that uses ingredients nearing expiration.\n"
            f"Expiring ingredients to prioritize: {exp_summary}\n"
            f"Other available pantry items: {avail_summary}\n"
            f"Chef dish theme/preference: {user_theme if user_theme else 'Zero-waste daily special'}\n\n"
            f"Respond ONLY with a valid JSON object matching this structure:\n"
            f"{{\n"
            f'  "recipe_name": "Dish Name",\n'
            f'  "category": "Main Course",\n'
            f'  "prep_time": 25,\n'
            f'  "servings": 4,\n'
            f'  "estimated_cost": 180.0,\n'
            f'  "instructions": "Step 1: ... Step 2: ...",\n'
            f'  "ingredients": [\n'
            f'    {{"ingredient_name": "Tomato", "required_quantity": 1.5, "unit": "kg"}}\n'
            f"  ],\n"
            f'  "ai_rationale": "Why this recipe helps divert expiring inventory"\n'
            f"}}"
        )
        
        try:
            r = requests.post(
                f"{LMSTUDIO_URL}/chat/completions",
                json={
                    "model": DEFAULT_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a professional restaurant chef and inventory optimization assistant. Respond ONLY with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 400
                },
                timeout=25
            )
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content'].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                parsed = json.loads(content)
                
                name_to_id = {i['ingredient_name'].lower(): (i['ingredient_id'], i['unit']) for i in ingredients}
                matched_ings = []
                for item in parsed.get("ingredients", []):
                    ing_name = item.get("ingredient_name", "")
                    ing_id, unit = name_to_id.get(ing_name.lower(), (None, item.get("unit", "kg")))
                    if not ing_id:
                        for k, v in name_to_id.items():
                            if k in ing_name.lower() or ing_name.lower() in k:
                                ing_id, unit = v
                                break
                    if ing_id:
                        matched_ings.append({
                            "ingredient_id": ing_id,
                            "ingredient_name": ing_name,
                            "required_quantity": float(item.get("required_quantity", 1.0)),
                            "unit": unit
                        })
                if matched_ings:
                    parsed["ingredients"] = matched_ings
                    return parsed
        except Exception:
            pass

        # Fallback intelligent recipe generator based on top expiring ingredients
        top_exp = expiring[0] if expiring else (ingredients[0] if ingredients else {"ingredient_name": "Tomato", "ingredient_id": "ING001", "unit": "kg"})
        sec_exp = expiring[1] if len(expiring) > 1 else (ingredients[1] if len(ingredients) > 1 else {"ingredient_name": "Onion", "ingredient_id": "ING002", "unit": "kg"})
        
        fallback_name = f"Chef's {top_exp['ingredient_name']} & {sec_exp['ingredient_name']} Sauté"
        if user_theme:
            fallback_name = f"{user_theme.title()} with {top_exp['ingredient_name']}"
            
        return {
            "recipe_name": fallback_name,
            "category": "Main Course",
            "prep_time": 25,
            "servings": 4,
            "estimated_cost": 160.0,
            "instructions": f"1. Prep and chop {top_exp['ingredient_name']} and {sec_exp['ingredient_name']}. 2. Heat oil in a heavy-bottom pan and sauté aromatics. 3. Add spices and simmer with {top_exp['ingredient_name']} until reduced and fragrant. 4. Finish with garnish and serve immediately.",
            "ingredients": [
                {
                    "ingredient_id": top_exp['ingredient_id'],
                    "ingredient_name": top_exp['ingredient_name'],
                    "required_quantity": min(2.0, float(top_exp.get('quantity', 2.0))),
                    "unit": top_exp['unit']
                },
                {
                    "ingredient_id": sec_exp['ingredient_id'],
                    "ingredient_name": sec_exp['ingredient_name'],
                    "required_quantity": min(1.5, float(sec_exp.get('quantity', 1.5))),
                    "unit": sec_exp['unit']
                }
            ],
            "ai_rationale": f"Directly utilizes soon-to-expire {top_exp['ingredient_name']} and {sec_exp['ingredient_name']} before spoilage threshold."
        }

    @staticmethod
    def search_recipes_rag(query: str) -> List[Dict[str, Any]]:
        all_recipes = RecipeService.get_all_recipes()
        q_lower = query.lower()
        matched = []
        for rec in all_recipes:
            text = f"{rec['recipe_name']} {rec['category']} {rec['instructions']} " + " ".join([i['ingredient_name'] for i in rec['ingredients']])
            if any(term in text.lower() for term in q_lower.split()):
                matched.append(rec)
        return matched if matched else all_recipes[:3]
