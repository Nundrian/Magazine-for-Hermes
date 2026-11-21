"""Actual isolated Hermes theme changes; no workflows/inference or user settings."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--browser',choices=['firefox','chromium'],required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
token=subprocess.check_output(['docker','exec','magazine-hermes-install-test','cat','/opt/data/magazine-test-token'],text=True).strip()

with sync_playwright() as p:
    browser=getattr(p,args.browser).launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1100},extra_http_headers={'X-Hermes-Session-Token':token})
    page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:9149/magazine',wait_until='domcontentloaded')
    page.locator('.mag').wait_for(timeout=30000)
    page.wait_for_function("document.querySelector('[data-id=dashboard-state]')?.textContent.includes('Connected')",timeout=30000)
    appearance=page.locator('[data-id=appearance]')
    assert appearance.input_value()=='host','New browsers must follow Hermes by default'
    checks=[]

    def colours():
        return page.evaluate('''() => {
          const style=s=>{const v=getComputedStyle(document.querySelector(s));return {background:v.backgroundColor,border:v.borderTopColor,width:v.borderTopWidth,text:v.color,font:v.fontFamily}};
          const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
          const ctx=canvas.getContext('2d');const rgba=c=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=c;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data]};
          const out={canvas:style('.mag'),panel:style('.mag [data-panel=overview]'),tab:style('.mag [role=tab][aria-selected=false]'),selected:style('.mag [role=tab][aria-selected=true]'),field:style('.mag [data-id=previous-runs]')};
          // Match the actual host palette without hard-coding a theme colour.
          const probe=document.createElement('span');probe.style.background='var(--background-base)';document.body.append(probe);out.host=rgba(getComputedStyle(probe).backgroundColor);probe.remove();
          for(const value of Object.values(out))if(value?.background){value.bg=rgba(value.background);value.outline=rgba(value.border)}
          return out;
        }''')

    def check(label):
        value=colours()
        assert value['canvas']['bg']==value['host'],value
        for key in ('panel','tab','field'):
            assert float(value[key]['width'].removesuffix('px'))>0 and value[key]['outline'][3]>0,(label,key,value)
            assert value[key]['bg'][3]>0 and value[key]['bg']!=value['canvas']['bg'],(label,key,value)
        assert value['selected']['bg']!=value['tab']['bg'],value
        checks.append({'theme':label,'computed_colours':value})
        page.screenshot(path=str(args.output/(label+'.png')),full_page=True)
        return value

    initial=check('initial-hermes')
    for label in ('Ember','Midnight','Hermes Teal'):
        old=colours()['canvas']['background']
        page.get_by_role('button',name='Switch theme',exact=True).click()
        target=page.get_by_role('option').filter(has_text=re.compile(label,re.I))
        assert target.count(),page.locator('body').inner_text()[-5000:]
        already_selected=target.first.get_attribute('aria-selected')=='true'
        target.first.click()
        if not already_selected:
            page.wait_for_function("old=>document.querySelector('.mag')&&getComputedStyle(document.querySelector('.mag')).backgroundColor!==old",arg=old)
        page.wait_for_function("document.querySelector('[data-id=dashboard-state]')?.textContent.includes('Connected')",timeout=30000)
        check(label.lower().replace(' ','-'))
        assert appearance.input_value()=='host'
    # Manual palettes still work and remain scoped to Magazine.
    appearance.select_option('light')
    assert page.locator('.mag').get_attribute('data-appearance')=='light'
    fixed=colours()['canvas']['background']
    page.get_by_role('button',name='Switch theme',exact=True).click()
    page.get_by_role('option').filter(has_text=re.compile('Ember',re.I)).first.click()
    assert colours()['canvas']['background']==fixed
    appearance.select_option('host');check('returned-to-host')
    page.reload(wait_until='domcontentloaded');page.locator('.mag').wait_for(timeout=30000)
    assert appearance.input_value()=='host'
    check('host-after-refresh')
    assert not errors,errors
    report={'passed':True,'browser':args.browser,'errors':errors,'default':'host',
            'actual_native_theme_changes':True,'immediate_colour_updates':True,
            'visible_panel_tab_field_borders':True,'manual_palette_retained':True,
            'host_choice_persisted':True,'inference_started':False,'checks':checks}
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    browser.close()
    print('PASS',args.browser,'native theme colours, visible controls, live switching and persistence')
