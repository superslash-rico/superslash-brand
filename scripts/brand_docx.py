#!/usr/bin/env python3
"""Native DOCX brand styles, headers, footers and expanding repeated-row tables."""
from __future__ import annotations
from pathlib import Path
from io import BytesIO
from docx import Document
from docx.shared import Mm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_TAB_ALIGNMENT, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from brand_assets import load_brand, asset_path
from brand_ooxml_theme import themed_bytes


def _font(run_or_style, family="MiSans", size=None, bold=None, color=None):
    run_or_style.font.name = family
    if size is not None: run_or_style.font.size = Pt(size)
    if bold is not None: run_or_style.font.bold = bold
    if color is not None: run_or_style.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
    pr = run_or_style._element.get_or_add_rPr()
    fonts = pr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts"); pr.insert(0, fonts)
    for key in list(fonts.attrib):
        if "theme" in key.lower():
            del fonts.attrib[key]
    for name in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + name), family)
    if size is not None:
        cs = pr.find(qn("w:szCs"))
        if cs is None: cs=OxmlElement("w:szCs");pr.append(cs)
        cs.set(qn("w:val"),str(round(size*2)))


def _field(paragraph, code):
    field = OxmlElement("w:fldSimple"); field.set(qn("w:instr"), code)
    value = OxmlElement("w:r"); text = OxmlElement("w:t"); text.text = "1"
    value.append(text); field.append(value); paragraph._p.append(field)


def new_document(title, page_format="a4_portrait", label=""):
    brand = load_brand()
    palette = brand["editorial_palette"]
    if page_format not in ("a4_portrait", "a4_landscape"):
        raise ValueError("Word document format must be a4_portrait or a4_landscape")
    doc = Document()
    doc.core_properties.title = title; doc.core_properties.author = brand["company_name"]
    section = doc.sections[0]
    section.page_width, section.page_height = (Mm(210), Mm(297)) if page_format == "a4_portrait" else (Mm(297), Mm(210))
    section.top_margin = section.bottom_margin = Mm(22)
    section.left_margin = section.right_margin = Mm(20)
    section.header_distance = section.footer_distance = Mm(10)
    section.different_first_page_header_footer = False
    style = doc.styles["Normal"]
    _font(style, size=11.5, color=palette["ink"])
    style.paragraph_format.line_spacing=Pt(17.5)
    style.paragraph_format.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
    style.paragraph_format.space_after=Pt(8)
    for name, size in [("Title", 38), ("Subtitle", 17), ("Heading 1", 25), ("Heading 2", 16), ("Heading 3", 13)]:
        s = doc.styles[name]; _font(s, size=size, bold=name != "Subtitle", color=palette["ink"])
        s.font.italic=False;s.font.underline=False
        ppr=s._element.get_or_add_pPr()
        for tag in ("w:pBdr","w:numPr"):
            for residue in list(ppr.findall(qn(tag))):ppr.remove(residue)
        s.paragraph_format.space_before = Pt(16 if name.startswith("Heading") else 0)
        s.paragraph_format.space_after = Pt(12)
        s.paragraph_format.keep_with_next = name.startswith("Heading")
    for name in ("Header", "Footer"):
        _font(doc.styles[name], size=8, color=palette["muted"])
        doc.styles[name].paragraph_format.tab_stops.clear_all()
    header = section.header.paragraphs[0]
    header.add_run().add_picture(str(asset_path(brand["logos"]["dark_on_light"])), width=Mm(47))
    header.add_run("   " + (label or title))
    footer = section.footer.paragraphs[0]
    footer.paragraph_format.tab_stops.add_tab_stop(section.page_width-section.left_margin-section.right_margin, WD_TAB_ALIGNMENT.RIGHT)
    footer.add_run(brand["company_name"] + "\t" + brand["domain"] + "  /  ")
    _field(footer, "PAGE")
    first = section.first_page_footer.paragraphs[0]
    first.add_run(brand["company_name"] + "   " + brand["domain"])
    return doc


def add_cover(doc, title, subtitle, *, meta="", eyebrow=None):
    brand = load_brand()
    if eyebrow is None:
        eyebrow = f"{brand['brand_name']}  /  报告"
    doc.sections[0].different_first_page_header_footer=True
    logo = doc.add_paragraph()
    logo.add_run().add_picture(str(asset_path(brand["logos"]["dark_on_light"])), width=Mm(58))
    logo.paragraph_format.space_after = Mm(38)
    p = doc.add_paragraph(); run = p.add_run(eyebrow)
    _font(run, size=10, color=brand["homepage_style"]["palette"]["action_purple"])
    p.paragraph_format.space_after = Pt(18)
    doc.add_paragraph(title, style="Title")
    doc.add_paragraph(subtitle, style="Subtitle")
    if meta:
        p = doc.add_paragraph(meta); p.paragraph_format.space_before = Mm(20)
        _font(p.runs[0], size=10, color=brand["editorial_palette"]["muted"])
    doc.add_page_break()


