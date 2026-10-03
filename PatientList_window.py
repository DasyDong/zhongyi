import sys
import os
import shutil
from PySide6.QtCore import Qt, QEvent, QSize, QTimer
from PySide6.QtGui import (QPixmap, QColor, QTextCursor, QTextBlock,
                           QTextDocument, QSyntaxHighlighter, QTextCharFormat,
                           QAction, QFont, QIcon)
from PySide6.QtWidgets import (QDialog, QTableWidgetItem, QMessageBox,
                               QFileDialog, QTextEdit, QHBoxLayout, QVBoxLayout,
                               QLabel, QToolButton, QStyle, QApplication,
                               QPushButton, QLineEdit,
                               QScrollArea, QTableWidget, QHeaderView, QGroupBox)
from ui_PatientList import Ui_Dialog
import pymysql
from Database_connection import load_db_config
from PySide6.QtWidgets import QDialog, QScrollArea, QVBoxLayout, QLabel


class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, compare_text):
        super().__init__(parent)
        self.compare_text = compare_text.split('\n')
        self.format = QTextCharFormat()
        self.format.setBackground(QColor(255, 200, 200))

    def highlightBlock(self, text):
        line = self.currentBlock().blockNumber()
        if line < len(self.compare_text):
            if text != self.compare_text[line]:
                self.setFormat(0, len(text), self.format)

class ImageViewer(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片查看器")
        self.setGeometry(100, 100, 800, 600)

        # 创建滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)  # 允许滚动区域内的部件调整大小

        # 创建图片标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)  # 图片居中显示
        self.image_label.setScaledContents(False)  # 不自动缩放图片

        # 设置滚动区域的部件
        self.scroll_area.setWidget(self.image_label)

        # 设置布局
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

        # 加载图片
        self.pixmap = None
        self.scaled_pixmap = None  # 缓存缩放后的图片
        if image_path and os.path.exists(image_path):
            self.pixmap = QPixmap(image_path)
            if not self.pixmap.isNull():
                self.resize_image()  # 初始调整图片大小

        # 使用定时器延迟重绘，减少频繁缩放
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)  # 单次触发
        self.resize_timer.timeout.connect(self.resize_image)

    def resizeEvent(self, event):
        """窗口大小变化时，延迟调整图片大小"""
        super().resizeEvent(event)
        self.resize_timer.start(100)  # 延迟 100 毫秒执行重绘

    def resize_image(self):
        """调整图片大小以适应窗口，并保持居中"""
        if self.pixmap is None or self.pixmap.isNull():
            return

        # 获取滚动区域的大小
        scroll_size = self.scroll_area.size()
        scroll_width = scroll_size.width()
        scroll_height = scroll_size.height()

        # 获取图片的原始大小
        pixmap_width = self.pixmap.width()
        pixmap_height = self.pixmap.height()

        # 计算缩放比例
        width_ratio = scroll_width / pixmap_width
        height_ratio = scroll_height / pixmap_height
        scale_ratio = min(width_ratio, height_ratio)

        # 按比例缩放图片，使用平滑变换
        self.scaled_pixmap = self.pixmap.scaled(
            QSize(int(pixmap_width * scale_ratio), int(pixmap_height * scale_ratio)),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation  # 使用平滑变换
        )
        self.image_label.setPixmap(self.scaled_pixmap)

        # 设置 QLabel 的大小与缩放后的图片一致
        self.image_label.resize(self.scaled_pixmap.size())

        # 计算居中位置
        x = (scroll_width - self.scaled_pixmap.width()) // 2
        y = (scroll_height - self.scaled_pixmap.height()) // 2

        # 设置 QLabel 的位置
        self.image_label.move(x, y)


