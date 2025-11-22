"""
Google Vision OCR Processor
Uses Google Vision API for high-accuracy OCR on voter ID regions
"""

import os
import base64
import requests
from typing import Dict, Optional
from dotenv import load_dotenv
from voter_id_corrector import correct_voter_id

# Load environment variables
load_dotenv()

class GoogleVisionOCRProcessor:
    """
    High-accuracy OCR processor using Google Vision API
    Superior to Tesseract for Marathi and Hindi text extraction
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Google Vision OCR with API key"""
        self.api_key = api_key or os.getenv('GOOGLE_VISION_API_KEY')
        
        if not self.api_key:
            print("WARNING: GOOGLE_VISION_API_KEY not set - will fallback to Tesseract OCR")
            self.enabled = False
            return
        
        self.api_url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
        self.enabled = True
        print(f"OK: Google Vision OCR initialized")
        print(f"  API URL: {self.api_url[:50]}...")
    
    def is_available(self) -> bool:
        """Check if Google Vision OCR is available and configured"""
        return self.enabled
    
    def extract_text_from_image(self, image_bytes: bytes, language: str = "en") -> Dict:
        """
        Extract text from image using Google Vision API
        
        Args:
            image_bytes: Image data as bytes (PNG/JPEG)
            language: Language code (en, hi, mr for Marathi)
        
        Returns:
            Dictionary with:
                - text: Extracted text string
                - confidence: Average confidence score (0-1)
                - lines: List of text lines with bounding boxes
                - success: Boolean indicating success
        """
        if not self.enabled:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'error': 'Google Vision OCR not configured'
            }
        
        try:
            # Convert image bytes to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Map language codes
            language_hints = []
            if language == 'hi':
                language_hints = ['hi', 'en']
            elif language == 'mr':
                language_hints = ['mr', 'hi', 'en']
            else:
                language_hints = ['en', 'hi']
            
            # Prepare request
            request_body = {
                'requests': [{
                    'image': {
                        'content': image_base64
                    },
                    'features': [{
                        'type': 'TEXT_DETECTION',
                        'maxResults': 1
                    }],
                    'imageContext': {
                        'languageHints': language_hints
                    }
                }]
            }
            
            # Make API request
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=request_body,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"Google Vision API error: {response.status_code}"
                print(f"  WARNING: {error_msg}")
                print(f"  Response: {response.text[:200]}")
                return {
                    'success': False,
                    'text': '',
                    'confidence': 0.0,
                    'error': error_msg
                }
            
            # Parse response
            result = response.json()
            
            if 'responses' not in result or not result['responses']:
                return {
                    'success': False,
                    'text': '',
                    'confidence': 0.0,
                    'error': 'No response from API'
                }
            
            response_data = result['responses'][0]
            
            # Check for errors
            if 'error' in response_data:
                error_msg = response_data['error'].get('message', 'Unknown error')
                return {
                    'success': False,
                    'text': '',
                    'confidence': 0.0,
                    'error': error_msg
                }
            
            # Extract text from text annotations
            text_lines = []
            all_lines = []
            text_annotations = response_data.get('textAnnotations', [])
            
            if not text_annotations:
                return {
                    'success': False,
                    'text': '',
                    'confidence': 0.0,
                    'error': 'No text detected'
                }
            
            # First annotation contains full text
            full_text = text_annotations[0].get('description', '').strip()
            
            # Extract individual lines from other annotations
            for annotation in text_annotations[1:]:
                line_text = annotation.get('description', '').strip()
                if line_text:
                    text_lines.append(line_text)
                    
                    # Get bounding box
                    bounding_poly = annotation.get('boundingPoly', {})
                    vertices = bounding_poly.get('vertices', [])
                    
                    all_lines.append({
                        'text': line_text,
                        'boundingBox': vertices
                    })
            
            # If no individual lines, use full text
            if not text_lines:
                text_lines = [full_text] if full_text else []
            
            # Estimate confidence (Google Vision doesn't provide confidence scores)
            confidence = self._estimate_confidence(full_text)
            
            return {
                'success': True,
                'text': full_text,
                'confidence': confidence,
                'lines': all_lines,
                'lineCount': len(text_lines)
            }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'error': 'Request timeout'
            }
        
        except Exception as e:
            print(f"  WARNING: Google Vision OCR error: {str(e)}")
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _estimate_confidence(self, text: str) -> float:
        """Estimate confidence based on text quality"""
        if not text or len(text.strip()) == 0:
            return 0.0
        
        confidence = 0.85  # Base confidence for Google Vision
        
        # Increase confidence if text looks valid
        if len(text) > 5:
            confidence = 0.9
        
        # Check for alphanumeric content
        has_letters = any(c.isalpha() for c in text)
        has_digits = any(c.isdigit() for c in text)
        
        if has_letters and has_digits:
            confidence = 0.95
        
        return min(confidence, 1.0)
    
    def extract_text_from_pil_image(self, pil_image) -> Dict:
        """
        Extract text from PIL Image object
        
        Args:
            pil_image: PIL Image object
        
        Returns:
            Same as extract_text_from_image
        """
        import io
        
        # Convert PIL image to bytes
        buffer = io.BytesIO()
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        pil_image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        return self.extract_text_from_image(image_bytes)
    
    def clean_voter_id(self, text: str) -> str:
        """
        Clean and extract voter ID from OCR text
        
        Args:
            text: Raw OCR text
        
        Returns:
            Cleaned voter ID string
        """
        import re
        
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Try to extract voter ID pattern (e.g., NOW1234567, ABC1234567)
        # Common patterns: 3 letters followed by 7 digits
        pattern = r'\b[A-Z]{3}\d{7}\b'
        match = re.search(pattern, text.upper())
        if match:
            cleaned = match.group(0)
            # Remove trailing underscores
            cleaned = cleaned.rstrip('_').strip()
            # Apply OCR error corrections
            cleaned = correct_voter_id(cleaned)
            return cleaned
        
        # Try alternative pattern: any letters followed by digits
        pattern2 = r'\b[A-Z]{2,4}\d{6,8}\b'
        match2 = re.search(pattern2, text.upper())
        if match2:
            cleaned = match2.group(0)
            # Remove trailing underscores
            cleaned = cleaned.rstrip('_').strip()
            # Apply OCR error corrections
            cleaned = correct_voter_id(cleaned)
            return cleaned
        
        # If no pattern match, return cleaned text (also remove trailing underscores)
        cleaned = text.strip()
        cleaned = cleaned.rstrip('_').strip()
        # Apply OCR error corrections even if pattern doesn't match
        if len(cleaned) == 10 and re.match(r'^[A-Z0-9]{10}$', cleaned):
            cleaned = correct_voter_id(cleaned)
        return cleaned


# Test function
if __name__ == '__main__':
    print("Testing Google Vision OCR Processor...")
    print("-" * 50)
    
    try:
        processor = GoogleVisionOCRProcessor()
        
        if processor.is_available():
            print("OK: Google Vision OCR is available and configured")
            print(f"OK: API URL configured")
            print("\nReady to process voter ID images with high accuracy!")
        else:
            print("FAIL: Google Vision OCR not configured")
            print("\nTo enable Google Vision OCR:")
            print("1. Add GOOGLE_VISION_API_KEY to .env file")
            print("2. Restart the Python service")
            print("\nExample .env:")
            print("  GOOGLE_VISION_API_KEY=your_key_here")
    
    except Exception as e:
        print(f"FAIL: Error: {str(e)}")

