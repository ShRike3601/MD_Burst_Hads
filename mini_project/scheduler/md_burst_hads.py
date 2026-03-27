class MDBurstHADS:

    def __init__(self, jobs, vms):
        self.jobs = jobs
        self.vms = vms
        self.dynamic = True

    def schedule(self, current_time):

        # simple EDF
        all_tasks.sort(key=lambda t: t.deadline)

        all_tasks = []

        for task in all_tasks:
            task.deadline = deadline
            all_tasks.append(task)

                if task.completed:
                    continue

                best_vm = None
                best_score = float('-inf')

                for vm in self.vms:

                    # compute queue time
                    queue_time = sum(t.remaining_time for t in vm.tasks) / vm.speed

                    exec_time = task.remaining_time / vm.speed
                    finish_time = current_time + queue_time + exec_time

                    slack = job.deadline - finish_time

                    if slack < 0:
                        continue

                    # load-aware scoring
                    score = slack - (2 * queue_time)

                    if score > best_score:
                        best_score = score
                        best_vm = vm

                # fallback
                if best_vm is None:
                    best_vm = self.vms[0]

                # 🔥 NOW handle reassignment safely
                current_vm = task.assigned_vm

                current_vm = task.assigned_vm

                if current_vm:

                    current_queue = sum(t.remaining_time for t in current_vm.tasks) / current_vm.speed
                    best_queue = sum(t.remaining_time for t in best_vm.tasks) / best_vm.speed

                    improvement = current_queue - best_queue

                    # 🚨 threshold condition
                    if improvement < 1:   # tune this later
                        continue

                if task.assigned_vm and task.assigned_vm != best_vm:
                    if current_time - task.last_migration_time < 3:
                        continue

                if current_vm and task in current_vm.tasks and not task.completed:
                    current_vm.tasks.remove(task)

                if task not in best_vm.tasks:
                    best_vm.tasks.append(task)

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