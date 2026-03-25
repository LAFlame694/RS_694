from django.db import models

class TenancyStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ENDED = "ENDED", "Ended"
    TERMINATED = "TERMINATED", "Terminated"