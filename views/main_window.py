import os
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QPushButton, QTableView, QVBoxLayout,
                             QHBoxLayout, QWidget, QListWidget, QLabel, QSplitter,
                             QProgressBar, QTextEdit, QDialog)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal
from views.canvas import LasPlotCanvas
from views.dialogs import VariableManagerDialog
from utils.parser import LasParser


class LasSaveWorker(QThread):
    """Фоновый поток для высокоскоростного сохранения LAS-файла без фризов UI."""
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, filename, df, original_filename):
        super().__init__()
        self.filename = filename
        self.df = df
        self.original_filename = original_filename

    def run(self):
        try:
            saved_path = LasParser.save(self.filename, self.df, self.original_filename)
            self.success.emit(saved_path)
        except Exception as e:
            self.error.emit(str(e))


class LasTableModel(QAbstractTableModel):
    """Высокопроизводительная виртуальная модель сетки для QTableView."""

    def __init__(self, df=None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole: return None
        if index.row() >= len(self._df) or index.column() >= len(self._df.columns): return ""
        val = self._df.iloc[index.row(), index.column()]
        try:
            return f"{float(val):.4f}"
        except (ValueError, TypeError):
            return str(val)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole: return None
        if orientation == Qt.Orientation.Horizontal and section < len(self._df.columns):
            return self._df.columns[section]
        elif orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    def update_dataframe(self, df):
        self.beginResetModel()
        self._df = df if df is not None else pd.DataFrame()
        self.endResetModel()


class MainWindow(QMainWindow):
    """Представление (View) — собирает компоненты UI и реагирует на обновление данных."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LasEditor — Редактор и анализатор LAS-файлов [MVC]")
        self.resize(1200, 850)
        self.table_model = LasTableModel()
        self.init_ui()
        self.log_message("Приложение LasEditor успешно запущено.")

    def init_ui(self):
        from PyQt6.QtWidgets import QFrame, QLineEdit, QComboBox  # Гарантируем импорт компонентов панели

        ms = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(ms)

        lw = QWidget()
        ll = QVBoxLayout(lw)

        self.btn_open = QPushButton("Открыть LAS-файл")
        self.btn_open.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; padding: 10px;")
        ll.addWidget(self.btn_open)

        self.btn_save = QPushButton("Сохранить изменения")
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet("background-color: #2ca02c; color: white; font-weight: bold; padding: 10px;")
        ll.addWidget(self.btn_save)

        self.btn_save_cof = QPushButton("Сохранить .cof")
        self.btn_save_cof.setEnabled(False)
        self.btn_save_cof.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; padding: 10px;")
        ll.addWidget(self.btn_save_cof)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        ll.addWidget(self.progress_bar)
        ll.addSpacing(10)

        lst_style = "QListWidget::item:selected{background:#007acc;color:white;} QListWidget::item:hover{background:#bae1ff;color:black;}"
        btn_action_style = "font-weight: bold; font-size: 9pt; padding: 3px;"

        widget_x = QWidget()
        layout_x = QVBoxLayout(widget_x)
        layout_x.setContentsMargins(0, 0, 0, 0)
        layout_x.addWidget(QLabel("Ось X графика:"))

        self.list_x = QListWidget()
        self.list_x.setStyleSheet(lst_style)
        layout_x.addWidget(self.list_x)

        tb_x = QHBoxLayout()
        self.btn_add_x = QPushButton("Добавить")
        self.btn_add_x.setEnabled(False)
        self.btn_add_x.setStyleSheet(btn_action_style)
        self.btn_add_x.clicked.connect(lambda: self.manage_variables('X', 'add'))
        self.btn_del_x = QPushButton("Удалить")
        self.btn_del_x.setEnabled(False)
        self.btn_del_x.setStyleSheet(btn_action_style)
        self.btn_del_x.clicked.connect(lambda: self.manage_variables('X', 'remove'))
        tb_x.addWidget(self.btn_add_x)
        tb_x.addWidget(self.btn_del_x)
        layout_x.addLayout(tb_x)
        ll.addWidget(widget_x)

        self.btn_plot = QPushButton("Отобразить")
        self.btn_plot.setEnabled(False)
        self.btn_plot.clicked.connect(self.update_graph)
        self.btn_plot.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 6px;")
        ll.addWidget(self.btn_plot)

        widget_y = QWidget()
        layout_y = QVBoxLayout(widget_y)
        layout_y.setContentsMargins(0, 0, 0, 0)
        layout_y.addWidget(QLabel("Ось Y графика:"))

        self.list_y = QListWidget()
        self.list_y.setStyleSheet(lst_style)
        layout_y.addWidget(self.list_y)

        tb_y = QHBoxLayout()
        self.btn_add_y = QPushButton("Добавить")
        self.btn_add_y.setEnabled(False)
        self.btn_add_y.setStyleSheet(btn_action_style)
        self.btn_add_y.clicked.connect(lambda: self.manage_variables('Y', 'add'))
        self.btn_del_y = QPushButton("Удалить")
        self.btn_del_y.setEnabled(False)
        self.btn_del_y.setStyleSheet(btn_action_style)
        self.btn_del_y.clicked.connect(lambda: self.manage_variables('Y', 'remove'))
        tb_y.addWidget(self.btn_add_y)
        tb_y.addWidget(self.btn_del_y)
        layout_y.addLayout(tb_y)
        ll.addWidget(widget_y)
        ms.addWidget(lw)
        rs = QSplitter(Qt.Orientation.Vertical)
        tc = QWidget()
        tl = QVBoxLayout(tc)
        tl.setContentsMargins(0, 0, 0, 0)

        tbl_tb = QHBoxLayout()
        self.btn_trim = QPushButton("Обрезать")
        self.btn_trim.setEnabled(False)
        self.btn_trim.setStyleSheet("font-weight: bold; padding: 5px 15px; background-color: #e67e22; color: white;")
        tbl_tb.addWidget(self.btn_trim)

        self.btn_coef = QPushButton("Коэффициент")
        self.btn_coef.setEnabled(False)
        self.btn_coef.setStyleSheet("font-weight: bold; padding: 5px 15px; background-color: #16a085; color: white;")
        tbl_tb.addWidget(self.btn_coef)

        self.btn_filter = QPushButton("Фильтр")
        self.btn_filter.setEnabled(False)
        self.btn_filter.setStyleSheet("font-weight: bold; padding: 5px 15px; background-color: #9b59b6; color: white;")
        tbl_tb.addWidget(self.btn_filter)

        self.btn_delete_col = QPushButton("Удалить")
        self.btn_delete_col.setEnabled(False)
        self.btn_delete_col.setStyleSheet(
            "font-weight: bold; padding: 5px 15px; background-color: #e74c3c; color: white;")
        tbl_tb.addWidget(self.btn_delete_col)
        tbl_tb.addStretch()
        tl.addLayout(tbl_tb)

        # СОЗДАЕМ ОБЩУЮ РАМКУ ВОКРУГ ТАБЛИЦЫ И КНОПКИ ПЕРЕХОДА
        self.table_frame = QFrame()
        self.table_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.table_frame.setFrameShadow(QFrame.Shadow.Sunken)
        self.table_frame.setStyleSheet("QFrame { border: 1px solid #ababab; background-color: white; }")

        frame_layout = QVBoxLayout(self.table_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self.table = QTableView()
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setModel(self.table_model)
        frame_layout.addWidget(self.table)

        # Нижняя серая панель управления быстрой навигацией
        nav_widget = QWidget()
        nav_widget.setStyleSheet(
            "QWidget { background-color: #f4f4f4; border-top: 1px solid #ababab; } QLabel, QComboBox, QLineEdit, QPushButton { border: none; background: transparent; }")
        nav_widget.setFixedHeight(35)
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(10, 0, 10, 0)
        nav_layout.setSpacing(10)

        nav_layout.addWidget(QLabel("<b>Перейти к:</b>"))

        self.combo_nav_target = QComboBox()
        self.combo_nav_target.setStyleSheet(
            "QComboBox { background-color: black; border: 1px solid #cccccc; padding: 2px 5px; min-width: 120px; }")
        self.combo_nav_target.addItem("Строка")
        nav_layout.addWidget(self.combo_nav_target)

        nav_layout.addWidget(QLabel("Значение:"))

        self.edit_nav_value = QLineEdit()
        self.edit_nav_value.setStyleSheet(
            "QLineEdit { background-color: white; border: 1px solid #cccccc; padding: 2px 5px; max-width: 150px; }")
        self.edit_nav_value.setText("1")
        nav_layout.addWidget(self.edit_nav_value)

        self.btn_nav_go = QPushButton("Перейти")
        self.btn_nav_go.setEnabled(False)
        self.btn_nav_go.setStyleSheet(
            "QPushButton { background-color: #34495e; color: white; font-weight: bold; padding: 3px 15px; border-radius: 2px; } QPushButton:hover { background-color: #2c3e50; } QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }")
        nav_layout.addWidget(self.btn_nav_go)

        nav_layout.addStretch()
        frame_layout.addWidget(nav_widget)

        tl.addWidget(self.table_frame)
        rs.addWidget(tc)

        # Оборачиваем холст графиков в контейнер QWidget для красивого отступа
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 15, 0, 0)

        self.canvas = LasPlotCanvas(self)
        canvas_layout.addWidget(self.canvas)
        rs.addWidget(canvas_container)

        gtc = QWidget()
        gtl = QHBoxLayout(gtc)
        gtl.setContentsMargins(0, 2, 0, 2)
        self.btn_reset_zoom = QPushButton("Сбросить зум")
        self.btn_reset_zoom.clicked.connect(self.canvas.reset_zoom)
        self.btn_reset_zoom.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        gtl.addWidget(self.btn_reset_zoom)
        gtl.addStretch()
        rs.addWidget(gtc)

        lc = QWidget()
        lcl = QVBoxLayout(lc)
        lcl.setContentsMargins(0, 5, 0, 0)
        lcl.addWidget(QLabel("Системный журнал (Лог):"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #f4f4f4; font-family: Consolas;")
        lcl.addWidget(self.log_area)
        rs.addWidget(lc)

        ms.addWidget(rs)
        ms.setSizes([250, 950])
        rs.setSizes([350, 350, 40, 110])

    def log_message(self, msg):
        if hasattr(self, 'log_area') and self.log_area is not None:
            self.log_area.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def set_ui_loading_state(self, is_loading):
        self.btn_open.setEnabled(not is_loading)
        has_data = hasattr(self, 'current_df') and self.current_df is not None
        active_state = not is_loading if has_data else False

        self.btn_trim.setEnabled(active_state)
        self.btn_coef.setEnabled(active_state)
        self.btn_filter.setEnabled(active_state)
        self.btn_delete_col.setEnabled(active_state)
        self.btn_save.setEnabled(active_state)
        self.btn_save_cof.setEnabled(active_state)  # ДОБАВЛЕНО
        self.btn_plot.setEnabled(active_state)
        self.progress_bar.setVisible(is_loading)
        if is_loading: self.progress_bar.setRange(0, 0)

    def on_file_loaded_successfully(self, df, null_value):
        """Срабатывает сразу после успешного чтения LAS-файла фоновым потоком."""
        self.current_df = df

        # Синяя кнопка "Отобразить" активируется графически
        self.btn_plot.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 6px;")

        # ИСПРАВЛЕНО: Полностью очищаем и заново наполняем списки доступных кривых для осей X и Y
        self.list_x.clear()
        self.list_y.clear()
        if not df.empty:
            for col in df.columns:
                self.list_x.addItem(col)
                self.list_y.addItem(col)

            # Фокусируем выбор на самых первых кривых, чтобы пользователю не нужно было кликать вслепую
            self.list_x.setCurrentRow(0)
            self.list_y.setCurrentRow(0)

        # Динамически наполняем выпадающий список быстрой навигации под таблицей
        self.combo_nav_target.clear()
        self.combo_nav_target.addItem("Строка")
        if not df.empty:
            for col in df.columns:
                self.combo_nav_target.addItem(col)
        self.edit_nav_value.setText("1")

        # Включаем все кнопки панели редактирования ГИС и панели графиков
        self.btn_trim.setEnabled(True)
        self.btn_coef.setEnabled(True)
        self.btn_filter.setEnabled(True)
        self.btn_delete_col.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.btn_save_cof.setEnabled(True)
        self.btn_plot.setEnabled(True)
        self.btn_nav_go.setEnabled(True)

        # Включаем кнопки ручного добавления/удаления переменных на оси
        self.btn_add_x.setEnabled(True)
        self.btn_del_x.setEnabled(True)
        self.btn_add_y.setEnabled(True)
        self.btn_del_y.setEnabled(True)

        self.log_message(f"Данные загружены. Строк: {len(df)}. Маркер пустоты: {null_value}")
        self.refresh_display_data(df)

    def refresh_display_data(self, df):
        self.current_df = df
        self.table_model.update_dataframe(df)
        self.table.viewport().update()

    def on_columns_deleted(self, deleted_cols):
        for col in deleted_cols:
            for i in range(self.list_x.count()):
                if self.list_x.item(i).text() == col: self.list_x.takeItem(i); break
            for i in range(self.list_y.count()):
                if self.list_y.item(i).text() == col: self.list_y.takeItem(i); break
        self.canvas.plot_widget.clear()

    def manage_variables(self, axis_name, mode):
        if not hasattr(self, 'current_df') or self.current_df is None: return
        target_list_widget = self.list_x if axis_name == 'X' else self.list_y
        existing_items = [target_list_widget.item(i).text() for i in range(target_list_widget.count())]

        if mode == 'add':
            title = f"Добавление переменных на Ось {axis_name}"
            available_items = [col for col in self.current_df.columns if col not in existing_items]
        else:
            title = f"Удаление переменных с Оси {axis_name}"
            available_items = existing_items

        if not available_items: return
        dialog = VariableManagerDialog(title, available_items, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = dialog.get_checked_items()
            if not selected_items: return

            if mode == 'add':
                for item in selected_items: target_list_widget.addItem(item)
                if target_list_widget.currentRow() == -1 and target_list_widget.count() > 0: target_list_widget.setCurrentRow(
                    0)
            else:
                for item in selected_items:
                    for i in range(target_list_widget.count()):
                        if target_list_widget.item(i).text() == item: target_list_widget.takeItem(i); break
                if target_list_widget.count() > 0: target_list_widget.setCurrentRow(0)

    def update_graph(self):
        x_item = self.list_x.currentItem()
        y_item = self.list_y.currentItem()
        if not x_item or not y_item:
            self.log_message("ВНИМАНИЕ: Выберите параметры перед построением.")
            return
        self.log_message(f"Отрисовка графика: X -> {x_item.text()}, Y -> {y_item.text()}")
        self.canvas.plot_curve(self.current_df, y_item.text(), x_item.text())