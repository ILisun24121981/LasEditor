import pandas as pd
import numpy as np
import re


class LasModel:
    """Модель (Model) — хранит состояние данных и бизнес-логику каротажного софта."""

    def __init__(self):
        self.df = None
        self.current_file_path = None
        self.null_value = -32768.0

    def set_data(self, df, file_path):
        """Обновляет текущие данные ГИС в модели."""
        self.df = df
        self.current_file_path = file_path
        self.null_value = df.attrs.get('null_value', -32768.0) if df is not None else -32768.0

    def has_data(self):
        return self.df is not None and not self.df.empty

    def trim(self, start_idx, end_idx):
        """Обрезает строки таблицы по индексам."""
        if not self.has_data():
            return 0
        old_count = len(self.df)
        self.df = self.df.iloc[start_idx:end_idx].reset_index(drop=True)
        return old_count

    def delete_columns(self, columns_to_delete):
        """Удаляет выбранные параметры каротажа из структуры."""
        if not self.has_data():
            return
        self.df.drop(columns=columns_to_delete, inplace=True)

    def apply_filter(self, settings):
        """Выполняет фильтрацию строк по логике И / ИЛИ."""
        if not self.has_data():
            return 0, ""

        target_cols = settings['columns']
        initial_rows = len(self.df)
        column_masks = []
        filter_log_name = ""

        for col in target_cols:
            col_series = pd.to_numeric(self.df[col], errors='coerce').to_numpy()
            if settings['filter_equal']:
                is_anomaly = np.isclose(col_series, settings['equal_value'], atol=1e-4, equal_nan=False)
                if np.isnan(settings['equal_value']):
                    is_anomaly |= np.isnan(col_series)
                column_masks.append(is_anomaly)
                filter_log_name = f"= {settings['equal_value']}"
            elif settings['filter_less']:
                column_masks.append(col_series < settings['less_value'])
                filter_log_name = f"< {settings['less_value']}"
            elif settings['filter_more']:
                column_masks.append(col_series > settings['more_value'])
                filter_log_name = f"> {settings['more_value']}"

        if settings['logic_and']:
            rows_to_remove = np.logical_and.reduce(column_masks)
        else:
            rows_to_remove = np.logical_or.reduce(column_masks)

        self.df = self.df[~rows_to_remove].reset_index(drop=True)
        return (initial_rows - len(self.df)), filter_log_name

    def find_column_by_pattern(self, pattern_str):
        """Ищет имя колонки в DataFrame по регулярному выражению без учета регистра."""
        if not self.has_data():
            return None
        compiled_re = re.compile(pattern_str, re.IGNORECASE)
        for col in self.df.columns:
            if compiled_re.search(col):
                return col
        return None

    def update_data_after_coef(self, filtered_df):
        """Обновляет внутренний DataFrame модели результатами фонового расчета."""
        self.df = filtered_df
