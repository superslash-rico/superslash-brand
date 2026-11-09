#!/usr/bin/env python3
"""Read-only artifact structure check; does not replace render or visual review."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from brand_assets import load_brand

NS = {"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main", "a":"http://schemas.openxmlformats.org/drawingml/2006/main", "p":"http://schemas.openxmlformats.org/presentationml/2006/main"}


def outline_count(items):
    return sum(outline_count(item) if isinstance(item,list) else 1 for item in items)


def check_pdf(path, require_font):
    from pypdf import PdfReader
    reader=PdfReader(path)
    fonts=set(); errors=[]; sizes=[]; texts=[]
    for i,page in enumerate(reader.pages,1):
        sizes.append([round(float(page.mediabox.width),2),round(float(page.mediabox.height),2)])
        texts.append(page.extract_text() or "")
        if not texts[-1].strip(): errors.append(f"Page {i} has no extractable text")
        font_resources=(page.get("/Resources") or {}).get("/Font") or {}
        for ref in font_resources.values():
            font=ref.get_object();name=str(font.get("/BaseFont","")); fonts.add(name)
            descendants=font.get("/DescendantFonts") or [font]
            if "MiSans" in name:
                for desc in descendants:
                    descriptor=desc.get_object().get("/FontDescriptor")
                    if not descriptor or not any(key in descriptor.get_object() for key in ["/FontFile", "/FontFile2", "/FontFile3"]):
                        errors.append(f"Unembedded MiSans on page {i}: {name}")
    if require_font and not any("MiSans" in font for font in fonts): errors.append("MiSans not found in PDF font resources")
    return {"type":"pdf","pages":len(reader.pages),"page_sizes_pt":sizes,"fonts":sorted(fonts),"text_characters":sum(map(len,texts)),"outline_entries":outline_count(reader.outline),"errors":errors}


def check_docx(path, require_font):
    with ZipFile(path) as archive:
        root=ET.fromstring(archive.read("word/document.xml"));styles=ET.fromstring(archive.read("word/styles.xml"))
        text="".join(root.itertext()); paragraphs=root.findall(".//w:p",NS);tables=root.findall(".//w:tbl",NS)
        fonts=set()
        for element in list(root.findall(".//w:rFonts",NS))+list(styles.findall(".//w:rFonts",NS)):
            fonts.update(v for k,v in element.attrib.items() if k.rsplit("}",1)[-1] in ("ascii","hAnsi","eastAsia"))
        sizes=[]
        for item in root.findall(".//w:sectPr/w:pgSz",NS):
            sizes.append([round(int(item.get(f"{{{NS['w']}}}w"))/20,2),round(int(item.get(f"{{{NS['w']}}}h"))/20,2)])
        errors=[]
        if require_font and "MiSans" not in fonts:errors.append("MiSans not found in DOCX")
        if not paragraphs:errors.append("No native paragraphs")
        headers=[n for n in archive.namelist() if re.fullmatch(r"word/header\d+\.xml",n)]
        footers=[n for n in archive.namelist() if re.fullmatch(r"word/footer\d+\.xml",n)]
        if not headers or not footers:errors.append("Header or footer parts missing")
    return {"type":"docx","sections":len(sizes),"page_sizes_pt":sizes,"native_paragraphs":len(paragraphs),"native_tables":len(tables),"fonts":sorted(fonts),"header_parts":len(headers),"footer_parts":len(footers),"text_characters":len(text),"errors":errors}


def check_pptx(path, require_font):
    with ZipFile(path) as archive:
        root=ET.fromstring(archive.read("ppt/presentation.xml"));size=root.find("p:sldSz",NS)
        slides=sorted((n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml",n)),key=lambda n:int(re.search(r"slide(\d+)",n).group(1)))
        fonts=set();native_tables=0;native_text=0;errors=[]
        for n in slides:
            slide=ET.fromstring(archive.read(n));native_tables+=len(slide.findall(".//a:tbl",NS));native_text+=len(slide.findall(".//a:t",NS))
            for tag in ["a:rPr","a:defRPr","a:endParaRPr"]:
                for run in slide.findall(".//"+tag,NS):
                    for item in run:
                        if item.tag.rsplit("}",1)[-1] in ("latin","ea","cs") and item.get("typeface"):fonts.add(item.get("typeface"))
        notes=[n for n in archive.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml",n)]
        if require_font and not any("MiSans" in font for font in fonts):errors.append("MiSans not found in native slide text")
        if not native_text:errors.append("No native editable text")
    return {"type":"pptx","pages":len(slides),"page_sizes_pt":[[round(int(size.get("cx"))/12700,2),round(int(size.get("cy"))/12700,2)]],"native_text_runs":native_text,"native_tables":native_tables,"notes_parts":len(notes),"fonts":sorted(fonts),"errors":errors}


def inspect_artifact(path, expected_pages=None, page_format=None, require_font=False):
    path=Path(path)
    check={".pdf":check_pdf,".docx":check_docx,".pptx":check_pptx}.get(path.suffix.lower())
    if not check:raise ValueError("Supported checks: PDF, DOCX, PPTX")
    result=check(path,require_font)
    if expected_pages is not None:
        if result["type"]=="docx":result["pagination_note"]="DOCX page count requires rendering; expected_pages was not validated"
        elif result["pages"]!=expected_pages:result["errors"].append(f"Expected {expected_pages} pages, got {result['pages']}")
    if page_format:
        fmt=load_brand()["formats"][page_format];expected=[fmt["width_pt"],fmt["height_pt"]]
        if any(any(abs(v-e)>.6 for v,e in zip(size,expected)) for size in result["page_sizes_pt"]):result["errors"].append(f"Unexpected size for {page_format}")
    result["ok"]=not result["errors"]
    result["visual_review_required"]=True
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file");parser.add_argument("--expected-pages",type=int)
    parser.add_argument("--format",choices=["a4_portrait","a4_landscape","slide_16_9"])
    parser.add_argument("--require-mi-sans",action="store_true")
    args=parser.parse_args()
    result=inspect_artifact(args.file,args.expected_pages,args.format,args.require_mi_sans)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result["ok"]:raise SystemExit(1)
