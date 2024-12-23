from typing import List, Dict
from app.database.models import MasterOrder  # Use MasterOrder for quantity
from app.schemas.component_quantities import ComponentQuantityIn, ComponentQuantityOut
from pony.orm import db_session, select, commit

@db_session
def fetch_component_quantities() -> Dict[str, int]:
    # Fetch launched quantities from MasterOrder table
    orders = select(order for order in MasterOrder)[:]
    return {order.part_number: order.launched_quantity for order in orders}  # Assuming part_number is the component identifier

@db_session
def insert_component_quantities(quantities: List[ComponentQuantityIn]) -> List[ComponentQuantityOut]:
    results = []
    for qty in quantities:
        component = qty.component
        quantity = qty.quantity
        existing = MasterOrder.get(part_number=component)
        if existing:
            existing.launched_quantity = quantity
        else:
            MasterOrder(part_number=component, launched_quantity=quantity, total_operations=0, routing_sequence_no=0,
                        required_quantity=0, production_order_no="")
        results.append(ComponentQuantityOut(component=component, quantity=quantity))
    commit()
    return results