class ComparisonDialog(QDialog):
    def __init__(self, columns, data1, data2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("对比结果")
        self.resize(1000, 600)

        self.group_box = QGroupBox()
        self.group_box.setStyleSheet("""
            QGroupBox {
                background-color: rgba(169,208,107,155);
                border:1px solid rgb(190, 190, 190);
                border-radius:10px;
            }
            QGroupBox QWidget {
                font-size: 12pt;
                font-weight: bold;
            }
        """)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["对比项目", "比较对象：甲", "比较对象：乙"])
        self.table.setColumnWidth(0, 150)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

        self.table.setRowCount(len(columns))
        for row, (col_name, val1, val2) in enumerate(zip(columns, data1, data2)):
            # 设置对比项目列的内容
            item = QTableWidgetItem(col_name)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            self.table.setItem(row, 0, item)

            # 设置比较对象：甲列的内容
            item1 = QTableWidgetItem(val1 if val1 else "")
            item1.setFlags(item1.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            item1.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)  # 设置文本对齐方式
            item1.setFlags(item1.flags() | Qt.TextWordWrap)  # 启用文本自动换行
            self.table.setItem(row, 1, item1)

            # 设置比较对象：乙列的内容
            item2 = QTableWidgetItem(val2 if val2 else "")
            item2.setFlags(item2.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            item2.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)  # 设置文本对齐方式
            item2.setFlags(item2.flags() | Qt.TextWordWrap)  # 启用文本自动换行
            self.table.setItem(row, 2, item2)

            if val1 != val2:
                for col in [1, 2]:
                    self.table.item(row, col).setBackground(QColor(199, 237, 204))

        # 初始调整行高
        self.table.resizeRowsToContents()

        layout = QVBoxLayout(self.group_box)
        layout.addWidget(self.table)
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.group_box)
        self.setLayout(main_layout)

    def resizeEvent(self, event):
        """窗口大小变化时，重新调整行高"""
        super().resizeEvent(event)
        self.table.resizeRowsToContents()


