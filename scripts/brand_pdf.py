#!/usr/bin/env python3
"""Reusable PDF typography, brand pages, continuous masks and flowing tables."""
from __future__ import annotations
import re
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics, pdfdoc
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import _normalizeColors, _buildColorFunction
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, LongTable, TableStyle, PageBreak, NextPageTemplate, Spacer

from brand_assets import load_brand, asset_path


def register_fonts():
    profile = load_brand()
    for role in ("regular", "medium", "semibold", "bold"):
        name = "SlashX-" + role
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(asset_path(profile["fonts"][role]))))
    pdfmetrics.registerFontFamily("SlashX-regular", normal="SlashX-regular", bold="SlashX-bold", italic="SlashX-regular", boldItalic="SlashX-bold")


def wrap_lines(text, font, size, width):
    """Wrap CJK and Latin, keeping punctuation attached and long tokens bounded."""
    if width <= 0:
        raise ValueError("Text width must be positive")
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z])|(?<=[A-Za-z])(?=[\u4e00-\u9fff])", " ", str(text))
    closing = set("，。！？；：、）】》〉」』’”.,!?;:)]}%")
    opening = set("（【《〈「『‘“([{")
    result = []
    for block in text.split("\n"):
        tokens = []
        for token in re.findall(r"[A-Za-z0-9]+(?:[./_@:-][A-Za-z0-9]+)*|[ \t]+|.", block):
            if tokens and (token in closing or tokens[-1][-1] in opening):
                tokens[-1] += token
            else:
                tokens.append(token)
        line = ""
        for token in tokens:
            if not line:
                token = token.lstrip()
            if pdfmetrics.stringWidth(token, font, size) > width:
                if line.strip():
                    result.append(line.rstrip()); line = ""
                for ch in token:
                    if pdfmetrics.stringWidth(ch, font, size) > width:
                        raise ValueError("Text box cannot fit one character")
                    if pdfmetrics.stringWidth(line + ch, font, size) > width:
                        if ch in closing or (line and line[-1] in opening):
                            carry=line[-1]
                            if pdfmetrics.stringWidth(carry+ch,font,size)>width:
                                raise ValueError("Text box cannot fit punctuation with its character")
                            if line[:-1]:result.append(line[:-1])
                            line=carry
                        else:
                            result.append(line); line = ""
                    line += ch
            elif line and pdfmetrics.stringWidth(line + token, font, size) > width - .6:
                result.append(line.rstrip()); line = token.lstrip()
            else:
                line += token
        result.append(line.rstrip())
    return result


def gradient_mask(canvas, width, height, axis, stops, fill):
    """Native luminosity soft-mask: a smooth layout overlay, no raster edits."""
    if axis not in ("x", "y"):
        raise ValueError("Mask axis must be x or y")
    if len(stops) < 2 or stops[0][0] != 0 or stops[-1][0] != 1 or any(not 0 <= x <= 1 or not 0 <= a <= 1 for x, a in stops) or any(a[0] >= b[0] for a, b in zip(stops, stops[1:])):
        raise ValueError("Mask stops must increase from 0 to 1 with valid opacity")
    cache = getattr(canvas, "_slashx_masks", {})
    canvas._slashx_masks = cache
    key = (width, height, axis, tuple(stops))
    if key not in cache:
        color_space, normalized = _normalizeColors([colors.Color(a, a, a) for _, a in stops])
        function = _buildColorFunction(normalized, [x for x, _ in stops])
        coords = (0, 0, width, 0) if axis == "x" else (0, height, 0, 0)
        shading = pdfdoc.PDFAxialShading(*coords, Function=function, ColorSpace=color_space, Extend="[true true]")
        name = canvas._doc.addShading(shading)
        form = pdfdoc.PDFStream(pdfdoc.PDFDictionary({
            "Type": pdfdoc.PDFName("XObject"), "Subtype": pdfdoc.PDFName("Form"), "FormType": 1,
            "BBox": pdfdoc.PDFArray([0, 0, width, height]),
            "Resources": pdfdoc.PDFDictionary({"Shading": pdfdoc.PDFDictionary({name: pdfdoc.PDFObjectReference(name)})}),
            "Group": pdfdoc.PDFDictionary({"S": pdfdoc.PDFName("Transparency"), "CS": pdfdoc.PDFName("DeviceRGB"), "I": pdfdoc.PDFtrue}),
        }), content=f"/{name} sh")
        reference = canvas._doc.Reference(form, f"SlashXMask{len(cache)}")
        cache[key] = pdfdoc.PDFDictionary({"S": pdfdoc.PDFName("Luminosity"), "G": reference})
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(fill))
    states = canvas._extgstate._c
    token = ("SMask", cache[key])
    if token not in states:
        states[token] = "gRLs" + str(len(states))
    canvas._code.append(f"/{states[token]} gs")
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.restoreState()


