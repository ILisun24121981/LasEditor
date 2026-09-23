from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
                             QPushButton, QRadioButton, QButtonGroup, QDoubleSpinBox,
                             QListWidget, QDialogButtonBox)
from views.dialogs.variable_dialog import VariableManagerDialog


class FilterDialog(QDialog):
    """Специализированное представление (View) фильтрации каротажных кривых."""

    def __init__(self, all_columns, null_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Фильтрация каротажных кривых")
        self.setModal(True)
        self.resize(750, 450)
        self.all_columns = all_columns

        main_layout = QHBoxLayout(self)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.addWidget(QLabel("<b>Критерий очистки (Выбрать один):</b>"))

        h_layout_equal = QHBoxLayout()
        self.rb_filter_equal = QRadioButton("Фильтр =")
        self.dsb_equal_val = QDoubleSpinBox()
        self.dsb_equal_val.setRange(-999999999.0, 999999999.0)
        self.dsb_equal_val.setValue(float(null_value))
        self.dsb_equal_val.setDecimals(4)
        h_layout_equal.addWidget(self.rb_filter_equal)
        h_layout_equal.addWidget(self.dsb_equal_val)

        h_layout_less = QHBoxLayout()
        self.rb_filter_less = QRadioButton("Фильтр <")
        self.dsb_less_val = QDoubleSpinBox()
        self.dsb_less_val.setRange(-999999999.0, 999999999.0)
        self.dsb_less_val.setValue(0.0)
        self.dsb_less_val.setDecimals(4)
        self.dsb_less_val.setEnabled(False)
        h_layout_less.addWidget(self.rb_filter_less)
        h_layout_less.addWidget(self.dsb_less_val)

        h_layout_more = QHBoxLayout()
        self.rb_filter_more = QRadioButton("Фи自由_more")
        self.rb_filter_more = QRadioButton("Фильтр >")
        self.dsb_more_val = QDoubleSpinBox()
        self.dsb_more_val.setRange(-999999999.0, 999999999.0)
        self.dsb_more_val.setValue(0.0)
        self.dsb_more_val.setDecimals(4)
        self.dsb_more_val.setEnabled(False)
        h_layout_more.addWidget(self.rb_filter_more)
        h_layout_more.addWidget(self.dsb_more_val)

        self.rb_filter_equal.setChecked(True)

        self.radio_group = QButtonGroup(self)
        self.radio_group.addButton(self.rb_filter_equal)
        self.radio_group.addButton(self.rb_filter_less)
        self.radio_group.addButton(self.rb_filter_more)
        self.radio_group.buttonToggled.connect(self.update_inputs_state)

        left_layout.addLayout(h_layout_equal)
        left_layout.addLayout(h_layout_less)
        left_layout.addLayout(h_layout_more)
        left_layout.addStretch()
        main_layout.addWidget(left_container)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.addWidget(QLabel("<b>Целевые кривые для очистки:</b>"))

        logic_layout = QHBoxLayout()
        self.rb_logic_and = QRadioButton("Логика И")
        self.rb_logic_or = QRadioButton("Логика ИЛИ")
        self.rb_logic_and.setChecked(True)
        self.rb_logic_and.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.rb_logic_or.setStyleSheet("font-weight: bold; color: #2c3e50;")

        self.logic_group = QButtonGroup(self)
        self.logic_group.addButton(self.rb_logic_and)
        self.logic_group.addButton(self.rb_logic_or)

        logic_layout.addWidget(self.rb_logic_and)
        logic_layout.addWidget(self.rb_logic_or)
        logic_layout.addStretch()
        right_layout.addLayout(logic_layout)

        self.list_vars = QListWidget()
        right_layout.addWidget(self.list_vars)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_add.clicked.connect(self.add_variables)
        self.btn_del = QPushButton("Удалить")
        self.btn_del.clicked.connect(self.remove_variables)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        right_layout.addLayout(btn_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        right_layout.addWidget(self.button_box)
        main_layout.addWidget(right_container)

    def update_inputs_state(self):
        self.dsb_equal_val.setEnabled(self.rb_filter_equal.isChecked())
        self.dsb_less_val.setEnabled(self.rb_filter_less.isChecked())
        self.dsb_more_val.setEnabled(self.rb_filter_more.isChecked())

    def add_variables(self):
        current_items = [self.list_vars.item(i).text() for i in range(self.list_vars.count())]
        available_items = [col for col in self.all_columns if col not in current_items]
        if not available_items: return
        dialog = VariableManagerDialog("Добавить кривые для фильтрации", available_items, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_checked_items()
            for item in selected: self.list_vars.addItem(item)

    def remove_variables(self):
        current_items = [self.list_vars.item(i).text() for i in range(self.list_vars.count())]
        if not current_items: return
        dialog = VariableManagerDialog("Удалить кривые из обработки", current_items, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_checked_items()
            for item in selected:
                for i in range(self.list_vars.count()):
                    if self.list_vars.item(i).text() == item:
                        self.list_vars.takeItem(i)
                        break

    def get_filter_settings(self):
        columns_to_process = [self.list_vars.item(i).text() for i in range(self.list_vars.count())]
        return {
            'filter_equal': self.rb_filter_equal.isChecked(),
            'filter_less': self.rb_filter_less.isChecked(),
            'filter_more': self.rb_filter_more.isChecked(),
            'logic_and': self.rb_logic_and.isChecked(),
            'equal_value': self.dsb_equal_val.value(),
            'less_value': self.dsb_less_val.value(),
            'more_value': self.dsb_more_val.value(),
            'columns': columns_to_process
        }
