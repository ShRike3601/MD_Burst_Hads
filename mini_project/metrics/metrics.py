class Metrics:

    def __init__(self, jobs, vms):
        self.jobs = jobs
        self.vms = vms

    def makespan(self):
        max_time = 0

        for job in self.jobs:
            for stage in job.stages:
                for task in stage.tasks:
                    if task.finish_time and task.finish_time > max_time:
                        max_time = task.finish_time

        return max_time

    def deadline_misses(self):
        misses = 0

        for job in self.jobs:
            for stage in job.stages:
                for task in stage.tasks:
                    if task.finish_time and task.finish_time > task.deadline:
                        misses += 1

        return misses

    def total_cost(self):
        cost = 0

        for job in self.jobs:
            for stage in job.stages:
                for task in stage.tasks:
                    if task.finish_time:
                        vm = task.assigned_vm
                        execution_time = task.finish_time  # simple approximation
                        cost += execution_time * vm.cost_rate

        return cost