class BrandPDF(BaseDocTemplate):
    def __init__(self, output, title, page_format="a4_portrait", *, size=None, accent=None, label="", overwrite=False):
        self.brand = load_brand()
        register_fonts()
        config = self.brand["formats"][page_format] if size is None else {"width_pt": size[0], "height_pt": size[1], "margin_pt": 48}
        self.page_width, self.page_height = float(config["width_pt"]), float(config["height_pt"])
        self.margin = float(config["margin_pt"])
        self.is_slide=self.page_width/self.page_height>1.7
        if min(self.page_width, self.page_height) < self.margin * 2 + 140:
            raise ValueError("Page size is too small for this document layout")
        self.content_width = self.page_width - 2 * self.margin
        self.title = str(title)
        self.label = str(label)
        self.accent = accent or self.brand["homepage_style"]["palette"]["action_purple"]
        self.cover_data = self.closing_data = None
        self._outline_count = 0
        self._outline_level = -1
        output = Path(output)
        if output.exists() and not overwrite:
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(str(output), pagesize=(self.page_width, self.page_height), leftMargin=self.margin, rightMargin=self.margin,
                         topMargin=110, bottomMargin=64, title=title, author=self.brand["company_name"], pageCompression=1)
        frame = Frame(self.margin, 64, self.content_width, self.page_height - 174, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        blank = Frame(self.margin, 60, self.content_width, self.page_height - 120, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate("body", [frame], onPage=self._body), PageTemplate("cover", [blank], onPage=self._cover), PageTemplate("closing", [blank], onPage=self._closing)])
        p = self.brand["editorial_palette"]
        slide = self.page_width / self.page_height > 1.7
        self.body_style = ParagraphStyle("SlashXBody", fontName="SlashX-regular", fontSize=18 if slide else 11.5, leading=28 if slide else 17.5, textColor=colors.HexColor(p["ink"]), spaceAfter=12, wordWrap="CJK")
        self.heading_style = ParagraphStyle("SlashXHeading", parent=self.body_style, fontName="SlashX-semibold", fontSize=32 if slide else 25, leading=42 if slide else 34, spaceAfter=16, spaceBefore=12, keepWithNext=True)
        self.table_style = ParagraphStyle("SlashXTable", parent=self.body_style, fontSize=17 if slide else 10.3, leading=24 if slide else 15, spaceAfter=0)

    def paragraph(self, text, emphasis=(), emphasis_mode="underline"):
        if emphasis_mode not in ("underline","text"):
            raise ValueError("Emphasis mode must be underline or text")
        words=[emphasis] if isinstance(emphasis,str) else list(emphasis)
        words=sorted({str(word) for word in words if str(word)},key=len,reverse=True)
        raw=str(text)
        if not words:return Paragraph(escape(raw).replace("\n", "<br/>"),self.body_style)
        pieces=re.split("("+"|".join(re.escape(word) for word in words)+")",raw)
        color=self.brand.get("emphasis",{}).get("color",self.brand["official_palette"]["purple"])
        result=[]
        for piece in pieces:
            display=escape(piece).replace("\n","<br/>")
            if piece in words:
                display=f'<font color="{color}"><b>{display}</b></font>' if emphasis_mode=="text" else f'<u color="{color}"><b>{display}</b></u>'
            result.append(display)
        return Paragraph("".join(result),self.body_style)

    def heading(self, text, level=1):
        if level not in (1,2,3):raise ValueError("Heading level must be 1, 2 or 3")
        style=self.heading_style
        if level>1:
            slide=self.page_width/self.page_height>1.7
            size=(24 if level==2 else 20) if slide else (16 if level==2 else 13)
            style=ParagraphStyle(f"SlashXHeading{level}",parent=self.heading_style,fontSize=size,leading=size*1.4,spaceBefore=14,spaceAfter=10)
        result=Paragraph(escape(str(text)),style)
        result._slashx_outline_level=level-1
        return result

    def table(self, rows, widths):
        if not rows or any(len(row) != len(widths) for row in rows) or min(widths) <= 12 or sum(widths) > self.content_width + .1:
            raise ValueError("Table needs rectangular data and columns within the content width")
        header_style = ParagraphStyle("SlashXTableHeader", parent=self.table_style, fontName="SlashX-medium", textColor=colors.white)
        data = [[Paragraph(escape(str(value)).replace("\n", "<br/>"), header_style if i == 0 else self.table_style) for value in row] for i, row in enumerate(rows)]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1, splitInRow=1, spaceAfter=16)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(self.accent)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(self.brand["editorial_palette"]["pale_blue"])]),
            ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#D9D9D9")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
        return table

    def _image(self, canvas, path, x, y, width):
        with Image.open(path) as image:
            height = width * image.height / image.width
        canvas.drawImage(str(path), x, y, width, height, mask="auto")
        return height

    def _canvas_text(self, canvas, text, x, top, width, size, color, leading=None, font="SlashX-regular"):
        lines = wrap_lines(text, font, size, width)
        leading = leading or size * 1.4
        bottom = top + len(lines) * leading
        if bottom > self.page_height - 35:
            raise ValueError("Brand page text exceeds its page")
        canvas.setFillColor(colors.HexColor(color)); canvas.setFont(font, size)
        for i, line in enumerate(lines):
            canvas.drawString(x, self.page_height - top - size - i * leading, line)
        return bottom

    def _body(self, canvas, doc):
        p = self.brand["editorial_palette"]
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(p["paper"])); canvas.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
        self._image(canvas, asset_path(self.brand["logos"]["dark_on_light"]), self.margin, self.page_height - 63, 132)
        auxiliary=12 if self.is_slide else 8.2
        canvas.setFont("SlashX-regular", auxiliary); canvas.setFillColor(colors.HexColor(p["muted"]))
        heading = self.label or self.title
        lines = wrap_lines(heading, "SlashX-regular", auxiliary, self.content_width - 150)
        if len(lines) > 1:
            heading = lines[0] + "…"
        canvas.drawRightString(self.page_width - self.margin, self.page_height - 51, heading)
        canvas.setStrokeColor(colors.HexColor(p["rule"])); canvas.setLineWidth(.5)
        canvas.line(self.margin, self.page_height - 80, self.page_width - self.margin, self.page_height - 80)
        canvas.line(self.margin, 47, self.page_width - self.margin, 47)
        canvas.setFont("SlashX-regular", 12 if self.is_slide else 7.8)
        canvas.drawString(self.margin, 29, self.brand["company_name"])
        canvas.drawRightString(self.page_width - self.margin, 29, f"{self.brand['domain']}  /  {doc.page:02d}")
        canvas.restoreState()

    def _homepage_backdrop(self, canvas):
        layout = "wide" if self.page_width > self.page_height else "portrait"
        background = self.brand["homepage_style"]["backdrops"][layout]["png"]
        canvas.drawImage(str(asset_path(background)), 0, 0, self.page_width, self.page_height)

    def _cover(self, canvas, doc):
        data = self.cover_data or {}
        p = self.brand["editorial_palette"]
        has_image = bool(data.get("image"))
        dark = has_image or data.get("style") == "dark"
        scene = data.get("scene") if not dark else None
        wide_scene = scene and self.page_width > self.page_height
        title_width = self.content_width * (.46 if wide_scene else .9)
        background = p["graphite"] if dark else p["paper"]
        foreground = p["white"] if dark else p["ink"]
        canvas.saveState(); canvas.setFillColor(colors.HexColor(background)); canvas.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
        if has_image:
            with Image.open(data["image"]) as im:
                scale = max(self.page_width / im.width, self.page_height / im.height)
                w, h = im.width * scale, im.height * scale
            canvas.drawImage(str(data["image"]), (self.page_width - w) / 2, (self.page_height - h) / 2, w, h, mask="auto")
            gradient_mask(canvas, self.page_width, self.page_height, "x", [(0, .98), (.45, .91), (.8, .2), (1, .12)], background)
            gradient_mask(canvas, self.page_width, self.page_height, "y", [(0, .2), (.4, 0), (.75, .85), (1, .98)], background)
        elif not dark:
            self._homepage_backdrop(canvas)
        self._image(canvas, asset_path(self.brand["logos"]["light_on_dark" if dark else "dark_on_light"]), self.margin, self.page_height - 90, 145)
        top = self.page_height * .26
        slug = data.get("eyebrow", f"{self.brand['brand_name']}  /  商务资料")
        self._canvas_text(canvas, slug, self.margin, top, self.content_width, 14 if self.is_slide else 9, foreground if dark else self.accent)
        title_bottom = self._canvas_text(canvas, data.get("title", self.title), self.margin, top + 38, title_width, 40 if self.page_width < 650 else 48, foreground, font="SlashX-semibold")
        subtitle_bottom=self._canvas_text(canvas, data.get("subtitle", ""), self.margin, title_bottom + 22, min(self.content_width * .88, title_width), 17 if self.page_width < 650 else 23, foreground)
        if subtitle_bottom>self.page_height-180:raise ValueError("Cover title/subtitle conflicts with its metadata; reflow the cover")
        if scene:
            scene_path = asset_path(self.brand["homepage_style"]["scenes"][scene])
            scene_width = self.content_width * (.49 if wide_scene else .68)
            scene_bottom = self.page_height * .19
            if not wide_scene:
                available_height = self.page_height - scene_bottom - subtitle_bottom - 24
                if available_height < 60:
                    raise ValueError("Cover text leaves too little space for its scene; reflow the cover")
                with Image.open(scene_path) as image:
                    scene_width = min(scene_width, available_height * image.width / image.height)
            self._image(canvas, scene_path, self.page_width - self.margin - scene_width, scene_bottom, scene_width)
        meta_width = title_width if wide_scene else self.content_width
        self._canvas_text(canvas, data.get("meta", ""), self.margin, self.page_height - 154, meta_width, 14 if self.is_slide else 11, foreground)
        self._canvas_text(canvas, self.brand["company_name"], self.margin, self.page_height - 75, self.content_width, 12 if self.is_slide else 9, foreground)
        canvas.setFont("SlashX-medium", 14 if self.is_slide else 10); canvas.setFillColor(colors.HexColor(foreground))
        canvas.drawRightString(self.page_width - self.margin, 40, self.brand["domain"])
        canvas.linkURL(self.brand["website"], (self.page_width-self.margin-80, 35, self.page_width-self.margin, 53))
        canvas.restoreState()

    def _closing(self, canvas, doc):
        data = self.closing_data or {}
        p = self.brand["editorial_palette"]
        cover = self.cover_data or {}
        default_style = "dark" if cover.get("style") == "dark" or cover.get("image") else "light"
        dark = (data.get("style") or default_style) == "dark"
        foreground = p["white"] if dark else p["ink"]
        canvas.saveState()
        if dark:
            canvas.setFillColor(colors.HexColor(p["graphite"]))
            canvas.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
        else:
            self._homepage_backdrop(canvas)
        logo_key = "light_on_dark" if dark else "dark_on_light"
        self._image(canvas, asset_path(self.brand["logos"][logo_key]), self.margin, self.page_height - 90, 145)
        title_bottom=self._canvas_text(canvas, data.get("title", "下一步"), self.margin, 165 if self.page_height > 650 else 128, self.content_width, 38 if self.is_slide else 31, foreground, font="SlashX-semibold")
        top=max(title_bottom+26,246 if self.page_height > 650 else 204)
        consultation = bool(data.get("consultation"))
        body_width = self.content_width - 162 if consultation else self.content_width
        bottom = self._canvas_text(canvas, data.get("text", ""), self.margin, top, body_width, 16 if self.is_slide else 13, foreground)
        if consultation:
            contact = self.brand["contact"]
            bottom = self._canvas_text(canvas, f"联系邮箱  {contact['email']}\n联系电话  {contact['phone']}\n微信沟通  {contact['wechat']}", self.margin, bottom + 30, body_width, 16 if self.is_slide else 12, foreground, leading=24)
            if bottom>self.page_height-185:raise ValueError("Closing copy conflicts with its contact/address area; shorten or reflow it")
            qr = asset_path(self.brand["assets"]["qr"])
            canvas.drawImage(str(qr), self.page_width - self.margin - 135, self.page_height - top - 145, 135, 135)
            self._canvas_text(canvas, "扫码微信沟通", self.page_width - self.margin - 135, top + 152, 135, 12 if self.is_slide else 10, foreground)
            self._canvas_text(canvas, contact["address"], self.margin, self.page_height - 145, self.content_width, 14 if self.is_slide else 10, foreground)
        self._canvas_text(canvas, self.brand["company_name"], self.margin, self.page_height - 75, self.content_width, 12 if self.is_slide else 9, foreground)
        canvas.setFont("SlashX-medium", 16 if self.is_slide else 12); canvas.setFillColor(colors.HexColor(foreground))
        canvas.drawRightString(self.page_width - self.margin, 40, self.brand["domain"])
        canvas.linkURL(self.brand["website"], (self.page_width-self.margin-90, 34, self.page_width-self.margin, 55))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and hasattr(flowable,"_slashx_outline_level"):
            key = f"section-{self._outline_count}"
            level=min(flowable._slashx_outline_level,self._outline_level+1)
            self.canv.bookmarkPage(key); self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level)
            self._outline_level=level
            self._outline_count += 1

    def build(self, story, cover=None, closing=None, **kwargs):
        self.cover_data, self.closing_data = cover, closing
        output_story = list(story)
        if cover:
            self._firstPageTemplateIndex = 1
            output_story = [NextPageTemplate("body"), Spacer(1, 1), PageBreak()] + output_story
        if closing:
            output_story += [NextPageTemplate("closing"), PageBreak(), Spacer(1, 1)]
        super().build(output_story, **kwargs)
