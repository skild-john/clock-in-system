from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout, QApplication,
    QMessageBox, QHBoxLayout, QStackedWidget, QSpacerItem, QSizePolicy, QCompleter
)
from PyQt5.QtCore import Qt, QTimer, QTime
from PyQt5.QtGui import QFont
import json
import os
from datetime import datetime

from googleAccess import GoogleDriveHandler

# --- CONFIGURATION ---
SERVICE_ACCOUNT_PATH = "gsheet-credentials.json"
SPREADSHEET_ID = "1Nw9K1pKDbNihWuVhc-nhx7SjWnqKfNpXXSjt7OVOZtE"
TIME_FORMAT = "%m/%d/%Y %H:%M:%S"
PIN_FILE = "pins.json"
SHIFT_STATE_FILE = "shift_states.json"

class VirtualKeyboard(QWidget):
    def __init__(self, target_lineedit, keyboard_type="number"):
        super().__init__()
        self.target_lineedit = target_lineedit
        self.keyboard_type = keyboard_type
        layout = QGridLayout()

        button_style = """
            background-color: rgb(238, 238, 238);
            font-size: 24px;
            border: none;
            border-radius: 10px;
            padding: 10px;
        """

        if self.keyboard_type == "qwerty":
            keys = [
                ("QWERTYUIOP", 0, 0),
                ("ASDFGHJKL", 1, 1),
                ("ZXCVBNM", 2, 2)
            ]
            for row_keys, row, col_offset in keys:
                for col, char in enumerate(row_keys):
                    button = QPushButton(char)
                    button.setFont(QFont("Monospace", 24))
                    button.setStyleSheet(button_style)
                    button.clicked.connect(self.button_clicked)
                    layout.addWidget(button, row, col + col_offset)

            space_button = QPushButton("Space")
            space_button.setFont(QFont("Monospace", 24))
            space_button.setStyleSheet(button_style)
            space_button.clicked.connect(self.button_clicked)
            layout.addWidget(space_button, 3, 1, 1, 4)

            del_button = QPushButton("Del")
            del_button.setFont(QFont("Monospace", 24))
            del_button.setStyleSheet(button_style)
            del_button.clicked.connect(self.button_clicked)
            layout.addWidget(del_button, 3, 5)

            clear_button = QPushButton("Clear")
            clear_button.setFont(QFont("Monospace", 24))
            clear_button.setStyleSheet(button_style)
            clear_button.clicked.connect(self.button_clicked)
            layout.addWidget(clear_button, 3, 6)

        else:
            buttons = [
                ['1', '2', '3'],
                ['4', '5', '6'],
                ['7', '8', '9'],
                ['0', 'Del', 'Clear']
            ]

            for row_idx, row in enumerate(buttons):
                for col_idx, char in enumerate(row):
                    button = QPushButton(char)
                    button.setFont(QFont("Monospace", 24))
                    button.setStyleSheet(button_style)
                    button.clicked.connect(self.button_clicked)
                    layout.addWidget(button, row_idx, col_idx)

        self.setLayout(layout)

    def button_clicked(self):
        sender = self.sender()
        if sender.text() == 'Del':
            self.target_lineedit.setText(self.target_lineedit.text()[:-1])
        elif sender.text() == 'Clear':
            self.target_lineedit.clear()
        elif sender.text() == 'Space':
            self.target_lineedit.setText(self.target_lineedit.text() + ' ')
        else:
            self.target_lineedit.setText(self.target_lineedit.text() + sender.text())

