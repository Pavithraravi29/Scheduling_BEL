from pony.orm import db_session, select, flush
from app.database.models import RawMaterial, MasterOrder
from app.database.models import WorkCenterMachine
from app.schemas.raw_material import RawMaterialIn, RawMaterialOut, MachineStatusIn, MachineStatusOut


from typing import List, Optional
from datetime import datetime

@db_session
def insert_raw_materials(raw_materials: List[RawMaterialIn]) -> List[RawMaterialOut]:
    inserted = []
    for rm in raw_materials:
        master_order = MasterOrder[rm.order_id]  # Assuming raw_material has order_id as reference to MasterOrder
        raw_material = RawMaterial(
            order=master_order,
            sl_no=rm.sl_no,
            child_part_no=rm.child_part_no,
            description=rm.description,
            qty_per_set=rm.qty_per_set,
            uom=rm.uom,
            total_qty=rm.total_qty,
            is_available=rm.is_available,
            available_from=rm.available_from
        )
        flush()  # Force the database to generate the ID
        inserted.append(RawMaterialOut(id=raw_material.raw_material_id, sl_no=raw_material.sl_no,
                                       description=raw_material.description, available_from=raw_material.available_from))
    return inserted

@db_session
def fetch_raw_materials():
    raw_materials = RawMaterial.select()
    return [
        RawMaterialOut(
            raw_material_id=rm.raw_material_id,
            order_id=rm.order.order_id,
            sl_no=rm.sl_no,
            child_part_no=rm.child_part_no,
            description=rm.description,
            qty_per_set=rm.qty_per_set,
            uom=rm.uom,
            total_qty=rm.total_qty,
            available_from=rm.available_from
        ) for rm in raw_materials
    ]

@db_session
def update_raw_material(raw_material_id: int, is_available: bool, available_from: Optional[datetime] = None) -> RawMaterialOut:
    rm = RawMaterial[raw_material_id]
    rm.is_available = is_available
    if available_from:
        rm.available_from = available_from
    return RawMaterialOut(id=rm.raw_material_id, sl_no=rm.sl_no, description=rm.description, available_from=rm.available_from)



@db_session
def insert_machine_statuses(statuses: List[MachineStatusIn]) -> List[MachineStatusOut]:
    inserted = []
    for status in statuses:
        work_center_machine = WorkCenterMachine[status.machine_id]  # Assuming status has machine_id
        machine_status = WorkCenterMachine(
            machine_name=status.machine,
            work_center=work_center_machine.work_center,
            status=status.status,
            available_from=status.available_from
        )
        flush()  # Force the database to generate the ID
        inserted.append(MachineStatusOut(id=machine_status.machine_id, machine=machine_status.machine_name,
                                         status=machine_status.status, available_from=machine_status.available_from))
    return inserted

@db_session
def fetch_machine_statuses():
    machine_statuses = WorkCenterMachine.select()
    return [
        MachineStatusOut(
            machine_id=ms.machine_id,
            machine=ms.machine_name,
            status=ms.status,
            available_from=ms.available_from,
            timestamp=datetime.now()
        ) for ms in machine_statuses
    ]

@db_session
def update_machine_status(machine_id: int, status: str, available_from: Optional[datetime] = None) -> MachineStatusOut:
    ms = WorkCenterMachine[machine_id]
    ms.status = status
    if available_from:
        ms.available_from = available_from
    return MachineStatusOut(id=ms.machine_id, machine=ms.machine_name, status=ms.status, available_from=ms.available_from)
