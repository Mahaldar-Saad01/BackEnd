import os
import django
from django.db.models import Count, Q

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from core.models import Project

stats = Project.objects.aggregate(
    completed=Count('id', filter=Q(status='Completed')),
    active=Count('id', filter=Q(status='Active')),
    pending=Count('id', filter=Q(status='Pending')),
)

with open('output.txt', 'w') as f:
    f.write(f"PROJECT STATS: {stats}\n")
