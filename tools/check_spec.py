import os

path = os.path.abspath("ArenaDuel.spec")
print("PATH:", path)
try:
    print("os.path.exists ->", os.path.exists(path))
    with open(path, "rb") as f:
        data = f.read(64)
        print("open -> OK, len=", len(data))
except Exception as e:
    print("open -> ERROR:", repr(e))

print("\n-- Directory listing (cwd) --")
print("CWD:", os.getcwd())
entries = os.listdir(".")
print("Entries count:", len(entries))
matches = [
    e
    for e in entries
    if "Arena" in e or e.lower().endswith(".spec") or "arena" in e.lower()
]
print("Matches:", matches)
for e in matches:
    try:
        s = os.stat(e)
        print("STAT", e, "size=", s.st_size)
    except Exception as se:
        print("STAT ERROR", e, se)
