from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QRadioButton, QDialogButtonBox


class TimeColumnSelectorDialog(QDialog):
    """Диалоговое окно для ручного выбора базовой колонки времени телеметрии."""

    def __init__(self, matches, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор временной оси")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>В структуре файла обнаружено несколько каналов времени:</b>"))
        layout.addWidget(QLabel("Укажите, какую кривую использовать в качестве базового времени кадра .cof:"))

        self.radio_buttons = []
        for i, col_name in enumerate(matches):
            rb = QRadioButton(col_name)
            if i == 0:
                rb.setChecked(True)  # Первая кнопка выбрана по умолчанию
            layout.addWidget(rb)
            self.radio_buttons.append(rb)

        buttons = QDialogButtonBox(QDialogButtonBox.ButtonRole.Ok | QDialogButtonBox.ButtonRole.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_column(self):
        """Возвращает имя кривой, выбранной пользователем."""
        for rb in self.radio_buttons:
            if rb.isChecked():
                return rb.text()
        return ""
