import os
import cv2
import numpy as np
from PIL import Image
import wave
import struct
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import base64

class SteganographyCore:
    
    @staticmethod
    def generate_key_pair():
        """Generate RSA key pair for encryption"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem.decode('utf-8'), public_pem.decode('utf-8')

    
    @staticmethod
    def encrypt_message(message, public_key_pem):
        """Encrypt message using RSA public key"""
        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
        
        # For large messages, use hybrid encryption
        if len(message.encode()) > 190:  # RSA limit
            # Generate symmetric key
            symmetric_key = Fernet.generate_key()
            f = Fernet(symmetric_key)
            encrypted_message = f.encrypt(message.encode())
            
            # Encrypt symmetric key with RSA
            encrypted_key = public_key.encrypt(
                symmetric_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return base64.b64encode(encrypted_key + b'||' + encrypted_message).decode()
        else:
            encrypted = public_key.encrypt(
                message.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return base64.b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt_message(encrypted_message, private_key_pem):
        """Decrypt message using RSA private key"""
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'), 
            password=None
        )
        
        encrypted_data = base64.b64decode(encrypted_message.encode())
        
        if b'||' in encrypted_data:
            # Hybrid decryption
            parts = encrypted_data.split(b'||', 1)
            encrypted_key = parts[0]
            encrypted_message_data = parts[1]
            
            # Decrypt symmetric key
            symmetric_key = private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt message
            f = Fernet(symmetric_key)
            decrypted = f.decrypt(encrypted_message_data)
            return decrypted.decode()
        else:
            decrypted = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted.decode()
    
    @staticmethod
    def hide_message_in_image(image_path, message, output_path):
        """Hide encrypted message in image using LSB steganography"""
        img = Image.open(image_path)
        img = img.convert('RGB')
        width, height = img.size
        
        # Convert message to binary
        binary_message = ''.join(format(ord(char), '08b') for char in message)
        binary_message += '1111111111111110'  # Delimiter
        
        # Check capacity
        max_capacity = width * height * 3  # 3 channels (RGB)
        if len(binary_message) > max_capacity:
            raise ValueError(f"Message too large. Max capacity: {max_capacity//8} chars")
        
        data_index = 0
        pixels = list(img.getdata())
        
        for i in range(len(pixels)):
            if data_index >= len(binary_message):
                break
                
            pixel = list(pixels[i])
            
            for j in range(3):  # RGB channels
                if data_index >= len(binary_message):
                    break
                
                # Modify LSB
                pixel[j] = (pixel[j] & 0xFE) | int(binary_message[data_index])
                data_index += 1
            
            pixels[i] = tuple(pixel)
        
        # Save image
        new_img = Image.new('RGB', (width, height))
        new_img.putdata(pixels)
        new_img.save(output_path, 'PNG')
        
        return True
    
    @staticmethod
    def extract_message_from_image(image_path):
        """Extract hidden message from image"""
        img = Image.open(image_path)
        img = img.convert('RGB')
        pixels = list(img.getdata())
        
        binary_message = ''
        
        for pixel in pixels:
            for channel in pixel:
                binary_message += str(channel & 1)
        
        # Find delimiter
        delimiter = '1111111111111110'
        if delimiter in binary_message:
            binary_message = binary_message[:binary_message.index(delimiter)]
        
        # Convert binary to text
        message = ''
        for i in range(0, len(binary_message), 8):
            byte = binary_message[i:i+8]
            if len(byte) == 8:
                message += chr(int(byte, 2))
        
        return message
    
    @staticmethod
    def hide_message_in_audio(audio_path, message, output_path):
        """Hide encrypted message in WAV audio using LSB"""
        # Convert to WAV if needed
        if not audio_path.lower().endswith('.wav'):
            raise ValueError("Only WAV format supported for audio steganography")
        
        with wave.open(audio_path, 'rb') as audio:
            frames = audio.readframes(-1)
            sound_info = [audio.getnframes(), audio.getnchannels(), 
                         audio.getsampwidth(), audio.getframerate()]
            
        # Convert to numpy array
        audio_data = np.frombuffer(frames, dtype=np.int16).copy()
        
        # Convert message to binary
        binary_message = ''.join(format(ord(char), '08b') for char in message)
        binary_message += '1111111111111110'  # Delimiter
        
        # Check capacity
        if len(binary_message) > len(audio_data):
            raise ValueError("Message too large for audio file")
        
        # Hide message in LSB
        for i in range(len(binary_message)):
            audio_data[i] = (audio_data[i] & 0xFFFE) | int(binary_message[i])
        
        # Save modified audio
        with wave.open(output_path, 'wb') as modified_audio:
            modified_audio.setnframes(sound_info[0])
            modified_audio.setnchannels(sound_info[1])
            modified_audio.setsampwidth(sound_info[2])
            modified_audio.setframerate(sound_info[3])
            modified_audio.writeframes(audio_data.tobytes())
        
        return True
    
    @staticmethod
    def extract_message_from_audio(audio_path):
        """Extract hidden message from audio"""
        with wave.open(audio_path, 'rb') as audio:
            frames = audio.readframes(-1)
        
        audio_data = np.frombuffer(frames, dtype=np.int16)
        
        # Extract LSBs
        binary_message = ''.join(str(sample & 1) for sample in audio_data)
        
        # Find delimiter
        delimiter = '1111111111111110'
        if delimiter in binary_message:
            binary_message = binary_message[:binary_message.index(delimiter)]
        
        # Convert binary to text
        message = ''
        for i in range(0, len(binary_message), 8):
            byte = binary_message[i:i+8]
            if len(byte) == 8:
                try:
                    message += chr(int(byte, 2))
                except ValueError:
                    continue
        
        return message
    
    @staticmethod
    def hide_message_in_video(video_path, message, output_path):
        """Hide encrypted message in video using LSB steganography on frames"""
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Convert message to binary
        binary_message = ''.join(format(ord(char), '08b') for char in message)
        binary_message += '1111111111111110'  # Delimiter
        
        # Check capacity
        max_capacity = total_frames * width * height * 3  # All frames, all pixels, all channels
        if len(binary_message) > max_capacity:
            cap.release()
            raise ValueError(f"Message too large for video. Max capacity: {max_capacity//8} bytes")
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'FFV1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            cap.release()
            raise ValueError("Could not create output video file")
        
        data_index = 0
        frame_count = 0
        message_embedded = False
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Embed message in frames until complete
                if not message_embedded:
                    # Make a writable copy of the flattened frame
                    frame_flat = frame.flatten().copy()
                    
                    for i in range(len(frame_flat)):
                        if data_index >= len(binary_message):
                            message_embedded = True
                            break
                        
                        # Modify LSB
                        frame_flat[i] = (frame_flat[i] & 0xFE) | int(binary_message[data_index])
                        data_index += 1
                    
                    # Reshape back to original frame shape
                    frame = frame_flat.reshape(frame.shape)
                
                out.write(frame)
                frame_count += 1
            
            return True
            
        finally:
            cap.release()
            out.release()
    
    @staticmethod
    def extract_message_from_video(video_path):
        """Extract hidden message from video"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")
        
        binary_message = ''
        delimiter = '1111111111111110'
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extract LSBs from frame
                frame_flat = frame.flatten()
                for pixel_value in frame_flat:
                    binary_message += str(pixel_value & 1)
                    
                    # Check if we found the delimiter
                    if len(binary_message) >= 16 and binary_message[-16:] == delimiter:
                        binary_message = binary_message[:-16]
                        
                        # Convert binary to text
                        message = ''
                        for i in range(0, len(binary_message), 8):
                            byte = binary_message[i:i+8]
                            if len(byte) == 8:
                                try:
                                    message += chr(int(byte, 2))
                                except ValueError:
                                    continue
                        
                        return message
            
            raise ValueError("No hidden message found (delimiter not detected)")
            
        finally:
            cap.release()
    
    @staticmethod
    def get_video_capacity(video_path):
        """Calculate the maximum message capacity of a video file"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")
        
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate max capacity in bits, convert to bytes
            max_capacity_bits = total_frames * width * height * 3
            max_capacity_bytes = max_capacity_bits // 8
            
            # Account for encryption overhead (roughly 30% increase)
            usable_capacity = int(max_capacity_bytes * 0.7)
            
            return usable_capacity
            
        finally:
            cap.release()
