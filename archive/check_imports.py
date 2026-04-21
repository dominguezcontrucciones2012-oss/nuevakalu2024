print("Checking blueprints for import errors...")
try:
    from app import app
    print("OK: App and all blueprints imported successfully.")
except Exception as e:
    import traceback
    print("ERROR: Import error detected:")
    print(traceback.format_exc())
