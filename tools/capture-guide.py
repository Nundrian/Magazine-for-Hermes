"""Read-only UI captures from an existing bounded test run. Never starts inference."""
import argparse
import json
from pathlib import Path
import subprocess
import requests
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--run-id',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
token=subprocess.check_output(['docker','exec','magazine-hermes-test','cat','/opt/data/magazine-test-token'],text=True).strip()
base='http://127.0.0.1:9139'
headers={'X-Hermes-Session-Token':token}
def rpc(action,**data):
    value=requests.post(base+'/api/plugins/magazine/rpc',headers=headers,json={'action':action,'data':data},timeout=120).json()
    assert value.get('ok'),value
    return value['result']
run=rpc('status',run_id=args.run_id)
assert run['status']=='COMPLETED' and not run['active']
project=run['project_id']
ledger=rpc('ledger',run_id=args.run_id)['ledger']
attempt_count=sum(len(c['attempts']) for c in ledger['cartridges'].values())
screens=[]

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1920,'height':1280},extra_http_headers=headers)
    context.add_init_script("localStorage.setItem('magazine-hermes-appearance','host');localStorage.setItem('hermes-dashboard-theme','default');")
    rpc('view_state',set={'run_id':None,'project_id':project})
    page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(base+'/magazine',wait_until='domcontentloaded')
    page.locator('.mag').wait_for(timeout=30000)
    page.wait_for_function("document.querySelector('[data-id=dashboard-state]')?.textContent.includes('Connected')",timeout=30000)
    q=lambda name:page.locator('[data-id="'+name+'"]')
    page.wait_for_function("!document.querySelector('[data-id=message]').textContent.startsWith('Reconnecting')")

    def capture(name,targets):
        page.wait_for_function("document.querySelector('[data-panel="+name+"]').hidden===false")
        items=[]
        for selector,label in targets:
            box=page.locator(selector).first.bounding_box()
            assert box is not None,(name,selector)
            assert box['y']+min(box['height'],40)<1280,(name,selector,box)
            items.append({'selector':selector,'label':label,'box':box})
        page.screenshot(path=str(args.output/(name+'.png')),full_page=False)
        screens.append({'tab':name,'width':1920,'height':1280,'targets':items})
        (args.output/'capture-manifest.json').write_text(json.dumps({'inference_started':False,'existing_real_test_run':args.run_id,'screens':screens},indent=2))

    q('nav-workflows').click()
    page.locator('.import-box > summary').click()
    q('project-filter').fill('')
    q('projects').select_option(project)
    page.wait_for_function("!document.querySelector('[data-id=load-workflow]').disabled")
    capture('workflows',[
        ('[data-id=zip]','1 Import a workflow ZIP'),
        ('[data-id=projects]','2 Choose a saved workflow'),
        ('[data-id=load-workflow]','3 Review its steps')])
    q('projects').select_option(project);q('load-workflow').click()
    page.wait_for_function("document.querySelector('[data-id=shared-model]').options.length>1")
    q('shared-model').select_option(run['cartridge_models']['first'])
    page.locator('[data-id=workflow-steps] > summary').click()
    page.locator('[data-id=tools] input[value=file]').check()
    page.locator('.tool-settings > summary').filter(has_text='Tools and protection').click()
    capture('setup',[
        ('[data-id=shared-model]','1 Choose the exact model'),
        ('.tool-settings > summary','2 Review tools and safeguards'),
        ('[data-id=prepare]','3 Prepare without starting')])

    q('nav-overview').click()
    q('previous-runs').select_option(args.run_id);q('view-previous').click()
    page.wait_for_function("document.querySelector('[data-id=run-summary]').textContent.includes('COMPLETED')")
    q('run-filter').fill(args.run_id)
    capture('overview',[
        ('[data-id=previous-runs]','1 Open saved work'),
        ('[data-id=scheduler-mode]','2 Choose queue order'),
        ('[data-id=dashboard]','3 Follow project progress'),
        ('.resource-strip','4 CPU, RAM and Workspace')])
    q('nav-ledger').click()
    page.wait_for_function("document.querySelector('[data-id=cartridge-select]').options.length===2")
    q('cartridge-select').select_option('second')
    page.wait_for_function("document.querySelectorAll('[data-id=ledger] details.attempt').length===3")
    capture('ledger',[
        ('[data-id=cartridge-select]','1 Choose one cartridge'),
        ('[data-id=ledger] .compact-ledger','2 Read status and attempts'),
        ('[data-id=ledger] details.attempt','3 Expand the evidence')])
    q('cartridge-chat').click()
    page.wait_for_function("document.querySelector('[data-id=chat-list]').children.length>0")
    q('chat-run-filter').select_option(args.run_id)
    q('chat-list').locator('button').last.click()
    page.wait_for_function("document.querySelector('[data-id=chat-messages]').children.length>0")
    capture('chats',[
        ('[data-id=chat-run-filter]','1 Filter saved conversations'),
        ('[data-id=chat-list]','2 Choose a real attempt'),
        ('[data-id=chat-messages]','3 Read messages and tool results')])
    q('nav-results').click()
    page.wait_for_function("document.querySelector('[data-id=results]').textContent.length>20")
    capture('results',[
        ('[data-id=download]','1 Download checked artifacts'),
        ('[data-id=download-jsonl]','2 Export the full run record'),
        ('[data-id=results]','3 Inspect saved results')])
    q('nav-manage').click()
    page.wait_for_function("document.querySelector('[data-id=manage-templates]').children.length>0")
    capture('manage',[
        ('[data-panel=manage] h2','1 Manage stored Magazine work'),
        ('[data-id=manage-templates] .manage-row','2 Templates and runs are separate'),
        ('[data-id=manage-templates] button','3 Review before deleting')])
    assert not errors,errors
    assert sum(len(c['attempts']) for c in rpc('ledger',run_id=args.run_id)['ledger']['cartridges'].values())==attempt_count
    assert not rpc('status',run_id=args.run_id)['active']
    (args.output/'capture-manifest.json').write_text(json.dumps({'inference_started':False,'existing_real_test_run':args.run_id,'screens':screens},indent=2))
    browser.close()
print('Captured seven actual interface tabs from a completed bounded test run; no inference or deletions')
