"""
Configuration Management
Centralized configuration with validation and defaults
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration with validation"""
    
    # Server
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5000'))
    
    # Security
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_FILE_SIZE', 500 * 1024 * 1024))  # 500MB default
    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',')
    AUTH_ENABLED = os.getenv('AUTH_ENABLED', 'False').lower() == 'true'
    API_KEYS = set(os.getenv('API_KEYS', '').split(',')) - {''}
    
    # File Management
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'outputs'
    FILE_RETENTION_HOURS = int(os.getenv('FILE_RETENTION_HOURS', '24'))
    
    # Google Vision API
    # Service account credentials file path (JSON file)
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    # Legacy API key support (deprecated, use GOOGLE_APPLICATION_CREDENTIALS instead)
    GOOGLE_VISION_API_KEY = os.getenv('GOOGLE_VISION_API_KEY', '')
    
    # Devanagari Transliterator API
    DEVANAGARI_TRANSLITERATOR_API_KEY = os.getenv('devanagari_transliterator', '')
    
    # OCR Settings
    TESSERACT_CMD = os.getenv('TESSERACT_CMD')
    OCR_DPI = int(os.getenv('OCR_DPI', '400'))
    OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '0.7'))
    
    # Performance
    MAX_BACKGROUND_WORKERS = int(os.getenv('MAX_BACKGROUND_WORKERS', '3'))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')
    
    @classmethod
    def validate(cls):
        """Validate configuration and return list of warnings"""
        warnings = []
        
        if cls.DEBUG:
            warnings.append("⚠️  DEBUG mode is enabled - should be disabled in production")
        
        if cls.AUTH_ENABLED and not cls.API_KEYS:
            warnings.append("⚠️  AUTH_ENABLED but no API_KEYS configured")
        
        if cls.MAX_CONTENT_LENGTH > 100 * 1024 * 1024:
            warnings.append(f"⚠️  MAX_CONTENT_LENGTH is very large: {cls.MAX_CONTENT_LENGTH / 1024 / 1024:.0f}MB")
        
        if not cls.GOOGLE_APPLICATION_CREDENTIALS and not cls.GOOGLE_VISION_API_KEY:
            warnings.append("ℹ️  Google Vision API not configured - using local OCR only")
        elif cls.GOOGLE_VISION_API_KEY and not cls.GOOGLE_APPLICATION_CREDENTIALS:
            warnings.append("⚠️  Using deprecated GOOGLE_VISION_API_KEY - consider using GOOGLE_APPLICATION_CREDENTIALS")
        
        if cls.OCR_CONFIDENCE_THRESHOLD < 0.5:
            warnings.append("⚠️  OCR_CONFIDENCE_THRESHOLD is low - may cause excessive API calls")
        
        return warnings
    
    @classmethod
    def summary(cls):
        """Return configuration summary for display"""
        return {
            'debug': cls.DEBUG,
            'auth_enabled': cls.AUTH_ENABLED,
            'max_file_size_mb': cls.MAX_CONTENT_LENGTH / 1024 / 1024,
            'file_retention_hours': cls.FILE_RETENTION_HOURS,
            'google_vision_enabled': bool(cls.GOOGLE_APPLICATION_CREDENTIALS or cls.GOOGLE_VISION_API_KEY),
            'ocr_dpi': cls.OCR_DPI,
            'max_workers': cls.MAX_BACKGROUND_WORKERS,
        }


if __name__ == '__main__':
    print("Configuration Summary")
    print("=" * 50)
    
    config_summary = Config.summary()
    for key, value in config_summary.items():
        print(f"  {key}: {value}")
    
    print("\nValidation:")
    warnings = Config.validate()
    if warnings:
        for warning in warnings:
            print(f"  {warning}")
    else:
        print("  ✓ Configuration is valid")

