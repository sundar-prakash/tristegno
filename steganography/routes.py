import os
import uuid
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import stego_bp
from .stego_core import SteganographyCore
from auth.models import User, SteganographyOperation
from extensions import db, limiter
from datetime import datetime
import time

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff',  # Images
                      'wav', 'mp3', 'ogg',  # Audio
                      'mp4', 'avi', 'mov', 'mkv', 'wmv', 'webm'}  # Video

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}:
        return 'image'
    elif ext in {'wav', 'mp3', 'ogg'}:
        return 'audio'
    elif ext in {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'webm'}:
        return 'video'
    return 'unknown'

def safe_file_remove(file_path, max_attempts=5, delay=0.1):
    """Safely remove file with retry logic for Windows"""
    for attempt in range(max_attempts):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except (OSError, PermissionError) as e:
            if attempt < max_attempts - 1:
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Failed to remove {file_path} after {max_attempts} attempts: {e}")
                return False
    return False

@stego_bp.route('/encode', methods=['GET', 'POST'])
@login_required
# @limiter.limit("10 per hour")
def encode():
    if request.method == 'POST':
        file_path = None
        try:
            # Validate inputs
            if 'file' not in request.files:
                flash('No file selected')
                return redirect(request.url)
            
            file = request.files['file']
            secret_message = request.form.get('message', '')
            public_key_option = request.form.get('public_key_option', 'own')
            custom_public_key = request.form.get('custom_public_key', '').strip()
            
            if file.filename == '' or not secret_message:
                flash('Please select a file and enter a message')
                return redirect(request.url)
            
            if not allowed_file(file.filename):
                flash('File type not supported')
                return redirect(request.url)
            
            # Save uploaded file
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(file_path)
            
            # Determine which public key to use for encryption
            encryption_public_key = None
            
            if public_key_option == 'custom':
                # Validate custom public key
                if not custom_public_key:
                    flash('Please provide a public key or select "Use Own Key"')
                    return redirect(request.url)
                
                # Validate PEM format
                if not (custom_public_key.startswith('-----BEGIN PUBLIC KEY-----') and 
                        custom_public_key.endswith('-----END PUBLIC KEY-----')):
                    flash('Invalid public key format. Please provide a valid PEM-formatted public key.')
                    return redirect(request.url)
                
                try:
                    # Test if key is valid by trying to load it
                    from cryptography.hazmat.primitives import serialization
                    serialization.load_pem_public_key(custom_public_key.encode('utf-8'))
                    encryption_public_key = custom_public_key
                except Exception as e:
                    flash(f'Invalid public key: {str(e)}')
                    return redirect(request.url)
            else:
                # Use own public key
                db.session.refresh(current_user)
                
                if not current_user.public_key:
                    # Generate key pair if doesn't exist
                    private_key, public_key = SteganographyCore.generate_key_pair()
                    current_user.public_key = public_key
                    db.session.commit()
                    flash('New key pair generated. Save your private key securely!')
                    
                    # Return private key to user (they must save it)
                    return render_template('save_private_key.html', 
                                         private_key=private_key, 
                                         message=secret_message,
                                         filename=unique_filename)
                
                encryption_public_key = current_user.public_key
            
            # Encrypt message with selected public key
            encrypted_message = SteganographyCore.encrypt_message(
                secret_message, encryption_public_key
            )
            
            # Determine file type and hide message
            file_type = get_file_type(filename)
            output_filename = f"hidden_{unique_filename}"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            success = False
            
            if file_type == 'image':
                # Convert to PNG for better steganography
                if not filename.lower().endswith('.png'):
                    output_filename = output_filename.rsplit('.', 1)[0] + '.png'
                    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
                
                success = SteganographyCore.hide_message_in_image(
                    file_path, encrypted_message, output_path
                )
            elif file_type == 'audio':
                # Convert non-WAV audio to WAV
                temp_wav_path = file_path
                if not filename.lower().endswith('.wav'):
                    try:
                        from .format_converter import convert_audio_to_wav, has_ffmpeg
                        if not has_ffmpeg():
                            flash('FFmpeg is required for MP3/OGG conversion. Please install FFmpeg or use WAV files.')
                            return redirect(request.url)
                        
                        temp_wav_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}.wav")
                        convert_audio_to_wav(file_path, temp_wav_path)
                    except Exception as e:
                        flash(f'Audio conversion failed: {str(e)}')
                        return redirect(request.url)
                
                # Ensure output is WAV
                if not output_filename.lower().endswith('.wav'):
                    output_filename = output_filename.rsplit('.', 1)[0] + '.wav'
                    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
                
                success = SteganographyCore.hide_message_in_audio(
                    temp_wav_path, encrypted_message, output_path
                )
                
                # Clean up temporary WAV if we converted
                if temp_wav_path != file_path and os.path.exists(temp_wav_path):
                    safe_file_remove(temp_wav_path)
            elif file_type == 'video':
                # Convert non-MP4 video to MP4
                temp_video_path = file_path
                if not filename.lower().endswith('.mp4'):
                    try:
                        from .format_converter import convert_video_to_mp4, has_ffmpeg
                        if not has_ffmpeg():
                            flash('FFmpeg is required for video format conversion. Please install FFmpeg or use MP4 files.')
                            return redirect(request.url)
                        
                        temp_video_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}.mp4")
                        convert_video_to_mp4(file_path, temp_video_path)
                    except Exception as e:
                        flash(f'Video conversion failed: {str(e)}')
                        return redirect(request.url)
                
                # Ensure output is AVI (required for lossless FFV1 codec)
                if not output_filename.lower().endswith('.avi'):
                    output_filename = output_filename.rsplit('.', 1)[0] + '.avi'
                    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
                
                success = SteganographyCore.hide_message_in_video(
                    temp_video_path, encrypted_message, output_path
                )
                
                # Clean up temporary MP4 if we converted
                if temp_video_path != file_path and os.path.exists(temp_video_path):
                    safe_file_remove(temp_video_path)
            else:
                flash('File type not supported')
                return redirect(request.url)
            
            # Log operation
            operation = SteganographyOperation(
                user_id=current_user.id,
                operation_type='encode',
                original_filename=filename,
                processed_filename=output_filename,
                file_type=file_type,
                message_length=len(secret_message),
                ip_address=request.remote_addr,
                success=success
            )
            db.session.add(operation)
            db.session.commit()
            
            if success:
                flash('Message hidden successfully!')
                return render_template('encode_success.html', 
                                     filename=output_filename,
                                     original_name=filename)
            else:
                flash('Failed to hide message')
                
        except Exception as e:
            flash(f'Error: {str(e)}')
            # Log failed operation
            operation = SteganographyOperation(
                user_id=current_user.id,
                operation_type='encode',
                original_filename=filename if 'filename' in locals() else 'unknown',
                file_type=get_file_type(filename) if 'filename' in locals() else 'unknown',
                message_length=len(secret_message) if 'secret_message' in locals() else 0,
                ip_address=request.remote_addr,
                success=False
            )
            db.session.add(operation)
            db.session.commit()
        finally:
            # Clean up original file safely
            if file_path and os.path.exists(file_path):
                safe_file_remove(file_path)
    
    return render_template('encode.html')

