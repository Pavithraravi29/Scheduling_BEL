from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict

class OperationIn(BaseModel):
    partno: str
    operation: str
    machine: str
    time: int  # Time in minutes
    sequence: int
    work_center: str

class OperationOut(BaseModel):
    partno: str
    operation: str
    machine: str
    time: int  # Time in minutes
    start_time: datetime
    end_time: datetime

class ScheduledOperation(BaseModel):
    component: str
    description: str
    machine: str
    start_time: datetime
    end_time: datetime
    quantity: str

class ScheduleResponse(BaseModel):
    scheduled_operations: List[ScheduledOperation]
    overall_end_time: datetime
    overall_time: str
    daily_production: Dict
    component_status: Dict


# Existing daily production schema
class DailyProductionOut(BaseModel):
    overall_end_time: str
    overall_time: str
    daily_production: Dict[str, Dict[str, int]]
    total_components: int

# Machine schedules schema
class MachineScheduleItem(BaseModel):
    component: str
    operation: str
    start_time: str
    end_time: str               
    duration_minutes: int

class MachineSchedulesOut(BaseModel):
    machine_schedules: Dict[str, List[MachineScheduleItem]]

class ScheduleValidationItem(BaseModel):
    datetime: datetime
    machine: str
    component: str
    quantity: int

class ScheduleValidationRequest(BaseModel):
    items: List[ScheduleValidationItem]

class ValidationResult(BaseModel):
    datetime: datetime
    machine: str
    component: str
    requested_quantity: int
    scheduled_quantity: int
    status: str
    message: str