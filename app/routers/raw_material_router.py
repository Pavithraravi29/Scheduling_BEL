from fastapi import APIRouter
from typing import List, Optional
from datetime import datetime
from app.crud.raw_material import insert_raw_materials, fetch_raw_materials, update_raw_material, insert_machine_statuses, fetch_machine_statuses, update_machine_status
from app.schemas.raw_material import RawMaterialIn, RawMaterialOut, MachineStatusIn, MachineStatusOut
from app.algorithms.scheduling import schedule_operations
from app.crud.operations import fetch_operations
from app.crud.component_quantities import fetch_component_quantities
from app.crud.leadtime import fetch_lead_times
router = APIRouter()

# Raw Material Routes
@router.post("/raw_materials/", response_model=List[RawMaterialOut])
async def create_raw_materials(raw_materials: List[RawMaterialIn]):
    return insert_raw_materials(raw_materials)

@router.get("/raw_materials/", response_model=List[RawMaterialOut])
async def read_raw_materials():
    return fetch_raw_materials()

# Machine Status Routes
@router.post("/machine_statuses/", response_model=List[MachineStatusOut])
async def create_machine_statuses(statuses: List[MachineStatusIn]):
    return insert_machine_statuses(statuses)

@router.get("/machine_statuses/", response_model=List[MachineStatusOut])
async def read_machine_statuses():
    return fetch_machine_statuses()

@router.put("/raw_materials/{raw_material_id}", response_model=RawMaterialOut)
async def update_raw_material_status(
    raw_material_id: int,
    is_available: bool,
    available_from: Optional[datetime] = None
):
    result = update_raw_material(raw_material_id, is_available, available_from)
    # Call scheduling function to update the schedule
    schedule_operations(fetch_operations(), fetch_component_quantities(), fetch_lead_times())
    return result

@router.put("/machine_statuses/{machine_id}", response_model=MachineStatusOut)
async def update_machine_status_endpoint(machine_id: int, status: str, available_from: Optional[datetime] = None):
    result = update_machine_status(machine_id, status, available_from)
    # Call scheduling function to update the schedule
    schedule_operations(fetch_operations(), fetch_component_quantities(), fetch_lead_times())
    return result
