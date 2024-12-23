from fastapi import APIRouter
from typing import List, Dict
from app.schemas.component_quantities import ComponentQuantityIn, ComponentQuantityOut
from app.crud.component_quantities import insert_component_quantities, fetch_component_quantities

router = APIRouter()

@router.post("/insert_component_quantities/", response_model=List[ComponentQuantityOut])
async def create_component_quantities(quantities: List[ComponentQuantityIn]):
    return insert_component_quantities(quantities)

@router.get("/fetch_component_quantities/", response_model=Dict[str, int])
async def read_component_quantities():
    return fetch_component_quantities()
