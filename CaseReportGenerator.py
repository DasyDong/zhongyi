"""病例报告阅览/打印：沿用处方笺版式，并附加病例报告字段。"""

from io import BytesIO
import re

import pymysql
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from Database_connection import load_db_config
from preview import PreviewGenerator

# 优先使用黑体（笔画粗、清晰），回退到 PreviewGenerator 的默认字体
import os
import sys
_win_font_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
_case_fonts = [
    ("SimHei", os.path.join(_win_font_dir, 'simhei.ttf')),   # Windows 黑体 - 正文字体
    ("SimHeiBold", os.path.join(_win_font_dir, 'simhei.ttf')),  # Windows 黑体 - 粗体（复用）
    ("Microsoft YaHei", os.path.join(_win_font_dir, 'msyh.ttc')),
    ("Microsoft YaHei Bold", os.path.join(_win_font_dir, 'msyhbd.ttc')),
]

CASE_NORMAL_FONT = None
CASE_BOLD_FONT = None

for name, path in _case_fonts:
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont(name, path))
            if CASE_NORMAL_FONT is None:
                CASE_NORMAL_FONT = name
            CASE_BOLD_FONT = name
        except Exception:
            pass

if CASE_NORMAL_FONT is None:
    CASE_NORMAL_FONT = PreviewGenerator(1, 1).font_name
    CASE_BOLD_FONT = CASE_NORMAL_FONT


