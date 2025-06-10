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
from PIL import Image, ImageTk
import tkinter as tk

# Initializing Flask app 
app = Flask(__name__)
upload_folder = '/home/pi/uploads'
app.config['upload_folder'] = upload_folder
logging.basicConfig(level=logging.INFO)
CORS(app)

# Global Variables 
ngrok_link = None
ngrok_event = threading.Event()  #signal ready

# Predefined file paths
file_path2 = '/home/pi/uploads/SanDisk_bill.pdf'
file_path3 = '/home/pi/uploads/SanDisk_bill.pdf'

#window name
window_name = 'Document Print Status'

# Function to start ngrok tunnel and get ngrok URL
def start_ngrok():
    global ngrok_link
    try:
        logging.info("Starting ngrok tunnel...")
        
        # Start ngrok subprocess to tunnel port 8080
        proc = subprocess.Popen(
            ['ngrok', 'http', '8080'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Waiting for ngrok to start
       
        time.sleep(10)  # sleeping in 10 to ensure ngrok is ready

        status_url = "http://127.0.0.1:4040/api/tunnels"
        logging.info("Checking ngrok tunnel status at %s", status_url)
        
        # Request ngrok status
        response = requests.get(status_url)

        if response.status_code == 200:
            # Extracting the public URL from the response
            data = response.json()  
            ngrok_link = data['tunnels'][0]['public_url']
            logging.info(f'ngrok URL: {ngrok_link}')
            ngrok_event.set()  
        else:
            logging.error(f"Failed to get ngrok status. Response: {response.status_code}")
            ngrok_event.set()  
            return None
    except Exception as e:
        logging.error(f"Error generating ngrok URL: {e}")
        ngrok_event.set()  

# generating QR code
def generate_qr_code():
    global ngrok_link
    ngrok_event.wait()  
    if ngrok_link:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(ngrok_link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_path = os.path.join(app.config['upload_folder'], 'qr_code.png')
        img.save(qr_path)
        logging.info(f'QR code saved at {qr_path}')
        display_qr(qr_path)
    else:
        logging.error("ngrok URL is not available, skipping QR code generation.")

# displaying QR code 
def display_qr(qr_path):
    root = tk.Tk()
    root.title("Scan QR Code to Upload File")
    img = Image.open(qr_path).resize((300, 300))
    img_tk = ImageTk.PhotoImage(img)
    label = tk.Label(root, image=img_tk)
    label.image = img_tk  
    label.pack(padx=10, pady=10)
    close_button = tk.Button(root, text="Close", command=root.destroy)
    close_button.pack(pady=10)
    root.after(0, root.deiconify)  
    root.mainloop()

# Route to upload file
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logging.error('No file part in the request')
        return 'No file part'
    
    file1 = request.files['file']
    if file1.filename == '':
        logging.error('No selected file')
        return 'No selected file'
    
    if file1:
        file_name = secure_filename(file1.filename)
        file_path = os.path.join(app.config['upload_folder'], file_name)
        file1.save(file_path)
        logging.info(f'File saved at {file_path}')
        print_file(file_path)
        return 'File successfully uploaded to the computer'

# Routes to print predefined files
@app.route('/print_printFile2', methods=['POST'])
def file2():
    data = request.get_json()
    page_count = int(data.get('page_count', 1))
    try:
        print_file(file_path2, page_count)
        return 'File 2 is printing'
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to print File 2: {e}")
        return 'Failed to print File 2'

@app.route('/print_printFile1', methods=['POST'])
def file3():
    data = request.get_json()
    page_count = int(data.get('page_count', 1))
    try:
        print_file(file_path3, page_count)
        return 'File 3 is printing'
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to print File 3: {e}")
        return 'Failed to print File 3'

# Function to handle printing process
def print_file(file_path, page_count=1):
    printer_name = 'Canon_LBP2900'
    try:
        for page in range(page_count):
            result = subprocess.run(
                ['lp', '-d', printer_name, file_path],
                check=True, text=True
            )
            logging.info(f'Successfully sent page {page + 1} to printer: {result.stdout}')
            
            # Wait and check printer status after each page
            time.sleep(5)
            status = capture_popup_message(window_name)
            logging.info(f'Printer status after page {page + 1}: {status}')
            
            if 'out of paper' in status.lower():
                logging.error("Printer is out of paper")
                break  # Stop printing if out of paper
            elif 'offline' in status.lower():
                logging.error("Printer is offline")
                break  # Stop printing if offline
            else:
                logging.info(f"Page {page + 1} printed successfully")
                
    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to print: {e.stderr}')

# Function to check the printer status with the help of the window reading
def get_window_id(window_name):
    try:
       
        # Running the xdotool to read the window ID with the help of the name
        result = subprocess.run(
            ['xdotool', 'search', '--name', window_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        window_id = result.stdout.strip()
        return window_id
    except Exception as e:
        logging.error(f"An error occurred while getting the window ID: {e}")
        return None

# Function to capture the popup window message
def capture_popup_message(window_name):
    try:
        window_id = get_window_id(window_name)

        if window_id:
            subprocess.run(['xdotool', 'windowactivate', window_id])
            time.sleep(3)  # Increased sleep to ensure the window content is fully updated

            subprocess.run(['import', '-window', window_id, 'popup.png'])
            time.sleep(2)

            subprocess.run(['tesseract', 'popup.png', 'output'])
            with open('output.txt', 'r') as file:
                message = file.read().strip()

                # Check for "out of paper" message
                if 'out of paper' in message.lower():
                    logging.info("Printer is out of paper.")
                    return 'out of paper'
                else:
                    logging.info("No 'out of paper' status found.")
                    return 'paper is present'
        else:
            logging.error(f"Window '{window_name}' not found.")
            return 'window not found'

    except Exception as e:
        logging.error(f"An error occurred while capturing popup message: {e}")
        return 'error'

# Start ngrok connection on app start
@app.route('/start-upload', methods=['POST'])
def start_upload():
    threading.Thread(target=start_ngrok).start()
    ngrok_event.wait()  # Waiting until ngrok URL is ready before generating QR code
   
    threading.Thread(target=generate_qr_code).start()
    return jsonify({'message': 'ngrok connection is being established'})

# Main function to start the Flask app and ngrok, with periodic status checking
if __name__ == '__main__':
   
    # Start ngrok connection and QR code generation in separate threads
    
    threading.Thread(target=start_ngrok).start()
    
    ngrok_event.wait()  # Ensuring ngrok URL is generated before starting QR code generation
    
    threading.Thread(target=generate_qr_code).start()

    app.run(host='0.0.0.0', port=8080)
