class Job:
    def __init__(self, job_id, stages):
        self.job_id = job_id
        self.stages = stages

class Stage:
    def __init__(self, stage_id, deadline, tasks):
        self.stage_id = stage_id
        self.deadline = deadline
        self.tasks = tasks