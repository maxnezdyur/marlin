"""Design system + layout helpers for the WCCM method-section deck.

Native python-pptx construction: real text boxes, real shapes, LaTeX-rendered
equation PNGs (cmbright sans math, transparent bg) sized in true points.
"""

import hashlib
import subprocess
from pathlib import Path

from PIL import Image
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
EQ_DIR = HERE / "eqs"
EQ_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------- palette
# INL 2022 brand theme (from INL_2022_hexLight_wide.potx theme1.xml)
INK = RGBColor(0x1E, 0x24, 0x30)      # near-black body headings inside cards
BODY = RGBColor(0x3A, 0x3F, 0x47)     # body text
MUTED = RGBColor(0x59, 0x59, 0x5C)    # INL gray — captions, secondary
FAINT = RGBColor(0xB6, 0xBA, 0xBF)    # hairlines
BLUE = RGBColor(0x06, 0x50, 0x9D)     # INL blue — primary accent
BLUE_T = RGBColor(0xE6, 0xEE, 0xF7)   # blue tint fill
SKY = RGBColor(0x2C, 0xA8, 0xE1)      # INL light blue
GREEN = RGBColor(0x5E, 0x86, 0x14)    # darkened INL green for text/strokes
GREEN_BRAND = RGBColor(0x8E, 0xC4, 0x23)  # INL lime green (fills/stripes)
GREEN_T = RGBColor(0xEF, 0xF6, 0xDF)  # green tint fill
RED = RGBColor(0xCF, 0x1D, 0x4C)      # INL crimson — bottleneck accent
RED_T = RGBColor(0xFA, 0xE8, 0xED)    # red tint fill
GOLD = RGBColor(0xB4, 0x62, 0x0B)     # takeaway accent (from INL orange)
GOLD_T = RGBColor(0xFD, 0xF0, 0xDF)   # takeaway fill
CARD = RGBColor(0xF4, 0xF5, 0xF7)     # neutral card fill
CARD_LN = RGBColor(0xDA, 0xDD, 0xE2)  # neutral card border
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = "Arial"

PAGE_W = Inches(13.333)
PAGE_H = Inches(7.5)
MARGIN = Inches(0.62)
FOOTER_TOP = Inches(6.7)  # INL green stripe + blue band start ~6.72in — keep clear

EQ_HEX = "1E2430"  # must match INK

# ---------------------------------------------------------------- equations
EQ_TEMPLATE = r"""\documentclass[border=1.5pt,varwidth=8in]{standalone}
\usepackage{amsmath,amssymb,bm}
\usepackage{cmbright}
\usepackage{xcolor}
\definecolor{ink}{HTML}{%s}
\color{ink}
\begin{document}
%s
\end{document}
"""

EQ_DPI = 600


def render_eq(latex, color_hex=EQ_HEX, name=None):
    """LaTeX -> transparent PNG, one equation per file. Returns (png_path, w_px, h_px).

    Cached by content hash; if `name` is given the PNG is also copied to
    eqs/<name>.png so it can be grabbed and pasted by hand.
    """
    key = hashlib.sha1((latex + color_hex).encode()).hexdigest()[:16]
    png = EQ_DIR / f"eq_{key}.png"
    if not png.exists():
        tex = EQ_DIR / f"eq_{key}.tex"
        tex.write_text(EQ_TEMPLATE % (color_hex, latex))
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex.name],
            cwd=EQ_DIR, capture_output=True, check=True, timeout=60,
        )
        subprocess.run(
            ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha", f"-r{EQ_DPI}",
             f"-sOutputFile={png.name}", f"eq_{key}.pdf"],
            cwd=EQ_DIR, capture_output=True, check=True, timeout=60,
        )
        for junk in EQ_DIR.glob(f"eq_{key}.{{aux,log,pdf}}".replace("{", "").replace("}", "")):
            junk.unlink(missing_ok=True)
        for ext in ("aux", "log", "pdf"):
            (EQ_DIR / f"eq_{key}.{ext}").unlink(missing_ok=True)
    if name:
        named = EQ_DIR / f"{name}.png"
        named.write_bytes(png.read_bytes())
        png = named
    with Image.open(png) as im:
        w, h = im.size
    return png, w, h