@stego_bp.route('/decode', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour")
def decode():
    if request.method == 'POST':
        file_path = None
        try:
            # Validate inputs
            if 'file' not in request.files:
                flash('No file selected')
                return redirect(request.url)
            
            file = request.files['file']
            private_key = request.form.get('private_key', '')
            
            if file.filename == '' or not private_key:
                flash('Please select a file and enter your private key')
                return redirect(request.url)
            
            # Save uploaded file
            filename = secure_filename(file.filename)
            unique_filename = f"decode_{uuid.uuid4()}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(file_path)
            
            # Extract message
            file_type = get_file_type(filename)
            extracted_message = None
            
            if file_type == 'image':
                extracted_message = SteganographyCore.extract_message_from_image(file_path)
            elif file_type == 'audio':
                extracted_message = SteganographyCore.extract_message_from_audio(file_path)
            elif file_type == 'video':
                extracted_message = SteganographyCore.extract_message_from_video(file_path)
            else:
                flash('File type not supported for decoding')
                return redirect(request.url)
            
            if not extracted_message:
                raise ValueError("No hidden message found")
            
            # Validate private key format
            if not (private_key.startswith('-----BEGIN PRIVATE KEY-----') or 
                    private_key.startswith('-----BEGIN RSA PRIVATE KEY-----')):
                raise ValueError("Invalid private key format. Must be a PEM-formatted private key starting with '-----BEGIN PRIVATE KEY-----'")
            
            # Decrypt message
            try:
                decrypted_message = SteganographyCore.decrypt_message(
                    extracted_message, private_key
                )
            except ValueError as e:
                if "Ciphertext length" in str(e) or "Decryption failed" in str(e):
                    raise ValueError("Decryption failed. This usually means you're using the wrong private key. Make sure you're using the private key that matches the public key used during encoding.")
                raise
            
            # Log operation
            operation = SteganographyOperation(
                user_id=current_user.id,
                operation_type='decode',
                original_filename=filename,
                file_type=file_type,
                ip_address=request.remote_addr,
                success=True
            )
            db.session.add(operation)
            db.session.commit()
            
            return render_template('decode_success.html', 
                                 message=decrypted_message,
                                 filename=filename)
            
        except Exception as e:
            flash(f'Decoding failed: {str(e)}')
            # Log failed operation
            operation = SteganographyOperation(
                user_id=current_user.id,
                operation_type='decode',
                original_filename=filename if 'filename' in locals() else 'unknown',
                file_type=get_file_type(filename) if 'filename' in locals() else 'unknown',
                ip_address=request.remote_addr,
                success=False
            )
            db.session.add(operation)
            db.session.commit()
        finally:
            # Clean up uploaded file safely
            if file_path and os.path.exists(file_path):
                safe_file_remove(file_path)
    
    return render_template('decode.html')

@stego_bp.route('/download/<filename>')
@login_required
def download_file(filename):
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, 
                           download_name=filename.replace('hidden_', ''))
        else:
            flash('File not found')
            return redirect(url_for('stego.encode'))
    except Exception as e:
        flash(f'Download failed: {str(e)}')
        return redirect(url_for('stego.encode'))

