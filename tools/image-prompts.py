"""Build the annotation prompt set from actual captured target positions."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
value=json.loads((root/'docs/images/raw/capture-manifest.json').read_text())
layouts={
    'overview':'Use the empty vertical gutter between the sidebar and main content (original x240–500) for cards 1, 2 and 3, near y650, y800 and y1010. Put card 4 in the empty right gutter near x1660 y1120. Keep the project table unobscured.',
    'setup':'Use the empty left gutter x250–495 for cards 1 and 2 near y430 and y670. Place card 3 in the empty canvas below the panel, around x700 y1020. Preserve all settings and the Prepare button.',
    'ledger':'Use the empty left gutter x250–495 for three vertically spaced cards near y600, y780 and y980. Arrow 3 must point to the first collapsed Attempt row, not an unrelated control.',
    'chats':'Use the empty left gutter x250–495 for three vertically spaced cards near y600, y850 and y1060. Keep conversation text, the attempt history list and tool results readable.',
    'results':'Use the large empty lower canvas below y820: card 1 around x530 y930, card 2 around x940 y1100, card 3 around x1330 y930. Curve arrows upwards to their actual targets.',
    'manage':'Use the empty left gutter x250–495 for three vertically spaced cards near y550, y740 and y940. Arrow 3 points to View / Load, explaining review before deletion. Keep all delete buttons visible.',
    'workflows':'Use the large empty lower canvas: card 1 around x530 y840, card 2 around x930 y1030, card 3 around x1330 y840.'}
prompts=[]
for screen in value['screens']:
    tab=screen['tab'];targets=[]
    for target in screen['targets']:
        box=target['box'];x=round(box['x']+box['width']/2);y=round(min(1250,box['y']+box['height']/2))
        targets.append(f"Exact label '{target['label']}', with its curved arrow ending at original screenshot coordinate ({x},{y}).")
    prompt=(f"Use case: precise-object-edit / compositing. Make a professional annotated screenshot for the {tab.upper()} tab of Magazine for Hermes. "
        "Image 1 is the actual screenshot EDIT TARGET, originally 1920x1280. Image 2 is only a STYLE REFERENCE for the callout cards and curved arrows, not a source of UI content. "
        "Preserve the entire interface of image 1 faithfully: all native UI text, numbers, controls, sidebar, positions, palette, selected tab and CPU/RAM/Workspace footer must remain. This is screenshot annotation, not a UI mockup. Do not invent controls, change values, remove content, crop or redesign the screenshot. "
        "Add only a clean annotation layer: dark-teal rounded callout cards, legible warm-white sans-serif text, numbered peach-outline circular badges, and crisp mint/cyan 4px curved arrows with open arrowheads and restrained shadows, matching image 2. "
        +layouts[tab]+" "+" ".join(targets)+
        " Keep labels exact and complete, wrapping them into two or three lines if needed. Do not obscure UI text or buttons. Keep the original 3:2 aspect ratio and all content. Each arrow must have a clear arrowhead aimed at the specified real control. Only the supplied labels are added; do not add invented headings or extra badges.")
    prompts.append({'tab':tab,'input':'raw/'+tab+'.png','output':tab+'-annotated.png','prompt':prompt})
(root/'docs/images/annotation-prompts.json').write_text(json.dumps({'tool':'built-in imagegen','raw_capture':'raw/capture-manifest.json','prompts':prompts},indent=2)+'\n',encoding='utf-8')
print('Prepared seven per-tab annotation prompts')
