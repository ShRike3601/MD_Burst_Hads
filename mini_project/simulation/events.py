class TaskCompleteEvent:
    def __init__(self, time, task, vm, engine):
        self.time = time
        self.task = task
        self.vm = vm
        self.engine = engine
        
    def execute(self):
        
        if self.task.current_event != self:
            return

        print(f"Task {self.task.id} completed on VM {self.vm.id} at time {self.time}")

        if self.task.completed:
            return

        self.task.finish_time = self.time
        self.task.completed = True
        
        if self.task in self.vm.tasks:
            self.vm.tasks.remove(self.task)

        # 🔥 START NEXT TASK (important)
        if self.vm.tasks:
            next_task = self.vm.tasks[0]

            execution_time = next_task.remaining_time / self.vm.speed
            finish_time = self.time + execution_time

            # create new event
            event = TaskCompleteEvent(finish_time, next_task, self.vm, self.engine)
            next_task.current_event = event

            # ⚠️ need access to event engine (we fix this below)
            self.engine.add_event(event)

            # 🔥 only apply work stealing if scheduler supports it
            if hasattr(self.engine.scheduler, "slack"):

                from policies.work_stealing import work_stealing

                idle_vm = self.vm
                busy_vms = [vm for vm in self.engine.scheduler.vms if vm.tasks]

                work_stealing(
                    idle_vm,
                    busy_vms,
                    self.engine.scheduler.jobs,
                    self.time,
                    self.engine.scheduler
                )

class HibernationEvent:
    def __init__(self, time, vm, scheduler):
        self.time = time
        self.vm = vm
        self.scheduler = scheduler

    def execute(self):
        
        print(f"VM {self.vm.id} hibernated at time {self.time}")

        # take all tasks from VM
        tasks_to_migrate = self.vm.tasks[:]
        self.vm.tasks.clear()

        # migrate each task
        for task in tasks_to_migrate:
            job = self.scheduler.jobs[task.job_id]

            new_vm = self.scheduler.select_vm(task, job, self.time)

            if new_vm.tasks and new_vm.tasks[0] == task:
                execution_time = task.remaining_time / new_vm.speed
                finish_time = self.time + execution_time

                event = TaskCompleteEvent(finish_time, task, new_vm, self.scheduler.event_engine)
                task.current_event = event
                self.scheduler.event_engine.add_event(event)

            if new_vm:
                new_vm.tasks.append(task)
                task.assigned_vm = new_vm

                # 🔥 schedule execution on new VM
                execution_time = task.remaining_time / new_vm.speed
                finish_time = self.time + execution_time

                event = TaskCompleteEvent(finish_time, task, new_vm, self.scheduler.event_engine)
                task.current_event = event