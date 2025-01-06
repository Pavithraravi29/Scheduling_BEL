import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, time
from pony.orm import db_session, select
from pydantic import BaseModel

from app.schemas.operations import OperationOut, ScheduledOperation, ScheduleResponse, MachineSchedulesOut
from app.crud.operations import fetch_operations
from app.crud.component_quantities import fetch_component_quantities
from app.crud.leadtime import fetch_lead_times
from app.algorithms.scheduling import schedule_operations
from app.database.models import Operation, MasterOrder, WorkCenter, DeliverySchedule, WorkCenterMachine,  RawMaterial


router = APIRouter()

@router.get("/schedule-batch/", response_model=ScheduleResponse)
async def schedule():
    try:
        print("Checking database state...")
        with db_session:
            ops_count = Operation.select().count()
            orders_count = MasterOrder.select().count()
            wc_count = WorkCenter.select().count()
            print(f"Database counts - Operations: {ops_count}, MasterOrders: {orders_count}, WorkCenters: {wc_count}")

        print("Fetching operations...")
        df = fetch_operations()
        print(f"Operations DataFrame shape: {df.shape}")
        print(f"Operations DataFrame columns: {df.columns.tolist()}")
        if not df.empty:
            print("First few rows of operations:")
            print(df.head().to_dict('records'))

        print("Fetching component quantities...")
        component_quantities = fetch_component_quantities()
        print(f"Component quantities: {component_quantities}")

        print("Fetching lead times...")
        lead_times = fetch_lead_times()
        print(f"Lead times: {lead_times}")

        # Validate operations match component quantities
        if not df.empty:
            matching_ops = df[df['partno'].isin(component_quantities.keys())]
            print(f"Found {len(matching_ops)} operations matching component quantities")
            print("Available part numbers in operations:", df['partno'].unique())
            print("Requested part numbers:", list(component_quantities.keys()))

        # Ensure DataFrame has required columns
        required_columns = ["partno", "operation_id", "operation", "machine", "time"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in operations DataFrame: {missing_columns}")

        schedule_df, overall_end_time, overall_time, daily_production, component_status, partially_completed = \
            schedule_operations(df, component_quantities, lead_times)

        print(f"Schedule created - operations count: {len(schedule_df) if not schedule_df.empty else 0}")
        print(f"Partially completed: {partially_completed}")

        scheduled_operations = []
        if not schedule_df.empty:
            scheduled_operations = [
                ScheduledOperation(
                    component=row['partno'],
                    description=row['operation'],
                    machine=row['machine'],
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    quantity=row['quantity']
                ) for _, row in schedule_df.iterrows()
            ]

        return ScheduleResponse(
            scheduled_operations=scheduled_operations,
            overall_end_time=overall_end_time,
            overall_time=str(overall_time),
            daily_production=daily_production,
            component_status=component_status
        )

    except Exception as e:
        print(f"Error in schedule endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/machine_schedules/", response_model=MachineSchedulesOut)
async def get_machine_schedules(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    with db_session:
        df = fetch_operations()
        component_quantities = fetch_component_quantities()
        lead_times = fetch_lead_times()

        schedule_df, _, _, _, _, _ = schedule_operations(
            df, component_quantities, lead_times
        )

        machine_schedules = {}
        for _, row in schedule_df.iterrows():
            machine = row['machine']
            if machine not in machine_schedules:
                machine_schedules[machine] = []

            machine_schedules[machine].append({
                "part_number": row['partno'],
                "operation": row['operation'],
                "start_time": row['start_time'],
                "end_time": row['end_time'],
                "duration_minutes": (row['end_time'] - row['start_time']).total_seconds() / 60
            })

        return MachineSchedulesOut(machine_schedules=machine_schedules)




@router.get("/unit_schedule/", response_model=List[ScheduledOperation])
async def unit_schedule():
    try:
        with db_session:
            # Fetch data from the scheduling algorithm
            df = fetch_operations()
            component_quantities = fetch_component_quantities()
            lead_times = fetch_lead_times()

            # Call existing scheduling logic
            result = schedule_operations(df, component_quantities, lead_times)
            schedule_df = result[0]

            if schedule_df.empty:
                return []

            # Transform into unit-level schedule
            unit_schedule_details = []
            operation_order = {}  # Track the order of operations as they appear
            current_order = 0

            for _, row in schedule_df.iterrows():
                if row['operation'] not in operation_order:
                    operation_order[row['operation']] = current_order
                    current_order += 1

                try:
                    quantity_info = str(row['quantity'])

                    # Handle setup operations
                    if quantity_info.startswith('Setup'):
                        setup_info = quantity_info.strip('Setup()').split('/')
                        if len(setup_info) == 2:
                            unit_schedule_details.append(ScheduledOperation(
                                component=row['partno'],
                                description=row['operation'],
                                machine=row['machine'],
                                start_time=row['start_time'],
                                end_time=row['end_time'],
                                quantity="setuptime"
                            ))

                    # Handle process operations
                    elif quantity_info.startswith('Process'):
                        process_info = quantity_info.strip('Process()').split('/')
                        if len(process_info) == 2:
                            completed_pieces = int(process_info[0].strip('pcs'))
                            total_pieces = int(process_info[1].strip('pcs'))

                            # Get operation details
                            operation = select(o for o in Operation
                                               if o.order.part_number == row['partno']
                                               and o.operation_description == row['operation']).first()

                            if operation:
                                # Calculate pieces in this block
                                previous_pieces = sum(1 for op in unit_schedule_details
                                                      if op.component == row['partno']
                                                      and op.description == row['operation']
                                                      and op.quantity != "setuptime")

                                pieces_in_block = completed_pieces - previous_pieces

                                if pieces_in_block > 0:
                                    # Calculate time per piece
                                    total_time = (row['end_time'] - row['start_time']).total_seconds()
                                    time_per_piece = total_time / pieces_in_block

                                    # Create individual piece operations
                                    for piece_idx in range(pieces_in_block):
                                        piece_number = previous_pieces + piece_idx + 1
                                        piece_start = row['start_time'] + timedelta(seconds=piece_idx * time_per_piece)
                                        piece_end = piece_start + timedelta(seconds=time_per_piece)

                                        unit_schedule_details.append(ScheduledOperation(
                                            component=row['partno'],
                                            description=row['operation'],
                                            machine=row['machine'],
                                            start_time=piece_start,
                                            end_time=piece_end,
                                            quantity=f"{piece_number}/{total_pieces}"
                                        ))

                except ValueError as ve:
                    print(f"Warning: Error processing operation: {str(ve)}")
                    continue
                except Exception as e:
                    print(f"Error processing operation: {str(e)}")
                    continue

            # Custom sorting function
            def sort_key(x):
                operation_seq = operation_order.get(x.description, float('inf'))
                is_setup = x.quantity == "setuptime"
                unit_number = 0
                if not is_setup:
                    try:
                        unit_number = int(x.quantity.split('/')[0])
                    except:
                        pass
                return (operation_seq, not is_setup, unit_number, x.start_time)

            # Sort operations
            sorted_schedule = sorted(unit_schedule_details, key=sort_key)
            return sorted_schedule

    except Exception as e:
        print(f"Error in unit_schedule endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



