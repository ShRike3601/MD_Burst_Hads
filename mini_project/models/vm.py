class VM:
    def __init__(self, id, vm_type, speed, cost_rate):
        self.id = id
        self.type = vm_type  # spot / burstable / ondemand
        self.speed = speed
        self.cost_rate = cost_rate
        self.tasks = []
        self.state = "idle"  # idle / busy / hibernated
        self.cpu_credits = 100 if vm_type == "burstable" else None