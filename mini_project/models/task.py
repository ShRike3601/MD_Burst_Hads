class Task:
    def __init__(self, id, runtime, job_id):
        self.id = id
        self.runtime = runtime
        self.remaining_time = runtime
        self.job_id = job_id
        self.start_time = None
        self.finish_time = None
        self.assigned_vm = None
        self.completed = False
        self.current_event = None
        self.last_migration_time = -1
        self.deadline = None