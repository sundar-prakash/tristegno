import cv2
import numpy as np
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from steganography.stego_core import SteganographyCore

def log_result(message):
    print(message)
    with open("codec_results.txt", "a") as f:
        f.write(message + "\n")

def create_test_video(filename, width=640, height=480, frames=60):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, 30, (width, height))
    for i in range(frames):
        # Create some noise/content to simulate real video
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

def test_codec(codec, extension, input_path):
    output_filename = f"output_{codec}.{extension}"
    log_result(f"\nTesting Codec: {codec} ({extension})")
    
    # 1. Hide Message
    msg = "Secret123"
    try:
        cap = cv2.VideoCapture(input_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if len(codec) == 4:
            fourcc = cv2.VideoWriter_fourcc(*codec)
        else:
             fourcc = cv2.VideoWriter_fourcc(*codec)

        out = cv2.VideoWriter(output_filename, fourcc, fps, (width, height))
        
        binary_message = ''.join(format(ord(char), '08b') for char in msg)
        binary_message += '1111111111111110'
        
        data_index = 0
        message_embedded = False
        
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            if not message_embedded:
                frame_flat = frame.flatten()
                remaining = len(binary_message) - data_index
                if remaining > 0:
                    available = len(frame_flat)
                    to_write = min(remaining, available)
                    
                    for i in range(to_write):
                        frame_flat[i] = (frame_flat[i] & 0xFE) | int(binary_message[data_index])
                        data_index += 1
                        
                    frame = frame_flat.reshape(frame.shape)
                    if data_index >= len(binary_message):
                        message_embedded = True
            
            out.write(frame)
            
        cap.release()
        out.release()
        
        if not os.path.exists(output_filename):
            log_result("FAILED: Output file not created")
            return
            
        size = os.path.getsize(output_filename)
        log_result(f"Output Size: {size/1024/1024:.2f} MB")
        
        # 2. Extract Message
        extracted = SteganographyCore.extract_message_from_video(output_filename)
        if extracted == msg:
            log_result("SUCCESS: Message recovered correctly!")
        else:
            log_result(f"FAILED: Message mismatch. Got '{extracted}'")
            
    except Exception as e:
        log_result(f"ERROR: {e}")

if __name__ == "__main__":
    if os.path.exists("codec_results.txt"):
        os.remove("codec_results.txt")
        
    test_video_path = "compression_source.mp4"
    if not os.path.exists(test_video_path):
        create_test_video(test_video_path)
        
    log_result(f"Source Video: {test_video_path} ({os.path.getsize(test_video_path)/1024/1024:.2f} MB)")
    
    # Test 1: FFV1 (Current Baseline)
    test_codec('FFV1', 'avi', test_video_path)
    
    # Test 2: H.264 (avc1) - Standard
    test_codec('avc1', 'mp4', test_video_path)
    
    # Test 4: PNG (Lossless) - Experimental
    # Note: 'png ' codec might not be supported by all containers/builds
    try:
        test_codec('png ', 'avi', test_video_path)
    except:
        log_result("PNG Codec not supported")
