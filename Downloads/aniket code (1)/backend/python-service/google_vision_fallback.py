"""
Google Cloud Vision API Fallback Service
Uses Google Vision API as fallback when local OCR fails or returns empty results
"""

import os
import io
import base64
import requests
from typing import Dict, Optional
from PIL import Image
import json

try:
    from google.cloud import vision
    from google.oauth2 import service_account
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False
    print("WARNING: google-cloud-vision not installed. Install with: pip install google-cloud-vision")


class GoogleVisionFallback:
    """
    Google Cloud Vision API fallback service
    Only used when local OCR fails or returns empty results
    """
    
    def __init__(self, credentials_path: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Google Vision API client
        
        Args:
            credentials_path: Path to Google service account JSON file (GOOGLE_APPLICATION_CREDENTIALS)
            api_key: Google API key (legacy, deprecated - use credentials_path instead)
        """
        self.enabled = False
        self.client = None
        self.api_key = None
        self.api_url = None
        
        # Priority 1: Use service account credentials (GOOGLE_APPLICATION_CREDENTIALS)
        credentials_path = credentials_path or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Check if credentials_path is actually a file path or an API key
        # API keys typically start with "AIza" and are 39 characters long
        is_api_key = False
        if credentials_path:
            # Remove quotes if present
            credentials_path = credentials_path.strip('"\'')
            # Check if it's a file path
            if os.path.exists(credentials_path):
                # It's a file path - try to use as service account
                try:
                    if GOOGLE_VISION_AVAILABLE:
                        credentials = service_account.Credentials.from_service_account_file(credentials_path)
                        self.client = vision.ImageAnnotatorClient(credentials=credentials)
                        self.enabled = True
                        print(f"OK: Google Vision API fallback initialized (Service Account: {credentials_path})")
                        return
                    else:
                        print("WARNING: google-cloud-vision library not installed. Install with: pip install google-cloud-vision")
                except Exception as e:
                    print(f"WARNING: Failed to initialize Google Vision with service account: {str(e)}")
            # Check if it looks like an API key (starts with "AIza" and is 39 chars)
            elif credentials_path.startswith('AIza') and len(credentials_path) >= 35:
                is_api_key = True
                # Treat it as an API key
                self.api_key = credentials_path
                self.enabled = True
                self.api_url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
                print("OK: Google Vision API fallback initialized (REST API - using GOOGLE_APPLICATION_CREDENTIALS as API key)")
                return
        
        # Priority 2: Fallback to API key (legacy method)
        if not is_api_key:
            self.api_key = api_key or os.getenv('GOOGLE_VISION_API_KEY')
            if self.api_key:
                # Remove quotes if present
                self.api_key = self.api_key.strip('"\'')
                self.enabled = True
                self.api_url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
                print("OK: Google Vision API fallback initialized (REST API - Legacy)")
                return
        
        if not self.enabled:
            print("WARNING: Google Vision API credentials not provided. Set GOOGLE_APPLICATION_CREDENTIALS in .env file.")
    
    def is_available(self) -> bool:
        """Check if Google Vision API is available"""
        return self.enabled and (self.client is not None or self.api_key is not None)
    
    def extract_text_from_image(self, image: Image.Image, language_hints: list = None) -> Dict:
        """
        Extract text from image using Google Vision API
        
        Args:
            image: PIL Image object
            language_hints: List of language codes (e.g., ['en', 'hi'])
        
        Returns:
            Dict with 'text', 'confidence', 'success', 'method'
        """
        if not self.is_available():
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'unavailable',
                'error': 'Google Vision API not available'
            }
        
        try:
            # Convert PIL Image to bytes
            buffer = io.BytesIO()
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(buffer, format='JPEG', quality=90)
            image_bytes = buffer.getvalue()
            
            # Use client library if available (preferred method)
            if self.client is not None:
                # Create image object
                vision_image = vision.Image(content=image_bytes)
                
                # Prepare image context with language hints
                language_hints = language_hints or ['en', 'hi']  # English and Hindi
                image_context = vision.ImageContext(language_hints=language_hints)
                
                # Perform text detection
                response = self.client.text_detection(image=vision_image, image_context=image_context)
                
                # Extract text annotations
                text_annotations = response.text_annotations
                
                if not text_annotations:
                    return {
                        'success': False,
                        'text': '',
                        'confidence': 0.0,
                        'method': 'no_text',
                        'error': 'No text annotations found'
                    }
                
                # First annotation contains full text
                full_text = text_annotations[0].description.strip()
                
                # Estimate confidence
                confidence = self._estimate_confidence(full_text)
                
                return {
                    'success': True,
                    'text': full_text,
                    'confidence': confidence,
                    'method': 'google_vision_client',
                    'raw_annotations': len(text_annotations)
                }
            
            # Fallback to REST API (legacy method with API key)
            elif self.api_key and self.api_url:
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                # Prepare request
                language_hints = language_hints or ['en', 'hi']  # English and Hindi
                
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
                    timeout=10
                )
                
                if response.status_code != 200:
                    error_msg = response.text
                    return {
                        'success': False,
                        'text': '',
                        'confidence': 0.0,
                        'method': 'api_error',
                        'error': f'API returned status {response.status_code}: {error_msg}'
                    }
                
                result = response.json()
                
                # Parse response
                if 'responses' not in result or not result['responses']:
                    return {
                        'success': False,
                        'text': '',
                        'confidence': 0.0,
                        'method': 'no_text',
                        'error': 'No text detected'
                    }
                
                response_data = result['responses'][0]
                
                # Check for errors
                if 'error' in response_data:
                    return {
                        'success': False,
                        'text': '',
                        'confidence': 0.0,
                        'method': 'api_error',
                        'error': response_data['error'].get('message', 'Unknown error')
                    }
                
                # Extract text
                text_annotations = response_data.get('textAnnotations', [])
                
                if not text_annotations:
                    return {
                        'success': False,
                        'text': '',
                        'confidence': 0.0,
                        'method': 'no_text',
                        'error': 'No text annotations found'
                    }
                
                # First annotation contains full text
                full_text = text_annotations[0].get('description', '').strip()
                
                # Estimate confidence based on text length and content
                confidence = self._estimate_confidence(full_text)
                
                return {
                    'success': True,
                    'text': full_text,
                    'confidence': confidence,
                    'method': 'google_vision_rest',
                    'raw_annotations': text_annotations
                }
            else:
                return {
                    'success': False,
                    'text': '',
                    'confidence': 0.0,
                    'method': 'unavailable',
                    'error': 'Google Vision API not properly initialized'
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'timeout',
                'error': 'Request timeout'
            }
        
        except Exception as e:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'error',
                'error': str(e)
            }
    
    def _estimate_confidence(self, text: str) -> float:
        """
        Estimate confidence based on text quality
        
        Args:
            text: Extracted text
        
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not text or len(text.strip()) == 0:
            return 0.0
        
        confidence = 0.7  # Base confidence for Google Vision
        
        # Increase confidence if text looks valid
        if len(text) > 3:
            confidence = 0.8
        
        # Check for alphanumeric content (good sign)
        has_letters = any(c.isalpha() for c in text)
        has_digits = any(c.isdigit() for c in text)
        
        if has_letters and has_digits:
            confidence = 0.85
        
        # Penalize if text is too short
        if len(text.strip()) < 2:
            confidence *= 0.5
        
        return min(confidence, 1.0)
    
    def extract_text_from_bytes(self, image_bytes: bytes, language_hints: list = None) -> Dict:
        """
        Extract text from image bytes using Google Vision API
        
        Args:
            image_bytes: Image as bytes
            language_hints: List of language codes
        
        Returns:
            Dict with 'text', 'confidence', 'success', 'method'
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return self.extract_text_from_image(image, language_hints)
        except Exception as e:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'error',
                'error': f'Failed to open image: {str(e)}'
            }
    
    def extract_text_from_page_batch(self, page_image: Image.Image, language_hints: list = None) -> Dict:
        """
        Process entire page image once and return all text annotations with bounding boxes.
        This allows extracting text from specific regions without making additional API calls.
        
        Args:
            page_image: PIL Image of the full page
            language_hints: List of language codes
        
        Returns:
            Dict with:
                - 'success': bool
                - 'annotations': List of text annotations with bounding boxes
                - 'image_width': int
                - 'image_height': int
                - 'method': str
        """
        if not self.is_available():
            return {
                'success': False,
                'annotations': [],
                'image_width': 0,
                'image_height': 0,
                'method': 'unavailable',
                'error': 'Google Vision API not available'
            }
        
        try:
            # Convert PIL Image to bytes
            buffer = io.BytesIO()
            if page_image.mode != 'RGB':
                page_image = page_image.convert('RGB')
            page_image.save(buffer, format='JPEG', quality=90)
            image_bytes = buffer.getvalue()
            image_width, image_height = page_image.size
            
            language_hints = language_hints or ['en', 'hi']
            
            # Use client library if available (preferred method)
            if self.client is not None:
                vision_image = vision.Image(content=image_bytes)
                image_context = vision.ImageContext(language_hints=language_hints)
                response = self.client.text_detection(image=vision_image, image_context=image_context)
                text_annotations = response.text_annotations
                
                if not text_annotations:
                    return {
                        'success': False,
                        'annotations': [],
                        'image_width': image_width,
                        'image_height': image_height,
                        'method': 'no_text',
                        'error': 'No text annotations found'
                    }
                
                # Convert annotations to a more usable format
                annotations = []
                for ann in text_annotations[1:]:  # Skip first (full text)
                    vertices = ann.bounding_poly.vertices
                    if len(vertices) >= 2:
                        x_coords = [v.x for v in vertices]
                        y_coords = [v.y for v in vertices]
                        annotations.append({
                            'text': ann.description.strip(),
                            'x': min(x_coords),
                            'y': min(y_coords),
                            'width': max(x_coords) - min(x_coords),
                            'height': max(y_coords) - min(y_coords),
                            'bounding_box': {
                                'x': min(x_coords),
                                'y': min(y_coords),
                                'width': max(x_coords) - min(x_coords),
                                'height': max(y_coords) - min(y_coords)
                            }
                        })
                
                return {
                    'success': True,
                    'annotations': annotations,
                    'image_width': image_width,
                    'image_height': image_height,
                    'method': 'google_vision_client',
                    'full_text': text_annotations[0].description if text_annotations else ''
                }
            
            # Fallback to REST API
            elif self.api_key and self.api_url:
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                request_body = {
                    'requests': [{
                        'image': {
                            'content': image_base64
                        },
                        'features': [{
                            'type': 'TEXT_DETECTION',
                            'maxResults': 1000  # Get all annotations
                        }],
                        'imageContext': {
                            'languageHints': language_hints
                        }
                    }]
                }
                
                headers = {'Content-Type': 'application/json'}
                response = requests.post(self.api_url, headers=headers, json=request_body, timeout=30)
                
                if response.status_code != 200:
                    return {
                        'success': False,
                        'annotations': [],
                        'image_width': image_width,
                        'image_height': image_height,
                        'method': 'api_error',
                        'error': f'API returned status {response.status_code}'
                    }
                
                result = response.json()
                if 'responses' not in result or not result['responses']:
                    return {
                        'success': False,
                        'annotations': [],
                        'image_width': image_width,
                        'image_height': image_height,
                        'method': 'no_text',
                        'error': 'No text detected'
                    }
                
                response_data = result['responses'][0]
                if 'error' in response_data:
                    return {
                        'success': False,
                        'annotations': [],
                        'image_width': image_width,
                        'image_height': image_height,
                        'method': 'api_error',
                        'error': response_data['error'].get('message', 'Unknown error')
                    }
                
                text_annotations = response_data.get('textAnnotations', [])
                if not text_annotations:
                    return {
                        'success': False,
                        'annotations': [],
                        'image_width': image_width,
                        'image_height': image_height,
                        'method': 'no_text',
                        'error': 'No text annotations found'
                    }
                
                # Convert annotations to usable format
                annotations = []
                for ann in text_annotations[1:]:  # Skip first (full text)
                    vertices = ann.get('boundingPoly', {}).get('vertices', [])
                    if len(vertices) >= 2:
                        x_coords = [v.get('x', 0) for v in vertices]
                        y_coords = [v.get('y', 0) for v in vertices]
                        annotations.append({
                            'text': ann.get('description', '').strip(),
                            'x': min(x_coords),
                            'y': min(y_coords),
                            'width': max(x_coords) - min(x_coords),
                            'height': max(y_coords) - min(y_coords),
                            'bounding_box': {
                                'x': min(x_coords),
                                'y': min(y_coords),
                                'width': max(x_coords) - min(x_coords),
                                'height': max(y_coords) - min(y_coords)
                            }
                        })
                
                return {
                    'success': True,
                    'annotations': annotations,
                    'image_width': image_width,
                    'image_height': image_height,
                    'method': 'google_vision_rest',
                    'full_text': text_annotations[0].get('description', '') if text_annotations else ''
                }
            else:
                return {
                    'success': False,
                    'annotations': [],
                    'image_width': 0,
                    'image_height': 0,
                    'method': 'unavailable',
                    'error': 'Google Vision API not properly initialized'
                }
        
        except Exception as e:
            return {
                'success': False,
                'annotations': [],
                'image_width': 0,
                'image_height': 0,
                'method': 'error',
                'error': str(e)
            }
    
    def extract_text_from_region(self, page_annotations: Dict, region_x: int, region_y: int, 
                                  region_width: int, region_height: int) -> Dict:
        """
        Extract text from a specific region using cached page annotations.
        This avoids making additional API calls.
        
        Args:
            page_annotations: Result from extract_text_from_page_batch()
            region_x: X coordinate of region
            region_y: Y coordinate of region
            region_width: Width of region
            region_height: Height of region
        
        Returns:
            Dict with 'text', 'confidence', 'success', 'method'
        """
        if not page_annotations.get('success'):
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'no_annotations',
                'error': 'Page annotations not available'
            }
        
        annotations = page_annotations.get('annotations', [])
        if not annotations:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'no_text',
                'error': 'No annotations in region'
            }
        
        # Find annotations that overlap with the region
        region_texts = []
        for ann in annotations:
            ann_x = ann.get('x', 0)
            ann_y = ann.get('y', 0)
            ann_width = ann.get('width', 0)
            ann_height = ann.get('height', 0)
            
            # Check if annotation overlaps with region
            if (ann_x < region_x + region_width and 
                ann_x + ann_width > region_x and
                ann_y < region_y + region_height and
                ann_y + ann_height > region_y):
                region_texts.append(ann.get('text', ''))
        
        if not region_texts:
            return {
                'success': False,
                'text': '',
                'confidence': 0.0,
                'method': 'no_text',
                'error': 'No text found in region'
            }
        
        # Combine all text in the region
        combined_text = ' '.join(region_texts).strip()
        confidence = self._estimate_confidence(combined_text)
        
        return {
            'success': True,
            'text': combined_text,
            'confidence': confidence,
            'method': 'google_vision_cached',
            'annotations_count': len(region_texts)
        }


# Global instance
_google_vision_fallback = None

def get_google_vision_fallback(credentials_path: Optional[str] = None, api_key: Optional[str] = None) -> Optional[GoogleVisionFallback]:
    """
    Get or create Google Vision fallback instance
    
    Args:
        credentials_path: Path to Google service account JSON file (optional, uses env var if not provided)
        api_key: Google API key (optional, legacy method - use credentials_path instead)
    
    Returns:
        GoogleVisionFallback instance or None if not available
    """
    global _google_vision_fallback
    
    if _google_vision_fallback is None:
        _google_vision_fallback = GoogleVisionFallback(credentials_path, api_key)
    
    return _google_vision_fallback if _google_vision_fallback.is_available() else None


if __name__ == '__main__':
    print("Testing Google Vision API Fallback...")
    print("=" * 60)
    
    # Test initialization
    fallback = GoogleVisionFallback()
    
    if fallback.is_available():
        print("✓ Google Vision API fallback is available")
    else:
        print("✗ Google Vision API fallback is not available")
        print("  Set GOOGLE_APPLICATION_CREDENTIALS in .env file (path to service account JSON)")
        print("  Or set GOOGLE_VISION_API_KEY for legacy API key method")
    
    print("=" * 60)

