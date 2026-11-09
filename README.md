# 超级斜杠品牌技能

用于制作超级斜杠AI的 PPT、PDF、Word、宣传海报与课程材料。当前技能内含用户确认的 v1.0 标志、品牌使用手册、官网社区首页风格、横竖版背景、场景图和不同载体的应用样张。

- [技能入口](SKILL.md)
- [官网首页风格规则](references/homepage-style.md)
- [PPT、PDF 和海报应用样张](assets/homepage-style/application-reference.png)
- [品牌配置](assets/brand.json)

## 安装与核验

将仓库放到 Codex 能发现的技能目录。首次安装可以执行：

```bash
git clone https://github.com/superslash-rico/superslash-brand.git ~/.agents/skills/superslash-brand
```

从[小米 MiSans 官方页面](https://hyperos.mi.com/font/details/sc)获取静态 TTF。将 Regular、Medium、Semibold 和 Bold 四个字重按下列文件名放入技能的 `assets/fonts/`。已有本地品牌字体时可复用原文件。字体软件由小米提供，授权见[官方下载页](https://hyperos.mi.com/font/download)。

```text
assets/fonts/MiSans-Regular.ttf
assets/fonts/MiSans-Medium.ttf
assets/fonts/MiSans-Semibold.ttf
assets/fonts/MiSans-Bold.ttf
```

使用 Codex 工作区的 Python 运行 `python scripts/brand_assets.py --verify` 核验入库素材。该命令核验仓库内的素材；本机字体准备好后再生成或渲染文档。源文件为 `assets/brand.json`，原确认版的字体摘要可在 `assets/asset-manifest.json` 的 `local_font_references` 查到。

在 Codex 输入「使用 `$superslash-brand` 按官网首页风格制作品牌材料」，并说明受众、用途和输出格式。
