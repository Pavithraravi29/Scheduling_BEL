from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from datetime import datetime
from pony.orm import db_session
from app.schemas.operations import OperationOut, ScheduledOperation, ScheduleResponse, MachineSchedulesOut
from app.crud.operations import fetch_operations
from app.crud.component_quantities import fetch_component_quantities
from app.crud.leadtime import fetch_lead_times
from app.algorithms.scheduling import schedule_operations
from app.database.models import Operation, MasterOrder, WorkCenter

router = APIRouter()

@router.get("/schedule/", response_model=ScheduleResponse)
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