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

try:
    pdfmetrics.registerFont(TTFont("STHeitiLight", "/System/Library/Fonts/STHeiti Light.ttc"))
    CASE_NORMAL_FONT = "STHeitiLight"
except Exception:
    CASE_NORMAL_FONT = PreviewGenerator(1, 1).font_name


class CaseReportGenerator(PreviewGenerator):
    """在处方笺正文前增加完整病例报告内容。"""

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
                           诊断, 医嘱处方, 服药方法, 禁忌, 日期时间
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

    def _draw_page_header(self, c):
        """病例报告页眉：患者资料、独立地址行、电话和日期行。"""
        c.setLineWidth(1.2)
        c.rect(self.margin, self.margin,
               self.page_width - 2 * self.margin,
               self.page_height - 2 * self.margin)

        self.y_position -= 0.5 * cm
        c.setFont(self.font_name, 12)
        clinic_name = self.data.get("诊所名称", "")
        c.drawCentredString(self.page_width / 2, self.y_position,
                            " ".join(list(clinic_name)) if clinic_name else "")
        self.y_position -= 0.7 * cm

        c.setFont(self.font_name, 18)
        c.drawCentredString(self.page_width / 2, self.y_position, "病历记录")
        self.y_position -= 1.0 * cm

        c.setFont(self.font_name, 13)
        patient_line = (
            f"姓名：{self.data.get('姓名', '')}                  "
            f"性别：{self.data.get('性别', '')}                  "
            f"年龄：{self.data.get('年龄', '')}"
        )
        c.drawString(2 * cm, self.y_position, patient_line)
        record_label = "病历号："
        record_number = str(self.data.get("病历号", ""))
        total_width = c.stringWidth(record_label, self.font_name, 13) + c.stringWidth(record_number, self.font_name, 13)
        start_x = self.page_width - 2 * cm - total_width
        c.drawString(start_x, self.y_position, record_label)
        c.drawString(start_x + c.stringWidth(record_label, self.font_name, 13), self.y_position, record_number)
        self._draw_underline(c)
        self.y_position -= 1.0 * cm

        # 地址独立一行，不再与电话并排。
        address = self.data.get("地址") or self.data.get("住址", "")
        c.drawString(2 * cm, self.y_position, f"地址：{address}")
        self._draw_underline(c)
        self.y_position -= 1.0 * cm

        # 第三行只显示电话和日期，病例报告页眉不显示诊断。
        c.drawString(2 * cm, self.y_position, f"电话：{self.data.get('电话', '')}")
        c.drawRightString(self.page_width - 2 * cm, self.y_position,
                          f"日期：{self.data.get('日期时间', '')}")
        self._draw_underline(c)
        self.y_position -= 0.5 * cm

    def _draw_plain_sections(self, c, new_page, fields):
        """以无表格分区绘制报告正文，长内容自动换行且不互相覆盖。"""
        min_y = self.margin + self.footer_height
        content_width = self.page_width - 4 * cm
        label_style = ParagraphStyle(name="plain_label", fontName=self.font_name,
                                     fontSize=11, leading=15, alignment=TA_LEFT, wordWrap="CJK")
        value_style = ParagraphStyle(name="plain_value", fontName=CASE_NORMAL_FONT,
                                     fontSize=11, leading=15, alignment=TA_LEFT, wordWrap="CJK")

        def safe_text(value):
            return ("" if value is None else str(value)).replace("&", "&amp;").replace(
                "<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

        for label, value in fields:
            label_para = Paragraph(f"<b>{safe_text(label)}</b>", label_style)
            value_text = safe_text(value)
            if label == "医嘱处方(单位克)":
                value_text = value_text.replace(" ", "&#160;")
            value_para = Paragraph(value_text, value_style)

            for paragraph in (label_para, value_para):
                available = max(self.y_position - min_y, 1)
                _, height = paragraph.wrap(content_width, available)
                if self.y_position - height < min_y:
                    new_page()
                    available = max(self.y_position - min_y, 1)
                    _, height = paragraph.wrap(content_width, available)
                paragraph.drawOn(c, 2 * cm, self.y_position - height)
                self.y_position -= height
            # 每个区域之间留出空白，并画一条轻分隔线，不使用表格边框。
            self.y_position -= 0.18 * cm
            c.setStrokeColor(colors.HexColor("#b0b0b0"))
            c.setLineWidth(0.5)
            c.line(2 * cm, self.y_position, self.page_width - 2 * cm, self.y_position)
            self.y_position -= 0.28 * cm

    def _draw_case_report_content(self, c, new_page):
        fields = (
            ("主诉", self.case_report.get("主诉", "")),
            ("现病史", self.case_report.get("现病史", "")),
            ("既往史", self.case_report.get("既往史", "")),
            ("过敏史", self.case_report.get("过敏史", "")),
            ("个人史", self.case_report.get("个人史", "")),
            ("诊断", self.case_report.get("诊断", self.data.get("诊断", ""))),
            ("医嘱处方(单位克)", self._report_prescription()),
            ("服药方法", self.case_report.get("服药方法", "")),
            ("禁忌", self.case_report.get("禁忌", "")),
        )
        self._draw_plain_sections(c, new_page, fields)

    def _draw_case_report_table(self, c, new_page):
        """用两列表格绘制病例字段，内容单元格按文字长度自适应并自动分页。"""
        min_y = self.margin + self.footer_height
        content_width = self.page_width - 4 * cm
        fields = (
            ("主诉", self.case_report.get("主诉", "")),
            ("现病史", self.case_report.get("现病史", "")),
            ("既往史", self.case_report.get("既往史", "")),
            ("过敏史", self.case_report.get("过敏史", "")),
            ("个人史", self.case_report.get("个人史", "")),
            ("诊断", self.case_report.get("诊断", self.data.get("诊断", ""))),
            ("医嘱处方(单位克)", self._report_prescription()),
            ("服药方法", self.case_report.get("服药方法", "")),
            ("禁忌", self.case_report.get("禁忌", "")),
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
        """统一报告中的药物间距为五个空格，兼容旧记录的换行格式。"""
        value = (self.case_report.get("医嘱处方") or
                 self.case_report.get("重要处方") or self._prescription_text())
        value = str(value).strip()
        # 旧记录可能是一味一行或使用两个空格，统一为五个空格。
        value = re.sub(r"[\r\n]+", "     ", value)
        value = re.sub(r" {2,}", "     ", value)
        return value

    def _prescription_text(self):
        """从处方数据生成医嘱处方，药物之间使用两个空格。"""
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
        return "     ".join(medicines)

    def _draw_footer(self, c):
        """完整病例报告页脚，仅显示医生和诊所联系方式。"""
        current_y = self.margin + self.footer_height
        c.setFont(self.font_name, 12)
        if self.data.get("医生"):
            c.drawString(2 * cm, current_y, f"医生：{self.data['医生']}")
        if self.data.get("配药"):
            c.drawRightString(self.page_width - 2 * cm, current_y, f"配药：{self.data['配药']}")
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
            self._draw_footer(c)
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

    def _draw_case_report_content(self, c, new_page):
        original = self.case_report
        self.case_report = {
            "诊断": original.get("诊断", self.data.get("诊断", "")),
            "医嘱处方": original.get("医嘱处方", ""),
            "服药方法": original.get("服药方法", ""),
            "禁忌": original.get("禁忌", ""),
        }
        try:
            fields = (
                ("诊断", self.case_report.get("诊断", "")),
                ("医嘱处方(单位克)", self._report_prescription()),
                ("服药方法", self.case_report.get("服药方法", "")),
                ("禁忌事项", self.case_report.get("禁忌", "")),
            )
            self._draw_plain_sections(c, new_page, fields)
        finally:
            self.case_report = original

    def _draw_case_report_table(self, c, new_page):
        original = self.case_report
        self.case_report = {
            "诊断": original.get("诊断", self.data.get("诊断", "")),
            "医嘱处方": original.get("医嘱处方", ""),
            "服药方法": original.get("服药方法", ""),
            "禁忌": original.get("禁忌", ""),
        }
        try:
            # 只绘制诊断、医嘱处方、服药方法、禁忌，不显示病例叙述字段。
            min_y = self.margin + self.footer_height
            content_width = self.page_width - 4 * cm
            fields = (
                ("诊断", self.case_report.get("诊断", "")),
                ("医嘱处方(单位克)", self._report_prescription()),
                ("服药方法", self.case_report.get("服药方法", "")),
                ("禁忌事项", self.case_report.get("禁忌", "")),
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

        if self.data.get("医生"):
            c.drawString(2 * cm, current_y, f"医生：{self.data['医生']}")
        if self.data.get("配药"):
            c.drawRightString(self.page_width - 2 * cm, current_y,
                              f"配药：{self.data['配药']}")
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
            self._draw_footer(c)
            c.showPage()
            draw_header()

        draw_header()
        self._draw_case_report_content(c, new_page)
        self._draw_footer(c)

        c.save()
        buffer.seek(0)
        return buffer
