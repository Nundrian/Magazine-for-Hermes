"""Read-only normal-host baseline and post-install dashboard smoke; no inference."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import requests

parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['before','after'])
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
container='hermes'
base='http://127.0.0.1:9119'

def native(code):
    return subprocess.check_output(['docker','exec',container,'/opt/hermes/.venv/bin/python','-c',code],text=True).strip()

def snapshot():
    inspection=json.loads(subprocess.check_output(['docker','inspect','--format',
        '{{json .Id}}|{{json .Image}}|{{json .Mounts}}|{{json .HostConfig.RestartPolicy}}|{{json .NetworkSettings.Ports}}',container],text=True).split('|')[0])
    parts=subprocess.check_output(['docker','inspect','--format',
        '{{json .Id}}|{{json .Image}}|{{json .Mounts}}|{{json .HostConfig.RestartPolicy}}|{{json .NetworkSettings.Ports}}',container],text=True).strip().split('|')
    host=json.loads(native("import sys,json,hashlib,psutil,sqlite3;sys.path.insert(0,'/opt/hermes');from hermes_cli.config import load_config;from hermes_constants import get_hermes_home;c=load_config();c.pop('plugins',None);h=get_hermes_home();db=sqlite3.connect('file:'+str(h/'state.db')+'?mode=ro',uri=True);print(json.dumps({'non_plugin_config_sha256':hashlib.sha256(json.dumps(c,sort_keys=True,default=str).encode()).hexdigest(),'native_sessions':db.execute('SELECT count(*) FROM sessions').fetchone()[0],'gateway_pids':[p.pid for p in psutil.process_iter() if 'gateway' in p.cmdline() and 's6-supervise' not in p.name()],'dashboard_pids':[p.pid for p in psutil.process_iter() if 'dashboard' in p.cmdline() and p.name()=='hermes']}));db.close()"))
    return {'container_id':inspection,'image':json.loads(parts[1]),'mounts':json.loads(parts[2]),
            'restart_policy':json.loads(parts[3]),'ports':json.loads(parts[4]),**host}

if args.phase=='before':
    value=snapshot()
    (args.output/'before.json').write_text(json.dumps(value,indent=2))
    print('Saved normal Hermes baseline; no configuration changes or inference')
else:
    from playwright.sync_api import sync_playwright
    # Existing deployment credential is used in memory and never logged/saved.
    token=native("import sys,os,pathlib;sys.path.insert(0,'/opt/hermes');from hermes_cli.env_loader import load_hermes_dotenv;load_hermes_dotenv();value=os.environ.get('HERMES_DASHBOARD_SESSION_TOKEN','');print(pathlib.Path(value[5:]).read_text().strip() if value.startswith('file:') else value)")
    if not token:
        match=re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*"([^"\n]+)"',requests.get(base+'/',timeout=15).text)
        if match:token=match[1]
    session=requests.Session()
    headers={'X-Hermes-Session-Token':token} if token else {}
    if not token:
        credentials=json.loads(native("import os,json;print(json.dumps({'username':os.environ.get('HERMES_DASHBOARD_BASIC_AUTH_USERNAME',''),'password':os.environ.get('HERMES_DASHBOARD_BASIC_AUTH_PASSWORD','')}))"))
        if not credentials['username'] or not credentials['password']:
            raise RuntimeError('Existing dashboard authentication must be supplied by its normal operator login')
        login=session.get(base+'/login',timeout=15)
        provider=re.search(r'data-provider="([^"\n]+)"',login.text)
        if not provider:raise RuntimeError('Existing password provider is unavailable')
        response=session.post(base+'/auth/password-login',json={**credentials,'provider':provider[1],'next':'/magazine'},timeout=30)
        if response.status_code!=200:raise RuntimeError('Normal dashboard password login failed: '+str(response.status_code))
        del credentials
    session.get(base+'/api/dashboard/plugins/rescan',headers=headers,timeout=30).raise_for_status()
    plugins=session.get(base+'/api/dashboard/plugins',headers=headers,timeout=30).json()
    assert any(p['name']=='magazine' for p in plugins),plugins
    def api(action):
        value=session.post(base+'/api/plugins/magazine/rpc',headers=headers,
                            json={'action':action,'data':{}},timeout=120).json()
        assert value.get('ok'),value
        return value['result']
    catalogue=api('catalogue')
    runs=api('runs')
    assert not any(r.get('active') for r in runs['runs'])
    browser_results=[]
    with sync_playwright() as p:
        for name in ('firefox','chromium'):
            browser=getattr(p,name).launch(headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000},extra_http_headers=headers)
            if session.cookies:
                context.add_cookies([{'name':c.name,'value':c.value,'domain':c.domain,'path':c.path,'secure':c.secure}
                                    for c in session.cookies])
            page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'/magazine',wait_until='domcontentloaded')
            try:page.locator('.mag').wait_for(timeout=30000)
            except Exception:
                page.screenshot(path=str(args.output/(name+'-load-failure.png')),full_page=True)
                (args.output/(name+'-load-failure.txt')).write_text(page.locator('body').inner_text()[:12000],encoding='utf-8')
                print(json.dumps({'browser':name,'errors':errors,'diagnostic':'Native dashboard load failure; see local screenshot/text'}))
                raise
            page.wait_for_timeout(2500)
            assert page.locator('.mag').get_by_role('tab',name='Workflows',exact=True).count()==1
            page.wait_for_function("document.querySelector('[data-id=dashboard-state]')?.textContent.includes('Connected')",timeout=30000)
            assert not errors,errors
            page.screenshot(path=str(args.output/(name+'-installed.png')),full_page=True)
            browser_results.append({'browser':name,'loaded':True,'errors':errors})
            browser.close()
    before=json.loads((args.output/'before.json').read_text())
    after=snapshot()
    for key in ('container_id','image','mounts','restart_policy','ports','non_plugin_config_sha256','gateway_pids'):
        assert before[key]==after[key],key+' changed'
    assert after['native_sessions']>=before['native_sessions']
    report={'passed':True,'before':before,'after':after,'browsers':browser_results,
            'model_count':len(catalogue['models']),'toolset_count':len(catalogue['tools']),
            'active_runs':0,'inference_started':False,'native_data_retained':True}
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    if not token:session.post(base+'/auth/logout',timeout=15)
    session.close()
    print('PASS installed native tab in Firefox/Chromium, catalogue, idle state and preserved normal Hermes configuration/data/container/gateway')
