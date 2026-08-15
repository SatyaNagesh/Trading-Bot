import sys, time, os
t0 = time.time()
print("Starting", flush=True)

import tracemalloc
tracemalloc.start()

from packages.production.persistence import PersistenceStore
from packages.production.checkpoint import Checkpointer
print("Imported: %.2fs" % (time.time()-t0), flush=True)

# Remove stale files
for p in ["./_rs_checkpoint.db", "./_rs_checkpoint.db-wal", "./_rs_checkpoint.db-shm"]:
    if os.path.exists(p):
        os.unlink(p)

store = PersistenceStore("./_rs_checkpoint.db")
print("Store init: %.2fs" % (time.time()-t0), flush=True)

cp = Checkpointer(store)
print("Checkpointer init: %.2fs" % (time.time()-t0), flush=True)

t1 = time.time()
cp.create_checkpoint()
print("First checkpoint: %.2fs" % (time.time()-t1), flush=True)

print("Total: %.2fs" % (time.time()-t0), flush=True)
tracemalloc.stop()
