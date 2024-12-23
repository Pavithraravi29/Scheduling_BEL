from pony.orm import Database, Required, Optional, PrimaryKey, Set
from datetime import date, datetime

db = Database()

class MasterOrder(db.Entity):
    order_id = PrimaryKey(int, auto=True)
    project_name = Required(str)
    part_number = Required(str)
    wbs = Required(str)
    sale_order = Required(str)
    part_description = Required(str)
    total_operations = Required(int)
    plant = Required(str)
    routing_sequence_no = Required(int)
    required_quantity = Required(int)
    launched_quantity = Required(int)
    production_order_no = Required(str)
    # Relationships
    document_references = Set('DocumentReference')
    raw_materials = Set('RawMaterial')
    operations = Set('Operation')
    delivery_schedules = Set('DeliverySchedule')

class DocumentReference(db.Entity):
    document_reference_id = PrimaryKey(int, auto=True)
    order = Required(MasterOrder)
    document_type = Required(str)  # e.g., "OARC Rev", "Drawing No", etc.
    document_number = Required(str)
    revision = Required(str, default='--')

class RawMaterial(db.Entity):
    raw_material_id = PrimaryKey(int, auto=True)
    order = Required(MasterOrder)
    sl_no = Required(str)
    child_part_no = Required(str)
    description = Required(str)
    qty_per_set = Required(float)
    uom = Required(str)
    total_qty = Required(float)
    is_available = Required(bool, default=True)
    available_from = Optional(datetime)

class WorkCenter(db.Entity):
    work_center_id = PrimaryKey(int, auto=True)
    work_center_code = Required(str, unique=True)
    work_center_name = Required(str)
    work_center_description = Required(str)
    work_center_machines = Set('WorkCenterMachine')
    # Reverse relationship to Operation
    operations = Set('Operation')  # Add reverse relationship here

class Operation(db.Entity):
    operation_id = PrimaryKey(int, auto=True)
    order = Required(MasterOrder)
    work_center = Required(WorkCenter)
    operation_number = Required(int)
    operation_description = Required(str) 
    setup_time = Required(float)
    per_piece_time = Required(float)
    jump_quantity = Required(int)
    total_quantity = Required(int)
    allowed_time = Required(float)
    actual_time = Optional(float)
    confirmation_number = Optional(str)
    # Relationships
    work_center_machines = Set('WorkCenterMachine')

class WorkCenterMachine(db.Entity):
    machine_id = PrimaryKey(int, auto=True)
    machine_name = Required(str)
    work_center = Required(WorkCenter)
    status = Required(str)  # 'OK', 'WARNING', 'CRITICAL', or 'OFF'
    available_from = Optional(datetime)
    # Reverse relationship
    operations = Set(Operation)

class DeliverySchedule(db.Entity):
    schedule_id = PrimaryKey(int, auto=True)
    order = Required(MasterOrder)
    scheduled_delivery_date = Required(date)
