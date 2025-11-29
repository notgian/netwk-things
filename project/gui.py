import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QGraphicsDropShadowEffect,
    QScrollArea, QFrame, QSizePolicy, QGridLayout, QLineEdit
)

from PyQt5.QtGui import (
    QPixmap, QFont, QIcon
)

from PyQt5.QtCore import (
    Qt, pyqtSignal, QThread
)

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import csv
import requests
import messages
import threading
import time
from PyQt5.QtCore import QTimer

# ---------------------------------------------
# 0. GAME THREADS FOR HOST / PLAYER / SPECTATOR
# ---------------------------------------------
from host import Host
from player import Player
from spectator import Spectator
import config
import socket


def get_my_ip():
    """Returns the actual local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


class HostThread(QThread):
    handshake_success = pyqtSignal()

    def __init__(self, host_obj):
        super().__init__()
        self.host = host_obj

    def run(self):
        # Run host loop until we enter SETUP
        while True:
            if self.host.protocol_handler.game_state == "SETUP":
                self.handshake_success.emit()
                break


        # Continue running the full host loop
        self.host.run_host_loop()


class PlayerThread(QThread):
    def __init__(self, player_obj):
        super().__init__()
        self.player = player_obj

    def run(self):
        self.player.run_game_loop()


class SpectatorThread(QThread):
    def __init__(self, spec_obj):
        super().__init__()
        self.spec = spec_obj

    def run(self):
        self.spec.connect_to_host()


# ---------------------------------------------
# Pokemon data + sprite loading
# ---------------------------------------------
POKE_SPRITE_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{id}.png"
)

def load_pokemon_list_from_csv(path="pokemon.csv"):
    mons = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    pid = int(row.get("pokedex_number", "").strip())
                except:
                    continue
                name = row.get("name", "").strip()
                if name:
                    mons.append({"id": pid, "name": name})
    except FileNotFoundError:
        print("[POKEMON] pokemon.csv not found")
    return mons

def fetch_pokemon_sprite(pokedex_id: int) -> QPixmap:
    url = POKE_SPRITE_URL.format(id=pokedex_id)
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            pm = QPixmap()
            pm.loadFromData(resp.content)
            return pm
    except Exception as e:
        print(f"[SPRITE] Failed to fetch sprite for #{pokedex_id}: {e}")
    return QPixmap()  # fallback



# ---------------------------------------------
# 1. SCALER (Base: 1920x1080)
# ---------------------------------------------
class Scaler:
    BASE_W = 1920
    BASE_H = 1080

    def __init__(self):
        screen = QApplication.primaryScreen().size()
        self.sx = screen.width() / self.BASE_W
        self.sy = screen.height() / self.BASE_H

    def x(self, v): return int(v * self.sx)
    def y(self, v): return int(v * self.sy)
    def w(self, v): return int(v * self.sx)
    def h(self, v): return int(v * self.sy)


# ---------------------------------------------
# 2. TITLE SCREEN
# ---------------------------------------------
class TitleScreen(QWidget):
    def __init__(self, parent, scaler: Scaler):
        super().__init__()
        self.parent = parent
        self.scaler = scaler
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: black;")

        self.bg = QLabel(self)
        pix = QPixmap("imgs/title_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        self.start_btn = QPushButton(self)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setFlat(True)
        self.start_btn.setStyleSheet("border: none; background: transparent;")

        btn_pix = QPixmap("imgs/start.png").scaled(
            self.scaler.w(324),
            self.scaler.h(98.5),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.start_btn.setIcon(QIcon(btn_pix))
        self.start_btn.setIconSize(btn_pix.size())

        self.start_btn.setGeometry(
            self.scaler.x(806.1),
            self.scaler.y(852.1),
            btn_pix.width(),
            btn_pix.height()
        )

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(0)
        glow.setColor(Qt.white)
        glow.setOffset(0, 0)
        self.start_btn.setGraphicsEffect(glow)

        def enter(e):
            glow.setBlurRadius(50)

        def leave(e):
            glow.setBlurRadius(0)

        self.start_btn.enterEvent = enter
        self.start_btn.leaveEvent = leave
        self.start_btn.clicked.connect(self.go_to_mode_select)

    def resizeEvent(self, event):
        self.bg.setGeometry(0, 0, self.width(), self.height())

    def go_to_mode_select(self):
        self.parent.setCurrentIndex(1)


# ---------------------------------------------
# 3. MODE SELECT
# ---------------------------------------------
class ModeSelectScreen(QWidget):
    def __init__(self, parent, scaler: Scaler):
        super().__init__()
        self.parent = parent
        self.scaler = scaler
        self.init_ui()

    def init_ui(self):
        self.bg = QLabel(self)
        pix = QPixmap("imgs/setup_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        def make_button(img, x, y, w, h, callback):
            btn = QPushButton(self)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFlat(True)
            btn.setStyleSheet("border: none; background: transparent;")
            pixmap = QPixmap(img).scaled(
                self.scaler.w(w), self.scaler.h(h),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(pixmap.size())
            btn.setGeometry(
                self.scaler.x(x), self.scaler.y(y),
                pixmap.width(), pixmap.height()
            )
            glow = QGraphicsDropShadowEffect(self)
            glow.setBlurRadius(0)
            glow.setColor(Qt.white)
            glow.setOffset(0, 0)
            btn.setGraphicsEffect(glow)
            btn.enterEvent = lambda e: glow.setBlurRadius(50)
            btn.leaveEvent = lambda e: glow.setBlurRadius(0)
            btn.clicked.connect(callback)
            return btn

        self.btn_host = make_button(
            "imgs/host.png", 108, 649.1, 537.3, 268.4, self.open_host_popup
        )
        self.btn_join = make_button(
            "imgs/join.png", 691.3, 649.1, 537.3, 268.4, self.open_join_popup
        )
        self.btn_spectate = make_button(
            "imgs/spectate.png", 1274.7, 649.1, 537.3, 268.4, self.open_spectate_popup
        )

    def resizeEvent(self, event):
        self.bg.setGeometry(0, 0, self.width(), self.height())

    # -------------------------
    # Popup Callbacks
    # -------------------------
    def open_host_popup(self):
        my_ip = get_my_ip()
        port = config.DEFAULT_PORT

        host_obj = Host(my_ip, port)
        self.parent.protocol_handler = host_obj.protocol_handler
        self.host_thread = HostThread(host_obj)

        # When handshake is done → let host choose Pokémon
        self.host_thread.handshake_success.connect(
            lambda: self.parent.open_pokemon_selection(role="host")
        )

        self.host_thread.start()
        self.host_popup = HostPopup(self, self.scaler, ip_address=my_ip)

    def open_join_popup(self):
        self.join_popup = JoinPopup(self, self.scaler)

    def open_spectate_popup(self):
        self.spectate_popup = SpectatePopup(self, self.scaler)


# ---------------------------------------------
# 4. HOST POP-UP
# ---------------------------------------------
class HostPopup(QWidget):
    def __init__(self, parent, scaler: Scaler, ip_address: str):
        super().__init__(parent)
        self.parent = parent
        self.scaler = scaler
        self.ip = ip_address
        self.init_ui()

    def init_ui(self):
        self.setGeometry(
            self.scaler.x(626.3), self.scaler.y(238.8),
            self.scaler.w(667.4), self.scaler.h(601.2)
        )
        self.setStyleSheet("background: transparent;")

        self.bg = QLabel(self)
        pix = QPixmap("imgs/popup_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)

        title = QLabel("HOSTING GAME", self)
        title.setFont(QFont("Arial", int(self.scaler.y(30)), QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setGeometry(
            self.scaler.x(120), self.scaler.y(80),
            self.scaler.w(430), self.scaler.h(50)
        )

        body = QLabel(
            f"You are now the host of a match.\n"
            f"Your battlefield is available at:\n\n"
            f"IP Address: {self.ip}\n\n"
            "Waiting for players or spectators to join...",
            self
        )
        body.setFont(QFont("Arial", int(self.scaler.y(16))))
        body.setStyleSheet("color: white;")
        body.setWordWrap(True)
        body.setGeometry(
            self.scaler.x(80), self.scaler.y(190),
            self.scaler.w(520), self.scaler.h(290)
        )

        cancel = QPushButton("Cancel", self)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(24))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(24))}px;
                border: none;
                padding: {int(self.scaler.h(10))}px;
            }}
            QPushButton:hover {{ background-color: #FF6A60; }}
        """)
        cancel.setGeometry(
            self.scaler.x(440), self.scaler.y(485),
            self.scaler.w(170), self.scaler.h(60)
        )
        cancel.clicked.connect(self.hide)

        self.raise_()
        self.show()


