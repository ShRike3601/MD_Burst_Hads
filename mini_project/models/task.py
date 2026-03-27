class Task:
    def __init__(self, task_id, job_id, stage_id, exec_time):
        self.task_id = task_id
        self.id = task_id
        
        self.job_id = job_id
        self.stage_id = stage_id

        self.exec_time = exec_time
        self.remaining_time = exec_time

        self.deadline = None

        # scheduling
        self.assigned_vm = None
        self.last_migration_time = 0

        # execution state (🔥 THIS WAS MISSING)
        self.current_event = None
        self.start_time = None
        self.finish_time = None
        self.completed = False