def add_eq(slide, latex, left, top, scale=1.9, align=None, valign=None, name=None):
    """Place a rendered equation. scale=1 -> LaTeX 10-11pt natural size.

    align: None -> `left` is left edge; 'center' -> `left` is center x;
           'right' -> `left` is right edge.
    valign: None -> `top` is top edge; 'center' -> `top` is center y.
    Returns the picture shape.
    """
    png, w_px, h_px = render_eq(latex, name=name)
    w = Emu(int(w_px / EQ_DPI * scale * 914400))
    h = Emu(int(h_px / EQ_DPI * scale * 914400))
    x = int(left) - (w // 2 if align == "center" else w if align == "right" else 0)
    y = int(top) - (h // 2 if valign == "center" else 0)
    return slide.shapes.add_picture(str(png), x, y, w, h)


# ---------------------------------------------------------------- text
def _set_font(run, size, color, bold, italic, font=FONT, sup=False, sub=False):
    f = run.font
    f.name = font
    f.size = Pt(size) if not isinstance(size, Pt.__class__) else size
    f.color.rgb = color
    f.bold = bold
    f.italic = italic
    # also set east-asian/cs so PowerPoint doesn't substitute
    rPr = run._r.get_or_add_rPr()
    if sup:
        rPr.set("baseline", "30000")
    elif sub:
        rPr.set("baseline", "-25000")
    for tag in ("latin", "cs"):
        el = rPr.find(qn(f"a:{tag}"))
        if el is None:
            el = rPr.makeelement(qn(f"a:{tag}"), {})
            rPr.append(el)
        el.set("typeface", font)


def add_text(slide, left, top, width, height, runs, size=16, color=BODY,
             bold=False, italic=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             leading=1.0, space_after=0, wrap=True, shrink=False):
    """Rich text box. `runs` is a str, or list of paragraphs; each paragraph is a
    str or list of (text, overrides-dict) segments. Returns the textbox shape.
    """
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if leading != 1.0:
            p.line_spacing = leading
        if space_after:
            p.space_after = Pt(space_after)
        segs = [(para, {})] if isinstance(para, str) else para
        for text, ov in segs:
            r = p.add_run()
            r.text = text
            _set_font(
                r,
                ov.get("size", size),
                ov.get("color", color),
                ov.get("bold", bold),
                ov.get("italic", italic),
                ov.get("font", FONT),
                ov.get("sup", False),
                ov.get("sub", False),
            )
    return box


def add_bullets(slide, left, top, width, height, items, size=16, color=BODY,
                gap=10, leading=1.06, bullet_color=BLUE, indent=0.24):
    """Hanging-indent bulleted list. `items` = list of paragraphs (str or seg-list),
    or (para, level) tuples. Returns the textbox shape."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    for i, item in enumerate(items):
        level = 0
        para = item
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], int):
            para, level = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = leading
        p.space_after = Pt(gap if level == 0 else gap * 0.6)
        pPr = p._pPr if p._pPr is not None else p.get_or_add_pPr()
        mar = Inches(indent * (1 + level * 0.9))
        pPr.set("marL", str(int(mar)))
        pPr.set("indent", str(-int(Inches(indent))))
        # bullet char
        buClr = pPr.makeelement(qn("a:buClr"), {})
        srgb = pPr.makeelement(qn("a:srgbClr"), {"val": f"{bullet_color:s}" if isinstance(bullet_color, str) else str(bullet_color)})
        buClr.append(srgb)
        buFont = pPr.makeelement(qn("a:buFont"), {"typeface": FONT})
        ch = "•" if level == 0 else "–"
        buChar = pPr.makeelement(qn("a:buChar"), {"char": ch})
        pPr.append(buClr)
        pPr.append(buFont)
        pPr.append(buChar)
        segs = [(para, {})] if isinstance(para, str) else para
        base = size if level == 0 else size - 1.5
        for text, ov in segs:
            r = p.add_run()
            r.text = text
            _set_font(r, ov.get("size", base), ov.get("color", color),
                      ov.get("bold", False), ov.get("italic", False), ov.get("font", FONT),
                      ov.get("sup", False), ov.get("sub", False))
    return box


# ---------------------------------------------------------------- shapes
def add_card(slide, left, top, width, height, fill=CARD, line=CARD_LN,
             line_w=0.75, radius=0.055, shadow=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    try:
        sh.adjustments[0] = radius
    except Exception:
        pass
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.shadow.inherit = False
    return sh


def add_rect(slide, left, top, width, height, fill, line=None, line_w=0.75):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.shadow.inherit = False
    return sh


def add_line(slide, x1, y1, x2, y2, color=FAINT, weight=0.75, dash=None):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    ln.shadow.inherit = False
    if dash:
        lnEl = ln.line._get_or_add_ln()
        d = lnEl.makeelement(qn("a:prstDash"), {"val": dash})
        lnEl.append(d)
    return ln


def add_arrow(slide, x1, y1, x2, y2, color=INK, weight=1.5, dash=None,
              head="triangle", tail=None):
    ln = add_line(slide, x1, y1, x2, y2, color=color, weight=weight, dash=dash)
    lnEl = ln.line._get_or_add_ln()
    if head:
        h = lnEl.makeelement(qn("a:headEnd"), {})  # placeholder, replaced below
    # pptx draws from (x1,y1)->(x2,y2); arrow at the END uses tailEnd
    if head:
        e = lnEl.makeelement(qn("a:tailEnd"), {"type": head, "w": "med", "len": "med"})
        lnEl.append(e)
    if tail:
        e = lnEl.makeelement(qn("a:headEnd"), {"type": tail, "w": "med", "len": "med"})
        lnEl.append(e)
    return ln


def shape_text(sh, runs, size=13, color=INK, bold=False, align=PP_ALIGN.CENTER,
               anchor=MSO_ANCHOR.MIDDLE, leading=1.0, margins=0.06):
    """Set text inside an autoshape."""
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(margins))
    for m in ("margin_top", "margin_bottom"):
        setattr(tf, m, Inches(0.03))
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if leading != 1.0:
            p.line_spacing = leading
        segs = [(para, {})] if isinstance(para, str) else para
        for text, ov in segs:
            r = p.add_run()
            r.text = text
            _set_font(r, ov.get("size", size), ov.get("color", color),
                      ov.get("bold", bold), ov.get("italic", False), ov.get("font", FONT),
                      ov.get("sup", False), ov.get("sub", False))
    return sh


# ---------------------------------------------------------------- INL base
INL_POTX = HERE.parent / "INL_2022_hexLight_wide.potx"


def load_inl_base():
    """Patch the INL .potx into a .pptx base, open it, strip its sample slides."""
    import zipfile

    from pptx import Presentation

    base = HERE / "inl_base.pptx"
    if not base.exists() or base.stat().st_mtime < INL_POTX.stat().st_mtime:
        with zipfile.ZipFile(INL_POTX) as zin, \
                zipfile.ZipFile(base, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    data = data.replace(
                        b"presentationml.template.main+xml",
                        b"presentationml.presentation.main+xml")
                zout.writestr(item, data)
    prs = Presentation(base)
    # drop the template's sample slides
    for sldId in list(prs.slides._sldIdLst):
        prs.part.drop_rel(sldId.get(qn("r:id")))
        prs.slides._sldIdLst.remove(sldId)
    return prs


def inl_layout(prs, name):
    for master in prs.slide_masters:
        for lo in master.slide_layouts:
            if lo.name == name:
                return lo
    raise KeyError(f"layout {name!r} not in template")


# ---------------------------------------------------------------- chrome
def new_slide(prs, kicker=None, title=None, number=None, total=None,
              foot=None):
    """Content slide on the INL 'Blank Full Footer' layout (green stripe +
    blue INL band come from the layout; keep custom content above FOOTER_TOP)."""
    slide = prs.slides.add_slide(inl_layout(prs, "Blank Full Footer"))
    if title:
        ph = slide.shapes.title
        ph.text = title
        for p in ph.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(26)
    if number:
        add_text(slide, PAGE_W - Inches(1.05), Inches(0.3), Inches(0.75), Inches(0.25),
                 f"{number}" + (f" / {total}" if total else ""),
                 size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    return slide
