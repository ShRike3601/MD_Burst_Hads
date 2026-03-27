class Job:

    def __init__(self, id, stages):
        self.id = id
        self.stages = stages   # list of (deadline, [tasks])