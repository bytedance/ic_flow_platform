import argparse
import os
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QSizePolicy
from PyQt5.QtGui import QFont, QMovie
from PyQt5.QtCore import Qt, QTimer, QSize


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-m', '--message',
                        default="Loading, please wait",
                        help='This is an example argument.')

    args = parser.parse_args()

    return args


class Counter:
    def __init__(self, reset_value=10):
        self.count = 0
        self.reset_value = reset_value

    def increment(self):
        self.count += 1
        if self.count >= self.reset_value:
            self.count = 0

    def get_count(self):
        return self.count


class WaitingWindow(QWidget):
    def __init__(self, message="Loading, please wait"):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(200, 200)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        self.layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel(self)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setAlignment(Qt.AlignCenter)

        self.movie = QMovie(f"{os.getenv('IFP_INSTALL_PATH')}/data/pictures/office/loading_bytedance.gif")
        self.movie.setScaledSize(QSize(200, 200))
        self.label.setMovie(self.movie)
        self.movie.start()

        self.text = message
        self.current_text = ""
        self.text_index = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_text)
        self.timer.start(20)

        self.text_label = QLabel(self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setFont(QFont("Arial", 10))
        self.text_label.setStyleSheet("""
            QLabel {
                background-color: #4169E1;
                color: white;
                font-weight: bold;
            }
        """)
        self.text_label.setFixedWidth(150)

        self.counter = Counter()
        self.layout.addStretch()
        self.layout.addWidget(self.label, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.text_label, alignment=Qt.AlignCenter)
        self.layout.addStretch()
        self.setLayout(self.layout)

    def update_text(self):
        self.counter.increment()

        if self.counter.get_count() == 9:
            pass
        else:
            return

        if self.text_index < len(self.text):
            self.text_index += 1
            self.current_text = self.text[:self.text_index]
            self.text_label.setText(self.current_text)
        else:
            self.text_index = 0
            self.current_text = ""
            self.text_label.setText(self.current_text)


if __name__ == "__main__":
    args = read_args()
    app = QApplication(sys.argv)
    win = WaitingWindow(message=args.message)
    win.show()
    sys.exit(app.exec_())

