import requests
from bs4 import BeautifulSoup
import os
import uuid
import time
import shutil
import numpy as np
import wave
import struct
import cv2

# Configuration
BASE_URL = "http://127.0.0.1:5000"
TEST_EMAIL = f"test_{uuid.uuid4()}@example.com"
TEST_PASSWORD = "Password123!"
TEST_USERNAME = f"user_{uuid.uuid4().hex[:8]}"
MESSAGE = "This is a secret automation test message!"

# Paths (Relative to script execution)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TEST_ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")

# Ensure directories exist
os.makedirs(TEST_ASSETS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()

def log(message):
    timestamp = time.strftime('%H:%M:%S')
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    with open(os.path.join(SCRIPT_DIR, "test_debug.txt"), "a") as f:
        f.write(formatted_message + "\n")

def get_csrf_token(url):
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrf_token'})
    return csrf_token['value'] if csrf_token else None

def create_test_assets():
    log("Creating test assets...")
    
    # 1. Create Image (PNG)
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    img_path = os.path.join(TEST_ASSETS_DIR, "test_image.png")
    from PIL import Image
    Image.fromarray(img).save(img_path)
    
    # 2. Create Audio (WAV)
    audio_path = os.path.join(TEST_ASSETS_DIR, "test_audio.wav")
    with wave.open(audio_path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        data = struct.pack('<h', 0) * 44100  # 1 sec silence
        w.writeframes(data)
        
    # 3. Create Video (MP4) - Input can be mp4, output will be avi
    video_path = os.path.join(TEST_ASSETS_DIR, "test_video.mp4")
    height, width = 480, 640
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 30, (width, height))
    for _ in range(30): # 1 sec
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        out.write(frame)
    out.release()
    
    return img_path, audio_path, video_path

def register():
    log("Testing Registration...")
    url = f"{BASE_URL}/auth/register"
    csrf_token = get_csrf_token(url)
    
    data = {
        'csrf_token': csrf_token,
        'email': TEST_EMAIL,
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'confirm_password': TEST_PASSWORD
    }
    
    response = session.post(url, data=data)
    if response.url == f"{BASE_URL}/auth/login" or "Registration successful" in response.text:
         log("Reference Check: Registration Likely Successful (Redirected to Login)")
         return True
    
    # Check for success message in html if not redirected
    if "Registration successful" in response.text:
        log("Registration Successful")
        return True
        
    log("Registration Failed")
    with open("registration_failure.html", "w") as f:
        f.write(response.text)
    return False

def login():
    log("Testing Login...")
    url = f"{BASE_URL}/auth/login"
    csrf_token = get_csrf_token(url)
    
    data = {
        'csrf_token': csrf_token,
        'email': TEST_EMAIL,
        'password': TEST_PASSWORD
    }
    
    response = session.post(url, data=data)
    if f"Welcome back, {TEST_USERNAME}" in response.text or "/stego/encode" in response.text or response.url == f"{BASE_URL}/":
        log("Login Successful")
        return True
    
    log("Login Failed")
    return False

def generate_keys_and_encode_decode(file_path, file_type):
    log(f"Testing {file_type.upper()} Steganography...")
    
    # --- ENCODE ---
    encode_url = f"{BASE_URL}/stego/encode"
    csrf_token = get_csrf_token(encode_url)
    
    if not csrf_token:
        log("Failed to get CSRF token for encode")
        return False

    files = {'file': open(file_path, 'rb')}
    data = {
        'csrf_token': csrf_token,
        'message': MESSAGE,
        'public_key_option': 'own' 
    }
    
    log(f"Uploading {file_type} for encoding...")
    response = session.post(encode_url, files=files, data=data)
    
    # Check if keys were generated (first time only)
    private_key = None
    if "Save your private key securely" in response.text:
        log("New Key Pair Generated. Extracting Private Key...")
        soup = BeautifulSoup(response.text, 'html.parser')
        # Assuming private key is in a textarea or code block. 
        # Based on steganography/routes.py: return render_template('save_private_key.html', private_key=private_key...)
        # We need to parse it. Let's look for the textarea content.
        textarea = soup.find('textarea')
        if textarea:
            private_key = textarea.text.strip()
        
        # We also need the filename to download
        # Route passes 'filename' (the output filename) to the template
        # Let's find the "Continue" or "Download" link/button that might have the filename
        # Or look for a success message with the filename?
        # Actually, in 'save_private_key.html', the user hasn't downloaded the file yet?
        # Wait, the code says: return render_template('save_private_key.html' ... filename=unique_filename)
        # But where is the output file?
        # Re-reading routes.py:
        # If keys generated -> returns 'save_private_key.html'.
        # The encoding actually happens *before* this return?
        # No, wait. 
        # routes.py Line 118: returns 'save_private_key.html'. The encoding logic (lines 126+) is AFTER the key check block BUT
        # 'return' terminates the function!
        # So if keys are generated, NO ENCODING HAPPENS in that request! The user gets the key and has to try again?
        # Let's check routes.py logic again.
        
        # routes.py:
        # if not current_user.public_key:
        #    generate keys
        #    return render_template('save_private_key.html' ...)
        # encryption_public_key = current_user.public_key
        
        # YES! If keys are generated, the execution stops and returns the page. 
        # The file was NOT encoded yet.
        # We need to save the private key and RETRY the encoding.
        
        # Save private key to file for later use
        with open(os.path.join(OUTPUT_DIR, "my_private_key.pem"), "w") as f:
            f.write(private_key)
            
        log("Private key saved. Retrying encoding...")
        
        # Reuse file and data
        files['file'].close()
        files = {'file': open(file_path, 'rb')}
        # Get fresh CSRF
        csrf_token = get_csrf_token(encode_url)
        data['csrf_token'] = csrf_token
        
        response = session.post(encode_url, files=files, data=data)

    elif os.path.exists(os.path.join(OUTPUT_DIR, "my_private_key.pem")):
         # Load existing private key for decoding later
         with open(os.path.join(OUTPUT_DIR, "my_private_key.pem"), "r") as f:
             private_key = f.read()
    else:
        # If we didn't get a key and don't have one, something is wrong or we already have one on server?
        # The server stores public key. We assumed we're a fresh user. 
        pass

    if "Message hidden successfully" not in response.text:
        log(f"Encoding Failed. Status Code: {response.status_code}")
        # log(f"Response Body: {response.text[:500]}") # Uncomment if needed
        return False
    
    log("Encoding Successful.")
    
    # Extract output filename from response
    soup = BeautifulSoup(response.text, 'html.parser')
    # Look for download link: <a href="/stego/download/hidden_...">
    download_link = soup.find('a', href=True, string=lambda s: s and "Download" in str(s)) # Improved string check
    if not download_link:
        download_link = soup.find('a', href=lambda h: h and "/stego/download/" in h)
    
    if not download_link:
        log("Could not find download link. Dumping HTML snippet:")
        log(str(soup)[:500])
        return False
        
    download_url_path = download_link['href']
    output_filename = download_url_path.split('/')[-1]
    
    # Download the encoded file
    log(f"Downloading {output_filename}...")
    dl_response = session.get(f"{BASE_URL}{download_url_path}")
    downloaded_file_path = os.path.join(OUTPUT_DIR, output_filename)
    with open(downloaded_file_path, 'wb') as f:
        f.write(dl_response.content)
        
    log(f"Downloaded size: {os.path.getsize(downloaded_file_path)} bytes")
        
    # --- DECODE ---
    decode_url = f"{BASE_URL}/stego/decode"
    csrf_token = get_csrf_token(decode_url)
    
    log("Testing Decoding...")
    files = {'file': open(downloaded_file_path, 'rb')}
    
    if not private_key:
        log("CRITICAL: Missing private key for decoding!")
        return False
        
    data = {
        'csrf_token': csrf_token,
        'private_key': private_key
    }
    
    response = session.post(decode_url, files=files, data=data)
    
    if MESSAGE in response.text and ("Message Decoded" in response.text or "Message Decoded Successfully" in response.text):
        log(f"{file_type.upper()} Validation PASSED: Message matched!")
        return True
    elif "Decryption failed" in response.text:
        log(f"{file_type.upper()} Validation FAILED: Decryption failed.")
        return False
    else:
        log(f"{file_type.upper()} Validation FAILED: Message not found in response.")
        with open(os.path.join(SCRIPT_DIR, f"decode_failure_{file_type}.html"), "w") as f:
            f.write(response.text)
        return False

def run_suite():
    try:
        if not register(): return
        if not login(): return
        
        img_path, audio_path, video_path = create_test_assets()
        
        results = {}
        
        results['Image'] = generate_keys_and_encode_decode(img_path, 'image')
        results['Audio'] = generate_keys_and_encode_decode(audio_path, 'audio')
        results['Video'] = generate_keys_and_encode_decode(video_path, 'video')
        
        # Report
        report_path = os.path.join(SCRIPT_DIR, "test_result.txt")
        with open(report_path, "w") as f:
            f.write("--- Automation Test Results ---\n")
            all_passed = True
            for test, passed in results.items():
                status = "PASSED" if passed else "FAILED"
                f.write(f"{test}: {status}\n")
                if not passed: all_passed = False
            
            f.write("\n")
            if all_passed:
                f.write("FINAL RESULT: ALL TESTS PASSED\n")
            else:
                f.write("FINAL RESULT: SOME TESTS FAILED\n")
        
        log(f"Test Suite Completed. Results saved to {report_path}")
        
    except Exception as e:
        log(f"Test Suite Crashing: {e}")
        import traceback
        traceback.print_exc()

def cleanup():
    log("Cleaning up...")
    if os.path.exists(TEST_ASSETS_DIR):
        shutil.rmtree(TEST_ASSETS_DIR)
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

if __name__ == "__main__":
    run_suite()
    # cleanup() # Uncomment to clean up after run
