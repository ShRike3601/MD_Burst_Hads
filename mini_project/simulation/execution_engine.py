from simulation.events import TaskCompleteEvent

def execute_tasks(vms, current_time, event_engine):
    for vm in vms:
        if vm.tasks:
            task = vm.tasks[0]

            execution_time = task.remaining_time / vm.speed
            finish_time = current_time + execution_time

            event_engine.add_event(
                TaskCompleteEvent(finish_time, task, vm)
            )

def start_execution(vms, current_time, event_engine):

    from simulation.events import TaskCompleteEvent

    for vm in vms:

        if vm.tasks:

            task = vm.tasks[0]

            # 🔥 skip if already scheduled
            if task.current_event is not None:
                continue

            execution_time = task.remaining_time / vm.speed
            finish_time = current_time + execution_time

            event = TaskCompleteEvent(finish_time, task, vm, event_engine)

            task.current_event = event
            event_engine.add_event(event)