def add_table(doc, rows, widths_mm):
    if not rows or any(len(row) != len(widths_mm) for row in rows) or min(widths_mm) <= 0:
        raise ValueError("Provide rectangular table rows and positive widths")
    section = doc.sections[-1]
    available_mm = (section.page_width-section.left_margin-section.right_margin) / 36000
    if sum(widths_mm) > available_mm + .1:
        raise ValueError("Table exceeds document content width")
    brand = load_brand()
    palette = brand["editorial_palette"]
    action = brand["homepage_style"]["palette"]["action_purple"]
    table = doc.add_table(rows=1, cols=len(widths_mm))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT; table.autofit = False
    for col, width in zip(table.columns, widths_mm): col.width = Mm(width)
    for i, values in enumerate(rows):
        row = table.rows[0] if i == 0 else table.add_row()
        pr = row._tr.get_or_add_trPr()
        if i == 0:
            repeat = OxmlElement("w:tblHeader"); repeat.set(qn("w:val"), "true"); pr.append(repeat)
        for j, value in enumerate(values):
            cell = row.cells[j]; cell.width = Mm(widths_mm[j]); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = str(value)
            cell_pr = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for side, twips in [("top",100),("bottom",100),("left",120),("right",120)]:
                item=OxmlElement("w:"+side);item.set(qn("w:w"),str(twips));item.set(qn("w:type"),"dxa");margins.append(item)
            cell_pr.append(margins)
            shading = OxmlElement("w:shd"); shading.set(qn("w:fill"), (action if i == 0 else (palette["paper"] if i % 2 == 0 else "#FFFFFF")).lstrip("#")); cell_pr.append(shading)
            borders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right"):
                edge = OxmlElement("w:"+side); edge.set(qn("w:val"),"single");edge.set(qn("w:sz"),"4");edge.set(qn("w:color"),palette["rule"].lstrip("#"));borders.append(edge)
            cell_pr.append(borders)
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=Pt(15)
                p.paragraph_format.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
                for run in p.runs: _font(run,size=10.5,bold=i==0,color="#FFFFFF" if i==0 else palette["ink"])
    doc.add_paragraph().paragraph_format.space_after=Pt(6)
    return table


def add_closing(doc, title, text, *, consultation=False):
    brand = load_brand()
    section = doc.add_section(WD_SECTION_START.NEW_PAGE)
    section.different_first_page_header_footer = True
    section.first_page_header.is_linked_to_previous = False
    logo = doc.add_paragraph()
    logo.add_run().add_picture(str(asset_path(brand["logos"]["dark_on_light"])), width=Mm(58))
    logo.paragraph_format.space_after = Mm(35)
    doc.add_paragraph(title, style="Title")
    doc.add_paragraph(text)
    if consultation:
        contact=brand["contact"]
        doc.add_paragraph(f"联系邮箱  {contact['email']}\n联系电话  {contact['phone']}\n微信沟通  {contact['wechat']}")
        doc.add_paragraph().add_run().add_picture(str(asset_path(brand["assets"]["qr"])),width=Mm(34))
    return section


def add_emphasis(paragraph,text,*,mode="underline",size=None):
    """Native editable emphasis: readable dark type with a brand-purple underline."""
    if mode not in ("underline","text"):raise ValueError("Emphasis mode must be underline or text")
    brand=load_brand();color=brand.get("emphasis",{}).get("color",brand["official_palette"]["purple"])
    run=paragraph.add_run(str(text))
    _font(run,size=size,bold=True,color=color if mode=="text" else brand["editorial_palette"]["ink"])
    if mode=="underline":
        item=OxmlElement("w:u");item.set(qn("w:val"),"single");item.set(qn("w:color"),color.lstrip("#"))
        run._r.get_or_add_rPr().append(item)
    return run


def save_document(doc, output, *, overwrite=False):
    output=Path(output)
    if output.exists() and not overwrite: raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    content=BytesIO();doc.save(content)
    output.write_bytes(themed_bytes(content.getvalue()))
