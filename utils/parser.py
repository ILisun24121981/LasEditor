import os
import pandas as pd
import numpy as np
import re
import struct
from PyQt6.QtCore import QThread, pyqtSignal


class LasParseWorker(QThread):
    """Высокоскоростной фоновый поток для парсинга LAS-файлов в сыром виде."""
    finished_successfully = pyqtSignal(object)
    finished_with_error = pyqtSignal(str)

    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def run(self):
        try:
            skip_rows = 0
            raw_columns = []
            null_value = -32768.0

            with open(self.filename, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line in lines:
                clean_upper = line.strip().upper()
                if clean_upper.startswith('NULL') and 'NULL VALUE' in clean_upper:
                    try:
                        left_part = line.split(':')
                        match = re.search(r'(-?\d+\.\d+|-?\d+)', left_part)
                        if match: null_value = float(match.group(1))
                    except Exception: pass
                    break

            in_curve_section = False
            for i, line in enumerate(lines):
                clean_line = line.strip()
                if clean_line.upper().startswith('~C'):
                    in_curve_section = True
                    continue
                elif clean_line.upper().startswith('~') and in_curve_section:
                    in_curve_section = False

                if in_curve_section and clean_line and not clean_line.startswith('#'):
                    match_mnem = re.match(r'^([^\s:]+)', clean_line)
                    if match_mnem:
                        mnemonic = match_mnem.group(1).strip()
                        if mnemonic: raw_columns.append(mnemonic)

                if clean_line.upper().startswith('~A'):
                    skip_rows = i + 1
                    break

            if not raw_columns: raise ValueError("Не удалось считать имена кривых из секции ~Curve")

            columns = []
            counts = {}
            for col in raw_columns:
                if col in counts:
                    counts[col] += 1
                    columns.append(f"{col}_{counts[col]}")
                else:
                    counts[col] = 0
                    columns.append(col)

            df = pd.read_csv(self.filename, skiprows=skip_rows, sep=r'\s+', names=columns, engine='python')
            df.attrs['null_value'] = null_value
            self.finished_successfully.emit(df)
        except Exception as e:
            self.finished_with_error.emit(str(e))


class LasParser:
    """Класс для экспорта сырых ГИС-данных с точечным вырезанием удаленных кривых из заголовка."""

    @staticmethod
    def save(output_filename, df, original_filename):
        final_header_lines = []
        current_columns = [re.sub(r'_\d+$', '', col).strip().upper() for col in df.columns]
        written_mnemonics = set()

        # Дефолтная позиция двоеточия, если исходный файл не прочитан
        colon_position = 28

        if original_filename and os.path.exists(original_filename):
            try:
                with open(original_filename, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                # ШАГ 1: Сканируем оригинальные строки секции ~Curve
                scan_in_curve = False
                found_positions = []
                for line in lines:
                    cl = line.strip()
                    if cl.upper().startswith('~C'):
                        scan_in_curve = True
                        continue
                    elif cl.upper().startswith('~') and scan_in_curve:
                        scan_in_curve = False

                    # ИСПРАВЛЕНО: Используем rfind(':'), чтобы не цеплять двоеточие из UTC+0:00
                    if scan_in_curve and cl and not cl.startswith('#') and ':' in line:
                        found_positions.append(line.rfind(':'))

                if found_positions:
                    colon_position = max(found_positions)

                # ШАГ 2: Перенос заголовка с гарантированным сохранением отступа в 1 пробел слева
                in_curve_section = False
                for line in lines:
                    clean_line = line.strip()

                    if clean_line.upper().startswith('~C'):
                        in_curve_section = True
                        final_header_lines.append(line)
                        continue
                    elif clean_line.upper().startswith('~') and in_curve_section:
                        # Вставляем новые расчетные параметры строго с пробелом в начале перед выходом из секции
                        for col in df.columns:
                            pure_col = re.sub(r'_\d+$', '', col).strip().upper()
                            if pure_col not in written_mnemonics and pure_col in current_columns:
                                if not any(re.match(r'^' + re.escape(pure_col) + r'\b', l.strip()) for l in lines if
                                           '~C' not in l and not l.strip().startswith('#') and not l.strip().startswith(
                                                   '~')):
                                    left_part = f" {pure_col}."
                                    formatted_line = f"{left_part:<{colon_position}}: CALCULATED PARAMETER\n"
                                    final_header_lines.append(formatted_line)
                                    written_mnemonics.add(pure_col)
                        in_curve_section = False

                    if in_curve_section and clean_line and not clean_line.startswith('#'):
                        match_mnem = re.match(r'^([^\s:]+)', clean_line)
                        if match_mnem:
                            file_mnemonic = match_mnem.group(1).strip().upper()
                            if file_mnemonic not in current_columns:
                                continue
                            else:
                                written_mnemonics.add(file_mnemonic)

                    if clean_line.upper().startswith('~A'):
                        break

                    final_header_lines.append(line)
            except Exception:
                final_header_lines = ["~Version information\n", "VERS. 2.0:\n", "WRAP. NO:\n", "~Well information\n",
                                      "~Curve information\n"]
        else:
            final_header_lines = ["~Version information\n", "VERS. 2.0:\n", "WRAP. NO:\n", "~Well information\n",
                                  "~Curve information\n"]
        # Финальная проверка на случай, если секция ~Curve в оригинальном файле шла впритык к блоку ~A
        current_header_str = "".join(final_header_lines)
        if "~Curve" in current_header_str and "COEF" not in current_header_str.upper():
            insert_idx = len(final_header_lines)
            for idx, l in enumerate(final_header_lines):
                if l.strip().upper().startswith('~A'):
                    insert_idx = idx
                    break
            for col in df.columns:
                pure_col = re.sub(r'_\d+$', '', col).strip().upper()
                if pure_col not in written_mnemonics:
                    left_part = f" {pure_col}."
                    formatted_line = f"{left_part:<{colon_position}}: CALCULATED PARAMETER\n"
                    final_header_lines.insert(insert_idx, formatted_line)
                    insert_idx += 1
                    written_mnemonics.add(pure_col)

        # Выгрузка числовой матрицы ASCII
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.writelines(final_header_lines)
            f.write("~ASCII Log Data\n")

            null_val = df.attrs.get('null_value', -32768.0)
            for _, row in df.iterrows():
                row_strings = []
                for val in row:
                    if pd.isna(val):
                        row_strings.append(f"{float(null_val):>17.4f}")
                    else:
                        try:
                            num_val = float(val)
                            if num_val.is_integer():
                                row_strings.append(f"{int(num_val):>17}")
                            else:
                                row_strings.append(f"{num_val:>17.4f}")
                        except (ValueError, TypeError):
                            row_strings.append(f"{str(val):>17}")
                f.write("".join(row_strings) + "\n")

        return output_filename


class LasCoefWorker(QThread):
    """Высокоскоростной фоновый поток для вычисления коэффициента отношений и фильтрации аномалий."""
    status_msg = pyqtSignal(str)
    success = pyqtSignal(object, int)  # Сигнал передает (new_df, removed_rows_count)
    error = pyqtSignal(list)  # Сигнал передает список missing (ненайденных мнемоник)

    def __init__(self, model):
        super().__init__()
        self.model = model

    def run(self):
        try:
            self.status_msg.emit("Инициализация математического расчета коэффициента...")

            cu_col = self.model.find_column_by_pattern(r'CU_R')
            ut_col = self.model.find_column_by_pattern(r'UT_R')
            pwm_col = self.model.find_column_by_pattern(r'PWM')

            missing = []
            if not cu_col: missing.append("CU_R")
            if not ut_col: missing.append("UT_R")
            if not pwm_col: missing.append("PWM")

            if missing:
                self.error.emit(missing)
                return

            self.status_msg.emit(
                f"Целевые кривые ГИС успешно идентифицированы: CU_R->[{cu_col}], UT_R->[{ut_col}], PWM->[{pwm_col}]")
            self.status_msg.emit("Конвертация табличных серий в высокоскоростные массивы NumPy...")

            cu_rpm = pd.to_numeric(self.model.df[cu_col], errors='coerce').fillna(0).to_numpy()
            ut_rpm = pd.to_numeric(self.model.df[ut_col], errors='coerce').fillna(0).to_numpy()
            pwm = pd.to_numeric(self.model.df[pwm_col], errors='coerce').fillna(0).to_numpy()

            n = len(pwm)
            ratio = np.zeros(n, dtype=np.float64)
            valid_mask = np.zeros(n, dtype=bool)
            window_size = 50

            self.status_msg.emit(
                f"Запуск алгоритма скользящего окна (размер: {window_size} точек, всего: {n} строк матрицы)...")

            log_step = max(1, (n - window_size) // 4)

            for i in range(n - window_size + 1):
                if i % log_step == 0 and i > 0:
                    pct = int((i / (n - window_size)) * 100)
                    self.status_msg.emit(f"Математическая обработка скользящего окна: выполнено {pct}%...")

                pwm_window = pwm[i: i + window_size]

                if np.all(pwm_window == 0):
                    ut_sub = ut_rpm[i: i + window_size]
                    cu_sub = cu_rpm[i: i + window_size]

                    mean_ut = np.mean(ut_sub)
                    mean_cu = np.mean(cu_sub)

                    if mean_cu != 0 and mean_ut != 0:
                        rat = mean_cu / mean_ut
                        if 0 < rat < 1:
                            ratio[i] = rat
                            valid_mask[i] = True

            self.status_msg.emit("Вычисления завершены. Запущена векторная фильтрация строк деления на ноль...")

            initial_rows = len(self.model.df)

            new_df = self.model.df.copy()
            new_df['COEF'] = ratio
            new_df = new_df[valid_mask].reset_index(drop=True)

            removed_rows = initial_rows - len(new_df)

            self.status_msg.emit("Синхронизация обновленной координатной сетки с интерфейсом...")
            self.success.emit(new_df, removed_rows)

        except Exception as e:
            self.status_msg.emit(f"КРИТИЧЕСКИЙ СБОЙ В ПОТОКЕ ВЫЧИСЛЕНИЙ: {str(e)}")


class LasSaveCofWorker(QThread):
    """Фоновый высокоскоростной поток для бинарной упаковки данных ГИС в формат .cof."""
    status_msg = pyqtSignal(str)
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, filename, df, time_col):
        super().__init__()
        self.filename = filename
        self.df = df
        self.time_col = time_col

    def run(self):
        try:
            self.status_msg.emit("Инициализация бинарного экспортера формата .cof...")

            # Составляем список колонок данных (все, кроме времени)
            data_cols = [col for col in self.df.columns if col != self.time_col]
            n_data_fields = len(data_cols)

            self.status_msg.emit(
                f"Конфигурация кадра регистрации: 11 байт заголовок + {n_data_fields * 4} байт данных (float).")

            # Извлекаем данные в numpy-массивы для мгновенного доступа
            time_array = pd.to_numeric(self.df[self.time_col], errors='coerce').fillna(0).astype(np.uint64).to_numpy()

            data_matrix = []
            for col in data_cols:
                data_matrix.append(pd.to_numeric(self.df[col], errors='coerce').fillna(0).astype(np.float32).to_numpy())

            n_rows = len(self.df)
            self.status_msg.emit(f"Запуск посимвольной упаковки потока телеметрии (всего: {n_rows} кадров)...")

            log_step = max(1, n_rows // 4)

            # Структура заголовка (Head): uint8 (B), uint64 (Q), uint16 (H) -> Общий размер 1 + 8 + 2 = 11 байт
            header_struct = struct.Struct('<BQH')
            # Структура блока данных (Data): массив из N элементов float (f)
            data_struct = struct.Struct(f'<{n_data_fields}f')

            with open(self.filename, 'wb') as f:
                for i in range(n_rows):
                    # Пошаговое логирование прогресса каждые 25%
                    if i % log_step == 0 and i > 0:
                        pct = int((i / n_rows) * 100)
                        self.status_msg.emit(f"Сборка бинарного файла .cof: упаковано {pct}% кадров...")

                    # 1. Формируем заголовок кадра Head (flags=0, Time=время, timeStamp=0)
                    header_bytes = header_struct.pack(0, int(time_array[i]), 0)

                    # 2. Формируем блок данных (вытаскиваем строку float-значений)
                    row_floats = [data_matrix[j][i] for j in range(n_data_fields)]
                    data_bytes = data_struct.pack(*row_floats)

                    # Соединяем заголовок и данные в один непрерывный пакет для расчета CRC
                    packet_bytes = header_bytes + data_bytes

                    # 3. Расчет циклической контрольной суммы по вашему алгоритму
                    check_sum = 0
                    for byte in packet_bytes:
                        check_sum ^= byte
                        # Циклический сдвиг: сдвигаем влево на 7 бит и вправо на 1 бит, объединяя по OR (в рамках 8-битного байта)
                        check_sum = ((check_sum << 7) & 0xFF) | (check_sum >> 1)
                        if check_sum > 127:
                            check_sum ^= 0x3C

                    # Превращаем контрольную сумму в 1 байт
                    checksum_byte = bytes([check_sum & 0xFF])

                    # 4. Финальный разделитель кадра регистрации
                    tail_byte = b'\xFF'

                    # Записываем готовый упакованный кадр в файл
                    f.write(packet_bytes + checksum_byte + tail_byte)

            self.success.emit(self.filename)
        except Exception as e:
            self.error.emit(str(e))