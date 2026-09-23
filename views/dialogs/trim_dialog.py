from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QDialogButtonBox


class TrimDialog(QDialog):
    """Представление для выбора диапазона строк при обрезке данных ГИС."""

    def __init__(self, max_rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обрезка данных по строкам")
        self.setModal(True)
        self.resize(300, 150)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Начальная строка:"))
        self.sb_start = QSpinBox()
        self.sb_start.setRange(1, max_rows)
        self.sb_start.setValue(1)
        layout.addWidget(self.sb_start)

        layout.addWidget(QLabel("Конечная строка:"))
        self.sb_end = QSpinBox()
        self.sb_end.setRange(1, max_rows)
        self.sb_end.setValue(max_rows)
        layout.addWidget(self.sb_end)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_range(self):
        return self.sb_start.value() - 1, self.sb_end.value()
