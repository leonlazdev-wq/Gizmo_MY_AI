"""
Automatic model file cleanup module.
Removes corrupt/empty model files to prevent loading errors.
"""

from pathlib import Path
from modules.logging_colors import logger


def cleanup_corrupt_models():
    """
    Remove corrupt model files on startup.
    Files smaller than 100KB are considered corrupt and auto-deleted.
    """
    
    models_dir = Path('models')
    if not models_dir.exists():
        logger.info("Models directory does not exist yet")
        return
    
    # All supported model file extensions
    extensions = [
        '*.gguf',           # GGUF models (llama.cpp)
        '*.safetensors',    # SafeTensors format
        '*.bin',            # PyTorch bins
        '*.pth',            # PyTorch checkpoints
        '*.pt',             # PyTorch models
        '*.ckpt',           # Checkpoint files
        '*.h5',             # Keras/TensorFlow
        '*.pb',             # TensorFlow protobuf
        '*.onnx',           # ONNX models
    ]
    
    corrupt_files = []
    MIN_VALID_SIZE = 100 * 1024  # 100KB minimum
    
    # Scan all model files
    for ext in extensions:
        for model_file in models_dir.rglob(ext):
            try:
                file_size = model_file.stat().st_size
                
                # Files smaller than 100KB are definitely corrupt
                if file_size < MIN_VALID_SIZE:
                    corrupt_files.append((model_file, file_size))
            
            except Exception as e:
                logger.error(f"Error checking {model_file.name}: {e}")
    
    # Delete corrupt files
    if corrupt_files:
        logger.warning(f"Found {len(corrupt_files)} corrupt model files:")
        
        for file_path, size in corrupt_files:
            logger.warning(f"  • {file_path.name} ({size} bytes)")
            
            try:
                file_path.unlink()
                logger.info(f"    ✓ Deleted")
            except Exception as e:
                logger.error(f"    ✗ Could not delete: {e}")
        
        logger.info(f"Cleanup complete: removed {len(corrupt_files)} corrupt files")
    else:
        logger.info("Model file check: all files valid")


def validate_model_file(model_path):
    """
    Validate that a model file is readable and has content.
    
    Args:
        model_path: Path to model file (str or Path)
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    from pathlib import Path
    
    model_path = Path(model_path)
    
    # Check exists
    if not model_path.exists():
        return False, f"File not found: {model_path.name}"
    
    # Check size
    try:
        file_size = model_path.stat().st_size
    except Exception as e:
        return False, f"Cannot read file stats: {e}"
    
    # Minimum 1KB for any valid model file
    MIN_SIZE = 1024
    if file_size < MIN_SIZE:
        return False, f"File too small ({file_size} bytes, expected >{MIN_SIZE})"
    
    # For GGUF files, verify magic number
    if model_path.suffix.lower() == '.gguf':
        try:
            import struct
            with open(model_path, 'rb') as f:
                magic_bytes = f.read(4)
                if len(magic_bytes) < 4:
                    return False, "Cannot read GGUF header"
                
                magic = struct.unpack("<I", magic_bytes)[0]
                GGUF_MAGIC = 0x46554747  # "GGUF" in little-endian
                
                if magic != GGUF_MAGIC:
                    return False, f"Invalid GGUF magic (got 0x{magic:08X}, expected 0x{GGUF_MAGIC:08X})"
        
        except Exception as e:
            return False, f"Error validating GGUF: {e}"
    
    return True, None
