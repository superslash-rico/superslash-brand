#!/usr/bin/env python3
"""Apply native Office theme fonts and colors while preserving all other parts."""
from __future__ import annotations
import argparse
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from brand_assets import load_brand

DRAWING="http://schemas.openxmlformats.org/drawingml/2006/main"
ET.register_namespace("a",DRAWING)


def themed_bytes(data:bytes,variant='light')->bytes:
    if variant not in ('light','dark'):raise ValueError('Theme variant must be light or dark')
    brand=load_brand();p=brand['editorial_palette'];official=brand['official_palette']
    home=brand['homepage_style']['palette']
    palette={'dk1':p['ink'],'lt1':'#FFFFFF','dk2':p['graphite'],'lt2':p['paper'],
             'accent1':home['action_purple'],'accent2':official['purple'],'accent3':home['action_blue'],
             'accent4':home['action_plum'],'accent5':home['label_fill'],'accent6':p['rule'],
             'hlink':home['action_blue'],'folHlink':home['action_plum']}
    if variant=='dark':
        dark=brand.get('presentation_themes',{}).get('dark',{})
        palette.update({'dk1':dark.get('foreground','#F6F7FB'),'lt1':dark.get('background',p['graphite']),
                        'dk2':dark.get('body','#CFD3DA'),'lt2':dark.get('surface','#20252D'),
                        'accent3':dark.get('muted','#A6AEBB'),'hlink':official['purple'],'folHlink':'#BE8AFF'})
    result=BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(result,'w') as target:
        for item in source.infolist():
            content=source.read(item.filename)
            if item.filename.startswith(('ppt/','word/')) and '/theme/' in item.filename and item.filename.endswith('.xml'):
                root=ET.fromstring(content)
                scheme=root.find(f'.//{{{DRAWING}}}clrScheme')
                if scheme is not None:
                    scheme.set('name','超级斜杠深色' if variant=='dark' else '超级斜杠')
                    for name,value in palette.items():
                        color=scheme.find(f'{{{DRAWING}}}{name}')
                        if color is not None:
                            for child in list(color):color.remove(child)
                            ET.SubElement(color,f'{{{DRAWING}}}srgbClr',{'val':value.lstrip('#')})
                fonts=root.find(f'.//{{{DRAWING}}}fontScheme')
                if fonts is not None:
                    fonts.set('name','MiSans')
                    for group in fonts:
                        for tag in ['latin','ea','cs']:
                            font=group.find(f'{{{DRAWING}}}{tag}')
                            if font is None:font=ET.SubElement(group,f'{{{DRAWING}}}{tag}')
                            font.set('typeface',brand['fonts']['family'])
                content=ET.tostring(root,encoding='utf-8',xml_declaration=True)
            target.writestr(item,content)
    return result.getvalue()


def apply_theme(source,output,variant='light'):
    source,output=Path(source),Path(output)
    if output.exists():raise FileExistsError(output)
    if source.suffix.lower() not in ('.docx','.pptx') or output.suffix.lower()!=source.suffix.lower():
        raise ValueError('Input and output must use the same DOCX or PPTX extension')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(themed_bytes(source.read_bytes(),variant))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source');parser.add_argument('output')
    parser.add_argument('--variant',choices=['light','dark'],default='light')
    args=parser.parse_args();apply_theme(args.source,args.output,args.variant)
