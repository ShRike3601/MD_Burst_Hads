from simulation.events import TaskCompleteEvent

def work_stealing(idle_vm, busy_vms, jobs, current_time, scheduler):

    for vm in busy_vms:

        if vm == idle_vm:
            continue

        if len(vm.tasks) <= 1:
            continue

        best_task = None
        best_gain = 0

        for task in vm.tasks:

            if task.completed:
                continue

            if current_time - task.last_migration_time < 3:
                continue

            job = jobs[task.job_id]

            current_slack = scheduler.slack(task, vm, job.deadline, current_time)
            new_slack = scheduler.slack(task, idle_vm, job.deadline, current_time)

            gain = new_slack - current_slack

            if gain > best_gain:
                best_gain = gain
                best_task = task

        if best_task and best_gain > 0:

            task = best_task

            vm.tasks.remove(task)
            task.assigned_vm = idle_vm
            idle_vm.tasks.append(task)

            task.last_migration_time = current_time

            execution_time = task.remaining_time / idle_vm.speed
            finish_time = current_time + execution_time

            event = TaskCompleteEvent(finish_time, task, idle_vm, scheduler.event_engine)
            task.current_event = event
            scheduler.event_engine.add_event(event)

            print(f"Task {task.id} stolen from VM {vm.id} to VM {idle_vm.id} at time {current_time}")

            return
        