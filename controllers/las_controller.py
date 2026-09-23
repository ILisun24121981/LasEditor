import os
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog
from utils.parser import LasParseWorker
from views.main_window import LasSaveWorker
from utils.settings import SettingsManager
from views.dialogs import TrimDialog, VariableManagerDialog, FilterDialog


class LasController:
    """Контроллер (Controller) — связывает Модель и Представление, управляет потоками ГИС."""

    def __init__(self, model, view):
        self.model = model
        self.view = view
        self._init_signals()

    def _init_signals(self):
        """Подписка на события графического интерфейса (View)."""
        self.view.btn_open.clicked.connect(self.open_file_dialog)
        self.view.btn_save.clicked.connect(self.save_file_dialog)
        self.view.btn_trim.clicked.connect(self.trim_data)
        self.view.btn_coef.clicked.connect(self.calculate_coefficient)
        self.view.btn_filter.clicked.connect(self.filter_data)
        self.view.btn_delete_col.clicked.connect(self.delete_columns)

        # СВЯЗЫВАНИЕ СИГНАЛОВ ПАНЕЛИ НАВИГАЦИИ С КОНТРОЛЛЕРОМ
        self.view.combo_nav_target.currentTextChanged.connect(self.update_nav_validator)
        self.view.btn_nav_go.clicked.connect(self.execute_navigation)

    def open_file_dialog(self):
        last_path = SettingsManager.get_last_path()
        init_dir = last_path if last_path and os.path.exists(last_path) else ""
        if not init_dir and last_path and os.path.exists(os.path.dirname(last_path)):
            init_dir = os.path.dirname(last_path)

        fp, _ = QFileDialog.getOpenFileName(self.view, "Открыть файл данных ГИС", init_dir, "LAS Files (*.las *.txt)")
        if fp:
            self.view.log_message(f"Запуск чтения файла: {os.path.basename(fp)}...")
            self.view.set_ui_loading_state(True)

            self.load_worker = LasParseWorker(fp)
            self.load_worker.finished_successfully.connect(lambda df: self.on_load_success(df, fp))
            self.load_worker.finished_with_error.connect(self.on_load_error)
            self.load_worker.start()

    def on_load_success(self, df, file_path):
        self.model.set_data(df, file_path)
        self.view.set_ui_loading_state(False)
        self.view.on_file_loaded_successfully(df, self.model.null_value)
        SettingsManager.set_last_path(file_path)

    def on_load_error(self, err_msg):
        self.view.set_ui_loading_state(False)
        self.view.log_message(f"ОШИБКА ЧТЕНИЯ: {err_msg}")
        QMessageBox.critical(self.view, "Ошибка чтения", f"Не удалось прочитать файл:\n{err_msg}")

    def save_file_dialog(self):
        if not self.model.has_data(): return
        dn, bn = os.path.split(self.model.current_file_path)
        np, ep = os.path.splitext(bn)
        while "_LasEditor" in np: np = np[:np.find("_LasEditor")]

        suffix_index = 0
        while True:
            suffix = "_LasEditor" if suffix_index == 0 else f"_LasEditor{suffix_index}"
            check_path = os.path.join(dn, f"{np}{suffix}{ep}")
            if not os.path.exists(check_path):
                default_path = check_path
                break
            suffix_index += 1

        fp, _ = QFileDialog.getSaveFileName(self.view, "Сохранить измененный LAS-файл", default_path,
                                            "LAS Files (*.las *.txt)")
        if fp:
            self.view.log_message(f"Запуск экспорта данных в файл: {os.path.basename(fp)}...")
            self.view.set_ui_loading_state(True)
            self.save_worker = LasSaveWorker(fp, self.model.df, self.model.current_file_path)
            self.save_worker.success.connect(self.on_save_success)
            self.save_worker.error.connect(self.on_save_error)
            self.save_worker.start()

    def on_save_success(self, saved_path):
        self.view.set_ui_loading_state(False)
        self.view.log_message(f"Экспорт выполнен успешно. Создан файл: {os.path.basename(saved_path)}")
        QMessageBox.information(self.view, "Успешное сохранение",
                                f"Данные сохранены в файл:\n\n{os.path.basename(saved_path)}")

    def on_save_error(self, err_msg):
        self.view.set_ui_loading_state(False)
        self.view.log_message(f"ОШИБКА СОХРАНЕНИЯ: {err_msg}")
        QMessageBox.critical(self.view, "Ошибка сохранения", f"Не удалось записать файл:\n{err_msg}")

    def trim_data(self):
        if not self.model.has_data(): return
        dialog = TrimDialog(len(self.model.df), self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            start_idx, end_idx = dialog.get_range()
            if start_idx >= end_idx:
                QMessageBox.warning(self.view, "Внимание", "Начальная строка должна быть меньше конечной.")
                return
            old_cnt = self.model.trim(start_idx, end_idx)
            self.view.log_message(f"Обрезка таблицы. Строк осталось: {len(self.model.df)} (было {old_cnt}).")
            self.view.refresh_display_data(self.model.df)

    def calculate_coefficient(self):
        if not self.model.has_data(): return

        self.view.log_message("Запуск фоновой математической обработки каротажных данных...")
        self.view.set_ui_loading_state(True)
        self.view.btn_coef.setEnabled(False)

        from utils.parser import LasCoefWorker
        self.coef_worker = LasCoefWorker(self.model)

        self.coef_worker.status_msg.connect(self.view.log_message)
        self.coef_worker.success.connect(self.on_coef_calculation_success)
        self.coef_worker.error.connect(self.on_coef_calculation_error)
        self.coef_worker.start()

    def on_coef_calculation_success(self, filtered_df, removed_count):
        self.model.update_data_after_coef(filtered_df)
        self.view.set_ui_loading_state(False)
        self.view.btn_coef.setEnabled(True)

        log_msg = (f"РАСЧЕТ ЗАВЕРШЕН УСПЕШНО. Из структуры LAS вырезано {removed_count} строк "
                   f"аномалий (деление на ноль / вне диапазона). Оставшийся массив: {len(self.model.df)} строк.")
        self.view.log_message(log_msg)

        QMessageBox.information(
            self.view,
            "Расчет и фильтрация завершены",
            f"Коэффициент успешно рассчитан!\n\n"
            f"Из загруженного LAS-файла автоматически удалено {removed_count} строк, "
            f"в которых произошло деление на ноль или значение вышло за границы (0, 1).\n"
            f"В таблицу добавлена колонка 'COEF'."
        )
        self.view.refresh_display_data(self.model.df)

    def on_coef_calculation_error(self, missing_list):
        self.view.set_ui_loading_state(False)
        self.view.btn_coef.setEnabled(True)

        missing_str = ", ".join(missing_list)
        self.view.log_message(f"ОШИБКА РАСЧЕТА: В заголовке/матрице отсутствуют обязательные параметры: {missing_str}")
        QMessageBox.warning(
            self.view,
            "Ошибка расчета",
            f"Невозможно рассчитать коэффициент.\nВ структуре файла отсутствуют параметры: {missing_str}\n\n"
            f"Проверьте правильность названий мнемоник."
        )

    def filter_data(self):
        if not self.model.has_data(): return
        dialog = FilterDialog(self.model.df.columns, self.model.null_value, self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_filter_settings()
            if not settings['columns']:
                QMessageBox.information(self.view, "Инфо", "Не выбрано ни одной переменной для фильтрации.")
                return

            logic_name = "И" if settings['logic_and'] else "ИЛИ"
            removed_rows, filter_log_name = self.model.apply_filter(settings)
            self.view.log_message(
                f"Фильтрация завершена. Логика [{logic_name}], критерий [{filter_log_name}]. Удалено строк: {removed_rows}. Осталось строк: {len(self.model.df)}.")
            self.view.refresh_display_data(self.model.df)

    def delete_columns(self):
        if not self.model.has_data(): return
        dialog = VariableManagerDialog("Удаление колонок из файла ГИС", list(self.model.df.columns), self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_cols = dialog.get_checked_items()
            if not selected_cols: return
            if len(selected_cols) >= len(self.model.df.columns):
                QMessageBox.warning(self.view, "Ошибка удаления", "Нельзя удалить все переменные.")
                return

            self.model.delete_columns(selected_cols)
            self.view.on_columns_deleted(selected_cols)
            self.view.log_message(
                f"Из структуры ГИС удалено кривых: {len(selected_cols)} ({', '.join(selected_cols)}).")
            self.view.refresh_display_data(self.model.df)

    def update_nav_validator(self, current_text):
        """Динамически меняет подсказку в поле ввода в зависимости от типа навигации."""
        if not self.model.has_data() or not current_text:
            return
        if current_text == "Строка":
            self.view.edit_nav_value.setText("1")
        else:
            # Если выбрана кривая, берем первую валидную строчку
            first_val = self.model.df[current_text].iloc[0]
            try:
                self.view.edit_nav_value.setText(f"{float(first_val):.4f}")
            except Exception:
                self.view.edit_nav_value.setText(str(first_val))

    def execute_navigation(self):
        """Выполняет высокоточный переход на строку или физическое значение кривой ГИС."""
        if not self.model.has_data():
            return

        target_type = self.view.combo_nav_target.currentText()
        input_str = self.view.edit_nav_value.text().strip().replace(',', '.')

        target_row_index = -1
        max_rows = len(self.model.df)

        if target_type == "Строка":
            try:
                row_num = int(input_str)
                if row_num < 1:
                    row_num = 1
                elif row_num > max_rows:
                    row_num = max_rows

                self.view.edit_nav_value.setText(str(row_num))
                target_row_index = row_num - 1
            except ValueError:
                QMessageBox.warning(self.view, "Ошибка ввода",
                                    "Пожалуйста, введите корректный номер строки (целое число).")
                return
        else:
            try:
                target_value = float(input_str)
                col_data = pd.to_numeric(self.model.df[target_type], errors='coerce').to_numpy()

                # Игнорируем маркеры отсутствия каротажа
                valid_indices = np.where(col_data != -32768.0)[0]
                if valid_indices.size == 0:
                    QMessageBox.information(self.view, "Навигация",
                                            "Выбранная кривая содержит только пустые значения NULL VALUE.")
                    return

                # Ищем строку с минимальной абсолютной разницей значений
                absolute_diff = np.abs(col_data[valid_indices] - target_value)
                best_valid_idx = np.argmin(absolute_diff)
                target_row_index = valid_indices[best_valid_idx]

                self.view.edit_nav_value.setText(f"{col_data[target_row_index]:.4f}")

            except ValueError:
                QMessageBox.warning(self.view, "Ошибка ввода",
                                    "Пожалуйста, введите корректное числовое значение параметра каротажа.")
                return

        # ЕСЛИ ИНДЕКС СТРОКИ ОПРЕДЕЛЕН — СКРОЛЛИМ ТАБЛИЦУ НА САМЫЙ ВЕРХ
        if target_row_index != -1:
            model_index = self.view.table_model.index(target_row_index, 0)
            if model_index.isValid():
                self.view.table.setCurrentIndex(model_index)
                # Позиционируем строку как самую верхнюю видимую строчку сетки
                self.view.table.scrollTo(model_index, self.view.table.ScrollHint.PositionAtTop)
                self.view.log_message(
                    f"Навигация: осуществлен переход на строку № {target_row_index + 1} по критерию [{target_type}].")