@stego_bp.route('/history')
@login_required
def history():
    operations = SteganographyOperation.query.filter_by(user_id=current_user.id)\
                                           .order_by(SteganographyOperation.timestamp.desc())\
                                           .all()
    return render_template('history.html', operations=operations)

@stego_bp.route('/check_capacity', methods=['POST'])
@login_required
def check_capacity():
    """AJAX endpoint to check file capacity"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    message = request.form.get('message', '')
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not supported'}), 400
    
    temp_path = None
    try:
        # Save temp file
        temp_filename = f"temp_{uuid.uuid4()}_{secure_filename(file.filename)}"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
        file.save(temp_path)
        
        file_type = get_file_type(file.filename)
        
        if file_type == 'image':
            from PIL import Image
            with Image.open(temp_path) as img:
                width, height = img.size
                max_capacity = (width * height * 3) // 8  # bits to bytes
        elif file_type == 'audio':
            import wave
            with wave.open(temp_path, 'rb') as audio:
                frames = audio.getnframes()
            max_capacity = frames // 8
        elif file_type == 'video':
            max_capacity = SteganographyCore.get_video_capacity(temp_path)
        else:
            max_capacity = 0
        
        # Account for encryption overhead (roughly 30% increase)
        usable_capacity = int(max_capacity * 0.7)
        message_size = len(message.encode())
        
        return jsonify({
            'max_capacity': usable_capacity,
            'message_size': message_size,
            'can_hide': message_size <= usable_capacity,
            'usage_percent': (message_size / usable_capacity * 100) if usable_capacity > 0 else 100
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp file safely
        if temp_path:
            safe_file_remove(temp_path)
