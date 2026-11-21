"""Read-only live/historical switching in both actual browsers during STOP test."""
import json
from pathlib import Path
import subprocess
import sys
import time
import requests
from playwright.sync_api import sync_playwright

workspace=Path(sys.argv[1]);output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
token=subprocess.check_output(['docker','exec','magazine-hermes-test','cat','/opt/data/magazine-test-token'],text=True).strip()
base='http://127.0.0.1:9139'
headers={'X-Hermes-Session-Token':token}
def api(action,**data):
    value=requests.post(base+'/api/plugins/magazine/rpc',headers=headers,json={'action':action,'data':data},timeout=30).json()
    assert value.get('ok'),value
    return value['result']
for _ in range(180):
    if (workspace/'live-stop-run-id').exists():break
    time.sleep(.5)
else:raise TimeoutError('STOP fixture did not become live')
rid=(workspace/'live-stop-run-id').read_text().strip()
results=[]
with sync_playwright() as p:
    for name in ('firefox','chromium'):
        browser=getattr(p,name).launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},extra_http_headers=headers)
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/magazine',wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('[data-id=current-chat]')&&!document.querySelector('[data-id=run-header]').hidden",timeout=20000)
        page.locator('[data-id=current-chat]').click()
        page.wait_for_function("document.querySelector('[data-id=chat-state]')?.textContent.includes('Live')",timeout=20000)
        rows=api('chats')['chats']
        live=next(c for c in rows if c['run_id']==rid and c['live'])
        old=next(c for c in rows if c['run_id']!=rid and not c['live'])
        page.locator('[data-chat="'+old['chat_id']+'"]').click()
        page.wait_for_function("!document.querySelector('[data-id=chat-state]').textContent.includes('Live')",timeout=10000)
        assert api('status',run_id=rid)['active']
        page.locator('[data-chat="'+live['chat_id']+'"]').click()
        page.wait_for_function("document.querySelector('[data-id=chat-state]')?.textContent.includes('Live')",timeout=10000)
        assert page.locator('[data-id=chat-messages] [data-message]').count()>0
        assert api('status',run_id=rid)['active']
        page.screenshot(path=str(output/(name+'-live.png')),full_page=True)
        assert not errors,errors
        results.append({'browser':name,'run_id':rid,'live_history_live_switch':True,'execution_remained_active':True,'errors':errors})
        browser.close()
(output/'report.json').write_text(json.dumps(results,indent=2))
print('PASS live/history/live switching in Firefox and Chromium')
