
from fastapi import APIRouter, HTTPException
from app.database.db import execute_query, execute_query_one

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("/")
async def get_products():
    """Retrieve all products."""
    return execute_query(
        """
        SELECT PRODUCT_ID, PRODUCT_NAME, PRODUCT_CATEGORY,
               MIN_TEMPERATURE, MAX_TEMPERATURE, SENSITIVITY_LEVEL
        FROM PRODUCTS
        ORDER BY PRODUCT_ID
        """
    )


@router.get("/{product_id}")
async def get_product(product_id: int):
    """Retrieve a product by ID."""
    product = execute_query_one(
        """
        SELECT PRODUCT_ID, PRODUCT_NAME, PRODUCT_CATEGORY,
               MIN_TEMPERATURE, MAX_TEMPERATURE, SENSITIVITY_LEVEL
        FROM PRODUCTS
        WHERE PRODUCT_ID = ?
        """,
        (product_id,)
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product
