from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    USER_TYPES = [('hospital', 'Hospital'), ('admin', 'Admin')]
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='hospital')
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'
