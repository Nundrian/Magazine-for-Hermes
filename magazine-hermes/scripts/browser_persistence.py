"""Read-only persistence acceptance using an existing three-cartridge UI fixture."""
import json
from pathlib import Path
import subprocess
import sys
import requests
from playwright.sync_api import sync_playwright

output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
token=subprocess.check_output(['docker','exec','magazine-hermes-test','cat','/opt/data/magazine-test-token'],text=True).strip()
headers={'X-Hermes-Session-Token':token}
base='http://127.0.0.1:9139'
def api(action,**data):
    value=requests.post(base+'/api/plugins/magazine/rpc',headers=headers,json={'action':action,'data':data},timeout=30).json()
    assert value.get('ok'),value
    return value['result']
runs=api('runs')['runs'];assert not any(r.get('active') for r in runs)
rid=next(r['run_id'] for r in runs if (r.get('name') or '').startswith('Browser-') and r['total']==3)
reports=[]
with sync_playwright() as p:
    for name in ('firefox','chromium'):
        browser=getattr(p,name).launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},extra_http_headers=headers)
        page=context.new_page();page.goto(base+'/magazine',wait_until='domcontentloaded')
        q=lambda value:page.locator('[data-id="'+value+'"]')
        page.wait_for_function("document.querySelector('[data-id=previous-runs]')?.options.length>2",timeout=30000)
        q('nav-overview').click();q('previous-runs').select_option(rid);q('view-previous').click()
        q('nav-ledger').click();q('cartridge-select').select_option('first')
        page.wait_for_function("document.querySelectorAll('[data-id=ledger] details.attempt').length===5",timeout=30000)
        first=page.locator('[data-id=ledger] details.attempt').first
        first.evaluate('(el)=>{el.open=true}')
        page.wait_for_function("JSON.parse(localStorage.getItem('magazine-hermes-expanded')||'[]').length>0",timeout=10000)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('[data-id=cartridge-select]')?.value==='first'&&document.querySelector('[data-id=ledger] details.attempt')?.open",timeout=30000)
        assert page.evaluate("localStorage.getItem('magazine-hermes-run')")==rid
        q('cartridge-select').select_option('third')
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('[data-id=cartridge-select]')?.value==='third'",timeout=30000)
        assert q('nav-ledger').get_attribute('aria-selected')=='true'
        assert api('status',run_id=rid)['status']=='READY'
        assert not api('status',run_id=rid)['active']
        page.screenshot(path=str(output/(name+'-restored.png')),full_page=True)
        reports.append({'browser':name,'run_id':rid,'run_panel_cartridge_and_attempt_expansion_restored':True,'inference_started':False})
        browser.close()
(output/'report.json').write_text(json.dumps(reports,indent=2))
print('PASS refresh persistence in Firefox and Chromium; no inference')
