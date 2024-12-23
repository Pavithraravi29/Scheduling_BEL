from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List

# Schema for input data to insert lead times (delivery schedules)
class LeadTimeIn(BaseModel):
    component: str  # This refers to the part_number in MasterOrder
    due_date: datetime

# Schema for the output data after inserting lead times
class LeadTimeOut(BaseModel):
    component: str  # This refers to the part_number in MasterOrder
    due_date: datetime

# Schema for individual component status with lead time information
class ComponentStatusOut(BaseModel):
    component: str
    scheduled_end_time: datetime
    lead_time: Optional[datetime]
    on_time: bool
    completed_quantity: int
    total_quantity: int
    lead_time_provided: bool

# Schema for individual component status (used in response)
class ComponentStatus(BaseModel):
    component: str
    scheduled_end_time: datetime
    lead_time: Optional[datetime]
    on_time: bool
    completed_quantity: int
    total_quantity: int
    lead_time_provided: bool
    delay: Optional[timedelta]

# Response schema for component status, categorized by early, on-time, and delayed
class ComponentStatusResponse(BaseModel):
    early_complete: List[ComponentStatus]
    on_time_complete: List[ComponentStatus]
    delayed_complete: List[ComponentStatus]

# Response schema for lead times, to show part number and due dates
class LeadTimeResponse(BaseModel):
    component: str  # part_number
    due_date: datetime
