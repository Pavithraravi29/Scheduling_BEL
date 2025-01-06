from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, Tuple, List
from app.crud.raw_material import fetch_raw_materials, fetch_machine_statuses
from app.database.models import MasterOrder, RawMaterial, WorkCenterMachine, DeliverySchedule
from pony.orm import select, db_session


def adjust_to_shift_hours(time: datetime) -> datetime:
    if time.hour < 9:
        return time.replace(hour=9, minute=0, second=0, microsecond=0)
    elif time.hour >= 17:
        return (time + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return time


@db_session
def schedule_operations(df: pd.DataFrame, component_quantities: Dict[str, int],
                        lead_times: Dict[str, datetime] = None) -> \
        Tuple[pd.DataFrame, datetime, float, Dict, Dict, List[str]]:
    if df.empty:
        return pd.DataFrame(), datetime.now(), 0.0, {}, {}, []

    # Fetch raw materials and machine statuses from database
    raw_materials = {rm.child_part_no: (rm.is_available, rm.total_qty, rm.uom) for rm in RawMaterial.select()}
    machine_statuses = {wm.machine_name: (wm.status, wm.available_from) for wm in WorkCenterMachine.select()}

    print("Raw Materials:", raw_materials)
    print("Machine Statuses:", machine_statuses)

    # Pre-process the dataframe to group by part number and get operation sequences
    df_sorted = df.sort_values(by=['partno', 'sequence'])
    part_operations = {
        partno: group.to_dict('records')
        for partno, group in df_sorted.groupby('partno')
    }

    start_date = datetime(2024, 12, 20, 9, 0)
    start_date = adjust_to_shift_hours(start_date)

    schedule = []
    machine_end_times = {machine: start_date for machine in df_sorted["machine"].unique()}
    daily_production = {}
    part_status = {}
    partially_completed = []

    def check_machine_status(machine: str, time: datetime) -> Tuple[bool, datetime]:
        status, available_from = machine_statuses.get(machine, ('ON', None))
        if status == 'OFF':
            return False, None
        if available_from and time < available_from:
            return False, available_from
        return True, time

    def find_last_available_operation(operations: List[dict], current_time: datetime) -> int:
        """Returns the index of the last available operation in the sequence."""
        last_available = -1
        current_op_time = current_time

        for idx, op in enumerate(operations):
            machine = op['machine']
            machine_available, available_time = check_machine_status(machine, current_op_time)

            if not machine_available and available_time is None:
                break

            if available_time:
                current_op_time = available_time

            last_available = idx
            current_op_time += timedelta(minutes=op['time'] * 60)

        return last_available

    def schedule_batch_operations(partno: str, operations: List[dict], quantity: int, start_time: datetime) -> Tuple[
        List[list], int, Dict[int, datetime]]:
        batch_schedule = []
        operation_time = start_time
        unit_completion_times = {}

        # Check raw material availability
        order = MasterOrder.select(lambda o: o.part_number == partno).first()
        raw_available = all(rm.is_available for rm in order.raw_materials)
        raw_available_time = max((rm.available_from for rm in order.raw_materials if rm.available_from), default=None)

        if not raw_available:
            return [], 0, {}

        if raw_available_time and operation_time < raw_available_time:
            operation_time = raw_available_time

        # Find the last available operation in the sequence
        last_available_idx = find_last_available_operation(operations, operation_time)

        if last_available_idx < 0:
            return [], 0, {}

        # Get the subset of operations that can be performed
        available_operations = operations[:last_available_idx + 1]

        # Process each operation for all units
        for op_idx, op in enumerate(available_operations):
            machine = op['machine']
            time_required = op['time'] * 60  # convert to minutes
            current_time = operation_time

            # Process all units for this operation
            for unit_number in range(1, quantity + 1):
                machine_available, available_time = check_machine_status(machine, current_time)
                if not machine_available:
                    if available_time is None:
                        continue
                    current_time = available_time

                current_time = adjust_to_shift_hours(current_time)
                current_time = max(current_time, machine_end_times.get(machine, current_time))
                operation_start = current_time

                # Calculate initial end time
                operation_end = operation_start + timedelta(minutes=time_required)
                shift_end = operation_start.replace(hour=17, minute=0, second=0, microsecond=0)

                if operation_end > shift_end:
                    # Calculate work that can be done today
                    work_today = (shift_end - operation_start).total_seconds() / 60

                    if work_today > 0:
                        # Schedule work until end of shift
                        batch_schedule.append([
                            partno, op['operation'], machine,
                            operation_start, shift_end, f"{unit_number}/{quantity}"
                        ])

                    # Calculate remaining work
                    remaining_time = time_required - work_today

                    # Start next day at 9 AM
                    next_day = shift_end + timedelta(days=1)
                    next_start = next_day.replace(hour=9, minute=0, second=0, microsecond=0)

                    # Continue scheduling remaining work in 8-hour chunks
                    while remaining_time > 0:
                        current_shift_end = next_start.replace(hour=17, minute=0, second=0, microsecond=0)
                        work_possible = min(remaining_time, (current_shift_end - next_start).total_seconds() / 60)

                        current_end = next_start + timedelta(minutes=work_possible)
                        batch_schedule.append([
                            partno, op['operation'], machine,
                            next_start, current_end, f"{unit_number}/{quantity}"
                        ])

                        remaining_time -= work_possible
                        if remaining_time > 0:
                            next_start = (current_shift_end + timedelta(days=1)).replace(hour=9, minute=0, second=0,
                                                                                         microsecond=0)

                        current_time = current_end
                        machine_end_times[machine] = current_end
                else:
                    # Operation can be completed within current shift
                    batch_schedule.append([
                        partno, op['operation'], machine,
                        operation_start, operation_end, f"{unit_number}/{quantity}"
                    ])
                    current_time = operation_end
                    machine_end_times[machine] = operation_end

                # Update completion time only after the last operation
                if op_idx == len(available_operations) - 1:
                    unit_completion_times[unit_number] = current_time

            # Update operation_time for next operation to ensure all units are processed before moving on
            operation_time = max(machine_end_times[machine], operation_time)

        return batch_schedule, len(available_operations), unit_completion_times

    # Rest of the code remains the same
    for partno in component_quantities.keys():
        if partno not in part_operations:
            continue

        operations = part_operations[partno]
        quantity = component_quantities[partno]

        lead_time = None
        if lead_times and partno in lead_times:
            lead_time = lead_times[partno]
        else:
            delivery_schedule = DeliverySchedule.select(lambda ds: ds.order.part_number == partno).first()
            lead_time = delivery_schedule.scheduled_delivery_date if delivery_schedule else None

        batch_schedule, completed_ops, unit_completion_times = schedule_batch_operations(
            partno, operations, quantity, start_date
        )

        if batch_schedule:
            schedule.extend(batch_schedule)
            latest_completion_time = max(unit_completion_times.values()) if unit_completion_times else None

            part_status[partno] = {
                'partno': partno,
                'scheduled_end_time': latest_completion_time,
                'lead_time': lead_time,
                'on_time': latest_completion_time.date() <= lead_time if lead_time and latest_completion_time else None,
                'completed_quantity': len(unit_completion_times),
                'total_quantity': quantity,
                'lead_time_provided': lead_time is not None
            }

            for unit_num, completion_time in unit_completion_times.items():
                completion_day = completion_time.date()
                if partno not in daily_production:
                    daily_production[partno] = {}
                if completion_day not in daily_production[partno]:
                    daily_production[partno][completion_day] = 0
                daily_production[partno][completion_day] += 1

            if completed_ops < len(operations):
                partially_completed.append(
                    f"{partno}: Completed {completed_ops}/{len(operations)} operation types for {quantity} units")

    schedule_df = pd.DataFrame(
        schedule,
        columns=["partno", "operation", "machine", "start_time", "end_time", "quantity"]
    )

    if schedule_df.empty:
        return schedule_df, start_date, 0.0, daily_production, {}, partially_completed

    overall_end_time = max(schedule_df['end_time'])
    overall_time = (overall_end_time - start_date).total_seconds() / 60

    return schedule_df, overall_end_time, overall_time, daily_production, part_status, partially_completed