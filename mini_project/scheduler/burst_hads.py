class BurstHADS:

    def __init__(self, jobs, vms):
        self.jobs = jobs
        self.vms = vms
        self.dynamic = False

    def schedule(self, current_time):

        for job in self.jobs:
            for stage in job.stages:
                for task in stage.tasks:

                    # 🔥 skip if already assigned
                    if task.assigned_vm is not None:
                        continue

                    # simple round-robin assignment
                    vm = self.vms[task.id % len(self.vms)]

                    vm.tasks.append(task)
                    task.assigned_vm = vm

    def select_vm(self, task, job, current_time):
        return self.vms[0]