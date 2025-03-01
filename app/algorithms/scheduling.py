from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, Tuple, List
from app.crud.raw_material import fetch_raw_materials, fetch_machine_statuses
from app.database.models import MasterOrder, RawMaterial, WorkCenterMachine, DeliverySchedule, Operation
from pony.orm import select, db_session
import math

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
        cumulative_pieces = {}  # Track cumulative pieces per operation
        operation_setup_done = {}  # Track if setup is done for each operation

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

        def calculate_exact_minutes(hours: float) -> float:
            """Convert hours to exact minutes with precision."""
            return hours * 60

        # Process each operation
        for op_idx, op in enumerate(available_operations):
            machine = op['machine']
            operation_key = f"{op['operation']}_{machine}"
            if operation_key not in cumulative_pieces:
                cumulative_pieces[operation_key] = 0
                operation_setup_done[operation_key] = False

            # Get setup time and per piece time from the operation record
            operation = Operation.select(lambda o: o.order.part_number == partno and
                                                   o.operation_number == op['sequence']).first()
            if not operation:
                continue

            # Calculate setup and processing times
            setup_minutes = calculate_exact_minutes(operation.setup_time)
            per_piece_minutes = calculate_exact_minutes(operation.per_piece_time)

            current_time = operation_time
            machine_available, available_time = check_machine_status(machine, current_time)

            if not machine_available:
                if available_time is None:
                    continue
                current_time = available_time

            current_time = adjust_to_shift_hours(current_time)
            current_time = max(current_time, machine_end_times.get(machine, current_time))
            operation_start = current_time

            # Handle setup time first if not done
            if not operation_setup_done[operation_key]:
                setup_end = operation_start + timedelta(minutes=setup_minutes)
                shift_end = operation_start.replace(hour=17, minute=0, second=0, microsecond=0)

                if setup_end > shift_end:
                    # Setup spans multiple shifts
                    batch_schedule.append([
                        partno, op['operation'], machine,
                        operation_start, shift_end,
                        f"Setup({int((shift_end - operation_start).total_seconds() / 60)}/{setup_minutes}min)"
                    ])

                    next_day = shift_end + timedelta(days=1)
                    next_start = next_day.replace(hour=9, minute=0, second=0, microsecond=0)
                    remaining_setup = setup_minutes - (shift_end - operation_start).total_seconds() / 60

                    while remaining_setup > 0:
                        current_shift_end = next_start.replace(hour=17, minute=0, second=0, microsecond=0)
                        setup_possible = min(remaining_setup, (current_shift_end - next_start).total_seconds() / 60)
                        current_end = next_start + timedelta(minutes=setup_possible)

                        batch_schedule.append([
                            partno, op['operation'], machine,
                            next_start, current_end,
                            f"Setup({setup_minutes - remaining_setup + setup_possible}/{setup_minutes}min)"
                        ])

                        remaining_setup -= setup_possible
                        if remaining_setup > 0:
                            next_start = (current_shift_end + timedelta(days=1)).replace(hour=9, minute=0, second=0,
                                                                                         microsecond=0)

                        current_time = current_end
                    operation_start = current_end
                else:
                    # Setup fits in current shift
                    batch_schedule.append([
                        partno, op['operation'], machine,
                        operation_start, setup_end, f"Setup({setup_minutes}/{setup_minutes}min)"
                    ])
                    operation_start = setup_end
                    current_time = setup_end

                operation_setup_done[operation_key] = True

            # Calculate quantity processing time
            total_processing_time = per_piece_minutes * quantity
            processing_end = operation_start + timedelta(minutes=total_processing_time)
            shift_end = operation_start.replace(hour=17, minute=0, second=0, microsecond=0)

            if processing_end > shift_end:
                # Calculate work that can be done today
                work_minutes_today = (shift_end - operation_start).total_seconds() / 60
                completion_ratio = work_minutes_today / total_processing_time if total_processing_time > 0 else 0
                pieces_today = int(quantity * completion_ratio)

                # Update cumulative pieces for this operation
                new_cumulative = min(cumulative_pieces[operation_key] + pieces_today, quantity)
                if work_minutes_today > 0:
                    batch_schedule.append([
                        partno, op['operation'], machine,
                        operation_start, shift_end, f"Process({new_cumulative}/{quantity}pcs)"
                    ])
                    cumulative_pieces[operation_key] = new_cumulative

                # Calculate remaining work
                remaining_time = total_processing_time - work_minutes_today
                remaining_pieces = quantity - new_cumulative

                # Start next day at 9 AM
                next_day = shift_end + timedelta(days=1)
                next_start = next_day.replace(hour=9, minute=0, second=0, microsecond=0)

                # Continue scheduling remaining work in 8-hour shifts
                while remaining_time > 0:
                    current_shift_end = next_start.replace(hour=17, minute=0, second=0, microsecond=0)
                    work_possible = min(remaining_time, (current_shift_end - next_start).total_seconds() / 60)
                    current_end = next_start + timedelta(minutes=work_possible)

                    shift_completion_ratio = work_possible / remaining_time
                    pieces_this_shift = min(remaining_pieces,
                                            remaining_pieces if work_possible >= remaining_time
                                            else int(remaining_pieces * shift_completion_ratio))

                    new_cumulative = min(cumulative_pieces[operation_key] + pieces_this_shift, quantity)

                    batch_schedule.append([
                        partno, op['operation'], machine,
                        next_start, current_end, f"Process({new_cumulative}/{quantity}pcs)"
                    ])

                    cumulative_pieces[operation_key] = new_cumulative
                    remaining_pieces = quantity - new_cumulative

                    remaining_time -= work_possible
                    if remaining_time > 0:
                        next_start = (current_shift_end + timedelta(days=1)).replace(hour=9, minute=0, second=0,
                                                                                     microsecond=0)

                    current_time = current_end
                    machine_end_times[machine] = current_end
            else:
                # Operation can be completed within current shift
                cumulative_pieces[operation_key] = quantity
                batch_schedule.append([
                    partno, op['operation'], machine,
                    operation_start, processing_end, f"Process({quantity}/{quantity}pcs)"
                ])
                current_time = processing_end
                machine_end_times[machine] = processing_end

            # Update completion times for all units after operation is complete
            if op_idx == len(available_operations) - 1:
                for unit_number in range(1, quantity + 1):
                    unit_completion_times[unit_number] = current_time

            # Update operation_time for next operation
            operation_time = max(machine_end_times[machine], operation_time)

        return batch_schedule, len(available_operations), unit_completion_times

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