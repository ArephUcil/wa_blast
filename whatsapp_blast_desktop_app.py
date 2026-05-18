import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import time
import threading
import os
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class WhatsAppBlastApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WhatsApp Blast Desktop App")
        self.root.geometry("700x500")

        self.csv_path = ""
        self.image_path = ""

        # For persistent WhatsApp Web login
        self.user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        self.profile_directory = "Default"

        self.build_ui()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="WhatsApp Blast Application", font=("Arial", 16, "bold")).pack(pady=10)

        # CSV Import
        ttk.Button(frame, text="Import CSV", command=self.load_csv).pack(pady=5)
        self.csv_label = ttk.Label(frame, text="No CSV selected")
        self.csv_label.pack()

        # Message Template
        ttk.Label(frame, text="Message Template ({name} supported):").pack(pady=(20, 5))
        self.message_box = tk.Text(frame, height=8, width=70)
        self.message_box.pack()

        # Image Attachment
        ttk.Button(frame, text="Select Image", command=self.load_image).pack(pady=10)
        self.image_label = ttk.Label(frame, text="No image selected")
        self.image_label.pack()

        # Delay
        ttk.Label(frame, text="Delay Between Sends (seconds):").pack(pady=(20, 5))
        self.delay_entry = ttk.Entry(frame)
        self.delay_entry.insert(0, "5")
        self.delay_entry.pack()

        # Start Button
        self.start_button = ttk.Button(frame, text="Start Sending", command=self.start_sending)
        self.start_button.pack(pady=25)

        self.status_label = ttk.Label(frame, text="Ready")
        self.status_label.pack(pady=5)

    def load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if path:
            self.csv_path = path
            self.csv_label.config(text=os.path.basename(path))

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if path:
            self.image_path = path
            self.image_label.config(text=os.path.basename(path))

    def start_sending(self):
        if not self.csv_path:
            messagebox.showerror("Error", "Please import CSV first")
            return

        message_template = self.message_box.get("1.0", tk.END).strip()
        if not message_template:
            messagebox.showerror("Error", "Message template cannot be empty")
            return

        try:
            delay = int(self.delay_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Delay must be a number")
            return

        try:
            df = pd.read_csv(self.csv_path)
        except Exception as e:
            messagebox.showerror("CSV Error", str(e))
            return

        if "phone" not in df.columns or "name" not in df.columns:
            messagebox.showerror(
                "CSV Error",
                "CSV must contain columns: phone, name"
            )
            return

        self.start_button.config(state=tk.DISABLED)
        self.status_label.config(text="Sending messages...")

        # Create a thread to run send_messages
        sending_thread = threading.Thread(
            target=self._send_messages_in_thread,
            args=(df, message_template, delay)
        )
        sending_thread.start()

    def _send_messages_in_thread(self, df, template, delay):
        try:
            self.send_messages(df, template, delay)
        finally:
            self.root.after(0, self._on_sending_complete)

    def _on_sending_complete(self):
        self.start_button.config(state=tk.NORMAL)
        self.status_label.config(text="Ready")
        messagebox.showinfo("Done", "Blast completed")

    def send_messages(self, df, template, delay):
        options = Options()
        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        options.add_argument(f"--profile-directory={self.profile_directory}")
        
        # Critical Chrome arguments for stability
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")  # Prevents crashes on Windows/Linux
        options.add_argument("--disable-gpu")  # Disables GPU acceleration to prevent crashes
        options.add_argument("--start-maximized")  # Ensures proper window initialization
        options.add_argument("--disable-blink-features=AutomationControlled")  # Hides automation
        options.add_argument("--disable-software-rasterizer")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        driver = None
        try:
            driver = webdriver.Chrome(options=options)
            driver.get("https://web.whatsapp.com")

            messagebox.showinfo(
                "Login Required",
                "Please scan QR code in WhatsApp Web, then click OK"
            )

            wait = WebDriverWait(driver, 30)

            for _, row in df.iterrows():
                phone = str(row["phone"])
                name = str(row["name"])
                message = template.replace("{name}", name)
                
                # Properly encode the message with newlines preserved
                encoded_message = quote(message)

                try:
                    url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}"
                    driver.get(url)

                    # Try more robust selectors for the send button
                    # WhatsApp Web updates frequently, so this XPath might need adjustments
                    try:
                        send_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Send"] | //span[@data-testid="send"]'))
                        )
                    except TimeoutException:
                        # WhatsApp shows an invalid-number message when the contact isn't on WhatsApp
                        invalid_selector = (
                            '//*[contains(text(), "Phone number shared via url is invalid") '
                            'or contains(text(), "Phone number shared via URL is invalid") '
                            'or contains(text(), "phone number is not on WhatsApp") '
                            'or contains(text(), "not on WhatsApp")]'
                        )
                        invalid_message = driver.find_elements(By.XPATH, invalid_selector)
                        if invalid_message:
                            print(f"WhatsApp number not found for {name} ({phone}). Skipping.")
                            continue
                        raise

                    time.sleep(2)
                    send_button.click()

                    print(f"Sent to {name} ({phone})")
                    time.sleep(delay)

                except Exception as e:
                    print(f"Failed sending to {phone}: {e}")
        
        finally:
            if driver:
                driver.quit()


if __name__ == "__main__":
    root = tk.Tk()
    app = WhatsAppBlastApp(root)
    root.mainloop()
