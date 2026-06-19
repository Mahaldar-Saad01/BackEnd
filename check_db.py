import os
import sys

output_path = r"c:\Users\onyxs\Desktop\project management system\BackEnd\output.txt"

with open(output_path, "w") as f:
    f.write("Starting database diagnostics script...\n")
    try:
        import django
        f.write(f"Django imported successfully. Version: {django.__version__}\n")
        
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
        django.setup()
        f.write("Django setup successful.\n")

        from core.models import User, Department, Project
        
        f.write("=== DEPARTMENTS ===\n")
        for d in Department.objects.all():
            f.write(f"ID: {d.id} | Name: {d.name} | Lead Manager: {d.lead_manager}\n")
            
        f.write("\n=== USERS ===\n")
        for u in User.objects.all():
            f.write(f"ID: {u.id} | Email: {u.email} | Name: {u.full_name} | Role: {u.role} | Dept: {u.department}\n")
            
        f.write("\n=== PROJECTS ===\n")
        for p in Project.objects.all():
            f.write(f"ID: {p.id} | Name: {p.name} | Manager: {p.lead_manager} | Dept: {p.department} | Status: {p.status}\n")
            
        f.write("\nDiagnostics completed successfully.\n")
    except Exception as e:
        import traceback
        f.write(f"An error occurred:\n{str(e)}\n")
        f.write(traceback.format_exc())