class PatientListWindow(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.conn = None
        self.selected_rows = []  # 用于存储当前选中的行（支持两行选择）
        self.current_row = -1  # 用于存储当前单行选择的行
        os.makedirs("images", exist_ok=True)  # 确保图片目录存在

        self.headers = [
            "编号", "姓名", "病历号", "性别", "年龄", "身份证号", "日期时间", "患者照片",
            "诊断", "诊断拼音", "住址", "电话", "姓名拼音", "剂数", "针灸次数", "用法",
            "计价", "年龄月", "血压", "病证", "先煎后下1", "先煎后下2", "先煎后下3", "先煎后下4",
            "先煎后下5", "先煎后下6", "先煎后下7", "先煎后下8", "先煎后下9", "先煎后下10",
            "先煎后下11", "先煎后下12", "先煎后下13", "先煎后下14", "先煎后下15", "先煎后下16",
            "先煎后下17", "先煎后下18", "先煎后下19", "先煎后下20", "药物1", "药物2", "药物3",
            "药物4", "药物5", "药物6", "药物7", "药物8", "药物9", "药物10", "药物11", "药物12",
            "药物13", "药物14", "药物15", "药物16", "药物17", "药物18", "药物19", "药物20",
            "用量1", "用量2", "用量3", "用量4", "用量5", "用量6", "用量7", "用量8", "用量9",
            "用量10", "用量11", "用量12", "用量13", "用量14", "用量15", "用量16", "用量17",
            "用量18", "用量19", "用量20", "单价1", "单价2", "单价3", "单价4", "单价5", "单价6",
            "单价7", "单价8", "单价9", "单价10", "单价11", "单价12", "单价13", "单价14",
            "单价15", "单价16", "单价17", "单价18", "单价19", "单价20", "诊金", "药费",
            "针灸费用", "辨证", "总费用", "针灸或其他", "备注", "病证照片1", "病证照片2",
            "病证照片3", "病证照片4", "病证照片5", "主治医生"
        ]

        self.init_db()
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        self.m_tle_PatientList.setColumnHidden(0, True)
        visible_columns = [1, 6, 8, 19, 18, 103, 105, *range(40, 60), *range(60, 80), 106]
        for col in range(len(self.headers)):
            self.m_tle_PatientList.setColumnHidden(col, True)
        for col in visible_columns:
            self.m_tle_PatientList.setColumnHidden(col, False)
        header = self.m_tle_PatientList.horizontalHeader()
        header.swapSections(18, 19)
        self.load_data()

    def setup_connections(self):
        self.m_tle_PatientList.itemSelectionChanged.connect(self.on_selection_changed)
        self.m_edt_searchpatient.textChanged.connect(self.search_patient)
        self.m_bt_compare.clicked.connect(self.compare_patients)
        self.pic_labels = [getattr(self, f"label_SyndromePic_{i}") for i in range(1, 11)]
        for label in self.pic_labels:
            label.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseButtonDblClick and source in self.pic_labels:
            index = self.pic_labels.index(source) + 1
            self.handle_pic_upload(index)
            return True
        return super().eventFilter(source, event)

    def init_db(self):
        try:
            self.conn = pymysql.connect(**load_db_config())
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据库连接失败：{str(e)}")
            sys.exit(1)

    def load_data(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT * FROM 常规资料 ORDER BY 编号 DESC")
                results = cursor.fetchall()
                self.m_tle_PatientList.setRowCount(0)
                self.m_tle_PatientList.setColumnCount(len(self.headers))
                self.m_tle_PatientList.setHorizontalHeaderLabels(self.headers)

                for row_data in results:
                    row = self.m_tle_PatientList.rowCount()
                    self.m_tle_PatientList.insertRow(row)
                    for col, data in enumerate(row_data):
                        item_text = str(data) if data is not None else ""
                        item = QTableWidgetItem(item_text)
                        self.m_tle_PatientList.setItem(row, col, item)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载数据失败：{str(e)}")

    def on_selection_changed(self):
        selected = self.m_tle_PatientList.selectedItems()
        rows = list({item.row() for item in selected}) if selected else []

        if len(rows) == 1:
            # 单行选择：显示当前行的数据
            self.current_row = rows[0]
            self.selected_rows = []  # 清空双行选择
            self.update_single_display()
        elif len(rows) == 2:
            # 双行选择：保留原有功能
            self.selected_rows = sorted(rows, key=lambda r: int(self.m_tle_PatientList.item(r, 0).text()))
            self.current_row = -1  # 清空单行选择
            self.update_group_boxes()
        else:
            # 无选择或选择多行：清空显示
            self.clear_display()
            self.selected_rows = []
            self.current_row = -1

    def clear_display(self):
        for label in self.pic_labels:
            label.clear()
            if hasattr(label, 'mag_btn'):
                label.mag_btn.hide()
        for widget in [self.m_edt_CompareName_1, self.m_edt_diagnosis_1,
                       self.m_edt_sysmpt_1, self.m_edt_Analysis_1,
                       self.m_edt_CompareName_2, self.m_edt_diagnosis_2,
                       self.m_edt_sysmpt_2, self.m_edt_Analysis_2]:
            widget.clear()

    def update_single_display(self):
        if self.current_row == -1:
            return

        # 更新当前选中行的数据到第一组控件
        row = self.current_row
        self.m_edt_CompareName_1.setText(self.get_cell_text(row, 1))
        self.m_edt_diagnosis_1.setPlainText(self.get_cell_text(row, 8))
        self.m_edt_sysmpt_1.setPlainText(self.get_cell_text(row, 19))
        self.m_edt_Analysis_1.setPlainText(self.get_cell_text(row, 103))
        for i in range(5):
            self.load_pic(row, 107 + i, getattr(self, f"label_SyndromePic_{i + 1}"))

        # 清空第二组控件
        self.m_edt_CompareName_2.clear()
        self.m_edt_diagnosis_2.clear()
        self.m_edt_sysmpt_2.clear()
        self.m_edt_Analysis_2.clear()
        for i in range(5):
            label = getattr(self, f"label_SyndromePic_{i + 6}")
            label.clear()
            if hasattr(label, 'mag_btn'):
                label.mag_btn.hide()

    def update_group_boxes(self):
        if len(self.selected_rows) != 2:
            return

        # 更新第一个患者
        row = self.selected_rows[0]
        self.m_edt_CompareName_1.setText(self.get_cell_text(row, 1))
        self.m_edt_diagnosis_1.setPlainText(self.get_cell_text(row, 8))
        self.m_edt_sysmpt_1.setPlainText(self.get_cell_text(row, 19))
        self.m_edt_Analysis_1.setPlainText(self.get_cell_text(row, 103))
        for i in range(5):
            self.load_pic(row, 107 + i, getattr(self, f"label_SyndromePic_{i + 1}"))

        # 更新第二个患者
        row = self.selected_rows[1]
        self.m_edt_CompareName_2.setText(self.get_cell_text(row, 1))
        self.m_edt_diagnosis_2.setPlainText(self.get_cell_text(row, 8))
        self.m_edt_sysmpt_2.setPlainText(self.get_cell_text(row, 19))
        self.m_edt_Analysis_2.setPlainText(self.get_cell_text(row, 103))
        for i in range(5):
            self.load_pic(row, 107 + i, getattr(self, f"label_SyndromePic_{i + 6}"))

    def get_cell_text(self, row, col):
        item = self.m_tle_PatientList.item(row, col)
        return item.text().strip() if item else ""

    def load_pic(self, row, col, label):
        item = self.m_tle_PatientList.item(row, col)
        path = item.text().strip() if item else ""

        # 清空 QLabel 和放大镜按钮
        label.clear()
        if hasattr(label, 'mag_btn'):
            label.mag_btn.hide()  # 隐藏放大镜按钮

        # 如果路径为空或文件不存在，直接返回
        if not path or not os.path.exists(path):
            return

        # 加载图片
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return

        # 缩放图片并显示
        scaled_pixmap = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)

        # 添加或更新放大镜按钮
        if not hasattr(label, 'mag_btn'):
            btn = QToolButton(label)
            btn.setIcon(QIcon(":/Resources/icons/icon_search.svg"))  # 使用放大镜图标
            btn.setStyleSheet("background-color: rgba(255, 255, 255, 150); border-radius: 8px;")
            btn.setIconSize(QSize(16, 16))
            btn.setFixedSize(20, 20)
            btn.clicked.connect(lambda: self.show_enlarged_image(path))  # 绑定最新路径
            btn.move(label.width() - 25, 5)
            btn.show()
            label.mag_btn = btn
        else:
            # 更新放大镜按钮的点击事件绑定到最新路径
            label.mag_btn.clicked.disconnect()  # 断开旧的绑定
            label.mag_btn.clicked.connect(lambda: self.show_enlarged_image(path))  # 绑定最新路径
            label.mag_btn.show()

    def show_enlarged_image(self, image_path):
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "错误", "图片文件不存在")
            return

        viewer = ImageViewer(image_path, self)  # 将 self 作为父窗口传递
        viewer.show()  # 使用 show() 而不是 exec()，使其作为非模态窗口显示

    def search_patient(self):
        search_text = self.m_edt_searchpatient.text().lower()

        for row in range(self.m_tle_PatientList.rowCount()):
            match_found = False
            for col in range(self.m_tle_PatientList.columnCount()):
                item = self.m_tle_PatientList.item(row, col)
                if item and search_text in item.text().lower():
                    match_found = True
                    break

            self.m_tle_PatientList.setRowHidden(row, not match_found)

    def handle_pic_upload(self, index):
        if self.current_row == -1 and len(self.selected_rows) != 2:
            QMessageBox.warning(self, "提示", "请先选择患者")
            return

        # 确定要更新的患者和起始偏移量
        if 1 <= index <= 5:
            row_idx = self.current_row if self.current_row != -1 else self.selected_rows[0]
            start_offset = index - 1  # 转换为0-4的偏移量
        elif 6 <= index <= 10:
            if len(self.selected_rows) != 2:
                QMessageBox.warning(self, "提示", "请选择两行患者")
                return
            row_idx = self.selected_rows[1]
            start_offset = index - 6  # 转换为0-4的偏移量
        else:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "选择病证照片", "",
            "图片文件 (*.png *.jpg *.jpeg);;所有文件 (*)"
        )

        if not files:
            return
        if len(files) > 5:
            QMessageBox.warning(self, "提示", "最多只能选择5张照片")
            return

        try:
            with self.conn.cursor() as cursor:
                patient_id = self.get_cell_text(row_idx, 0)
                if not patient_id:
                    raise ValueError("无效的患者ID")

                success_count = 0
                for i, file_path in enumerate(files[:5]):
                    # 文件大小校验
                    if os.path.getsize(file_path) > 200 * 1024:
                        QMessageBox.warning(self, "错误", f"图片 {os.path.basename(file_path)} 大小超过200KB")
                        continue

                    # 计算当前列（核心修改点）
                    current_col = 107 + (start_offset + i) % 5  # 通过取模实现循环覆盖

                    # 保存图片到相对路径
                    filename = f"patient_{patient_id}_syndrome_{(start_offset + i) % 5 + 1}{os.path.splitext(file_path)[1]}"
                    save_path = os.path.join("images", filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    shutil.copy(file_path, save_path)

                    # 更新数据库（根据需求选择存储路径或二进制数据）
                    cursor.execute(
                        f"UPDATE 常规资料 SET {self.headers[current_col]}=%s WHERE 编号=%s",
                        (save_path, patient_id)  # 或改为存储二进制数据
                    )

                    # 更新表格
                    item = self.m_tle_PatientList.item(row_idx, current_col)
                    if item:
                        item.setText(save_path)
                        success_count += 1
                    else:
                        print(f"警告：未找到行{row_idx}列{current_col}的单元格")

                self.conn.commit()
                if self.current_row != -1:
                    self.update_single_display()
                elif len(self.selected_rows) == 2:
                    self.update_group_boxes()
                QMessageBox.information(self, "成功", f"已成功上传{success_count}张照片")
        except Exception as e:
            self.conn.rollback()
            QMessageBox.warning(self, "错误", f"更新失败：{str(e)}")

    def compare_patients(self):
        if len(self.selected_rows) != 2:
            QMessageBox.warning(self, "提示", "请选择两行进行比较")
            return

        col_names, data1 = self.get_compare_data(self.selected_rows[0])
        _, data2 = self.get_compare_data(self.selected_rows[1])
        dlg = ComparisonDialog(col_names, data1, data2, self)
        dlg.exec()

    def get_compare_data(self, row):
        compare_columns = [
            (1, "姓名"), (8, "诊断"), (19, "病证"), (18, "血压"),
            (103, "辨证"), (105, "针灸或其他"),
            *[(i, f"药物{i-39}") for i in range(40, 60)],
            *[(i, f"用量{i-59}") for i in range(60, 80)],
            (106, "备注")
        ]
        values = [self.get_cell_text(row, col) for col, _ in compare_columns]
        return [name for _, name in compare_columns], values

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
        event.accept()


class PatientViewerWindow(QDialog):
    """查看患者：基础资料列表及病例详情、病例报告、处方报告入口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("查看患者")
        self.resize(1200, 700)
        self.conn = None
        self.detail_windows = []

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("查询："))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("输入病例号、姓名、性别、年龄、住址查询")
        toolbar.addWidget(self.search_edit)
        toolbar.addStretch()
        self.new_patient_button = QPushButton("新增患者", self)
        self.new_patient_button.setObjectName("primarySaveButton")
        self.new_patient_button.setStyleSheet(
            "QPushButton { background: #1976d2; color: white; padding: 6px 16px; "
            "border: 1px solid #125aa0; border-radius: 4px; }"
            "QPushButton:hover { background: #1565c0; }"
        )
        toolbar.addWidget(self.new_patient_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(self)
        self.headers = ["ID主键号", "病例号", "姓名", "性别", "年龄", "住址", "创建时间",
                        "病例详情", "复诊", "病例报告", "处方报告", "删除"]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(10 * 30)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.search_edit.textChanged.connect(self.filter_rows)
        self.new_patient_button.clicked.connect(self.open_new_patient)
        self.init_db()
        self.load_data()

    def init_db(self):
        try:
            self.conn = pymysql.connect(**load_db_config())
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据库连接失败：{e}")
            self.close()

    def load_data(self):
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 编号, 病历号, 姓名, 性别, 年龄, 住址, 日期时间
                    FROM 常规资料 ORDER BY 编号 DESC
                """)
                rows = cursor.fetchall()
            self.table.setRowCount(0)
            for patient_id, case_number, name, gender, age, address, created_at in rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [patient_id, case_number, name, gender, age, address, created_at]
                for col, value in enumerate(values):
                    item = QTableWidgetItem("" if value is None else str(value))
                    if col == 0:
                        # 第一列直接显示数据库主键，所有操作仍使用该主键。
                        item.setData(Qt.UserRole, patient_id)
                    self.table.setItem(row, col, item)

                self._add_action_button(row, 7, "病例详情",
                                        lambda checked=False, pid=patient_id: self.open_detail(pid))
                self._add_action_button(row, 8, "复诊",
                                        lambda checked=False, pid=patient_id: self.open_followup(pid))
                self._add_action_button(row, 9, "病例报告",
                                        lambda checked=False, pid=patient_id: self.open_report(pid, False))
                self._add_action_button(row, 10, "处方报告",
                                        lambda checked=False, pid=patient_id: self.open_report(pid, True))
                self._add_action_button(row, 11, "删除",
                                        lambda checked=False, pid=patient_id: self.delete_patient(pid))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"患者列表加载失败：{e}")

    def _add_action_button(self, row, col, text, slot):
        button = QPushButton(text, self.table)
        button.setStyleSheet(
            "QPushButton { background: #1976d2; color: white; padding: 4px 12px; "
            "border: 1px solid #125aa0; border-radius: 4px; }"
            "QPushButton:hover { background: #1565c0; }"
            "QPushButton:pressed { background: #0d47a1; }"
        )
        button.clicked.connect(slot)
        self.table.setCellWidget(row, col, button)

    def filter_rows(self, text):
        keyword = text.strip().lower()
        for row in range(self.table.rowCount()):
            matched = not keyword
            for col in range(7):
                item = self.table.item(row, col)
                if item and keyword in item.text().lower():
                    matched = True
                    break
            self.table.setRowHidden(row, not matched)

    def open_detail(self, patient_id):
        """打开与主界面一致的完整患者详情，并填充全部字段。"""
        try:
            self._open_patient_window(patient_id)
        except Exception as e:
            QMessageBox.critical(self, "病例详情", f"打开病例详情失败：{e}")

    def _open_patient_window(self, patient_id=None):
        """复用原主界面；传入患者编号时先完整载入该患者资料。"""
        from main_window_system import MyMainWindow

        parent_window = self.parent()
        reuse_parent = isinstance(parent_window, MyMainWindow)
        window = parent_window if reuse_parent else MyMainWindow(parent_window.current_user_id)
        if patient_id is not None:
            patient_id = str(patient_id)
            window._active_patient_id = patient_id

            # 不依赖新窗口列表的加载时机，直接按数据库主键加载完整患者资料。
            data = window.m_databaseUtil.query_database_info(
                """SELECT 姓名,性别,年龄,病证,诊断,血压,住址,电话,病历号,身份证号
                   FROM 常规资料 WHERE 编号 = %s""",
                patient_id,
            )
            if data is None:
                raise ValueError(f"未找到编号为 {patient_id} 的患者记录")
            window.display_patient_info(data)
            window.query_and_fill_data(patient_id)
            window.load_case_report(patient_id)

            # 同步主界面左侧查询表格的当前行，保证保存、复诊等操作使用该患者。
            for row in range(window.m_tle_Basic_Filter.rowCount()):
                item = window.m_tle_Basic_Filter.item(row, 0)
                if item and item.text().strip() == patient_id:
                    window.m_tle_Basic_Filter.setCurrentCell(row, 1)
                    window.m_tle_Basic_Filter.selectRow(row)
                    break
        window.showMaximized()
        if reuse_parent:
            # 本窗口由 exec() 打开，必须结束弹窗事件循环，否则原主窗口仍被模态阻塞。
            self.accept()
        else:
            self.detail_windows.append(window)
            self.hide()
        if patient_id is not None and not reuse_parent:
            # MyMainWindow 构造函数会默认选中查询列表第一行。延迟到事件循环
            # 完成后再次回填，避免默认行覆盖从“查看患者”传入的目标患者。
            QTimer.singleShot(
                0,
                lambda w=window, pid=str(patient_id):
                    self._force_patient_selection(w, pid),
            )
        return window

    def _force_patient_selection(self, window, patient_id):
        """在主界面完成显示后，强制保持查看患者传入的患者。"""
        try:
            item = None
            for row in range(window.m_tle_Basic_Filter.rowCount()):
                candidate = window.m_tle_Basic_Filter.item(row, 0)
                if candidate and candidate.text().strip() == str(patient_id):
                    item = candidate
                    window.m_tle_Basic_Filter.setCurrentCell(row, 1)
                    window.m_tle_Basic_Filter.selectRow(row)
                    break
            if item is None:
                raise ValueError(f"病例查询列表中未找到患者编号 {patient_id}")

            # 显式调用原有加载函数，确保基础资料、处方和病例报告全部以
            # 当前点击的患者为准，而不是依赖表格信号的触发顺序。
            window.on_row_basic_filter_click(item)
        except Exception as e:
            QMessageBox.critical(self, "病例详情", f"加载当前患者失败：{e}")

    def open_new_patient(self):
        """新增患者：复用主界面原有的初诊逻辑。"""
        try:
            window = self._open_patient_window()
            window.handle_firstvisit_click()
        except Exception as e:
            QMessageBox.critical(self, "新增患者", f"打开新增患者界面失败：{e}")

    def open_followup(self, patient_id):
        """复诊：先载入原患者全部资料，再复用主界面原有复诊逻辑。"""
        try:
            window = self._open_patient_window(patient_id)
            window.handle_secondvisit_click()
        except Exception as e:
            QMessageBox.critical(self, "复诊", f"打开复诊界面失败：{e}")

    def open_report(self, patient_id, prescription_only):
        try:
            from CaseReportGenerator import (CaseReportGenerator,
                                              PrescriptionReportGenerator)
            generator_cls = PrescriptionReportGenerator if prescription_only else CaseReportGenerator
            generator = generator_cls(patient_id, self.parent().current_user_id)
            pdf_data = generator.generate().getvalue()
            from PdfViewerDialog import PdfViewerDialog
            viewer = PdfViewerDialog(pdf_data, self)
            viewer.exec()
        except Exception as e:
            QMessageBox.critical(self, "报告", f"生成报告失败：{e}")

    def delete_patient(self, patient_id):
        """删除患者整条常规资料记录。"""
        row = next((r for r in range(self.table.rowCount())
                    if not self.table.isRowHidden(r)
                    and self.table.item(r, 0)
                    and self.table.item(r, 0).data(Qt.UserRole) == patient_id), None)
        name = self.table.item(row, 1).text() if row is not None else ""
        answer = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除患者“{name}”的全部资料吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("DELETE FROM `常规资料` WHERE `编号`=%s", (patient_id,))
            self.conn.commit()
            self.load_data()
            QMessageBox.information(self, "删除成功", "患者资料已删除")
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "删除失败", f"删除患者资料失败：{e}")

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
        event.accept()
