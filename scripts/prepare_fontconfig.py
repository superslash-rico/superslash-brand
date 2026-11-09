#!/usr/bin/env python3
"""Write a task-local font configuration; never install fonts or edit runtime files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,tostring
from brand_assets import asset_path


def prepare_fontconfig(output_dir, extra_dirs=()):
    output=Path(output_dir).resolve();output.mkdir(parents=True,exist_ok=True)
    config=Element('fontconfig')
    font_dir=asset_path('fonts/MiSans-Regular.ttf').parent
    directories=[font_dir,*map(Path,extra_dirs)]
    for directory in directories:
        directory=directory.resolve()
        if not directory.is_dir():raise FileNotFoundError(directory)
        SubElement(config,'dir').text=str(directory)
    cache=output/'font-cache';cache.mkdir(exist_ok=True)
    SubElement(config,'cachedir').text=str(cache)
    alias=SubElement(config,'alias');SubElement(alias,'family').text='sans-serif'
    prefer=SubElement(alias,'prefer');SubElement(prefer,'family').text='MiSans'
    path=output/'fonts.conf'
    path.write_bytes(b'<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'+tostring(config,encoding='utf-8'))
    return {'FONTCONFIG_FILE':str(path),'FONTCONFIG_PATH':str(output),'font_directory':str(font_dir)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir');parser.add_argument('--extra-dir',action='append',default=[])
    args=parser.parse_args();print(json.dumps(prepare_fontconfig(args.output_dir,args.extra_dir),ensure_ascii=False,indent=2))
