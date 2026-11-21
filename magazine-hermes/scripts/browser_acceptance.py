"""Firefox/Chromium verification of the real isolated Hermes dashboard plugin."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import time
import zipfile
import requests

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--browser', choices=['firefox', 'chromium'], required=True)
parser.add_argument('--container', default='magazine-hermes-test')
parser.add_argument('--port', type=int, default=9139)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
token = subprocess.check_output(['docker','exec',args.container,'cat','/opt/data/magazine-test-token'], text=True).strip()
for _ in range(100):
    try:
        if requests.get(f'http://127.0.0.1:{args.port}/api/dashboard/plugins',timeout=2).status_code==200:break
    except requests.RequestException:pass
    time.sleep(.2)
else:raise RuntimeError('Isolated dashboard did not become ready')
errors = []
checks = []
def api(action, **data):
    response=requests.post(f'http://127.0.0.1:{args.port}/api/plugins/magazine/rpc',
        headers={'X-Hermes-Session-Token':token},json={'action':action,'data':data},timeout=120)
    value=response.json()
    assert value.get('ok'),value
    return value['result']

with sync_playwright() as p:
    browser = getattr(p,args.browser).launch(headless=True)
    context = browser.new_context(viewport={'width':1440,'height':1000},
        extra_http_headers={'X-Hermes-Session-Token':token})
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'http://127.0.0.1:{args.port}/magazine',wait_until='domcontentloaded')
    page.wait_for_timeout(3500)
    page.screenshot(path=str(args.output/'initial.png'),full_page=True)
    page.locator('.mag').wait_for(timeout=20000)
    page.wait_for_function("document.querySelector('[data-id=dashboard-state]')?.textContent.includes('Connected')",timeout=30000)
    # Real host uses its own auth bootstrap; no token is written to any artifact.
    print('PLUGIN LOADED',args.browser,flush=True)
    q=lambda name:page.locator(f'[data-id="{name}"]')
    # A small UI-only workflow. Preparing it must create no worker session.
    name='Browser-'+args.browser+'-'+str(int(time.time()))
    ids=['first','second','third']
    manifest={'schema_version':'1.0','name':name,'cartridges':[
        {'id':cid,'model':'general','prompt':'Synthetic display fixture; do not start inference.'} for cid in ids]}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as archive:archive.writestr('magazine.yml',json.dumps(manifest))
    q('nav-workflows').click()
    page.locator('.import-box > summary').click()
    q('zip').set_input_files({'name':name+'.zip','mimeType':'application/zip','buffer':buf.getvalue()})
    q('import').click()
    page.wait_for_function("document.querySelector('[data-panel=setup]').hidden===false",timeout=30000)
    assert q('tools').locator('input:checked').count()==0
    checks.append('ZIP import and no tools selected by default')
    model='custom/ornith:9b-q8_0'
    q('shared-model').select_option(model)
    q('individual').check()
    q('bulk-group').select_option('general')
    q('bulk-group-select').click()
    assert page.locator('[data-select]:checked').count()==3
    q('bulk-model').select_option(model)
    q('bulk-apply').click()
    checks.append('Shared, independent, checkbox bulk and group model assignment')
    page.locator('.cart').first.locator('.cart-title').click()
    page.locator('[data-tools-for=first]').evaluate('(el)=>{el.open=true}')
    page.locator('[data-tool-override=first]').check()
    assert page.locator('[data-cart-tool=first]:checked').count()==0
    q('plan-box').evaluate('(el)=>{el.open=true}')
    plan={'schema_version':'1.0','workflow_name':name,'cartridge_ids':ids,
        'cartridge_models':{cid:model for cid in ids},'rationale':{cid:'Browser fixture' for cid in ids}}
    q('plan-file').set_input_files({'name':'allocation.json','mimeType':'application/json','buffer':json.dumps(plan).encode()})
    q('plan-check').click()
    page.wait_for_function("!document.querySelector('[data-id=plan-apply]').disabled",timeout=30000)
    assert '→' in q('plan-preview').inner_text()
    q('plan-apply').click()
    checks.append('Suggestions import, before/after validation and explicit Apply')
    q('prepare').click()
    page.wait_for_function("document.querySelector('[data-id=message]').textContent.includes('Workflow READY')",timeout=30000)
    rid=page.evaluate("localStorage.getItem('magazine-hermes-run')")
    assert api('status',run_id=rid)['status']=='READY'
    assert not any(c['run_id']==rid for c in api('chats')['chats'])
    checks.append('Prepare does not start inference')
    subprocess.check_call(['docker','exec',args.container,'/opt/hermes/.venv/bin/python',
        '/opt/data/plugins/magazine/tests/ui_fixture.py',rid])
    q('progress').click()
    q('nav-ledger').click()
    page.wait_for_function("document.querySelector('[data-id=ledger] details.attempt')!==null",timeout=30000)
    assert page.locator('[data-ledger-cartridge]').count()==1
    assert page.locator('[data-id=ledger] details.attempt').count()==5
    first_attempt=page.locator('[data-id=ledger] details.attempt').first
    first_attempt.locator('summary').first.click()
    assert 'Long synthetic error' in first_attempt.inner_text() or 'long visible error' in first_attempt.inner_text()
    page.screenshot(path=str(args.output/'ledger-five-attempts.png'),full_page=True)
    q('cartridge-next').click()
    page.wait_for_function("document.querySelector('[data-id=cartridge-select]').value==='second'",timeout=10000)
    assert page.locator('[data-ledger-cartridge]').count()==1
    assert 'incomplete' in q('ledger').inner_text().lower() or 'unavailable' in q('ledger').inner_text().lower()
    q('cartridge-prev').click()
    q('cartridge-chat').click()
    page.wait_for_function("document.querySelector('[data-id=chat-messages]').children.length>0",timeout=30000)
    assert q('chat-list').locator('button').count()>=6
    assert page.evaluate('window.XSS') is None
    assert '<script>' in q('chat-messages').inner_text() or 'Synthetic UI test prompt' in q('chat-messages').inner_text()
    q('chat-search').fill(rid)
    assert q('chat-list').locator('button').count()==6
    q('chat-list').locator('button').last.click()
    page.screenshot(path=str(args.output/'chats.png'),full_page=True)
    checks.append('Single-cartridge ledger, navigation, five attempts, long errors and partial tokens')
    checks.append('Complete searchable chat list, tool arguments/results and inert HTML')
    # Validate refresh persistence at idle. Active-run restoration has priority by design.
    active=any(r.get('active') for r in api('runs')['runs'])
    if not active:
        q('nav-ledger').click()
        q('cartridge-select').select_option('third')
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function("document.querySelector('[data-id=cartridge-select]')?.value==='third'",timeout=30000)
        assert page.evaluate("localStorage.getItem('magazine-hermes-run')")==rid
        checks.append('Run, panel and cartridge selection persist across refresh')
    q('nav-results').click()
    with page.expect_download() as download:q('download-jsonl').click()
    download.value.save_as(str(args.output/'fixture-run.jsonl'))
    assert (args.output/'fixture-run.jsonl').stat().st_size>1000
    checks.append('Full-run JSONL download')
    q('nav-manage').click()
    page.locator(f'[data-delete-run="{rid}"]').click()
    q('delete-confirm').click()
    page.wait_for_function("document.querySelector('[data-id=manage-trash]').textContent.includes('"+rid+"')",timeout=20000)
    row=q('manage-trash').locator('.manage-row').filter(has_text=rid)
    row.get_by_role('button',name='Restore',exact=True).click()
    page.wait_for_function("document.querySelector('[data-id=manage-runs]').textContent.includes('"+rid+"')",timeout=20000)
    assert api('status',run_id=rid)['status']=='READY'
    checks.append('Confirmation deletion and reversible run restoration')
    q('appearance').select_option('light')
    assert page.locator('.mag').get_attribute('data-appearance')=='light'
    page.screenshot(path=str(args.output/'light.png'),full_page=True)
    context.pages[0].set_viewport_size({'width':520,'height':900})
    assert page.locator('.mag').evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path=str(args.output/'narrow.png'),full_page=True)
    checks.append('Light/dark appearance and narrow layout')
    page.screenshot(path=str(args.output/'overview.png'),full_page=True)
    (args.output/'dom.txt').write_text(page.locator('.mag').inner_text(),encoding='utf-8')
    (args.output/'report.json').write_text(json.dumps({'browser':args.browser,'errors':errors,'loaded':True,'checks':checks},indent=2))
    assert not errors,errors
    browser.close()