class SignInPage(QWidget):
    def __init__(self, service_account_path, spreadsheet_id):
        super().__init__()
        self.spreadsheet_id = spreadsheet_id
        self.setWindowTitle("Sign In")
        self.drive_handler = GoogleDriveHandler(service_account_path)
        self.drive_handler.authenticate()
        self.operator_names = self.drive_handler.get_names_from_schedule(spreadsheet_id)
        self.pins = self.load_pins()
        self.active_shifts = {}
        self.shift_states = {}

        self.init_ui()
        self.scan_active_shifts_today()
        QApplication.instance().focusChanged.connect(self.on_focus_changed)

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setStyleSheet("background-color: rgb(248, 248, 248);")
        main_layout.setAlignment(Qt.AlignCenter)

        main_layout.addSpacerItem(QSpacerItem(20, 150, QSizePolicy.Minimum, QSizePolicy.Expanding))

        button_style = """
            background-color: rgb(133, 191, 157);
            color: white;
            font-weight: bold;
            border: none;
            border-radius: 10px;
            padding: 10px;
        """

        input_style = """
            background-color: rgb(214, 209, 199);
            font-size: 24px;
            border: none;
            border-radius: 10px;
            padding: 10px;
        """

        # --- Title ---
        self.sign_in_label = QLabel("Please Sign In")
        self.sign_in_label.setFont(QFont("Monospace", 36, QFont.Bold))
        self.sign_in_label.setAlignment(Qt.AlignCenter)

        # --- Clock ---
        self.clock_label = QLabel()
        self.clock_label.setFont(QFont("Monospace", 64, QFont.Bold))
        self.clock_label.setAlignment(Qt.AlignCenter)

        timer = QTimer(self)
        timer.timeout.connect(self.update_clock)
        timer.start(1000)

        # --- Instructions ---
        self.instructions_label = QLabel("")
        self.instructions_label.setFont(QFont("Monospace", 24))
        self.instructions_label.setAlignment(Qt.AlignCenter)
        self.instructions_label.setVisible(True)

        # --- Name Input ---
        self.name_label = QLabel("Select Your Name")
        self.name_label.setFont(QFont("Monospace", 28, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)

        self.name_combo = QComboBox()
        self.name_combo.setEditable(True)
        self.name_combo.setInsertPolicy(QComboBox.NoInsert)
        self.name_combo.setStyleSheet(input_style)
        self.name_combo.setFixedWidth(1000)
        self.name_combo.setFixedHeight(100)
        self.name_combo.lineEdit().setPlaceholderText("Type your name...")
        self.name_combo.lineEdit().setFont(QFont("Monospace", 36))
        self.name_combo.lineEdit().setAlignment(Qt.AlignCenter)
        self.name_combo.addItem("")
        self.name_combo.addItems(self.operator_names)
        self.name_combo.currentTextChanged.connect(self.check_pin_status)


        completer = QCompleter(self.operator_names)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.name_combo.setCompleter(completer)

        # --- PIN Input ---
        self.pin_label = QLabel("Enter Your PIN")
        self.pin_label.setFont(QFont("Monospace", 28, QFont.Bold))
        self.pin_label.setAlignment(Qt.AlignCenter)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("Enter 4-digit PIN")
        self.pin_input.setFont(QFont("Monospace", 24))
        self.pin_input.setMaxLength(4)
        self.pin_input.setMaximumWidth(400)
        self.pin_input.setStyleSheet(input_style)

        # --- Sign In Button ---
        self.signin_button = QPushButton("Sign In")
        self.signin_button.setFont(QFont("Monospace", 28))
        self.signin_button.setMaximumWidth(300)
        self.signin_button.setFixedHeight(70)
        self.signin_button.setStyleSheet(button_style)
        self.signin_button.clicked.connect(self.handle_signin)

        # --- Shift Action Buttons ---
        self.shift_buttons_container = QWidget()
        self.shift_buttons_layout = QHBoxLayout()
        self.shift_buttons_container.setLayout(self.shift_buttons_layout)

        self.clock_in_button = QPushButton("Clock In")
        self.lunch_button = QPushButton("Start Lunch")
        self.clock_out_button = QPushButton("Clock Out")

        for button in (self.clock_in_button, self.lunch_button, self.clock_out_button):
            button.setFont(QFont("Monospace", 24))
            button.setVisible(False)
            button.setStyleSheet(button_style)
            button.setFixedHeight(70)
            button.setMinimumWidth(250)
            self.shift_buttons_layout.addWidget(button)

        self.clock_in_button.clicked.connect(lambda: self.update_shift_state("clock_in"))
        self.lunch_button.clicked.connect(self.handle_lunch_button)
        self.clock_out_button.clicked.connect(lambda: self.update_shift_state("clock_out"))

        # --- View Active Shifts ---
        self.view_active_button = QPushButton("Currently Clocked In")
        self.view_active_button.setFont(QFont("Monospace", 24))
        self.view_active_button.setStyleSheet(button_style)
        self.view_active_button.setMaximumWidth(300)
        self.view_active_button.setFixedHeight(70)
        self.view_active_button.clicked.connect(self.view_active_shifts)

        # --- Message Label ---
        self.message_label = QLabel("")
        self.message_label.setFont(QFont("Monospace", 28, QFont.Bold))
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setVisible(False)

        # --- Keyboards ---
        self.keyboard_area = QStackedWidget()
        self.keyboard_area.setFixedHeight(400)

        self.qwerty_keyboard = VirtualKeyboard(self.name_combo.lineEdit(), keyboard_type="qwerty")
        self.number_keyboard = VirtualKeyboard(self.pin_input, keyboard_type="number")
        self.keyboard_area.addWidget(self.qwerty_keyboard)
        self.keyboard_area.addWidget(self.number_keyboard)
        self.keyboard_area.setCurrentIndex(-1)

        # --- Layout Assembly ---
        main_layout.addWidget(self.sign_in_label)
        main_layout.addWidget(self.clock_label)
        main_layout.addWidget(self.instructions_label)
        main_layout.addSpacerItem(QSpacerItem(20, 100, QSizePolicy.Minimum, QSizePolicy.Expanding))
        main_layout.addWidget(self.name_label)
        main_layout.addWidget(self.name_combo, alignment=Qt.AlignCenter)
        main_layout.addWidget(self.pin_label)
        main_layout.addWidget(self.pin_input, alignment=Qt.AlignCenter)
        main_layout.addWidget(self.signin_button, alignment=Qt.AlignCenter)
        main_layout.addWidget(self.shift_buttons_container)
        
        view_active_layout = QHBoxLayout()
        view_active_layout.addStretch()
        view_active_layout.addWidget(self.view_active_button)
        main_layout.addLayout(view_active_layout)

        main_layout.addWidget(self.message_label)
        main_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        main_layout.addWidget(self.keyboard_area)

        self.setLayout(main_layout)
        self.showFullScreen()


    def update_clock(self):
        current_time = QTime.currentTime().toString('hh:mm:ss')
        self.clock_label.setText(current_time)

    def load_pins(self):
        if os.path.exists(PIN_FILE):
            with open(PIN_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_pins(self):
        with open(PIN_FILE, 'w') as f:
            json.dump(self.pins, f, indent=4)

    
    def scan_active_shifts_today(self):
        self.active_shifts = {}
        sheet = self.drive_handler.get_log_sheet(self.spreadsheet_id)
        data = sheet.get_all_values()

        today_str = datetime.now().strftime("%m/%d/%Y")

        for idx, row in enumerate(data[1:], start=2):
            operator = row[0]
            time_in = row[2]  # Assume time in column
            time_out = row[3]

            if operator and time_in and not time_out:
                # Try parsing
                try:
                    if "/" in time_in:
                        # full date and time format
                        time_in_datetime = datetime.strptime(time_in, TIME_FORMAT)
                        if time_in_datetime.strftime("%m/%d/%Y") != today_str:
                            continue  # Skip if not today
                    else:
                        # Only time, assume it's today (legacy behavior)
                        pass
                except Exception as e:
                    print(f"Skipping bad time_in format for row {idx}: {time_in} ({e})")
                    continue

                self.active_shifts[operator] = {
                    'row': idx,
                    'time_in': time_in,
                    'lunch_start': row[4] if len(row) > 4 and row[4] else None,
                    'lunch_end': row[5] if len(row) > 5 and row[5] else None
                }


    def is_in_shift_window(self):
        now = datetime.now()
        hour = now.hour

        if 6 <= hour < 14:  # First shift window 6:00am-1:59pm
            return True
        elif 14 <= hour < 21:  # Second shift window 2:00pm-8:59pm
            return True
        else:
            return False


    def on_focus_changed(self, old_widget, new_widget):
        if new_widget is None:
            return
        if new_widget == self.name_combo or new_widget == self.name_combo.lineEdit():
            self.keyboard_area.setCurrentWidget(self.qwerty_keyboard)
        elif new_widget == self.pin_input:
            self.keyboard_area.setCurrentWidget(self.number_keyboard)


    def check_pin_status(self, name):
        name = name.strip()
        if name:
            if name not in self.pins:
                self.instructions_label.setText("Type desired PIN in")
                self.signin_button.setText("Submit PIN")
            else:
                self.instructions_label.setText("PIN is already set, sign in to clock in")
                self.signin_button.setText("Sign In")
        else:
            self.instructions_label.setText("")
            self.signin_button.setText("Sign In")
            
    def handle_signin(self):
        name = self.name_combo.currentText().strip()  # ✅ fix: pull name properly
        pin = self.pin_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please select or enter your name.")
            return

        if name not in self.pins:
            QMessageBox.information(self, "Create PIN", "No PIN found. Setting new PIN.")
            if len(pin) == 4 and pin.isdigit():
                self.pins[name] = pin
                self.save_pins()
                QMessageBox.information(self, "Success", "PIN created successfully!")
            else:
                QMessageBox.warning(self, "Error", "Invalid PIN format.")
            return

        if self.pins[name] == pin:
            self.signin_button.setVisible(False)
            self.instructions_label.setText("Press Clock In to log your time")
            self.active_user = name
            
            if not self.is_in_shift_window():
                QMessageBox.warning(self, "Error", "Not within allowed clock-in hours.")
                return
            
            self.load_shift_state()
            self.scan_active_shifts_today()

            if name in self.active_shifts:
                self.clock_in_button.setVisible(False)
                self.lunch_button.setVisible(True)
                self.clock_out_button.setVisible(True)
            else:
                self.clock_in_button.setVisible(True)
                self.lunch_button.setVisible(False)
                self.clock_out_button.setVisible(False)

            self.shift_buttons_container.setVisible(True)
        else:
            QMessageBox.warning(self, "Error", "Incorrect PIN.")

    def update_shift_state(self, action):
        now_time = datetime.now().strftime("%H:%M:%S")

        if action == "clock_in":
            print(f"[ACTION] {self.active_user} clocked in at {now_time}")
            self.drive_handler.save_clock_in(self.spreadsheet_id, self.active_user, now_time)
            self.scan_active_shifts_today()

        elif action == "clock_out":
            print(f"[ACTION] {self.active_user} clocked out at {now_time}")
            self.finish_lunch_if_needed(now_time)
            self.drive_handler.save_clock_out(self.spreadsheet_id, self.active_user, now_time)
            self.drive_handler.finalize_shift(self.spreadsheet_id, self.active_user)
            if self.active_user in self.active_shifts:
                del self.active_shifts[self.active_user]
            self.scan_active_shifts_today()

        self.shift_buttons_container.setVisible(False)
        self.show_message("Thank you! See you soon!")

    def handle_lunch_button(self):
        user_state = self.shift_states.get(self.active_user, "needs_clock_in")
        now_time = QTime.currentTime().toString('hh:mm:ss')

        if user_state == "working":
            print(f"[ACTION] {self.active_user} started lunch at {now_time}")
            self.shift_states[self.active_user] = "at_lunch"
            self.drive_handler.save_lunch_start(self.spreadsheet_id, self.active_user, now_time)
            self.show_message("Enjoy your lunch!")

        elif user_state == "at_lunch":
            print(f"[ACTION] {self.active_user} ended lunch at {now_time}")
            self.shift_states[self.active_user] = "working"
            self.drive_handler.save_lunch_end(self.spreadsheet_id, self.active_user, now_time)
            self.show_message("Back to work!")

        self.save_shift_states()

    def finish_lunch_if_needed(self, now_time):
        sheet = self.drive_handler.get_log_sheet(self.spreadsheet_id)
        row = self.drive_handler.find_or_create_operator_log_row(self.spreadsheet_id, self.active_user)
        lunch_start = sheet.cell(row, 5).value
        lunch_end = sheet.cell(row, 6).value

        if lunch_start and not lunch_end:
            print(f"[ACTION] {self.active_user} auto-ended lunch at {now_time}")
            self.drive_handler.save_lunch_end(self.spreadsheet_id, self.active_user, now_time)

    def load_shift_state(self):
        if os.path.exists(SHIFT_STATE_FILE):
            with open(SHIFT_STATE_FILE, 'r') as f:
                self.shift_states = json.load(f)
        else:
            self.shift_states = {}

    def save_shift_states(self):
        with open(SHIFT_STATE_FILE, 'w') as f:
            json.dump(self.shift_states, f, indent=4)

    def show_message(self, text):
        self.name_combo.setEnabled(False)
        self.pin_input.setEnabled(False)
        self.signin_button.setEnabled(False)
        self.shift_buttons_container.setVisible(False)
        self.message_label.setText(text)
        self.message_label.setVisible(True)
        QTimer.singleShot(5000, self.reset_page)

    def reset_page(self):
        self.message_label.setVisible(False)
        self.name_combo.setEnabled(True)
        self.pin_input.setEnabled(True)
        self.signin_button.setEnabled(True)
        self.name_combo.setCurrentIndex(0)
        self.pin_input.clear()
        self.shift_buttons_container.setVisible(False)
        self.keyboard_area.setCurrentIndex(-1)

    def view_active_shifts(self):
        self.scan_active_shifts_today()
        if not self.active_shifts:
            QMessageBox.information(self, "Currently Clocked In", "No operators are currently clocked in.")
            return

        message = "Current Shift Status:\n\n"
        for operator, info in self.active_shifts.items():
            message += f"{operator}\n"
            message += f"- Time In: {info['time_in']}\n"
            message += f"- Lunch Start: {info['lunch_start'] or 'None'}\n"
            message += f"- Lunch End: {info['lunch_end'] or 'None'}\n\n"

        QMessageBox.information(self, "Currently Clocked In", message)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = SignInPage(SERVICE_ACCOUNT_PATH, SPREADSHEET_ID)
    window.show()
    sys.exit(app.exec_())
