"""Native resource reads and Workspace UI; faults are browser-local test fixtures."""
import argparse
import json
from pathlib import Path
import subprocess
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--browser',choices=['firefox','chromium'],required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
token=subprocess.check_output(['docker','exec','magazine-hermes-install-test','cat','/opt/data/magazine-test-token'],text=True).strip()
with sync_playwright() as p:
    browser=getattr(p,args.browser).launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000},extra_http_headers={'X-Hermes-Session-Token':token})
    page=context.new_page();errors=[];requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append((request.method,request.url)))
    page.goto('http://127.0.0.1:9149/magazine',wait_until='domcontentloaded')
    page.locator('.mag').wait_for(timeout=30000)
    page.wait_for_function("/^CPU [0-9.]+%$/.test(document.querySelector('[data-id=resource-cpu]')?.textContent||'')")
    assert any('/api/system/stats' in url for method,url in requests if method=='GET')
    q=lambda name:page.locator('[data-id="'+name+'"]')
    for panel in ('overview','workflows','setup','ledger','chats','results','manage'):
        q('nav-'+panel).click()
        assert page.locator('.resource-strip').is_visible()
    q('workspace').click();dialog=q('workspace-dialog')
    assert dialog.is_visible()
    assert q('workspace-root').input_value()=='/workspace'
    page.wait_for_function("document.querySelector('[data-id=workspace-policy]').textContent.includes('/opt/data')")
    assert q('workspace-policy').inner_text().startswith('Hermes Files is limited to /opt/data')
    with page.expect_popup() as opened:dialog.get_by_role('link',name='Open Hermes Files').click()
    popup=opened.value;popup.wait_for_load_state('domcontentloaded');assert '/files' in popup.url;popup.close()
    page.bring_to_front();q('workspace-close').click();assert not dialog.is_visible()
    page.set_viewport_size({'width':520,'height':900})
    rect=page.locator('.resource-strip').bounding_box();assert rect and rect['x']>=0 and rect['x']+rect['width']<=520
    page.screenshot(path=str(args.output/'narrow-resource-strip.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1000})
    # Test missing/error/zero states without altering native metrics or backend.
    mode={'value':'zero'}
    def respond(route):
        if mode['value']=='error':route.fulfill(status=503,content_type='application/json',body='{}')
        else:route.fulfill(status=200,content_type='application/json',body=json.dumps({'cpu_percent':0,'memory':{'percent':18,'used':100,'total':1000}} if mode['value']=='zero' else {}))
    page.route('**/api/system/stats',respond)
    page.wait_for_function("document.querySelector('[data-id=resource-cpu]').textContent==='CPU 0%'&&document.querySelector('[data-id=resource-ram]').textContent==='RAM 18%'")
    mode['value']='missing'
    page.wait_for_function("document.querySelector('[data-id=resource-cpu]').textContent==='CPU —'&&document.querySelector('[data-id=resource-ram]').textContent==='RAM —'")
    mode['value']='error'
    page.wait_for_function("document.querySelector('[data-id=resource-cpu]').parentElement.title.includes('unavailable')")
    mode['value']='zero'
    page.wait_for_function("document.querySelector('[data-id=resource-cpu]').textContent==='CPU 0%'&&!document.querySelector('[data-id=resource-cpu]').parentElement.title.includes('unavailable')")
    assert not errors,errors
    assert not any(method=='POST' and any(part in url for part in ('/auth/password-login','/api/files/')) for method,url in requests)
    (args.output/'report.json').write_text(json.dumps({'passed':True,'browser':args.browser,'errors':errors,
        'real_native_stats':True,'all_seven_tabs':True,'native_file_policy_preserved':True,'workspace_and_native_files_link':True,
        'narrow_layout':True,'browser_local_zero_missing_failure_recovery':True,'inference_started':False},indent=2))
    browser.close()
print('PASS',args.browser,'resource strip, Workspace, native file policy, missing/zero/failure recovery and narrow layout')
