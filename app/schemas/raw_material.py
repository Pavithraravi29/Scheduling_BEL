from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

# RawMaterial Schemas
class RawMaterialBase(BaseModel):
    sl_no: str
    child_part_no: str
    description: str
    qty_per_set: float
    uom: str
    total_qty: float
    is_available: bool = True
    available_from: Optional[datetime] = None

class RawMaterialIn(RawMaterialBase):
    order_id: int  # Reference to MasterOrder

class RawMaterialOut(BaseModel):
    raw_material_id: int
    order_id: int
    sl_no: str
    child_part_no: str
    description: str
    qty_per_set: float
    uom: str
    total_qty: float
    available_from: datetime | None = None

# WorkCenter Schemas
class WorkCenterBase(BaseModel):
    work_center_code: str
    work_center_name: str
    work_center_description: str

class WorkCenterIn(WorkCenterBase):
    pass

class WorkCenterOut(WorkCenterBase):
    work_center_id: int

    class Config:
        orm_mode = True


# WorkCenterMachine Schemas
class WorkCenterMachineBase(BaseModel):
    machine_name: str
    status: str  # 'OK', 'WARNING', 'CRITICAL', or 'OFF'
    available_from: Optional[datetime] = None

class WorkCenterMachineIn(WorkCenterMachineBase):
    work_center_id: int  # Reference to WorkCenter

class WorkCenterMachineOut(WorkCenterMachineBase):
    machine_id: int
    work_center_id: int  # Reference to WorkCenter

    class Config:
        orm_mode = True

# Scheduling Output Schemas
class DailyProductionOut(BaseModel):
    overall_end_time: str
    overall_time: str
    daily_production: Dict[str, Dict[datetime, int]]
    total_components: int

class MachineSchedulesOut(BaseModel):
    machine_schedules: Dict[str, List[Dict[str, str]]]

# Component Status Schema
class ComponentStatus(BaseModel):
    scheduled_end_time: datetime
    lead_time: Optional[datetime]
    on_time: bool
    completed_quantity: int
    total_quantity: int
    lead_time_provided: bool

# Component Status Response Schema
class ComponentStatusResponse(BaseModel):
    early_complete: List[ComponentStatus]
    on_time_complete: List[ComponentStatus]
    delayed_complete: List[ComponentStatus]

class OperationOut1(BaseModel):
    component: str
    description: str
    type: str
    machine: str
    start_time: datetime
    end_time: datetime
    quantity: str

class MachineStatusIn(BaseModel):
    machine_id: int  # The ID of the machine
    status: str  # The status of the machine (e.g., "running", "idle", "maintenance")
    timestamp: int  # The timestamp when the status was recorded (e.g., Unix timestamp in milliseconds)

    class Config:
        # Optional configuration for validation or serialization
        orm_mode = True

class MachineStatusOut(BaseModel):
    machine_id: int
    machine: str
    status: str
    available_from: datetime | None = None
    timestamp: datetime = datetime.now()