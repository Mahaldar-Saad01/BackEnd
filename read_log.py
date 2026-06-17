with open('runserver.log', 'rb') as f:
    content = f.read().decode('utf-16', errors='ignore')
print("--- RUNSERVER LOG TAIL ---")
print(content[-2000:])
print("--------------------------")