class CaseReportGenerator(PreviewGenerator):
    """在处方笺正文前增加完整病例报告内容。"""
    report_title = "病历记录"

    def __init__(self, patient_id, user_id=1):
        super().__init__(patient_id, user_id)
        self.case_report = {}

    def _fetch_data(self):
        # 与“查看处方”完全复用患者、药品和诊所信息。
        data = super()._fetch_data()
        connection = pymysql.connect(**load_db_config(), cursorclass=pymysql.cursors.DictCursor)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 编号, 主诉, 现病史, 既往史, 过敏史, 个人史,
                           诊断, 医嘱处方, 服药方法, 禁忌, 备注, 日期时间
                    FROM 常规资料
                    WHERE 编号=%s
                    """,
                    (self.patient_id,),
                )
                self.case_report = cursor.fetchone() or {}
        finally:
            connection.close()

        if self.case_report.get("诊断"):
            data["诊断"] = self.case_report["诊断"]
        return data

    def _prescription_usage_text(self):
        """生成处方下方的剂数和煎服用法说明。"""
        doses = str(self.data.get("剂数") or "15").strip()
        decoction = str(self.data.get("煎服方式") or "煎服").strip()
        frequency = str(self.data.get("每日次数") or "一日二次").strip()
        volume = str(self.data.get("每次容量") or "一袋/150ml").strip()
        return (
            f"剂数：{doses}剂    煎服：{decoction}    "
            f"频次：{frequency}    每次容量：{volume}"
        )

    def _draw_page_header(self, c):
        """病例报告页眉：采用处方报告的合并标题和三行患者信息布局。"""
        c.setLineWidth(1.2)
        c.rect(self.margin, self.margin,
               self.page_width - 2 * self.margin,
               self.page_height - 2 * self.margin)

        clinic_name = self.data.get("诊所名称", "")
        title = f"{clinic_name}病例报告" if clinic_name else "病例报告"
        self.y_position -= 0.55 * cm
        c.setFont(self.font_name, 18)
        c.drawCentredString(self.page_width / 2, self.y_position, title)
        self.y_position -= 1.0 * cm

        c.setFont(self.font_name, 13)
        # 第一排：病例号左侧，日期右侧。
        c.drawString(2 * cm, self.y_position, f"病例号：{self.data.get('病历号', '')}")
        date_text = str(self.data.get('日期时间', '') or '')[:10]
        c.drawRightString(self.page_width - 2 * cm, self.y_position, f"日期：{date_text}")
        self._draw_underline(c)
        self.y_position -= 0.9 * cm

        # 第二排：住址左侧，电话右侧。
        address = self.data.get("地址") or self.data.get("住址", "")
        c.drawString(2 * cm, self.y_position, f"住址：{address}")
        c.drawRightString(self.page_width - 2 * cm, self.y_position,
                          f"电话：{self.data.get('电话', '')}")
        self._draw_underline(c)
        self.y_position -= 0.9 * cm

        # 患者基本信息另起一排，避免与病例号和联系方式重叠。
        c.drawString(2 * cm, self.y_position, f"姓名：{self.data.get('姓名', '')}")
        c.drawCentredString(self.page_width / 2, self.y_position,
                           f"性别：{self.data.get('性别', '')}")
        c.drawRightString(self.page_width - 2 * cm, self.y_position,
                          f"年龄：{self.data.get('年龄', '')}")
        self._draw_underline(c)
        self.y_position -= 0.5 * cm

    def _draw_plain_sections(self, c, new_page, fields, value_font_size=11,
                             value_bold=False):
        """以无表格分区绘制报告正文，长内容自动换行且不互相覆盖。"""
        min_y = self.margin + self.footer_height
        content_width = self.page_width - 4 * cm
        label_style = ParagraphStyle(name="plain_label", fontName=self.font_name,
                                     fontSize=11, leading=15, alignment=TA_LEFT, wordWrap="CJK")
        value_style = ParagraphStyle(name="plain_value",
                                     fontName=CASE_BOLD_FONT if value_bold else CASE_NORMAL_FONT,
                                     fontSize=value_font_size,
                                     leading=max(15, value_font_size + 4),
                                     alignment=TA_LEFT, wordWrap="CJK",
                                     fontWeight="bold" if value_bold else "normal")

        def safe_text(value):
            return ("" if value is None else str(value)).replace("&", "&amp;").replace(
                "<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

        def draw_paragraph(paragraph):
            """绘制可跨页的段落，避免长内容把后续字段挤出页面。"""
            while True:
                available = self.y_position - min_y
                if available <= 1:
                    new_page()
                    continue

                # 空字段不需要绘制；Paragraph.split 对空文本会返回空列表。
                _, natural_height = paragraph.wrap(content_width, available)
                if natural_height <= 0:
                    return

                parts = paragraph.split(content_width, available)
                if not parts:
                    new_page()
                    continue

                part = parts[0]
                _, height = part.wrap(content_width, available)
                if height > available and self.y_position < self.page_height - self.margin - 1:
                    new_page()
                    continue

                part.drawOn(c, 2 * cm, self.y_position - height)
                self.y_position -= height
                if len(parts) == 1:
                    return

                new_page()
                paragraph = parts[1]

        for label, value in fields:
            label_para = Paragraph(f"<b>{safe_text(label)}</b>", label_style)
            value_text = safe_text(value)
            if label.startswith("医嘱处方(单位克)"):
                # 保留药物间距，同时在每组间距后提供可分页断点。
                value_text = value_text.replace("          ", "&#160;" * 10 + "&#8203;")
                value_text = value_text.replace(" ", "&#160;")
            if value_bold:
                value_text = f"<b>{value_text}</b>"
            value_para = Paragraph(value_text, value_style)

            for paragraph in (label_para, value_para):
                draw_paragraph(paragraph)
            # 每个区域之间留出空白，并画一条轻分隔线，不使用表格边框。
            self.y_position -= 0.18 * cm
            c.setStrokeColor(colors.HexColor("#b0b0b0"))
            c.setLineWidth(0.5)
            c.line(2 * cm, self.y_position, self.page_width - 2 * cm, self.y_position)
            self.y_position -= 0.28 * cm

    def _draw_prescription_grid(self, c, new_page):
        """病例报告中的医嘱处方：每行五味药，单位为g。"""
        min_y = self.margin + self.footer_height
        content_width = self.page_width - 4 * cm
        label_style = ParagraphStyle(name="case_rx_label", fontName=self.font_name,
                                     fontSize=11, leading=15, alignment=TA_LEFT,
                                     wordWrap="CJK")
        value_style = ParagraphStyle(name="case_rx_value", fontName=CASE_NORMAL_FONT,
                                     fontSize=10.5, leading=14, alignment=TA_LEFT,
                                     wordWrap="CJK")

        heading = Paragraph(
            '<b>医嘱处方</b> '
            '<font size="8">RP:如无特殊标明数量后面均为g</font>',
            label_style,
        )
        _, heading_height = heading.wrap(content_width, max(self.y_position - min_y, 1))
        if self.y_position - heading_height < min_y:
            new_page()
        heading.drawOn(c, 2 * cm, self.y_position - heading_height)
        self.y_position -= heading_height + 0.18 * cm

        medicines = []
        for i in range(1, 41):
            name = str(self.data.get(f"药物{i}", "") or "").strip()
            if not name:
                continue
            dose = str(self.data.get(f"用量{i}", "") or "").strip()
            medicines.append(f"{name} {dose}g" if dose and dose.lower() != "none" else name)
        if not medicines:
            medicines = ["无"]

        rows = []
        for start in range(0, len(medicines), 5):
            row = medicines[start:start + 5]
            row += [""] * (5 - len(row))
            rows.append([Paragraph(value, value_style) for value in row])

        table = Table(rows, colWidths=[content_width / 5] * 5, splitByRow=1)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#777777")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        remaining = table
        while remaining:
            available = max(self.y_position - min_y, 1)
            pieces = remaining.split(content_width, available)
            if not pieces:
                new_page()
                continue
            part = pieces[0]
            _, height = part.wrap(content_width, available)
            part.drawOn(c, 2 * cm, self.y_position - height)
            self.y_position -= height + 0.28 * cm
            remaining = pieces[1] if len(pieces) > 1 else None
            if remaining:
                new_page()

    def _draw_case_report_content(self, c, new_page):
        fields_before_prescription = (
            ("主诉：", self.case_report.get("主诉", "")),
            ("现病史：", self.case_report.get("现病史", "")),
            ("既往史：", self.case_report.get("既往史", "")),
            ("过敏史：", self.case_report.get("过敏史", "")),
            ("个人史：", self.case_report.get("个人史", "")),
            ("诊断：", self.case_report.get("诊断", self.data.get("诊断", ""))),
        )
        fields_after_prescription = (
            ("煎服用法：", self._prescription_usage_text()),
            ("禁忌：", self.case_report.get("禁忌", "无")),
            ("备注：", self.case_report.get("备注", "无")),
        )
        self._draw_plain_sections(c, new_page, fields_before_prescription)
        self.y_position -= 0.45 * cm
        self._draw_prescription_grid(c, new_page)
        self.y_position -= 0.45 * cm
        self._draw_plain_sections(c, new_page, fields_after_prescription)

    def _draw_case_report_table(self, c, new_page):
        """用两列表格绘制病例字段，内容单元格按文字长度自适应并自动分页。"""
        min_y = self.margin + self.footer_height
        content_width = self.page_width - 4 * cm
        fields = (
            ("主诉：", self.case_report.get("主诉", "")),
            ("现病史：", self.case_report.get("现病史", "")),
            ("既往史：", self.case_report.get("既往史", "")),
            ("过敏史：", self.case_report.get("过敏史", "")),
            ("个人史：", self.case_report.get("个人史", "")),
            ("诊断：", self.case_report.get("诊断", self.data.get("诊断", ""))),
            ("医嘱处方(单位克)：", self._report_prescription()),
            ("煎服用法：", self._prescription_usage_text()),
            ("禁忌：", self.case_report.get("禁忌", "无")),
            ("备注：", self.case_report.get("备注", "无")),
        )

        label_style = ParagraphStyle(
            name="case_label", fontName=self.font_name, fontSize=11,
            leading=15, alignment=TA_LEFT, wordWrap="CJK",
        )
        value_style = ParagraphStyle(
            name="case_value", fontName=CASE_NORMAL_FONT, fontSize=11,
            leading=15, alignment=TA_LEFT, wordWrap="CJK",
        )

        def safe_text(value):
            return ("" if value is None else str(value)).replace("&", "&amp;").replace(
                "<", "&lt;"
            ).replace(">", "&gt;").replace("\n", "<br/>")

        rows = []
        for label, value in fields:
            safe_value = safe_text(value)
            if label == "医嘱处方(单位克)":
                # ReportLab Paragraph 会折叠普通空格；不可折叠空格才能稳定显示五格间距。
                safe_value = safe_value.replace(" ", "&#160;")
            rows.append([Paragraph(f"<b>{safe_text(label)}</b>", label_style),
                         Paragraph(safe_value, value_style)])

        table = Table(rows, colWidths=[3.6 * cm, content_width - 3.6 * cm],
                      splitByRow=1, repeatRows=0)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#777777")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        # 分页时保持表格边框和每一行完整，长文本会自动增加该行高度。
        remaining = table
        while remaining:
            available = max(self.y_position - min_y, 1)
            pieces = remaining.split(content_width, available)
            if not pieces:
                new_page()
                continue
            part = pieces[0]
            _, height = part.wrap(content_width, available)
            part.drawOn(c, 2 * cm, self.y_position - height)
            self.y_position -= height
            remaining = pieces[1] if len(pieces) > 1 else None
            if remaining:
                new_page()

    def _report_prescription(self):
        """统一报告中的药物间距为至少十个空格，兼容旧记录的换行格式。"""
        value = (self.case_report.get("医嘱处方") or
                 self.case_report.get("重要处方") or self._prescription_text())
        value = str(value).strip()
        # 旧记录可能是一味一行或使用较少空格，统一为十个空格。
        value = re.sub(r"[\r\n]+", "          ", value)
        value = re.sub(r" {2,}", "          ", value)
        return value

    def _prescription_text(self):
        """从处方数据生成医嘱处方，药物之间使用十个空格。"""
        medicines = []
        for i in range(1, 41):
            name = str(self.data.get(f"药物{i}", "") or "").strip()
            if not name:
                continue
            dose = str(self.data.get(f"用量{i}", "") or "").strip()
            method = str(self.data.get(f"先煎后下{i}", "") or "").strip()
            item = f"{name} {dose}克" if dose else name
            if method:
                item += f"（{method}）"
            medicines.append(item)
        return "          ".join(medicines)

    def _draw_footer(self, c):
        """病例报告页脚只保留左侧主治医师。"""
        current_y = self.margin + self.footer_height
        c.setFont(self.font_name, 12)
        doctor = self.data.get("主治医生") or self.data.get("医生", "")
        c.drawString(2 * cm, current_y, f"主治医师：{doctor}")
        current_y -= 0.9 * cm
        contact = []
        if self.data.get("诊所地址"):
            contact.append(f"地址：{self.data['诊所地址']}")
        if self.data.get("诊所电话"):
            contact.append(f"电话：{self.data['诊所电话']}")
        if contact:
            c.drawString(2 * cm, current_y, "    ".join(contact))

    def generate(self):
        """生成完整病例报告，不能落回旧版处方预览流程。"""
        self.data = self._fetch_data()
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        def draw_header():
            self.y_position = self.page_height - self.margin
            self._draw_page_header(c)

        def new_page():
            c.showPage()
            draw_header()

        draw_header()
        self._draw_case_report_content(c, new_page)
        self._draw_footer(c)
        c.save()
        buffer.seek(0)
        return buffer


class PrescriptionReportGenerator(CaseReportGenerator):
    """精简处方报告：保留患者信息及处方相关字段，沿用病例报告版式。"""

    def _draw_page_header(self, c):
        """处方笺专用页眉：标题合并，病例号/日期第一行，住址/电话第二行。"""
        c.setLineWidth(1.2)
        c.rect(self.margin, self.margin,
               self.page_width - 2 * self.margin,
               self.page_height - 2 * self.margin)

        clinic_name = self.data.get("诊所名称", "")
        title = f"{clinic_name}处方笺" if clinic_name else "处方笺"
        self.y_position -= 0.55 * cm
        c.setFont(self.font_name, 18)
        c.drawCentredString(self.page_width / 2, self.y_position, title)
        self.y_position -= 1.0 * cm

        c.setFont(self.font_name, 13)
        # 病例号独占第一行：左侧病例号，右侧日期，中间留空。
        c.drawString(2 * cm, self.y_position, f"病例号：{self.data.get('病历号', '')}")
        date_text = str(self.data.get('日期时间', '') or '')[:10]
        c.drawRightString(self.page_width - 2 * cm, self.y_position, f"日期：{date_text}")
        self._draw_underline(c)
        self.y_position -= 1.0 * cm

        # 第二行显示患者基本信息。
        c.drawString(2 * cm, self.y_position, f"姓名：{self.data.get('姓名', '')}")
        c.drawCentredString(self.page_width / 2, self.y_position,
                           f"性别：{self.data.get('性别', '')}")
        c.drawRightString(self.page_width - 2 * cm, self.y_position,
                          f"年龄：{self.data.get('年龄', '')}")
        self._draw_underline(c)
        self.y_position -= 0.9 * cm

        # 第三行显示住址和电话。
        address = self.data.get("地址") or self.data.get("住址", "")
        c.drawString(2 * cm, self.y_position, f"住址：{address}")
        c.drawRightString(self.page_width - 2 * cm, self.y_position,
                          f"电话：{self.data.get('电话', '')}")
        self._draw_underline(c)
        self.y_position -= 0.5 * cm

    def _clinical_diagnosis_text(self):
        """处方笺显示临床诊断和证型，兼容旧数据字段。"""
        diagnosis = self.case_report.get("诊断") or self.data.get("诊断", "")
        syndrome = self.data.get("辨证") or self.data.get("证型", "")
        if diagnosis and syndrome:
            return f"{diagnosis}\n证型：{syndrome}"
        return diagnosis or syndrome

    def _draw_prescription_grid(self, c, new_page):
        """处方报告专用药物表：每行五味药，药名和单位保持同一行。"""
        min_y = self.margin + self.footer_height
        content_width = self.page_width - 4 * cm
        label_style = ParagraphStyle(name="rx_grid_label", fontName=self.font_name,
                                     fontSize=11, leading=15, alignment=TA_LEFT, wordWrap="CJK")
        value_style = ParagraphStyle(name="rx_grid_value", fontName=CASE_NORMAL_FONT,
                                     fontSize=10.5, leading=14, alignment=TA_LEFT, wordWrap="CJK")

        def safe_text(value):
            return ("" if value is None else str(value)).replace("&", "&amp;").replace(
                "<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

        heading = Paragraph(
            '<b>医嘱处方</b> '
            '<font size="8">RP:如无特殊标明数量后面均为g</font>',
            label_style,
        )
        _, heading_height = heading.wrap(content_width, max(self.y_position - min_y, 1))
        if self.y_position - heading_height < min_y:
            new_page()
        heading.drawOn(c, 2 * cm, self.y_position - heading_height)
        self.y_position -= heading_height + 0.18 * cm

        medicines = []
        for i in range(1, 41):
            name = str(self.data.get(f"药物{i}", "") or "").strip()
            if not name:
                continue
            dose = str(self.data.get(f"用量{i}", "") or "").strip()
            if dose and dose.lower() != "none":
                medicines.append(f"{safe_text(name)} {safe_text(dose)}g")
            else:
                medicines.append(safe_text(name))
        if not medicines:
            medicines = ["无"]

        rows = []
        for start in range(0, len(medicines), 5):
            row = medicines[start:start + 5]
            row += [""] * (5 - len(row))
            rows.append([Paragraph(value, value_style) for value in row])
        table = Table(rows, colWidths=[content_width / 5] * 5, splitByRow=1)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#777777")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        remaining = table
        while remaining:
            available = max(self.y_position - min_y, 1)
            pieces = remaining.split(content_width, available)
            if not pieces:
                new_page()
                continue
            part = pieces[0]
            _, height = part.wrap(content_width, available)
            part.drawOn(c, 2 * cm, self.y_position - height)
            self.y_position -= height + 0.28 * cm
            remaining = pieces[1] if len(pieces) > 1 else None
            if remaining:
                new_page()

    def _draw_case_report_content(self, c, new_page):
        original = self.case_report
        self.case_report = {
            "诊断": original.get("诊断", self.data.get("诊断", "")),
            "医嘱处方": original.get("医嘱处方", ""),
            "禁忌": original.get("禁忌", "无"),
            "备注": original.get("备注", "无"),
        }
        try:
            # 患者基本信息与临床诊断之间留一整行空白。
            self.y_position -= 0.45 * cm
            self._draw_plain_sections(c, new_page, (
                ("临床诊断及证型", self._clinical_diagnosis_text()),
            ), value_font_size=13, value_bold=False)
            # 临床诊断、医嘱处方及其后的内容使用同样的分隔间距。
            self.y_position -= 0.45 * cm
            self._draw_prescription_grid(c, new_page)
            self.y_position -= 0.45 * cm
            self._draw_plain_sections(c, new_page, (
                ("煎服用法", self._prescription_usage_text()),
                ("禁忌事项", self.case_report.get("禁忌", "无")),
                ("备注", self.case_report.get("备注", "无")),
            ))
        finally:
            self.case_report = original

    def _draw_case_report_table(self, c, new_page):
        original = self.case_report
        self.case_report = {
            "诊断": original.get("诊断", self.data.get("诊断", "")),
            "医嘱处方": original.get("医嘱处方", ""),
            "禁忌": original.get("禁忌", "无"),
            "备注": original.get("备注", "无"),
        }
        try:
            # 只绘制诊断、医嘱处方、煎服用法、禁忌，不显示病例叙述字段。
            min_y = self.margin + self.footer_height
            content_width = self.page_width - 4 * cm
            fields = (
                ("临床诊断及证型", self._clinical_diagnosis_text()),
                ("医嘱处方", self._report_prescription()),
                ("煎服用法", self._prescription_usage_text()),
                ("禁忌事项", self.case_report.get("禁忌", "无")),
                ("备注", self.case_report.get("备注", "无")),
            )
            label_style = ParagraphStyle(name="prescription_label", fontName=self.font_name,
                                         fontSize=11, leading=15, alignment=TA_LEFT, wordWrap="CJK")
            value_style = ParagraphStyle(name="prescription_value", fontName=CASE_NORMAL_FONT,
                                         fontSize=11, leading=15, alignment=TA_LEFT, wordWrap="CJK")

            def safe_text(value):
                return ("" if value is None else str(value)).replace("&", "&amp;").replace(
                    "<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

            rows = []
            for label, value in fields:
                text_value = safe_text(value)
                if label == "医嘱处方(单位克)":
                    text_value = text_value.replace(" ", "&#160;")
                rows.append([Paragraph(f"<b>{safe_text(label)}</b>", label_style),
                             Paragraph(text_value, value_style)])
            table = Table(rows, colWidths=[3.6 * cm, content_width - 3.6 * cm], splitByRow=1)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#777777")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            remaining = table
            while remaining:
                available = max(self.y_position - min_y, 1)
                pieces = remaining.split(content_width, available)
                if not pieces:
                    new_page()
                    continue
                part = pieces[0]
                _, height = part.wrap(content_width, available)
                part.drawOn(c, 2 * cm, self.y_position - height)
                self.y_position -= height
                remaining = pieces[1] if len(pieces) > 1 else None
                if remaining:
                    new_page()
        finally:
            self.case_report = original

    def _draw_footer(self, c):
        """病例报告页脚只保留医生和诊所联系方式，不显示计价信息。"""
        current_y = self.margin + self.footer_height
        c.setFont(self.font_name, 12)

        doctor = self.data.get("主治医生") or self.data.get("医生", "")
        signoff = (
            f"审核：____________    核对：____________    "
            f"调配：____________    医师：{doctor}"
        )
        c.drawString(2 * cm, current_y, signoff)
        current_y -= 0.9 * cm

        contact = []
        if self.data.get("诊所地址"):
            contact.append(f"地址：{self.data['诊所地址']}")
        if self.data.get("诊所电话"):
            contact.append(f"电话：{self.data['诊所电话']}")
        if contact:
            c.setFont(self.font_name, 12)
            c.drawString(2 * cm, current_y, "    ".join(contact))


    def generate(self):
        self.data = self._fetch_data()
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        def draw_header():
            self.y_position = self.page_height - self.margin
            self._draw_page_header(c)

        def new_page():
            c.showPage()
            draw_header()

        draw_header()
        self._draw_case_report_content(c, new_page)
        self._draw_footer(c)

        c.save()
        buffer.seek(0)
        return buffer
