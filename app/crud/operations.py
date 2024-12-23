from pony.orm import db_session, select, commit # Import db_session directly from pony.orm
import pandas as pd
from datetime import datetime
from app.database.models import Operation, MasterOrder, WorkCenter, WorkCenterMachine  # Import only the models
from typing import List


@db_session
def fetch_operations():
    """
    Fetch operations and convert to DataFrame with correct column names.
    Machine name is determined by work_center_id, time is set to allowed_time, and sequence is derived from operation_number.
    """
    try:
        operations = select((
            op.operation_description,  # Maps to 'operation'
            wc_machine.machine_name,   # Maps to 'machine'
            op.allowed_time,           # Maps to 'time'
            op.order.part_number,      # Maps to 'partno'
            op.operation_id,
            op.operation_number,
            op.setup_time,
            op.jump_quantity,
            op.total_quantity,
            op.work_center.work_center_id  # Maps to 'work_center_id'
        ) for op in Operation for wc_machine in WorkCenterMachine if wc_machine.work_center == op.work_center)

        df = pd.DataFrame(list(operations), columns=[
            "operation", "machine", "time", "partno", "operation_id",
            "operation_number", "setup_time", "jump_quantity",
            "total_quantity", "work_center_id"
        ])

        # Derive 'sequence' from 'operation_number'
        df['sequence'] = df['operation_number']

        return df

    except Exception as e:
        print(f"Error in fetch_operations: {str(e)}")
        return pd.DataFrame(columns=[
            "operation", "machine", "time", "partno", "operation_id",
            "operation_number", "setup_time", "jump_quantity",
            "total_quantity", "work_center_id", "sequence"
        ])


    
@db_session
def insert_operations(operations_data: List[dict]) -> List[dict]:
    """
    Insert new operations into the database.
    Returns list of created operations.
    """
    results = []
    
    try:
        for op_data in operations_data:
            # Find the related master order
            master_order = MasterOrder.get(part_number=op_data['partno'])
            if not master_order:
                print(f"Master order not found for part number: {op_data['partno']}")
                continue

            # Find or create work center
            work_center = WorkCenter.get(work_center_name=op_data.get('work_center'))
            if not work_center:
                print(f"Work center not found: {op_data.get('work_center')}")
                continue
                
            # Create new operation
            new_op = Operation(
                master_order=master_order,
                partno=op_data['partno'],
                operation=op_data['operation'],
                machine=op_data['machine'],
                time=op_data['time'],
                sequence=op_data.get('sequence', 0),
                work_center=work_center
            )
            
            results.append({
                "operation_id": new_op.operation_id,
                "partno": new_op.partno,
                "operation": new_op.operation,
                "machine": new_op.machine,
                "time": new_op.time,
                "sequence": new_op.sequence,
                "work_center": work_center.work_center_name
            })

    except Exception as e:
        print(f"Error in insert_operations: {str(e)}")
        
    return results



@db_session
def seed_test_data():
    """
    Seed the database with test data for scheduling
    """
    try:
        # Check if data already exists
        if MasterOrder.select().count() > 0:
            print("Data already exists in database")
            return
            
        # Create WorkCenter
        work_center = WorkCenter(
            work_center_code="WC001",
            work_center_name="Assembly Line 1",
            work_center_description="Main Assembly Line"
        )
        
        # Create MasterOrder
        master_order = MasterOrder(
            project_name="Test Project",
            part_number="62805080AA",  # Matching the component quantity from logs
            wbs="WBS001",
            sale_order="SO001",
            part_description="Test Part",
            total_operations=3,
            plant="Plant 1",
            routing_sequence_no=1,
            required_quantity=9,  # Matching the component quantity from logs
            launched_quantity=9,
            production_order_no="PO001"
        )
        
        # Create Operations
        operations = [
            {
                "operation": "Assembly",
                "machine": "M001",
                "time": 60,
                "sequence": 1
            },
            {
                "operation": "Testing",
                "machine": "M002",
                "time": 45,
                "sequence": 2
            },
            {
                "operation": "Packaging",
                "machine": "M003",
                "time": 30,
                "sequence": 3
            }
        ]
        
        for op_data in operations:
            Operation(
                master_order=master_order,
                partno=master_order.part_number,
                operation=op_data["operation"],
                machine=op_data["machine"],
                time=op_data["time"],
                sequence=op_data["sequence"],
                work_center=work_center
            )
            
        commit()
        print("Test data seeded successfully")
        
        # Verify data
        print(f"MasterOrders: {MasterOrder.select().count()}")
        print(f"Operations: {Operation.select().count()}")
        print(f"WorkCenters: {WorkCenter.select().count()}")
        
    except Exception as e:
        print(f"Error seeding test data: {str(e)}")
        raise


@db_session
def fix_operation_data():
    """
    Update existing operations to match the correct part number
    """
    try:
        # Get the master order
        master_order = MasterOrder.get(part_number='62805080AA')
        if not master_order:
            print("Master order not found for part number 62805080AA")
            return False

        # Update all operations to use the correct part number
        operations = Operation.select()[:]
        for op in operations:
            op.partno = '62805080AA'
            op.master_order = master_order
        
        commit()
        
        # Verify the update
        updated_count = Operation.select(lambda o: o.partno == '62805080AA').count()
        print(f"Updated {updated_count} operations with correct part number")
        
        return True
        
    except Exception as e:
        print(f"Error fixing operation data: {str(e)}")
        return False

@db_session
def verify_data_consistency():
    """
    Print current state of data for verification
    """
    try:
        print("\nData Verification:")
        print("==================")
        
        # Check MasterOrder
        master_order = MasterOrder.get(part_number='62805080AA')
        if master_order:
            print(f"\nMaster Order found:")
            print(f"Part Number: {master_order.part_number}")
            print(f"Project Name: {master_order.project_name}")
            print(f"Required Quantity: {master_order.required_quantity}")
        else:
            print("No master order found for 62805080AA")
            
        # Check Operations
        operations = Operation.select(lambda o: o.partno == '62805080AA')[:]
        print(f"\nOperations for 62805080AA: {len(operations)}")
        for op in operations:
            print(f"Operation ID: {op.operation_id}")
            print(f"Part No: {op.partno}")
            print(f"Operation: {op.operation}")
            print(f"Machine: {op.machine}")
            print(f"Time: {op.time}")
            print("---")
            
        # Check WorkCenters
        work_centers = WorkCenter.select()[:]
        print(f"\nWork Centers: {len(work_centers)}")
        for wc in work_centers:
            print(f"Name: {wc.work_center_name}")
            
    except Exception as e:
        print(f"Error in data verification: {str(e)}")