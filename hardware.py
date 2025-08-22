from flask import Flask, request, jsonify
import os
import subprocess
import logging
import time
import requests
import threading
from werkzeug.utils import secure_filename
from flask_cors import CORS
import qrcode
from PIL import Image, ImageTk, ImageDraw, ImageFont
import tkinter as tk
import RPi.GPIO as GPIO
import time
import textwrap
import re
import difflib
import pyautogui

# For TFT Display
import board
import digitalio
import busio
from adafruit_rgb_display import ili9341
import math

#motor pin and ir pin conf

IR_DO_PIN = 4
motor_pins = {
    1: {'DIR': 20, 'STEP': 21, 'M0': 17, 'M1': 27, 'M2': 22, 'SLP': 16},
    2: {'DIR': 5,  'STEP': 6,  'M0': 13, 'M1': 19, 'M2': 26, 'SLP': 12}
}

microstep_mode = '1/4'
microstep_settings = {'1/4': (0, 1, 1)}

steps_per_rev = 200
microstep = 4
total_steps = steps_per_rev * microstep

rpm_motor1 = 30
rpm_motor2 = 60
delay_motor1 = 60.0 / (total_steps * rpm_motor1)
delay_motor2 = 60.0 / (total_steps * rpm_motor2)

#enabling the motor pins to high to hold down the torque and ir pin setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# IR sensor pin
GPIO.setup(IR_DO_PIN, GPIO.IN)

# Setup all motor pins
for motor in motor_pins.values():
    for pin in motor.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)  # Default LOW

    # Wake up motor driver (holding torque ON)
    GPIO.output(motor['SLP'], GPIO.HIGH)

# Set microstep mode globally
m0_state, m1_state, m2_state = microstep_settings[microstep_mode]
for motor in motor_pins.values():
    GPIO.output(motor['M0'], m0_state)
    GPIO.output(motor['M1'], m1_state)
    GPIO.output(motor['M2'], m2_state)

# Set direction globally
for motor in motor_pins.values():
    GPIO.output(motor['DIR'], GPIO.HIGH)



#display configure
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D24)
reset_pin = digitalio.DigitalInOut(board.D25)
display = ili9341.ILI9341(spi, cs=cs_pin, dc=dc_pin, rst=reset_pin, baudrate=24000000)

WIDTH = display.width
HEIGHT = display.height
FONT = ImageFont.load_default()
LARGE_FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)

#virtual display configure
env = os.environ.copy()
env['DISPLAY'] = ':99'

# Initialize Flask app
app = Flask(__name__)
upload_folder = '/home/pi/uploads'
app.config['upload_folder'] = upload_folder
logging.basicConfig(level=logging.INFO)
CORS(app)

# Global Variables
serveo_url = None
serveo_event = threading.Event()
qr_path = None

# Predefined file paths
file_path2 = '/home/pi/uploads/SanDisk_bill.pdf'
file_path3 = '/home/pi/uploads/SanDisk_bill.pdf'
window_name = 'Document Print Status'

# Start ngrok tunnel
def start_serveo():
    global serveo_url
    try:
        logging.info("Starting ngrok tunnel...")
        proc = subprocess.Popen(['ngrok', 'http', '8080'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,env=env)
        time.sleep(10)
        response = requests.get("http://127.0.0.1:4040/api/tunnels")
        if response.status_code == 200:
            data = response.json()
            serveo_url = data['tunnels'][0]['public_url']
            logging.info(f'Serveo URL: {serveo_url}')
            serveo_event.set()
        else:
            logging.error(f"Failed to get ngrok status. Response: {response.status_code}")
            serveo_event.set()
    except Exception as e:
        logging.error(f"Error generating Serveo URL: {e}")
        serveo_event.set()

# Generate QR code and display
def generate_qr_code():
    global serveo_url
    global qr_path
    serveo_event.wait()
    if serveo_url:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(serveo_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_path = os.path.join(app.config['upload_folder'], 'qr_code.png')
        img.save(qr_path)
        logging.info(f'QR code saved at {qr_path}')

        # Launch both displays
        threading.Thread(target=display_qr_on_tft, args=(qr_path,)).start()
        display_qr(qr_path)
    else:
        logging.error("Serveo URL is not available, skipping QR code generation.")

# Display QR in Tkinter window
def display_qr(qr_path):
    root = tk.Tk()
    root.title("Scan QR Code to Upload File")
    img = Image.open(qr_path).resize((300, 300))
    img_tk = ImageTk.PhotoImage(img)
    label = tk.Label(root, image=img_tk)
    label.image = img_tk
    label.pack(padx=10, pady=10)
    tk.Button(root, text="Close", command=root.destroy).pack(pady=10)
    root.after(0, root.deiconify)
    root.mainloop()

# Display QR on TFT
def display_qr_on_tft(qr_path, text="Scan the QR code to upload your file"):
    try:
        # Open and convert QR image
        qr_image = Image.open(qr_path).convert("RGB")

        # Calculate sizes for top 2/3 and bottom 1/3
        qr_width = WIDTH
        qr_height = int(HEIGHT * 2 / 3)

        text_width = WIDTH
        text_height = HEIGHT - qr_height  # bottom 1/3

        # Resize QR code to fit top 2/3 of the screen width and height
        qr_image = qr_image.resize((qr_width, qr_height))

        # Create blank image for full display
        final_image = Image.new("RGB", (WIDTH, HEIGHT), "black")

        # Paste QR code on top 2/3 of display
        final_image.paste(qr_image, (0, 0))

        # Prepare text area on bottom 1/3
        text_image = Image.new("RGB", (text_width, text_height), "black")
        draw = ImageDraw.Draw(text_image)

        # Font setup
        font_size = 18
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)

        # Wrap text to fit width with margin
        margin = 5
        max_text_width = text_width - 2 * margin
        lines = []
        words = text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
            if w <= max_text_width:
                line = test_line
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)

        # Draw text lines vertically centered in bottom area
        bbox = font.getbbox("A")
        line_height = bbox[3] - bbox[1]
        total_text_height = line_height * len(lines)
        y_text = (text_height - total_text_height) // 2

        for line in lines:
            draw.text((margin, y_text), line, font=font, fill="white")
            y_text += line_height

        # Paste text area on bottom 1/3 of display
        final_image.paste(text_image, (0, qr_height))

        # Show combined image on TFT
        display.image(final_image)
        logging.info("QR code and text displayed on TFT.")

    except Exception as e:
        logging.error(f"Failed to display QR and text on TFT: {e}")