# ---------------------------------------------
# 5. JOIN POP-UP
# ---------------------------------------------
class JoinPopup(QWidget):
    def __init__(self, parent, scaler: Scaler):
        super().__init__(parent)
        self.parent = parent
        self.scaler = scaler
        self.init_ui()

    def init_ui(self):
        self.setGeometry(
            self.scaler.x(626.3), self.scaler.y(238.8),
            self.scaler.w(667.4), self.scaler.h(601.2)
        )
        self.setStyleSheet("background: transparent;")

        self.bg = QLabel(self)
        pix = QPixmap("imgs/popup_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)

        title = QLabel("JOINING GAME", self)
        title.setFont(QFont("Arial", int(self.scaler.y(30)), QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setGeometry(
            self.scaler.x(140), self.scaler.y(100),
            self.scaler.w(430), self.scaler.h(50)
        )

        body = QLabel("Connect to an existing host’s battlefield.\nEnter the Host’s IP Address below.", self)
        body.setFont(QFont("Arial", int(self.scaler.y(16))))
        body.setStyleSheet("color: white;")
        body.setGeometry(
            self.scaler.x(80), self.scaler.y(210),
            self.scaler.w(520), self.scaler.h(60)
        )

        self.input_field = QLabel(self)
        self.input_field.setGeometry(
            self.scaler.x(75), self.scaler.y(290),
            self.scaler.w(520), self.scaler.h(60)
        )
        self.input_field.setStyleSheet("""
            background-color: #14114E;
            border-radius: 20px;
        """)

        my_ip = get_my_ip()

        self.ip_textbox = QLineEdit(self)
        self.ip_textbox.setPlaceholderText(f"Leave blank for {my_ip}")
        self.ip_textbox.setFont(QFont("Arial", int(self.scaler.y(16))))
        self.ip_textbox.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: white;
                padding-left: 15px;
                border-radius: 12px;
                border: none;
                font-weight: bold;
            }
        """)
        self.ip_textbox.setGeometry(
            self.scaler.x(95), self.scaler.y(305),
            self.scaler.w(480), self.scaler.h(30)
        )

        join = QPushButton("Join", self)
        join.setCursor(Qt.PointingHandCursor)
        join.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(22))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(24))}px;
            }}
            QPushButton:hover {{ background-color: #FF6A60; }}
        """)
        join.setGeometry(
            self.scaler.x(270), self.scaler.y(485),
            self.scaler.w(150), self.scaler.h(55)
        )
        join.clicked.connect(self.join_selected)

        cancel = QPushButton("Cancel", self)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(22))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(24))}px;
            }}
            QPushButton:hover {{ background-color: #FF6A60; }}
        """)
        cancel.setGeometry(
            self.scaler.x(440), self.scaler.y(485),
            self.scaler.w(150), self.scaler.h(55)
        )
        cancel.clicked.connect(self.hide)

        self.show()

    def join_selected(self):
        ip = self.ip_textbox.text().strip()
        my_ip = get_my_ip()
        host_ip = ip if ip else my_ip

        print(f"[GUI] Joining host at: {host_ip}")

        player_obj = Player(host_ip, config.DEFAULT_PORT, local_ip=my_ip, local_port=0)
        ok = player_obj.connect()

        if ok:
            print("[GUI] Player handshake successful. Starting game loop...")
            self.player_thread = PlayerThread(player_obj)
            self.player_thread.start()

            # FIX: access MainWindow properly
            main_window = self.parent.parent
            main_window.protocol_handler = player_obj.protocol_handler
            main_window.open_pokemon_selection(role="player")

        else:
            print("[GUI] Failed to join host.")

        self.hide()


# ---------------------------------------------
# 6. SPECTATE POP-UP
# ---------------------------------------------
class SpectatePopup(QWidget):
    def __init__(self, parent, scaler: Scaler):
        super().__init__(parent)
        self.parent = parent
        self.scaler = scaler
        self.init_ui()

    def init_ui(self):
        self.setGeometry(
            self.scaler.x(626.3), self.scaler.y(238.8),
            self.scaler.w(667.4), self.scaler.h(601.2)
        )
        self.setStyleSheet("background: transparent;")

        self.bg = QLabel(self)
        pix = QPixmap("imgs/popup_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)

        title = QLabel("SPECTATE GAME", self)
        title.setFont(QFont("Arial", int(self.scaler.y(30)), QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setGeometry(
            self.scaler.x(120), self.scaler.y(100),
            self.scaler.w(430), self.scaler.h(50)
        )

        body = QLabel("Watch an active battle in real time.\nEnter the Host’s IP Address below.", self)
        body.setFont(QFont("Arial", int(self.scaler.y(16))))
        body.setStyleSheet("color: white;")
        body.setGeometry(
            self.scaler.x(80), self.scaler.y(210),
            self.scaler.w(520), self.scaler.h(60)
        )

        my_ip = get_my_ip()

        self.input_field = QLabel(self)
        self.input_field.setGeometry(
            self.scaler.x(75), self.scaler.y(290),
            self.scaler.w(520), self.scaler.h(60)
        )
        self.input_field.setStyleSheet("""
            background-color: #14114E;
            border-radius: 20px;
        """)

        self.ip_textbox = QLineEdit(self)
        self.ip_textbox.setPlaceholderText(f"Leave blank for {my_ip}")
        self.ip_textbox.setFont(QFont("Arial", int(self.scaler.y(16))))
        self.ip_textbox.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: white;
                padding-left: 15px;
                border-radius: 12px;
                border: none;
                font-weight: bold;
            }
        """)
        self.ip_textbox.setGeometry(
            self.scaler.x(95), self.scaler.y(305),
            self.scaler.w(480), self.scaler.h(30)
        )

        join = QPushButton("Join", self)
        join.setCursor(Qt.PointingHandCursor)
        join.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(22))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(24))}px;
            }}
            QPushButton:hover {{ background-color: #FF6A60; }}
        """)
        join.setGeometry(
            self.scaler.x(270), self.scaler.y(485),
            self.scaler.w(150), self.scaler.h(55)
        )
        join.clicked.connect(self.join_selected)

        cancel = QPushButton("Cancel", self)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(22))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(24))}px;
            }}
            QPushButton:hover {{ background-color: #FF6A60; }}
        """)
        cancel.setGeometry(
            self.scaler.x(440), self.scaler.y(485),
            self.scaler.w(150), self.scaler.h(55)
        )
        cancel.clicked.connect(self.hide)

        self.show()

    def join_selected(self):
        ip = self.ip_textbox.text().strip()
        my_ip = get_my_ip()
        host_ip = ip if ip else my_ip

        print(f"[GUI] Spectating host at: {host_ip}")

        spec_obj = Spectator(host_ip, config.DEFAULT_PORT, local_ip=my_ip, local_port=0)
        self.spec_thread = SpectatorThread(spec_obj)
        self.spec_thread.start()

        self.hide()



# ---------------------------------------------
# 7. SPRITE PICKER
# ---------------------------------------------

# ---------------------------------------------
# Pokémon Card (clickable + hover glow)
# ---------------------------------------------
class PokemonCard(QPushButton):
    def __init__(self, mon: dict, scaler: Scaler, parent=None):
        super().__init__(parent)
        self.mon = mon
        self.scaler = scaler

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(self.scaler.w(150), self.scaler.h(160))

        self.setStyleSheet("""
            QPushButton {
                background-color: #1D3EF3;
                border-radius: 20px;
            }
            QPushButton:checked {
                border: 3px solid white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.img_label = QLabel(self)
        self.img_label.setAlignment(Qt.AlignCenter)

        self.name_label = QLabel(mon["name"], self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 22px;
        """)

        layout.addWidget(self.img_label)
        layout.addWidget(self.name_label)

        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setBlurRadius(0)
        self.glow.setColor(Qt.white)
        self.glow.setOffset(0, 0)
        self.setGraphicsEffect(self.glow)

    def enterEvent(self, event):
        self.glow.setBlurRadius(40)

    def leaveEvent(self, event):
        self.glow.setBlurRadius(0)



class SpriteLoaderThread(QThread):
    sprite_loaded = pyqtSignal(int, QPixmap)

    def __init__(self, mons):
        super().__init__()
        self.mons = mons

    def run(self):
        for mon in self.mons:
            pix = fetch_pokemon_sprite(mon["id"])
            self.sprite_loaded.emit(mon["id"], pix)

# ---------------------------------------------
# Pokémon Selection Screen crollable grid)
# ---------------------------------------------
class PokemonSelectionScreen(QWidget):
    def __init__(self, parent, scaler: Scaler):
        super().__init__()
        self.parent = parent
        self.scaler = scaler

        self.selected_mon = None
        self.cards = []
        self.mons = load_pokemon_list_from_csv()

        self.init_ui()

    def init_ui(self):
        # Background
        self.bg = QLabel(self)
        pix = QPixmap("imgs/pick_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        # --------------------------------------------------
        # SCROLL AREA
        # --------------------------------------------------
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)

        self.scroll.setGeometry(
            self.scaler.x(739.9),
            self.scaler.y(236),
            self.scaler.w(1020.4),
            self.scaler.h(590)
        )

        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical { width: 0px; }
            QScrollBar:horizontal { height: 0px; }
            background: transparent;
        """)

        self.scroll.viewport().setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(container)

        # Tighter spacing for a 5-column layout
        self.grid.setContentsMargins(20, 20, 20, 20)
        self.grid.setSpacing(15)

        self.scroll.setWidget(container)

        # ------------------------------------
        # 5-COLUMN GRID (was 8 columns before)
        # ------------------------------------
        columns = 5
        row = 0
        col = 0

        self.cards = []

        for mon in self.mons:
            card = PokemonCard(mon, self.scaler)
            card.clicked.connect(lambda _, m=mon, c=card: self.select_mon(m, c))
            self.cards.append(card)
            self.grid.addWidget(card, row, col)

            col += 1
            if col >= columns:
                col = 0
                row += 1

        # Confirm button
        self.confirm_btn = QPushButton("Confirm", self)
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(24))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(28))}px;
                padding: 10px 30px;
            }}
            QPushButton:hover {{
                background-color: #FF6A60;
            }}
        """)

        self.confirm_btn.setGeometry(
            self.scaler.x(1555.1),
            self.scaler.y(926.4),
            self.scaler.w(236.8),
            self.scaler.h(63.2)
        )
        self.confirm_btn.clicked.connect(self.confirm_selection)

        # Sprite loader thread
        self.loader_thread = SpriteLoaderThread(self.mons)
        self.loader_thread.sprite_loaded.connect(self.update_card_sprite)
        self.loader_thread.start()

    def resizeEvent(self, event):
        self.bg.setGeometry(0, 0, self.width(), self.height())
        self.bg.lower()

    def update_card_sprite(self, mon_id, pixmap):
        if pixmap.isNull():
            return

        for card in self.cards:
            if card.mon["id"] == mon_id:
                sprite = pixmap.scaled(
                    self.scaler.w(96),
                    self.scaler.h(96),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                card.img_label.setPixmap(sprite)
                break

    def select_mon(self, mon, card):
        for c in self.cards:
            if c is not card:
                c.setChecked(False)
        card.setChecked(True)
        self.selected_mon = mon
        print(f"[GUI] Selected: {mon['name']}")

    def confirm_selection(self):
        if not self.selected_mon:
            print("[GUI] No Pokémon selected.")
            return

        protocol = self.parent.protocol_handler

        pokemon_name = self.selected_mon["name"]
        stat_boosts = {"special_attack_uses": 0, "special_defense_uses": 0}

        protocol.start_battle_setup(
            pokemon_name=pokemon_name,
            stat_boosts=stat_boosts,
            communication_mode=messages.CommunicationMode.P2P
        )

        print(f"[GUI] Submitted Pokémon to protocol: {pokemon_name}")

        # Start waiting until both players have selected
        self.parent.wait_for_both_pokemon()


class SetupPopup(QWidget):
    def __init__(self, parent, scaler, protocol_handler):
        super().__init__(parent)
        self.parent = parent
        self.scaler = scaler
        self.protocol = protocol_handler

        self.sa_value = 0
        self.sd_value = 0

        self.init_ui()

    def init_ui(self):
        self.setGeometry(
            self.scaler.x(626.3), self.scaler.y(238.8),
            self.scaler.w(667.4), self.scaler.h(601.2)
        )
        self.setStyleSheet("background: transparent;")

        # Background image
        self.bg = QLabel(self)
        pix = QPixmap("imgs/popup_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 10)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)

        # Stacked pages
        self.pages = QStackedWidget(self)
        self.pages.setGeometry(0, 0, self.width(), self.height())

        self.build_stat_page()
        self.build_comm_page()

        self.pages.setCurrentIndex(0)
        self.show()

    # -----------------------------------------------------------
    # PAGE 1 — STAT BOOSTS (clean & centered)
    # -----------------------------------------------------------
    def build_stat_page(self):
        page = QWidget(self)

        # Title stays in same place
        title = QLabel("Select Stat Boosts", page)
        title.setFont(QFont("Arial", int(self.scaler.y(32)), QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        title.setGeometry(
            self.scaler.x(0), self.scaler.y(60),
            self.scaler.w(667.4), self.scaler.h(60)
        )

        # --- SHIFT ALL STAT FIELDS DOWN ---
        base_y = 230  # ↓↓↓ lowered from 170 → 230

        # SA label
        sa_label = QLabel("Special Attack Uses (0–5):", page)
        sa_label.setFont(QFont("Arial", int(self.scaler.y(16))))
        sa_label.setStyleSheet("color: white;")
        sa_label.setGeometry(
            self.scaler.x(70), self.scaler.y(base_y),
            self.scaler.w(320), self.scaler.h(40)
        )

        # SA input background (smaller width)
        sa_bg = QLabel(page)
        sa_bg.setGeometry(
            self.scaler.x(430), self.scaler.y(base_y - 5),
            self.scaler.w(150), self.scaler.h(45)
        )
        sa_bg.setStyleSheet("background-color: #14114E; border-radius: 14px;")

        # SA input (smaller width, nudged right)
        self.sa_input = QLineEdit(page)
        self.sa_input.setText("0")
        self.sa_input.setFont(QFont("Arial", int(self.scaler.y(18))))
        self.sa_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: white;
                border: none;
                padding-left: 12px;
                font-weight: bold;
            }
        """)
        self.sa_input.setGeometry(
            self.scaler.x(430), self.scaler.y(base_y + 7),
            self.scaler.w(130), self.scaler.h(25)
        )

        # SD label (spaced further down)
        sd_label = QLabel("Special Defense Uses (0–5):", page)
        sd_label.setFont(QFont("Arial", int(self.scaler.y(16))))
        sd_label.setStyleSheet("color: white;")
        sd_label.setGeometry(
            self.scaler.x(70), self.scaler.y(base_y + 70),
            self.scaler.w(340), self.scaler.h(40)
        )

        # SD input background
        sd_bg = QLabel(page)
        sd_bg.setGeometry(
            self.scaler.x(430), self.scaler.y(base_y + 65),
            self.scaler.w(150), self.scaler.h(45)
        )
        sd_bg.setStyleSheet("background-color: #14114E; border-radius: 14px;")

        # SD input
        self.sd_input = QLineEdit(page)
        self.sd_input.setText("0")
        self.sd_input.setFont(QFont("Arial", int(self.scaler.y(18))))
        self.sd_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: white;
                border: none;
                padding-left: 12px;
                font-weight: bold;
            }
        """)
        self.sd_input.setGeometry(
            self.scaler.x(430), self.scaler.y(base_y + 77),
            self.scaler.w(130), self.scaler.h(25)
        )

        # NEXT BUTTON — unchanged
        next_btn = QPushButton("Next", page)
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(24))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(25))}px;
            }}
            QPushButton:hover {{ background-color: #FF6A60; }}
        """)
        next_btn.setGeometry(
            self.scaler.x(250), self.scaler.y(470),
            self.scaler.w(180), self.scaler.h(60)
        )
        next_btn.clicked.connect(self.go_to_comm_page)

        self.pages.addWidget(page)

    # -----------------------------------------------------------
    # PAGE 2 — COMMUNICATION MODE (vertical, larger buttons)
    # -----------------------------------------------------------
    def build_comm_page(self):
        page = QWidget(self)

        # Title
        title = QLabel("Communication Mode", page)
        title.setFont(QFont("Arial", int(self.scaler.y(30)), QFont.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        title.setGeometry(
            self.scaler.x(0), self.scaler.y(80),
            self.scaler.w(667.4), self.scaler.h(60)
        )

        # ------- BIG RED BUTTON STYLE -------
        red_button_style = f"""
            QPushButton {{
                background-color: #FF3B30;
                color: white;
                font-size: {int(self.scaler.y(26))}px;
                font-weight: bold;
                border-radius: {int(self.scaler.h(28))}px;
            }}
            QPushButton:hover {{
                background-color: #FF6A60;
            }}
        """

        # P2P BUTTON (big & centered)
        btn_p2p = QPushButton("P2P Mode", page)
        btn_p2p.setCursor(Qt.PointingHandCursor)
        btn_p2p.setStyleSheet(red_button_style)
        btn_p2p.setGeometry(
            self.scaler.x(200), self.scaler.y(240),  # moved down & centered
            self.scaler.w(260), self.scaler.h(70)
        )
        btn_p2p.clicked.connect(lambda: self.finish_setup(messages.CommunicationMode.P2P))

        # BROADCAST BUTTON (big & directly below)
        btn_bc = QPushButton("Broadcast Mode", page)
        btn_bc.setCursor(Qt.PointingHandCursor)
        btn_bc.setStyleSheet(red_button_style)
        btn_bc.setGeometry(
            self.scaler.x(200), self.scaler.y(340),
            self.scaler.w(260), self.scaler.h(70)
        )
        btn_bc.clicked.connect(lambda: self.finish_setup(messages.CommunicationMode.BROADCAST))

        self.pages.addWidget(page)

    # -----------------------------------------------------------
    # SWITCH PAGE
    # -----------------------------------------------------------
    def go_to_comm_page(self):
        try:
            sa = int(self.sa_input.text())
            sd = int(self.sd_input.text())
            if not (0 <= sa <= 5 and 0 <= sd <= 5):
                raise ValueError
        except:
            print("[GUI] Invalid stat boost input.")
            return

        self.sa_value = sa
        self.sd_value = sd
        self.pages.setCurrentIndex(1)

    # -----------------------------------------------------------
    # FINAL SEND
    # -----------------------------------------------------------
    def finish_setup(self, mode):
        ip = self.protocol.local_ip
        mon = self.protocol.match_data[ip]["pokemon_name"]

        boosts = {
            "special_attack_uses": self.sa_value,
            "special_defense_uses": self.sd_value
        }

        self.protocol.start_battle_setup(
            pokemon_name=mon,
            stat_boosts=boosts,
            communication_mode=mode
        )

        self.hide()
        if hasattr(self.parent, "open_vs_screen"):
            self.parent.open_vs_screen()



# ---------------------------------------------
# LOADING SCREEN
# ---------------------------------------------
class VsScreen(QWidget):
    def __init__(self, parent, scaler: Scaler, host_mon, player_mon):
        super().__init__(parent)
        self.parent = parent
        self.scaler = scaler
        self.host_mon = host_mon
        self.player_mon = player_mon

        self.init_ui()

    def init_ui(self):
        self.setGeometry(0, 0, self.parent.width(), self.parent.height())

        # Background (full screen)
        self.bg = QLabel(self)
        pix = QPixmap("imgs/vs_bg.png")
        self.bg.setPixmap(pix)
        self.bg.setScaledContents(True)
        self.bg.setGeometry(0, 0, self.width(), self.height())

        # ---------------------------------------------
        # LEFT SIDE POKEMON (HOST)
        # ---------------------------------------------
        self.left_sprite = QLabel(self)
        self.left_sprite.setGeometry(
            self.scaler.x(150),
            self.scaler.y(200),
            self.scaler.w(500),
            self.scaler.h(500)
        )
        self.left_sprite.setAlignment(Qt.AlignCenter)

        host_pix = fetch_pokemon_sprite(self.host_mon["id"])
        host_pix = host_pix.scaled(
            self.left_sprite.width(),
            self.left_sprite.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.left_sprite.setPixmap(host_pix)

        # ---------------------------------------------
        # RIGHT SIDE POKEMON (PLAYER)
        # ---------------------------------------------
        self.right_sprite = QLabel(self)
        self.right_sprite.setGeometry(
            self.scaler.x(900),
            self.scaler.y(200),
            self.scaler.w(500),
            self.scaler.h(500)
        )
        self.right_sprite.setAlignment(Qt.AlignCenter)

        player_pix = fetch_pokemon_sprite(self.player_mon["id"])
        player_pix = player_pix.scaled(
            self.right_sprite.width(),
            self.right_sprite.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.right_sprite.setPixmap(player_pix)

        # ---------------------------------------------
        # Timer → after 5 seconds, continue to battle
        # ---------------------------------------------
        QTimer.singleShot(5000, self.finish_vs)

    def finish_vs(self):
        print("[GUI] VS screen finished, switching to battle view...")
        if hasattr(self.parent, "open_battle_screen"):
            self.parent.open_battle_screen()





# ---------------------------------------------
# 9. MAIN APPLICATION WINDOW
# ---------------------------------------------
class MainWindow(QStackedWidget):
    def __init__(self):
        super().__init__()

        self.scaler = Scaler()

        self.title_screen = TitleScreen(self, self.scaler)
        self.mode_select = ModeSelectScreen(self, self.scaler)
        self.pokemon_screen = PokemonSelectionScreen(self, self.scaler)

        # IMPORTANT: will be set by host/join popup
        self.protocol_handler = None

        self.addWidget(self.title_screen)    # index 0
        self.addWidget(self.mode_select)     # index 1
        self.addWidget(self.pokemon_screen)  # index 2

        self.setCurrentWidget(self.title_screen)

    # -----------------------------------------
    # OPEN Pokémon SELECTION SCREEN
    # -----------------------------------------
    def open_pokemon_selection(self, role="player"):
        print(f"[GUI] Switching to Pokémon selection screen ({role})")

        self.pokemon_screen.selected_mon = None
        for c in self.pokemon_screen.cards:
            c.setChecked(False)

        self.setCurrentIndex(2)

    # -----------------------------------------
    # WAIT FOR BOTH POKÉMON SELECTIONS
    # -----------------------------------------
    def wait_for_both_pokemon(self):
        protocol = self.protocol_handler

        def poll():
            while True:
                data = protocol.match_data

                # Must exist on both sides
                if protocol.local_ip in data and protocol.opponent_addr[0] in data:
                    print("[GUI] Both players selected Pokémon!")
                    QTimer.singleShot(0, self.open_setup_popup)
                    break

                time.sleep(0.1)

        threading.Thread(target=poll, daemon=True).start()

    # -----------------------------------------
    # OPEN THE SETUP POPUP (STAT + COMM MODE)
    # -----------------------------------------
    def open_setup_popup(self):
        protocol = self.protocol_handler

        print("[GUI] Opening Setup Popup")
        self.setup_popup = SetupPopup(self, self.scaler, protocol)

    def open_vs_screen(self):
        protocol = self.protocol_handler

        # The keys in match_data are IPs of players
        host_ip = protocol.host_ip
        player_ip = protocol.local_ip if not protocol.is_host else protocol.opponent_addr[0]

        host_mon = protocol.match_data[host_ip]
        player_mon = protocol.match_data[player_ip]

        print(f"[GUI] Loading VS screen: {host_mon['pokemon_name']} VS {player_mon['pokemon_name']}")

        self.vs_screen = VsScreen(self, self.scaler, host_mon, player_mon)
        self.addWidget(self.vs_screen)
        self.setCurrentWidget(self.vs_screen)


# ---------------------------------------------
# 10. RUN APPLICATION
# ---------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.setWindowTitle("Pokemon Quantum Arena")
    window.showMaximized()

    sys.exit(app.exec_())
