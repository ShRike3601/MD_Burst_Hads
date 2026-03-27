class MDBurstHADS:
    def __init__(self, vms, all_tasks, jobs=None):
        self.vms = vms
        self.all_tasks = all_tasks
        self.jobs = jobs

    def schedule(self, current_time):
        # prevent excessive rescheduling
        if hasattr(self, "last_schedule_time"):
            if current_time - self.last_schedule_time < 1:
                return

        self.last_schedule_time = current_time

        # print("Scheduling at time:", current_time)

        all_tasks = self.all_tasks

        # sort by task deadline (EDF)
        all_tasks.sort(key=lambda t: t.deadline)

        for task in all_tasks:
            if task.completed:
                continue

            # print("Checking task:", task.task_id, "deadline:", task.deadline)

            # prevent duplicate assignment
            if task.assigned_vm and not task.completed:
                continue

            if task.deadline <= 10:
                priority_boost = 2
            else:
                priority_boost = 1

            best_vm = None
            best_finish_time = float('inf')

            for vm in self.vms:

                queue_time = sum(t.remaining_time for t in vm.tasks) / vm.speed

                # prevent overloading fast VM
                if len(vm.tasks) >= 5:
                    continue

                exec_time = task.remaining_time / vm.speed
                finish_time = current_time + queue_time + exec_time

                # respect deadline
                if finish_time > task.deadline:
                    continue

                adjusted_finish = finish_time / priority_boost
                cost_penalty = vm.cost_rate * exec_time
                score = adjusted_finish + cost_penalty

                if score < best_finish_time:
                    best_finish_time = score
                    best_vm = vm

            if best_vm is None:
                # pick least loaded available VM
                available_vms = [vm for vm in self.vms]

                if available_vms:
                    best_vm = min(available_vms, key=lambda vm: len(vm.tasks))
                else:
                    continue

            current_vm = task.assigned_vm

            # migration logic
            if current_vm:

                current_queue = sum(t.remaining_time for t in current_vm.tasks) / current_vm.speed
                best_queue = sum(t.remaining_time for t in best_vm.tasks) / best_vm.speed

                improvement = current_queue - best_queue

                if improvement < 5:
                    continue

                if current_vm != best_vm:
                    if current_time - task.last_migration_time < 3:
                        continue

            # remove from old VM
            if current_vm and task in current_vm.tasks and not task.completed:
                current_vm.tasks.remove(task)

            # add to new VM
            if task not in best_vm.tasks:
                task.priority = 1 / task.deadline
                best_vm.tasks.append(task)
                best_vm.tasks.sort(key=lambda t: t.priority, reverse=True)

            # update migration time
            if current_vm != best_vm:
                task.last_migration_time = current_time

            task.assigned_vm = best_vm
    
    def slack(self, task, vm, deadline, current_time):
        
        queue_time = 0

        for t in vm.tasks:
            queue_time += t.remaining_time

        queue_time = queue_time / vm.speed

        execution_time = task.remaining_time / vm.speed

        finish_time = current_time + queue_time + execution_time

        return deadline - finish_time
    
    def select_vm(self, task, job, current_time):

        best_vm = None
        min_load = float('inf')

        for vm in self.vms:

            queue_time = sum(t.remaining_time for t in vm.tasks) / vm.speed

            exec_time = task.remaining_time / vm.speed
            finish_time = current_time + queue_time + exec_time

            slack = task.deadline - finish_time

            # 🚨 enforce feasibility
            if slack < 0:
                continue

            if queue_time < min_load:
                min_load = queue_time
                best_vm = vm

            if best_vm is None:
                best_vm = self.vms[0]

        return best_vm
