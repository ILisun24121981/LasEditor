import sys
from PyQt6.QtWidgets import QApplication
from models.las_model import LasModel
from views.main_window import MainWindow
from controllers.las_controller import LasController
from utils.settings import SettingsManager


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    initial_config = SettingsManager.load_config()
    if not initial_config:
        SettingsManager.save_config({"LasPath": ""})

    model = LasModel()
    view = MainWindow()
    controller = LasController(model, view)

    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
