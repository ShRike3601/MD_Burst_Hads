from models.task import Task
from models.job import Job
from models.vm import VM
import random

from simulation.event_engine import EventEngine
from simulation.execution_engine import start_execution

from metrics.metrics import Metrics

def run_simulation(scheduler_class, n_tasks, deadline_factor=1.0):

    from models.utils import flatten_and_assign_deadlines
    from models.stage import Stage

    tasks = []
    for i in range(n_tasks):
        runtime = random.randint(2, 15)
        tasks.append(Task(i, job_id=0, stage_id=0, exec_time=runtime))

    base_deadline = 30
    deadline = base_deadline * deadline_factor

    stage = Stage(stage_id=0, deadline=deadline, tasks=tasks)
    job = Job(0, [stage])
    jobs = [job]

    # flatten tasks
    all_tasks = flatten_and_assign_deadlines(jobs)

    # AWS-like VM setup
    vm1 = VM(0, "c5.large", speed=2, cost_rate=0.085)     # 2 vCPU
    vm2 = VM(1, "c4.large", speed=2, cost_rate=0.10)      # older gen
    vm3 = VM(2, "c5.xlarge", speed=4, cost_rate=0.17)     # 4 vCPU (fast)
    vm4 = VM(3, "t3.large", speed=2, cost_rate=0.083)     # burstable
    vms = [vm1, vm2, vm3, vm4]

    # scheduler now takes tasks, not jobs
    if scheduler_class.__name__ == "MDBurstHADS":
        scheduler = scheduler_class(vms, all_tasks, jobs)
    else:
        scheduler = scheduler_class(jobs, vms)
    scheduler.schedule(0)

    # ensure VM queues exist
    for vm in vms:
        vm.tasks = list(vm.tasks)

    # for vm in vms:
    #     print(f"VM {vm.id} tasks:", [t.task_id for t in vm.tasks])

    # engine
    engine = EventEngine(scheduler)
    scheduler.event_engine = engine

    # execution
    start_execution(vms, 0, engine)

    from simulation.events import HibernationEvent
    event = HibernationEvent(3, vm1, scheduler)
    engine.add_event(event)

    # run
    engine.run()

    # metrics still use jobs
    metrics = Metrics(jobs, vms)

    return metrics

if __name__ == "__main__":
    pass
