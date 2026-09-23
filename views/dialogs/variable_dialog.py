from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QListWidget, QListWidgetItem, QDialogButtonBox
from PyQt6.QtCore import Qt


class VariableManagerDialog(QDialog):
    """Диалоговое окно добавления/удаления переменных с чекбоксом 'Выбрать все'."""

    def __init__(self, title, items_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(350, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите переменные из списка:"))

        self.cb_select_all = QCheckBox("Выбрать все")
        self.cb_select_all.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        self.cb_select_all.stateChanged.connect(self.toggle_select_all)
        layout.addWidget(self.cb_select_all)

        self.list_widget = QListWidget()
        for item in items_list:
            list_item = QListWidgetItem(item)
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(list_item)

        layout.addWidget(self.list_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def toggle_select_all(self, state):
        self.list_widget.blockSignals(True)
        target_state = Qt.CheckState.Checked if state == 2 else Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(target_state)
        self.list_widget.blockSignals(False)

    def get_checked_items(self):
        checked_items = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_items.append(item.text())
        return checked_items
