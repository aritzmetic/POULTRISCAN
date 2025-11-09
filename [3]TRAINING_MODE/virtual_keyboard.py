import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit,
    QDialog, QHBoxLayout, QPushButton, QLabel
)
from PySide6.QtCore import Qt, QEvent, QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QGuiApplication

# --- 1. CHANGE INHERITANCE ---
class VirtualKeyboard(QWidget):
    # --- 2. ADD A SIGNAL ---
    close_requested = Signal()
    
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        
        # --- 3. REMOVE ALL DIALOG/WINDOW FLAGS ---
        # self.setWindowFlags(...) removed
        
        self.palette = palette
        self.target_widget = None
        self.is_shift_active = False
        self.is_symbols_active = False
        
        # --- 4. SET OBJECT NAME FOR STYLING ---
        self.setObjectName("virtualKeyboard")

        self.setStyleSheet(f"""
            /* --- 5. STYLE WIDGET BY NAME --- */
            QWidget[objectName="virtualKeyboard"] {{
                background-color: {palette["SECONDARY_BG"]};
                border: 2px solid {palette["BORDER"]};
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: {palette["BG"]};
                color: {palette["TEXT"]};
                border: 1px solid {palette["BORDER"]};
                border-radius: 4px;
                font: bold 12pt 'Bahnschrift';
                min-width: 32px;
                min-height: 32px;
            }}
            QPushButton:pressed {{
                background-color: {palette["PRIMARY"]};
                color: {palette["BG"]};
            }}
            QPushButton[objectName="special"], QPushButton[objectName="shift"], QPushButton[objectName="sym"] {{
                background-color: {palette["BORDER"]};
                font-size: 10pt;
            }}
            QPushButton[objectName="shift"]:checked, QPushButton[objectName="sym"]:checked {{
                background-color: {palette["PRIMARY"]};
                color: {palette["BG"]};
            }}
            QPushButton[objectName="close"] {{
                background-color: {palette["DANGER"]};
                color: {palette["DANGER_TEXT"]};
                font-size: 10pt;
            }}
            QPushButton[objectName="enter"] {{
                background-color: {palette["SUCCESS"]};
                color: {palette["SUCCESS_TEXT"]};
                font-size: 10pt;
            }}
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(3)

        self.keys_lower = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
            ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
            ['z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.']
        ]
        self.keys_upper = [
            ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')'],
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', '<', '>']
        ]
        self.keys_sym = [
            ['[', ']', '{{', '}}', '#', '%', '^', '*', '+', '='],
            ['_', '\\', '|', '~', '<', '>', '€', '£', '¥', '@'],
            ['.', ',', '?', '!', '\'', '"', ':', ';', '/'],
            ['(', ')', '-', '–', '—', '¿', '¡', '«', '»']
        ]
        
        self.button_rows = []
        self._init_ui()

        self.setFixedWidth(600)
        self.adjustSize()

    
    def _init_ui(self):
        # Row 1
        row1 = QHBoxLayout()
        self.button_rows.append(self._create_row(self.keys_lower[0], row1))
        btn_back = self._create_special_button("⌫", "special", lambda: self._send_key(Qt.Key.Key_Backspace))
        btn_back.setMinimumWidth(45)
        row1.addWidget(btn_back)
        self.layout.addLayout(row1)

        # Row 2
        row2 = QHBoxLayout()
        self.button_rows.append(self._create_row(self.keys_lower[1], row2))
        self.layout.addLayout(row2)

        # Row 3
        row3 = QHBoxLayout()
        row3.addSpacing(15)
        self.button_rows.append(self._create_row(self.keys_lower[2], row3))
        btn_enter = self._create_special_button("ENTER", "enter", self._on_enter)
        btn_enter.setMinimumWidth(60)
        row3.addWidget(btn_enter)
        self.layout.addLayout(row3)

        # Row 4
        row4 = QHBoxLayout()
        self.btn_shift = self._create_special_button("⇧", "shift", self._toggle_shift)
        self.btn_shift.setCheckable(True)
        self.btn_shift.setMinimumWidth(45)
        row4.addWidget(self.btn_shift)
        self.button_rows.append(self._create_row(self.keys_lower[3], row4))
        self.layout.addLayout(row4)

        # Row 5
        row5 = QHBoxLayout()
        self.btn_sym = self._create_special_button("?123", "sym", self._toggle_symbols)
        self.btn_sym.setCheckable(True)
        self.btn_sym.setMinimumWidth(60)
        row5.addWidget(self.btn_sym)

        btn_space = self._create_special_button("SPACE", "special", lambda: self._send_text(" "))
        btn_space.setSizePolicy(btn_space.sizePolicy().horizontalPolicy().Expanding, btn_space.sizePolicy().verticalPolicy())
        row5.addWidget(btn_space)

        btn_left = self._create_special_button("←", "special", lambda: self._send_key(Qt.Key.Key_Left))
        btn_right = self._create_special_button("→", "special", lambda: self._send_key(Qt.Key.Key_Right))
        btn_left.setMinimumWidth(40)
        btn_right.setMinimumWidth(40)
        row5.addWidget(btn_left)
        row5.addWidget(btn_right)

        btn_close = self._create_special_button("CLOSE", "close", self._on_close)
        btn_close.setMinimumWidth(60)
        row5.addWidget(btn_close)

        self.layout.addLayout(row5)

    def _create_row(self, keys, layout):
        buttons = []
        for char in keys:
            btn = QPushButton(char)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(self._on_char_clicked)
            layout.addWidget(btn)
            buttons.append(btn)
        return buttons

    def _create_special_button(self, text, obj_name, callback):
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(callback)
        return btn

    def _on_char_clicked(self):
        sender = self.sender()
        if sender:
            self._send_text(sender.text())

    def _update_keys(self):
        if self.is_symbols_active:
            target_set = self.keys_sym
            self.btn_shift.setEnabled(False)
        elif self.is_shift_active:
            target_set = self.keys_upper
            self.btn_shift.setEnabled(True)
        else:
            target_set = self.keys_lower
            self.btn_shift.setEnabled(True)
            
        for i, row_btns in enumerate(self.button_rows):
            for j, btn in enumerate(row_btns):
                if i < len(target_set) and j < len(target_set[i]):
                    btn.setText(target_set[i][j])

    def _toggle_shift(self):
        self.is_shift_active = not self.is_shift_active
        self.btn_shift.setChecked(self.is_shift_active)
        self._update_keys()

    def _toggle_symbols(self):
        self.is_symbols_active = not self.is_symbols_active
        self.btn_sym.setChecked(self.is_symbols_active)
        self.is_shift_active = False
        self.btn_shift.setChecked(False)
        self.btn_sym.setText("ABC" if self.is_symbols_active else "?123")
        self._update_keys()

    # --- SEGFAULT FIX 1: ADD SAFETY CHECKER ---
    def _check_target_alive(self):
        """
        Checks if the target widget's underlying C++ object still exists.
        Returns True if alive, False otherwise.
        """
        if not self.target_widget:
            return False
            
        try:
            # Accessing a property like .window() will throw a
            # RuntimeError if the C++ object has been deleted.
            self.target_widget.window() 
            return True
        except RuntimeError:
            print("VirtualKeyboard: Target widget is no longer alive.")
            self.target_widget = None # Clear the dead reference
            return False

    # --- SEGFAULT FIX 2: UPDATE _send_text ---
    def _send_text(self, text):
        if self._check_target_alive() and hasattr(self.target_widget, 'insert'):
            self.target_widget.insert(text)

    # --- SEGFAULT FIX 3: UPDATE _send_key ---
    def _send_key(self, key_code):
        if not self._check_target_alive():
            return

        # Use postEvent for better safety, as sendEvent is synchronous
        # and can cause crashes if the target is unstable.
        press_event = QKeyEvent(QEvent.Type.KeyPress, key_code, Qt.KeyboardModifier.NoModifier)
        release_event = QKeyEvent(QEvent.Type.KeyRelease, key_code, Qt.KeyboardModifier.NoModifier)
        
        QApplication.postEvent(self.target_widget, press_event)
        QApplication.postEvent(self.target_widget, release_event)

    # --- 6. EMIT SIGNAL ON ENTER/CLOSE ---
    def _on_enter(self):
        self._send_key(Qt.Key.Key_Return)
        # self.close_requested.emit() # <-- This remains commented out


    def _on_close(self):
        self.close_requested.emit()

    # --- 7. REMOVE ALL POSITIONING/SHOWING LOGIC ---
    # ... (removed) ...

    def eventFilter(self, obj, event):
        # This filter *only* blocks hardware keys on the target
        if obj == self.target_widget and event.type() == QEvent.Type.KeyPress:
            if event.spontaneous():
                return True # Eat the event
        
        return super().eventFilter(obj, event)

# --- 8. REMOVE KeyboardManager AND main() ---
# ... (removed) ...