import runpy, datetime, traceback
mod = runpy.run_path("production.py")
adapter = mod["adapter"]
now = datetime.datetime.now(datetime.timezone.utc)

for source in ["signoz", "kuma", "matomo"]:
    print(f"\n=== {source} ===")
    try:
        result = adapter(source, now)
        print("SUCCESS:", result)
    except Exception as e:
        print("EXCEPTION:", type(e).__name__, "-", e)
        traceback.print_exc()