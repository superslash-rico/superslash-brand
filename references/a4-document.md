# A4 文档

## 版式与内容

用户指定尺寸优先。此品牌文档默认 A4 竖版 210×297 mm；比较或宽表可用 A4 横版 297×210 mm。横竖混排保持同一字体与品牌，说明为什么切换。封面、尾页与正文分别规划，长文按需要加入目录。

正文建议 11.5 pt、17.5 pt 行距、20 mm 边距；标题分级清晰。表格列宽按信息量分配，短编号、日期、状态列保持紧凑，叙述列够宽。长表跨页重复表头，允许单元格换行和行高扩展；完整记录不能静默截断。图题靠近图片，步骤截图与说明一起分页。

## PDF

封面和阅读页按 [官网首页风格](homepage-style.md) 分配装饰密度。`brand_pdf.py` 的浅色封面和尾页使用配套点阵、轨道背景，正文使用淡紫近白底和深紫正文。指定深色或使用满版照片时可保留深色配对封面与尾页；在 `closing` 传入 `style` 可单独指定尾页。浅色封面可在 `cover` 中用 `scene` 指定 `homepage_style.scenes` 的场景键，例如 `workshop`。

读取当前可用 PDF 技能执行生成、渲染及其交付要求。`scripts/brand_pdf.py` 是可选的可维护基础组件，不是唯一生成方式。它按实例保存尺寸与主题，没有课程数字或项目绝对路径。

```python
import sys
from pathlib import Path
skill_dir = Path(actual_skill_directory)
sys.path.insert(0, str(skill_dir / "scripts"))
from brand_pdf import BrandPDF

pdf = BrandPDF(output_path, title="客户方案", page_format="a4_portrait")
story = [pdf.heading("方案范围"), pdf.paragraph(verified_content)]
story += [pdf.table(verified_rows, [80, 150, pdf.content_width - 230])]
pdf.build(story, cover={"title": "客户方案", "subtitle": "实际项目范围"},
          closing={"title": "下一步沟通", "consultation": True})
```

写入文件时不覆盖现有输出，除非用户明确要求替换。中文断行与原生字体由组件处理，语义层级支持书签；复杂目录与互链按任务补充。不要宣称每个 PDF 都已有自动目录。主图若存在用 `image` 字段指定，组件提供连续遮罩；简洁封面省略它。

## Word

使用当前 Word 技能与原生 DOCX 元素。`scripts/brand_docx.py` 提供 A4 尺寸、MiSans 中英字体、标题样式、页眉页脚和跨页表头。文字、表格与图片可编辑；不能把 PDF 页截图作为 Word 正文。

```python
from brand_docx import new_document, add_cover, add_table, add_closing, save_document
doc = new_document("报告主题", page_format="a4_portrait")
add_cover(doc, "报告主题", "报告周期与用途")
doc.add_heading("结论", level=1)
doc.add_paragraph(verified_summary)
add_table(doc, verified_rows, [25, 80, 65])  # 列宽单位 mm，总宽 <= 正文宽
add_closing(doc, "下一步", verified_actions, consultation=False)
save_document(doc, output_path)
```

目录、页码与编号使用原生域和样式，导出前检查更新。复杂封面可使用新的节与独立页眉，保留正文自动排版。不要固定行高压住中文。图像、表格的宽度适配页面，而非无条件满宽。

## 从 Word 导出 PDF

先渲染 DOCX 并逐页检查；随后检查导出的 PDF，确认页数、字体、表格与链接。Word 中选了 MiSans 不等于客户设备已安装；如需稳定分发，同时提供已嵌入字体的 PDF。字体安装或嵌入按实际环境和任务处理，技能不会擅自改系统。

导出器可能没有读取系统字体。若出现缺字或字体替换，先检查字体资源，使用 `python scripts/prepare_fontconfig.py TASK_PRIVATE_FONT_DIR` 创建任务内配置，并把返回的 `FONTCONFIG_FILE`、`FONTCONFIG_PATH` 传给支持 Fontconfig 的渲染器，再核验导出 PDF 中的 MiSans。它只写入指定的私有目录，不改全局字体或插件缓存；不能认为所有平台与导出器都支持同一种方式。

复用模板时保留原生样式与结构，按本次品牌身份检查封面、页眉和尾页标志，并替换样例文字、图表和日期。新制文件的生成脚本默认从 `brand.json` 取 v1.0。

## 品牌色强调

重点增强遵循品牌规范。PDF 的 `pdf.paragraph(text, emphasis=["关键短语"])` 用加粗与 `#E802F8` 下划线标记重要内容；需要直接使用紫色文字时传 `emphasis_mode="text"` 并选择合适字号与背景。Word 的 `add_emphasis(paragraph, text)` 使用原生可编辑文字与紫色下划线；`mode="text"` 可创建紫色加粗文字。不要自动把整段或所有数字标为重点。
