"""Capture deterministic/native-storage/process checks without model inference."""
import json
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
reports=[]
for name in ('test_safety.py','native_lineage.py','timeout_diagnostic.py'):
    result=subprocess.run([sys.executable,str(root/name)],capture_output=True,text=True)
    reports.append({'test':name,'returncode':result.returncode,'output':result.stdout+result.stderr})
    Path('/workspace/deterministic-report.json').write_text(json.dumps(reports,indent=2))
    if result.returncode:raise RuntimeError(name+' failed: '+result.stdout+result.stderr)
    print('PASS',name,flush=True)
