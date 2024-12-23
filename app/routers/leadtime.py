from fastapi import APIRouter
from app.crud.leadtime import fetch_lead_times, insert_lead_times
from app.schemas.leadtime import LeadTimeResponse, LeadTimeIn, LeadTimeOut, ComponentStatusResponse, ComponentStatus
from app.algorithms.scheduling import schedule_operations
from app.crud.component_quantities import fetch_component_quantities
from app.crud.operations import fetch_operations
from typing import List, Optional
from datetime import datetime
from pony.orm import db_session
from app.database.models import DeliverySchedule

router = APIRouter()

# Endpoint to fetch the current lead times (delivery schedules)
@router.get("/lead-time-table", response_model=List[LeadTimeResponse])
@db_session
def get_lead_times():
    # Fetching all delivery schedules
    delivery_schedules = DeliverySchedule.select()

    result = []
    for ds in delivery_schedules:
        # Construct the response with part_number and due_date (lead time)
        result.append(LeadTimeResponse(
            component=ds.order.part_number,  # This refers to part_number in MasterOrder
            due_date=ds.scheduled_delivery_date
        ))

    return result

# Endpoint to insert new lead times (delivery schedules) or update existing ones
@router.post("/insert_lead_times/", response_model=List[LeadTimeOut])
async def create_lead_times(lead_times: List[LeadTimeIn]):
    return insert_lead_times(lead_times)

# Endpoint to fetch component statuses based on scheduling
@router.get("/component_status/", response_model=ComponentStatusResponse)
async def get_component_status():
    # Fetch operations and component quantities for scheduling
    df = fetch_operations()
    component_quantities = fetch_component_quantities()
    lead_times = fetch_lead_times()
    
    # Schedule operations and categorize components based on completion status
    _, _, _, _, component_status, _ = schedule_operations(df, component_quantities, lead_times)

    # Categorize components into early, on-time, and delayed
    early_complete = []
    on_time_complete = []
    delayed_complete = []

    for comp, status in component_status.items():
        scheduled_end_time: Optional[datetime] = status.get('scheduled_end_time')

        if scheduled_end_time is None:
            # Skip component if the scheduled end time is missing
            continue

        # Create component status with lead time information
        component = ComponentStatus(
            component=comp,
            scheduled_end_time=status['scheduled_end_time'],
            lead_time=status['lead_time'],
            on_time=status['on_time'],
            completed_quantity=status['completed_quantity'],
            total_quantity=status['total_quantity'],
            lead_time_provided=status['lead_time'] is not None,
            delay=None
        )

        # Categorize components based on their lead time and scheduled end time
        if status['lead_time_provided']:
            if status['scheduled_end_time'] < status['lead_time']:
                early_complete.append(component)
            elif status['scheduled_end_time'] == status['lead_time']:
                on_time_complete.append(component)
            else:
                component.delay = status['scheduled_end_time'] - status['lead_time']
                delayed_complete.append(component)
        else:
            on_time_complete.append(component)

    # Return response with categorized components
    return ComponentStatusResponse(
        early_complete=early_complete,
        on_time_complete=on_time_complete,
        delayed_complete=delayed_complete
    )
