import sys
import logging
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Configuración de logs en consola
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    app = QApplication(sys.argv)
    
    # Creamos y mostramos la ventana principal de PySide6
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
