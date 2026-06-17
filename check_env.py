import sys
import os

output_path = r"c:\Users\onyxs\Desktop\project management system\BackEnd\env_diag.txt"
with open(output_path, "w") as f:
    f.write(f"Python Executable: {sys.executable}\n")
    f.write(f"Python Version: {sys.version}\n")
    f.write(f"Current Working Directory: {os.getcwd()}\n")
    try:
        import django
        f.write(f"Django Version: {django.__version__}\n")
    except Exception as e:
        f.write(f"Failed to import Django: {e}\n")
print("Diagnostics written to env_diag.txt")
