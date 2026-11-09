"""
ClaimGuard AI - Policies & Customers Router
Provides CRUD endpoints for CUSTOMER_DETAILS and POLICY_DETAILS tables.
"""

from typing import List
from fastapi import APIRouter, HTTPException, status
from ..database.repository import repository
from ..models.schemas import CustomerCreate, CustomerResponse, PolicyCreate, PolicyResponse

router = APIRouter(prefix="/api", tags=["Policies & Customers"])


@router.get("/customers", response_model=List[CustomerResponse])
def list_customers():
    """Lists all registered customers from IBM Db2 CUSTOMER_DETAILS."""
    rows = repository.list_customers()
    return [
        CustomerResponse(
            customer_id=r["CUSTOMER_ID"],
            first_name=r["FIRST_NAME"],
            last_name=r["LAST_NAME"],
            email=r["EMAIL"],
            phone=r.get("PHONE"),
            date_of_birth=str(r.get("DATE_OF_BIRTH") or ""),
            national_id=r.get("NATIONAL_ID"),
            address=r.get("ADDRESS"),
            created_at=str(r.get("CREATED_AT") or "")
        )
        for r in rows
    ]


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str):
    """Retrieves a single customer profile."""
    r = repository.get_customer_by_id(customer_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return CustomerResponse(
        customer_id=r["CUSTOMER_ID"],
        first_name=r["FIRST_NAME"],
        last_name=r["LAST_NAME"],
        email=r["EMAIL"],
        phone=r.get("PHONE"),
        date_of_birth=str(r.get("DATE_OF_BIRTH") or ""),
        national_id=r.get("NATIONAL_ID"),
        address=r.get("ADDRESS"),
        created_at=str(r.get("CREATED_AT") or "")
    )


@router.get("/policies", response_model=List[PolicyResponse])
def list_policies():
    """Lists all insurance policies from IBM Db2 POLICY_DETAILS."""
    rows = repository.list_policies()
    return [
        PolicyResponse(
            policy_id=r["POLICY_ID"],
            customer_id=r["CUSTOMER_ID"],
            policy_number=r["POLICY_NUMBER"],
            policy_type=r["POLICY_TYPE"],
            status=r["STATUS"],
            start_date=str(r["START_DATE"]),
            end_date=str(r["END_DATE"]),
            max_coverage_amount=float(r["MAX_COVERAGE_AMOUNT"]),
            remaining_coverage=float(r["REMAINING_COVERAGE"]),
            deductible=float(r.get("DEDUCTIBLE") or 0.0),
            copay_percentage=float(r.get("COPAY_PERCENTAGE") or 0.0),
            created_at=str(r.get("CREATED_AT") or "")
        )
        for r in rows
    ]


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str):
    """Retrieves a single insurance policy."""
    r = repository.get_policy_by_id(policy_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found.")
    return PolicyResponse(
        policy_id=r["POLICY_ID"],
        customer_id=r["CUSTOMER_ID"],
        policy_number=r["POLICY_NUMBER"],
        policy_type=r["POLICY_TYPE"],
        status=r["STATUS"],
        start_date=str(r["START_DATE"]),
        end_date=str(r["END_DATE"]),
        max_coverage_amount=float(r["MAX_COVERAGE_AMOUNT"]),
        remaining_coverage=float(r["REMAINING_COVERAGE"]),
        deductible=float(r.get("DEDUCTIBLE") or 0.0),
        copay_percentage=float(r.get("COPAY_PERCENTAGE") or 0.0),
        created_at=str(r.get("CREATED_AT") or "")
    )
