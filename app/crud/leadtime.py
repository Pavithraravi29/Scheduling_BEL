from datetime import datetime
from typing import List, Dict
from app.database.models import DeliverySchedule, MasterOrder
from app.schemas.leadtime import LeadTimeIn, LeadTimeOut
from pony.orm import db_session, select, commit

@db_session
def fetch_lead_times() -> Dict[str, datetime]:
    # Fetching delivery schedules and associating part_number with scheduled delivery date (lead time)
    delivery_schedules = select(ds for ds in DeliverySchedule)[:]
    return {ds.order.part_number: ds.scheduled_delivery_date for ds in delivery_schedules}

@db_session
def insert_lead_times(lead_times: List[LeadTimeIn]) -> List[LeadTimeOut]:
    results = []
    for lt in lead_times:
        part_number = lt.component  # Assuming 'component' refers to part_number
        due_date = lt.due_date
        existing = DeliverySchedule.get(order__part_number=part_number)
        
        # If the delivery schedule already exists, update the due date
        if existing:
            existing.scheduled_delivery_date = due_date
        else:
            # Get the MasterOrder associated with the part_number
            order = MasterOrder.get(part_number=part_number)
            if order:
                # Insert new delivery schedule for the order
                DeliverySchedule(order=order, scheduled_delivery_date=due_date)
        
        # Add result for response
        results.append(LeadTimeOut(component=part_number, due_date=due_date))
    
    commit()
    return results
