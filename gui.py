import sys
import requests
import threading
from collections import deque
from PyQt6.QtCore import pyqtSignal
# --- Import PyQt6 components ---
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QTextEdit, QLabel
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QTimer
from PyQt6.QtGui import QFont

# --- Import keyboard listener ---
from pynput import keyboard

# --- CONFIGURATION ---
AGENT_API_URL = "http://127.0.0.1:8080/invoke" # Ensure this port matches your server
HOTKEY_WORD = ['l', 'e', 'x'] # The word to type to toggle the window

class AgentApp(QWidget):

    response_received = pyqtSignal(str) # Custom signal to handle responses from the agent
 

    def __init__(self):
        super().__init__()
        self.is_visible = False
        self.key_history = deque(maxlen=len(HOTKEY_WORD)) # Tracks recent key presses
        self.init_ui()
        self.response_received.connect(self.output_display.setText) 
        self.setup_hotkey_listener()
        self.response_received.connect(self.output_display.setText)


    def init_ui(self):
        # --- Window Styling (Borderless, on-top, transparent background) ---
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")

        # --- Main Layout ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # --- Container for all visible elements (provides the dark background and rounded corners) ---
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container.setStyleSheet("""
            background-color: #282c34; 
            border-radius: 15px; 
            padding: 20px;
        """)
        self.layout.addWidget(container)

        # --- Input Box ---
        self.input_box = QLineEdit()
        self.input_box.setFont(QFont("Arial", 12))
        self.input_box.setPlaceholderText("Ask Lex...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: #3a3f4b;
                color: #abb2bf;
                border: 1px solid #5c6370;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        self.input_box.returnPressed.connect(self.send_task_to_agent)
        container_layout.addWidget(self.input_box)

        # --- Output Display ---
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Arial", 11))
        self.output_display.setStyleSheet("""
            QTextEdit {
                background-color: #21252b;
                color: #abb2bf;
                border: 1px solid #5c6370;
                border-radius: 8px;
            }
        """)
        container_layout.addWidget(self.output_display)

        # --- Status Label ---
        self.status_label = QLabel(f"Type '{''.join(HOTKEY_WORD)}' to toggle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #5c6370; font-size: 9pt;")
        container_layout.addWidget(self.status_label)
        
        # --- Sizing and Initial Positioning (off-screen) ---
        self.resize(600, 400)
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        self.move(x, -self.height())

    def toggle_visibility(self):
        """Checks the current state and calls the appropriate show/hide function."""
        if self.is_visible:
            self.hide_window()
        else:
            self.show_window()

    def show_window(self):
        """Animates the window sliding down into view."""
        self.show() # Make the widget visible before animating
        
        start_pos = self.pos()
        end_y = 50  # Distance from the top of the screen
        
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300) # Animation speed in milliseconds
        self.animation.setStartValue(QRect(start_pos.x(), -self.height(), self.width(), self.height()))
        self.animation.setEndValue(QRect(start_pos.x(), end_y, self.width(), self.height()))
        self.animation.start()
        
        self.is_visible = True # Update state AFTER starting the show animation
        self.activateWindow()
        self.input_box.setFocus()

    def hide_window(self):
        """Animates the window sliding up out of view."""
        start_pos = self.pos()
        
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setStartValue(QRect(start_pos.x(), start_pos.y(), self.width(), self.height()))
        self.animation.setEndValue(QRect(start_pos.x(), -self.height(), self.width(), self.height()))
        self.animation.finished.connect(self.hide) # Fully hide widget after animation
        self.animation.start()
        
        self.is_visible = False # Update state AFTER starting the hide animation

    def send_task_to_agent(self):
        """Sends the user's task to the agent server."""
        task = self.input_box.text()
        if not task:
            return
        
        self.output_display.setText("Thinking...")
        self.input_box.clear()

        # Run the network request in a separate thread to keep the GUI responsive
        thread = threading.Thread(target=self.get_agent_response, args=(task,))
        thread.start()

    def get_agent_response(self, task):
        """Handles the network request and updates the GUI with the response."""
        try:
            response = requests.post(AGENT_API_URL, json={"task": task}, timeout=120)
            response.raise_for_status()
            data = response.json()
            final_text = data.get("response", "Error: 'response' key not found in JSON.")
            print("The GUI has received the response:", final_text)

        # Send result to main thread
            self.response_received.emit(final_text)

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to agent: {e}"
            self.response_received.emit(error_message)

    def on_press(self, key):
        """Listens for keyboard presses to detect the hotkey word."""
        try:
            self.key_history.append(key.char)
            if list(self.key_history) == HOTKEY_WORD:
                # Use QTimer to safely call the GUI function from the listener thread
                QTimer.singleShot(0, self.toggle_visibility)
        except AttributeError:
            # Ignore special keys (like Shift, Ctrl, etc.)
            pass

    def setup_hotkey_listener(self):
        """Starts the global keyboard listener in a background thread."""
        listener = keyboard.Listener(on_press=self.on_press)
        listener.daemon = True # Allows the main program to exit even if the listener is running
        listener.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AgentApp()
    # The window starts hidden and is only shown via the hotkey
    sys.exit(app.exec())