import pyqtgraph as pg
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt


class CustomViewBox(pg.ViewBox):
    """Кастомный ViewBox для реализации сфокусированного зума колесиком мыши."""

    def __init__(self, canvas_ref, parent=None):
        super().__init__(parent)
        self.canvas_ref = canvas_ref  # Ссылка на холст для доступа к лимитам данных

    def wheelEvent(self, ev, axis=None):
        # Если зажаты Ctrl или Shift, игнорируем встроенное событие и отдаем его холсту QWidget
        if ev.modifiers() in [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier]:
            ev.ignore()
            return

        # Проверяем лимиты строго через ссылку на холст self.canvas_ref
        if self.canvas_ref.x_min_limit is None or self.canvas_ref.x_max_limit is None:
            ev.ignore()
            return

        mask = self.state['mouseEnabled']
        if not any(mask):
            ev.accept()
            return

        # Получаем позицию курсора мыши в координатах графика из графической сцены
        pos = self.mapSceneToView(ev.scenePos())

        # Направление вращения без кнопок: от себя (delta > 0) приближает, на себя (delta < 0) отдаляет
        delta = ev.delta()
        factor = 0.85 if delta > 0 else 1.15

        # Масштабируем оси X и Y относительно точки, где стоит курсор
        self.scaleBy(s=(factor, factor), center=pos)

        # Проверяем и жестко зажимаем границы по оси X, чтобы не выйти за рамки первичных данных
        x_range, _ = self.viewRange()
        current_x_min, current_x_max = x_range
        current_width = current_x_max - current_x_min
        total_limit_width = self.canvas_ref.x_max_limit - self.canvas_ref.x_min_limit

        if current_width > total_limit_width:
            current_width = total_limit_width

        new_min = current_x_min
        new_max = current_x_min + current_width

        if new_min < self.canvas_ref.x_min_limit:
            new_min = self.canvas_ref.x_min_limit
            new_max = new_min + current_width
        if new_max > self.canvas_ref.x_max_limit:
            new_max = self.canvas_ref.x_max_limit
            new_min = new_max - current_width

        self.setXRange(new_min, new_max, padding=0)
        ev.accept()


