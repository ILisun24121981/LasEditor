import pyqtgraph as pg
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal


class CustomViewBox(pg.ViewBox):
    """Кастомный ViewBox для реализации сфокусированного зума колесиком мыши."""

    def __init__(self, canvas_ref, parent=None):
        super().__init__(parent)
        self.canvas_ref = canvas_ref

    def wheelEvent(self, ev, axis=None):
        if ev.modifiers() in [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier]:
            ev.ignore()
            return

        if self.canvas_ref.x_min_limit is None or self.canvas_ref.x_max_limit is None:
            ev.ignore()
            return

        mask = self.state['mouseEnabled']
        if not any(mask):
            ev.accept()
            return

        pos = self.mapSceneToView(ev.scenePos())
        delta = ev.delta()
        factor = 0.85 if delta > 0 else 1.15

        self.scaleBy(s=(factor, factor), center=pos)

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
    """Компонент отрисовки каротажных диаграмм с MinMax-даунсемплингом, навигацией и маркерами."""

    # ДОБАВЛЕНО: Сигнал отправляет индекс строки в главное окно при установке маркера
    marker_placed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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

        # Хранилища для сырых валидных данных и их сквозных индексов
        self.raw_x_visual = None
        self.raw_y_visual = None
        self.raw_indices = None  # ДОБАВЛЕНО: Массив оригинальных индексов строк из DataFrame

        self.markers = []
        self.plot_widget.scene().sigMouseClicked.connect(self.on_scene_clicked)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def fast_downsample(self, x_raw, y_raw, indices_raw, start_idx, end_idx, target_bins=4000):
        """Высокоточный MinMax-даунсемплинг, сохраняющий оригинальные индексы строк таблицы."""
        n_points = end_idx - start_idx
        if n_points <= target_bins * 2 or target_bins < 2:
            return x_raw[start_idx:end_idx], y_raw[start_idx:end_idx], indices_raw[start_idx:end_idx]

        raw_bin_size = n_points // target_bins
        bin_size = max(2, (raw_bin_size // 2) * 2)

        actual_bins = n_points // bin_size
        if actual_bins <= 0:
            return x_raw[start_idx:end_idx], y_raw[start_idx:end_idx], indices_raw[start_idx:end_idx]

        has_tail = (n_points % bin_size) > 0
        total_bins = actual_bins + 1 if has_tail else actual_bins

        out_x = np.empty(total_bins * 2, dtype=np.float64)
        out_y = np.empty(total_bins * 2, dtype=np.float64)
        out_idx = np.empty(total_bins * 2, dtype=np.int64)  # ДОБАВЛЕНО: Массив выходных индексов

        for i in range(actual_bins):
            b_start = start_idx + i * bin_size
            b_end = b_start + bin_size
            y_sub = y_raw[b_start:b_end]

            local_min_idx = np.argmin(y_sub)
            local_max_idx = np.argmax(y_sub)
            min_idx = b_start + local_min_idx
            max_idx = b_start + local_max_idx

            if min_idx < max_idx:
                out_x[i * 2] = float(x_raw[min_idx])
                out_y[i * 2] = float(y_sub[local_min_idx])
                out_idx[i * 2] = indices_raw[min_idx]  # Сохраняем исходный индекс

                out_x[i * 2 + 1] = float(x_raw[max_idx])
                out_y[i * 2 + 1] = float(y_sub[local_max_idx])
                out_idx[i * 2 + 1] = indices_raw[max_idx]
            else:
                out_x[i * 2] = float(x_raw[max_idx])
                out_y[i * 2] = float(y_sub[local_max_idx])
                out_idx[i * 2] = indices_raw[max_idx]

                out_x[i * 2 + 1] = float(x_raw[min_idx])
                out_y[i * 2 + 1] = float(y_sub[local_min_idx])
                out_idx[i * 2 + 1] = indices_raw[min_idx]

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
                out_x[idx_dest] = float(x_raw[min_idx])
                out_y[idx_dest] = float(y_sub[local_min_idx])
                out_idx[idx_dest] = indices_raw[min_idx]

                out_x[idx_dest + 1] = float(x_raw[max_idx])
                out_y[idx_dest + 1] = float(y_sub[local_max_idx])
                out_idx[idx_dest + 1] = indices_raw[max_idx]
            else:
                out_x[idx_dest] = float(x_raw[max_idx])
                out_y[idx_dest] = float(y_sub[local_max_idx])
                out_idx[idx_dest] = indices_raw[max_idx]

                out_x[idx_dest + 1] = float(x_raw[min_idx])
                out_y[idx_dest + 1] = float(y_sub[local_min_idx])
                out_idx[idx_dest + 1] = indices_raw[min_idx]

        return out_x, out_y, out_idx

    def plot_curve(self, df, y_col, x_col):
        """Быстрая отрисовка каротажной кривой."""
        self.clear_all_markers()
        self.plot_widget.clear()

        if y_col in df.columns and x_col in df.columns:
            x_data = pd.to_numeric(df[x_col], errors='coerce').astype(float).to_numpy()
            y_data = pd.to_numeric(df[y_col], errors='coerce').astype(float).to_numpy()

            valid_mask = (x_data != -32768.0) & (y_data != -32768.0) & (y_data < 9999999999)

            # Сохраняем сырые массивы и массив их реальных индексов в pandas DataFrame
            self.raw_x_visual = x_data[valid_mask]
            self.raw_y_visual = y_data[valid_mask]
            self.raw_indices = np.arange(len(df))[valid_mask]  # ДОБАВЛЕНО: Индексы валидных строк

            if len(self.raw_x_visual) > 0:
                self.x_min_limit = float(np.min(self.raw_x_visual))
                self.x_max_limit = float(np.max(self.raw_x_visual))

                if self.x_min_limit == self.x_max_limit:
                    self.x_max_limit += 1.0

                # Запускаем даунсемплинг, пробрасывая массив индексов
                x_resampled, y_resampled, _ = self.fast_downsample(
                    self.raw_x_visual, self.raw_y_visual, self.raw_indices, start_idx=0, end_idx=len(self.raw_x_visual),
                    target_bins=4000
                )

                pen = pg.mkPen(color='#007acc', width=2)
                self.current_plot = self.plot_widget.plot(x_resampled, y_resampled, pen=pen, name=x_col)

                view_box = self.plot_widget.getViewBox()
                view_box.setRange(
                    xRange=(self.x_min_limit, self.x_max_limit),
                    yRange=(float(np.min(self.raw_y_visual)), float(np.max(self.raw_y_visual))),
                    padding=0.02
                )
            else:
                self.x_min_limit = None
                self.x_max_limit = None
                self.raw_x_visual = None
                self.raw_y_visual = None
                self.raw_indices = None

            self.plot_widget.setLabel('bottom', x_col, **self.label_style)
            self.plot_widget.setLabel('left', y_col, **self.label_style)

            plot_item = self.plot_widget.getPlotItem()
            plot_item.getAxis('left').enableAutoSIPrefix(True)
            plot_item.getAxis('bottom').enableAutoSIPrefix(True)

            view_box = self.plot_widget.getViewBox()
            if any(word in y_col.upper() for word in ['TIME', 'DEPT', 'DEPTH', 'ГЛУБ']):
                view_box.invertY(True)
            else:
                view_box.invertY(False)

    def on_scene_clicked(self, event):
        """Ловит клики мыши. Если зафиксирован двойной клик — синхронизирует таблицу."""
        if event.double():
            scene_pos = event.scenePos()
            view_box = self.plot_widget.getViewBox()
            plot_pos = view_box.mapSceneToView(scene_pos)
            click_x = plot_pos.x()

            if self.raw_x_visual is None or len(self.raw_x_visual) == 0:
                return

            x_range, _ = view_box.viewRange()
            threshold = (x_range[1] - x_range[0]) * 0.005

            for marker in self.markers:
                if abs(marker['x'] - click_x) <= threshold:
                    self.plot_widget.removeItem(marker['line'])
                    self.plot_widget.removeItem(marker['text'])
                    self.markers.remove(marker)
                    event.accept()
                    return

            closest_idx = np.argmin(np.abs(self.raw_x_visual - click_x))
            exact_x = self.raw_x_visual[closest_idx]
            exact_y = self.raw_y_visual[closest_idx]

            # ИСПРАВЛЕНО: Вытаскиваем точный оригинальный индекс строки из сохраненного массива
            original_table_row = self.raw_indices[closest_idx]

            line_pen = pg.mkPen(color='#e74c3c', width=1.5, style=Qt.PenStyle.DashLine)
            line = pg.InfiniteLine(pos=exact_x, angle=90, pen=line_pen, movable=False)
            self.plot_widget.addItem(line)

            x_str = f"{exact_x:.0f}" if exact_x > 1000000 else f"{exact_x:.4f}"
            label_text = f"X: {x_str}\nY: {exact_y:.4f}"

            text_item = pg.TextItem(text=label_text, color='#ffffff', anchor=(0, 1), fill='#2c3e50')
            text_item.setPos(exact_x, exact_y)
            self.plot_widget.addItem(text_item)

            self.markers.append({'line': line, 'text': text_item, 'x': exact_x})

            # ИСПРАВЛЕНО: Эмитим сигнал с индексом строки наружу, в основное окно
            self.marker_placed.emit(int(original_table_row))
            event.accept()

    def clear_all_markers(self):
        for marker in self.markers:
            self.plot_widget.removeItem(marker['line'])
            self.plot_widget.removeItem(marker['text'])
        self.markers.clear()

    def reset_zoom(self):
        if self.current_plot is not None:
            x_bounds = self.current_plot.dataBounds(0)
            y_bounds = self.current_plot.dataBounds(1)
            if x_bounds is not None and y_bounds is not None:
                view_box = self.plot_widget.getViewBox()
                view_box.setRange(xRange=x_bounds, yRange=y_bounds, padding=0.02)

    def wheelEvent(self, event):
        if self.x_min_limit is None or self.x_max_limit is None:
            event.ignore()
            return
        modifiers = event.modifiers()
        view_box = self.plot_widget.getViewBox()
        x_range, _ = view_box.viewRange()
        current_x_min, current_x_max = x_range
        current_width = current_x_max - current_x_min
        delta = event.angleDelta().y()
        if delta == 0: return

        step_factor = 0.1
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if delta > 0:
                shift_val = -current_width * step_factor
            else:
                shift_val = current_width * step_factor
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
        elif modifiers == Qt.KeyboardModifier.ShiftModifier:
            center = (current_x_min + current_x_max) / 2.0
            if delta > 0:
                new_width = current_width * (1.0 + step_factor)
            else:
                new_width = current_width * (1.0 - step_factor)
            total_limit_width = self.x_max_limit - self.x_min_limit
            if new_width > total_limit_width: new_width = total_limit_width
            new_min = center - new_width / 2.0
            new_max = center + new_width / 2.0
            if new_min < self.x_min_limit:
                new_min = self.x_min_limit
                new_max = new_min + new_width
            if new_max > self.x_max_limit:
                max_val = self.x_max_limit
                new_min = max_val - new_width
            view_box.setXRange(new_min, new_max, padding=0)
            event.accept()
        else:
            super().wheelEvent(event)