def show_text(text):
    max_font_size = 30
    min_font_size = 10
    margin = 10  # margin on all sides

    image = Image.new("RGB", (WIDTH, HEIGHT), "black")
    draw = ImageDraw.Draw(image)

    def wrap_text(text, font, max_width):
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    font_size = max_font_size
    while font_size >= min_font_size:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        lines = wrap_text(text, font, WIDTH - 2 * margin)
        bbox = font.getbbox("A")
        line_height = bbox[3] - bbox[1]
        total_height = line_height * len(lines) + margin * 2
        if total_height <= HEIGHT:
            break
        font_size -= 1

    # Render text
    image = Image.new("RGB", (WIDTH, HEIGHT), "black")
    draw = ImageDraw.Draw(image)
    y_text = margin
    for line in lines:
        draw.text((margin, y_text), line, font=font, fill="white")
        y_text += line_height

    display.image(image)

def draw_countdown_clock(current_sec, total_sec=10):
    imageclock = Image.new("RGB", (WIDTH, HEIGHT), "black")
    draw = ImageDraw.Draw(imageclock)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 20
    radius = min(WIDTH, HEIGHT) // 3

    # Draw clock circle
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline="white", width=3)

    # Draw tick marks
    for angle_deg in range(0, 360, 30):
        angle_rad = math.radians(angle_deg)
        x_outer = cx + int(radius * math.cos(angle_rad))
        y_outer = cy + int(radius * math.sin(angle_rad))
        x_inner = cx + int((radius - 10) * math.cos(angle_rad))
        y_inner = cy + int((radius - 10) * math.sin(angle_rad))
        draw.line((x_inner, y_inner, x_outer, y_outer), fill="white", width=2)

    # Draw sweeping clock hand
    angle = 360 * (current_sec / total_sec)
    angle_rad = math.radians(angle - 90)
    x_hand = cx + int((radius - 20) * math.cos(angle_rad))
    y_hand = cy + int((radius - 20) * math.sin(angle_rad))
    draw.line((cx, cy, x_hand, y_hand), fill="red", width=3)

    # Static countdown number (int)
    countdown_number = total_sec - int(current_sec) + 1
    countdown_text = f"{countdown_number}"

    # Text bounding box
    bbox = draw.textbbox((0, 0), countdown_text, font=LARGE_FONT)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    draw.text(
        (cx - text_width // 2, cy + radius + 10),
        countdown_text,
        font=LARGE_FONT,
        fill="yellow"
    )

    display.image(imageclock)

# Upload route
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part'
    file1 = request.files['file']
    if file1.filename == '':
        return 'No selected file'
    file_path = os.path.join(app.config['upload_folder'], secure_filename(file1.filename))
    file1.save(file_path)
    logging.info(f'File saved at {file_path}')
    print_file(file_path)
    return 'File successfully uploaded to the computer we are preparing your doc to print'

# Print predefined files
@app.route('/print_printFile2', methods=['POST'])
def file2():
    data = request.get_json()
    page_count = int(data.get('page_count', 1))
    try:
        print_file(file_path2, page_count)
        return 'File 2 is printing'
    except subprocess.CalledProcessError as e:
        return 'Failed to print File 2'

@app.route('/print_printFile1', methods=['POST'])
def file3():
    data = request.get_json()
    page_count = int(data.get('page_count', 1))
    try:
        print_file(file_path3, page_count)
        return 'File 3 is printing'
    except subprocess.CalledProcessError as e:
        return 'Failed to print File 3'

def print_file(file_path, page_count=1):
    printer_name = 'HP-LaserJet-M1005'
    try:
        show_text("we are printing your doc please wait untill we complete")
        
        for page in range(page_count):
            result = subprocess.run(['lp', '-d', printer_name, file_path], check=True, text=True)
            logging.info(f'Successfully sent page {page + 1} to printer')
            status = capture_popup_message(window_name)  
            if status and status.lower() == 'completed':
                display_qr_on_tft(qr_path)

            time.sleep(5)

    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to print: {e.stderr}')

def get_window_id(window_name):
    try:
        
        icon_location = pyautogui.locateCenterOnScreen("/home/pi/screenshot.png",confidence = 0.8)  
        pyautogui.click(icon_location)
        
        result = subprocess.run(['xdotool', 'search', '--name', window_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,env=env)
        return result.stdout.strip()
    except Exception as e:
        return None

def capture_popup_message(window_name):
    try:
        window_id = get_window_id(window_name)
        if window_id:
            
            subprocess.run(["xdotool", "windowactivate", window_id],env=env)
            subprocess.run(["xdotool", "windowsize", window_id, "100%", "100%"],env=env)

            
            time.sleep(3)
            subprocess.run(['import', '-window', window_id, 'popup.png'],env=env)
            subprocess.run(['convert', 'popup.png', '-density', '300', 'popup.png'],env=env)
            
            time.sleep(2) #sleep to process the ocr

            subprocess.run(['tesseract', 'popup.png', 'output'],env=env)
            with open('output.txt', 'r') as file:
                message = file.read().strip()
                if 'out of paper' in message.lower():
                    print('out of paper')
                    return 'out of paper'
                elif 'completed' in message.lower() or 'print complete' in message.lower() or 'job finished' in message.lower():
                    print('completed')
                    return 'completed'
                elif 'not connected' in message.lower():
                    print('not connected')
                    return 'not connected'
                elif 'idle' in message.lower():
                    print('idle')
                    return 'idle'
                elif 'processing' in message.lower():
                    return 'processing'
        else:
            return 'window not found'
    except Exception as e:
        return 'error'

def ir_motor():
    try:
        print("checking of paper tray")
        #show_text("Waiting for object...\nObject = stop motors")

        while True:
            if GPIO.input(IR_DO_PIN) == GPIO.LOW:
                print("Paper tray have gone empty please wait we are processing")
                cancel = False

                for i in range(1, 6):
                    if GPIO.input(IR_DO_PIN) == GPIO.HIGH:
                        print("Paper is present in the system.")
                        #show_text("Object detected!\nMotors idle.")
                        cancel = True
                        break
                    draw_countdown_clock(i, 6)
                    time.sleep(1)

                if not cancel:
                    print("Printer is out of paper motors are going to run now")
                    show_text("Please wait we are putting paper into the printer")

                    # Motor 1 - 1 rotation
                    
                    for _ in range(total_steps):
                        GPIO.output(motor_pins[1]['STEP'], GPIO.HIGH)
                        time.sleep(delay_motor1)
                        GPIO.output(motor_pins[1]['STEP'], GPIO.LOW)
                        time.sleep(delay_motor1)

                    # Motor 2 - 10 rotations
                    for _ in range(total_steps * 10):
                        GPIO.output(motor_pins[2]['STEP'], GPIO.HIGH)
                        time.sleep(delay_motor2)
                        GPIO.output(motor_pins[2]['STEP'], GPIO.LOW)
                        time.sleep(delay_motor2)

                    print("refilling has been done successfully")
                    show_text("we have successfully completed the refilling process in the printer tray please wait we are printing the your paper if you have requested")
                    time.sleep(5)
                    status = capture_popup_message(window_name)
                    if (status and status.lower() == 'idle') or (status and status.lower() == 'not connected'):
                        display_qr_on_tft(qr_path)
                    else: 
                        print('we are not able read the status')
                    time.sleep(1.5)

            else:
                print("Paper is present Motors idle.")
                #show_text("Object detected!\nMotors idle.")

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("Interrupted by user.")

    finally:
        GPIO.cleanup()

@app.route('/start-upload', methods=['POST'])
def start_upload():
    threading.Thread(target=start_serveo).start()
    serveo_event.wait()
    threading.Thread(target=generate_qr_code).start()
    threading.Thread(target=ir_motor).start()

    return jsonify({'message': 'Serveo connetion is being established'})

if __name__ == '__main__':
    threading.Thread(target=start_serveo).start()
    serveo_event.wait()
    threading.Thread(target=generate_qr_code).start()
    threading.Thread(target=ir_motor).start()
    app.run(host='0.0.0.0', port=8080)