class LasPlotCanvas(QWidget):
    """Компонент отрисовки каротажных диаграмм с MinMax-даунсемплингом и расширенной навигацией."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Создаем PlotWidget с использованием нашего кастомного CustomViewBox
        custom_view_box = CustomViewBox(canvas_ref=self)
        self.plot_widget = pg.PlotWidget(viewBox=custom_view_box)
        self.plot_widget.setMouseEnabled(x=True, y=True)

        self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        layout.addWidget(self.plot_widget)

        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        self.label_style = {'color': '#000000', 'font-size': '11pt', 'font-weight': 'bold'}
        self.current_plot = None

        self.x_min_limit = None
        self.x_max_limit = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def fast_downsample(self, x_raw, y_raw, start_idx, end_idx, target_bins=4000):
        """
        Высокоточный MinMax-даунсемплинг с гарантированным разделением типов данных
        осей X (время) и Y (коэффициенты) для исключения искажения масштаба.
        """
        n_points = end_idx - start_idx
        if n_points <= target_bins * 2 or target_bins < 2:
            return x_raw[start_idx:end_idx], y_raw[start_idx:end_idx]

        raw_bin_size = n_points // target_bins
        bin_size = max(2, (raw_bin_size // 2) * 2)

        actual_bins = n_points // bin_size
        if actual_bins <= 0:
            return x_raw[start_idx:end_idx], y_raw[start_idx:end_idx]

        has_tail = (n_points % bin_size) > 0
        total_bins = actual_bins + 1 if has_tail else actual_bins

        # ИСПРАВЛЕНО: Массив out_x наследует тип от x_raw (int64 для TIME.MS),
        # а массив out_y ОБЯЗАН наследовать тип от y_raw (float64 для COEF.).
        # Это полностью исключит искажение разрядов и масштаба мелких дробей.
        out_x = np.empty(total_bins * 2, dtype=x_raw.dtype)
        out_y = np.empty(total_bins * 2, dtype=y_raw.dtype)

        # 1. Основной цикл по всем полным окнам
        for i in range(actual_bins):
            b_start = start_idx + i * bin_size
            b_end = b_start + bin_size
            y_sub = y_raw[b_start:b_end]

            local_min_idx = np.argmin(y_sub)
            local_max_idx = np.argmax(y_sub)

            min_idx = b_start + local_min_idx
            max_idx = b_start + local_max_idx

            if min_idx < max_idx:
                out_x[i * 2] = x_raw[min_idx]
                out_y[i * 2] = y_sub[local_min_idx]
                out_x[i * 2 + 1] = x_raw[max_idx]
                out_y[i * 2 + 1] = y_sub[local_max_idx]
            else:
                out_x[i * 2] = x_raw[max_idx]
                out_y[i * 2] = y_sub[local_max_idx]
                out_x[i * 2 + 1] = x_raw[min_idx]
                out_y[i * 2 + 1] = y_sub[local_min_idx]

        # 2. Обработка финального остатка
        if has_tail:
            b_start = start_idx + actual_bins * bin_size
            b_end = end_idx
            y_sub = y_raw[b_start:b_end]

            local_min_idx = np.argmin(y_sub)
            local_max_idx = np.argmax(y_sub)

            min_idx = b_start + local_min_idx
            max_idx = b_start + local_max_idx

            idx_dest = actual_bins * 2
            if min_idx < max_idx:
                out_x[idx_dest] = x_raw[min_idx]
                out_y[idx_dest] = y_sub[local_min_idx]
                out_x[idx_dest + 1] = x_raw[max_idx]
                out_y[idx_dest + 1] = y_sub[local_max_idx]
            else:
                out_x[idx_dest] = x_raw[max_idx]
                out_y[idx_dest] = y_sub[local_max_idx]
                out_x[idx_dest + 1] = x_raw[min_idx]
                out_y[idx_dest + 1] = y_sub[local_min_idx]

        return out_x, out_y

    def plot_curve(self, df, y_col, x_col):
        """Быстрая отрисовка каротажной кривой с автоматическими множителями осей."""
        self.plot_widget.clear()

        if y_col in df.columns and x_col in df.columns:
            try:
                x_data = df[x_col].astype(float).to_numpy()
                y_data = df[y_col].astype(float).to_numpy()
            except Exception:
                x_data = pd.to_numeric(df[x_col], errors='coerce').to_numpy()
                y_data = pd.to_numeric(df[y_col], errors='coerce').to_numpy()

            valid_mask = (x_data != -32768.0) & (y_data != -32768.0) & (y_data < 9999999999)

            x_visual = x_data[valid_mask]
            y_visual = y_data[valid_mask]

            if len(x_visual) > 0:
                self.x_min_limit = float(np.min(x_visual))
                self.x_max_limit = np.max(x_visual)

                if self.x_min_limit == self.x_max_limit:
                    self.x_max_limit += 1.0

                x_resampled, y_resampled = self.fast_downsample(
                    x_visual, y_visual, start_idx=0, end_idx=len(x_visual), target_bins=4000
                )

                pen = pg.mkPen(color='#007acc', width=2)
                self.current_plot = self.plot_widget.plot(x_resampled, y_resampled, pen=pen, name=x_col)

                view_box = self.plot_widget.getViewBox()
                view_box.setRange(
                    xRange=(self.x_min_limit, self.x_max_limit),
                    yRange=(float(np.min(y_visual)), float(np.max(y_visual))),
                    padding=0.02
                )
            else:
                self.x_min_limit = None
                self.x_max_limit = None

            self.plot_widget.setLabel('bottom', x_col, **self.label_style)
            self.plot_widget.setLabel('left', y_col, **self.label_style)

            # Автоматическое определение SI-префиксов (возвращает e12 для TIME.MS и x0.001 / m для COEF.)
            plot_item = self.plot_widget.getPlotItem()
            plot_item.getAxis('left').enableAutoSIPrefix(True)
            plot_item.getAxis('bottom').enableAutoSIPrefix(True)

            # Настройка инверсии оси Y для глубин и времени
            view_box = self.plot_widget.getViewBox()
            if any(word in y_col.upper() for word in ['TIME', 'DEPT', 'DEPTH', 'ГЛУБ']):
                view_box.invertY(True)
            else:
                view_box.invertY(False)

    def wheelEvent(self, event):
        """Метод обработки прокрутки колесика мыши на уровне QWidget холста."""
        if self.x_min_limit is None or self.x_max_limit is None:
            event.ignore()
            return

        modifiers = event.modifiers()
        view_box = self.plot_widget.getViewBox()

        x_range, _ = view_box.viewRange()
        current_x_min, current_x_max = x_range
        current_width = current_x_max - current_x_min

        delta = event.angleDelta().y()
        if delta == 0:
            return

        step_factor = 0.1

        # СЦЕНАРИЙ 1: Нажат CTRL -> Прокрутка текущего графика влево/вправо
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if delta > 0:
                shift_val = -current_width * step_factor  # От себя -> ВЛЕВО
            else:
                shift_val = current_width * step_factor  # На себя -> ВПРАВО

            new_min = current_x_min + shift_val
            new_max = current_x_max + shift_val

            if new_min < self.x_min_limit:
                new_min = self.x_min_limit
                new_max = new_min + current_width
            if new_max > self.x_max_limit:
                new_max = self.x_max_limit
                new_min = new_max - current_width

            view_box.setXRange(new_min, new_max, padding=0)
            event.accept()

        # СЦЕНАРИЙ 2: Нажат SHIFT -> Масштабирование по оси X
        elif modifiers == Qt.KeyboardModifier.ShiftModifier:
            center = (current_x_min + current_x_max) / 2.0

            if delta > 0:
                # Вращение ОТ СЕБЯ (вверх) -> Знак поменян! Теперь график РАСТЯГИВАЕТСЯ по горизонтали
                new_width = current_width * (1.0 - step_factor)
            else:
                # Вращение НА СЕБЯ (вниз) -> Знак поменян! Теперь график СУЖАЕТСЯ по горизонтали
                new_width = current_width * (1.0 + step_factor)

            total_limit_width = self.x_max_limit - self.x_min_limit
            if new_width > total_limit_width:
                new_width = total_limit_width

            new_min = center - new_width / 2.0
            new_max = center + new_width / 2.0

            if new_min < self.x_min_limit:
                new_min = self.x_min_limit
                new_max = new_min + new_width
            if new_max > self.x_max_limit:
                new_max = self.x_max_limit
                new_min = new_max - new_width

            view_box.setXRange(new_min, new_max, padding=0)
            event.accept()
        else:
            super().wheelEvent(event)

    def reset_zoom(self):
        """Возвращает полномасштабный вид всех данных в строгих рамках ограничений."""
        if self.current_plot is not None:
            # Безопасное извлечение числовых границ для каждой оси
            x_bounds = self.current_plot.dataBounds(0)
            y_bounds = self.current_plot.dataBounds(1)

            if x_bounds is not None and y_bounds is not None:
                view_box = self.plot_widget.getViewBox()
                view_box.setRange(xRange=x_bounds, yRange=y_bounds, padding=0.02)
