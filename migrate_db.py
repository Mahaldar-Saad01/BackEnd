import os
import sys
import django
from django.core.management import call_command

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

output_path = r"C:\Users\onyxs\.gemini\antigravity-ide\brain\e188edc6-7d40-4858-b8db-e058038aa593\migrations_result.txt"

with open(output_path, "w") as f:
    f.write("Starting migrations script...\n")
    
    # Run makemigrations
    f.write("Running makemigrations core...\n")
    try:
        call_command('makemigrations', 'core')
        f.write("makemigrations successful.\n")
    except Exception as e:
        f.write(f"Error during makemigrations: {str(e)}\n")
        
    # Run migrate
    f.write("Running migrate...\n")
    try:
        call_command('migrate')
        f.write("migrate successful.\n")
    except Exception as e:
        f.write(f"Error during migrate: {str(e)}\n")

    f.write("Migrations script finished.\n")
print("Done writing migrations_result.txt")
