import sys, tracemalloc, os, time, tempfile, gc
t0 = time.time()
print("Starting...", flush=True)
tracemalloc.start()
from packages.production.persistence import PersistenceStore
from packages.production.checkpoint import Checkpointer
print("Imports: %.2fs" % (time.time()-t0), flush=True)

db_path = "/tmp/test_checkpoint.db"
if os.path.exists(db_path):
    os.unlink(db_path)
store = PersistenceStore(db_path)
print("Store: %.2fs" % (time.time()-t0), flush=True)
cp = Checkpointer(store)
print("Checkpointer: %.2fs" % (time.time()-t0), flush=True)
print("Starting 100 checkpoints...", flush=True)
snapshots = []
for i in range(100):
    if i < 5 or i % 10 == 0:
        print("  Iteration %d start... " % i, end="", flush=True)
    t1 = time.time()
    result = cp.create_checkpoint()
    if i < 5 or i % 10 == 0:
        print("done in %.2fs" % (time.time()-t1), flush=True)
    if i % 20 == 0:
        current, peak = tracemalloc.get_traced_memory()
        snapshots.append((i, current, peak))
store.close()
tracemalloc.stop()
try:
    os.unlink(db_path)
except:
    pass
print("RESULT: %.0fKB -> %.0fKB (%.1fs)" % (snapshots[0][1]/1024, snapshots[-1][1]/1024, time.time()-t0))
