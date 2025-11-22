"""
Google Vision Service - Region Detection
Detects voter ID and photo boxes from document pages using Google Vision API
"""

import os
import json
import base64
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GoogleVisionService:
    """Service for detecting voter regions using Google Vision API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Google Vision Service with API key"""
        self.api_key = api_key or os.getenv('GOOGLE_VISION_API_KEY')
        
        if not self.api_key:
            raise ValueError("GOOGLE_VISION_API_KEY not found in environment variables")
        
        self.api_url = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
        print(f"Google Vision Service initialized")
        print(f"API URL: {self.api_url[:50]}...")
    
    def detect_voter_regions(self, image_bytes: bytes, image_width: int, image_height: int) -> Dict:
        """
        Detect voter ID and photo regions from a page image using Google Vision API
        
        Args:
            image_bytes: Image data as bytes (PNG/JPEG)
            image_width: Original image width in pixels
            image_height: Original image height in pixels
        
        Returns:
            Dictionary with detected regions:
            {
                'voterIdBoxes': [{'x': int, 'y': int, 'width': int, 'height': int, 'confidence': float}],
                'photoBoxes': [{'x': int, 'y': int, 'width': int, 'height': int, 'confidence': float}],
                'gridDetected': bool,
                'gridRows': int,
                'gridColumns': int,
                'gridBoundary': {'x': int, 'y': int, 'width': int, 'height': int}
            }
        """
        try:
            # Convert image to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Use Google Vision API to detect text and objects
            # We'll use TEXT_DETECTION to find voter IDs and OBJECT_LOCALIZATION to find photos
            request_body = {
                'requests': [{
                    'image': {
                        'content': image_base64
                    },
                    'features': [
                        {
                            'type': 'TEXT_DETECTION',
                            'maxResults': 50
                        },
                        {
                            'type': 'OBJECT_LOCALIZATION',
                            'maxResults': 50
                        }
                    ],
                    'imageContext': {
                        'languageHints': ['en', 'hi']
                    }
                }]
            }
            
            print(f"Sending request to Google Vision API...")
            print(f"Image size: {len(image_bytes)} bytes, Dimensions: {image_width}x{image_height}")
            
            # Make API request
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=request_body,
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = f"Google Vision API error: {response.status_code} - {response.text}"
                print(error_msg)
                raise Exception(error_msg)
            
            # Parse response
            result = response.json()
            
            if 'responses' not in result or not result['responses']:
                raise Exception("No response from Google Vision API")
            
            response_data = result['responses'][0]
            
            # Check for errors
            if 'error' in response_data:
                error_msg = response_data['error'].get('message', 'Unknown error')
                raise Exception(f"Google Vision API error: {error_msg}")
            
            # Extract voter ID boxes from text annotations
            voter_id_boxes = self._extract_voter_id_boxes(response_data, image_width, image_height)
            
            # Extract photo boxes from object localization
            photo_boxes = self._extract_photo_boxes(response_data, image_width, image_height)
            
            # Detect grid structure
            grid_info = self._detect_grid_structure(voter_id_boxes, photo_boxes, image_width, image_height)
            
            detected_regions = {
                'voterIdBoxes': voter_id_boxes,
                'photoBoxes': photo_boxes,
                **grid_info
            }
            
            print(f"Detection successful!")
            print(f"Detected: {len(voter_id_boxes)} voter IDs, {len(photo_boxes)} photos")
            
            return detected_regions
            
        except Exception as e:
            print(f"Error in Google Vision detection: {str(e)}")
            raise
    
    def _extract_voter_id_boxes(self, response_data: Dict, image_width: int, image_height: int) -> List[Dict]:
        """Extract voter ID boxes from text annotations"""
        import re
        
        voter_id_boxes = []
        text_annotations = response_data.get('textAnnotations', [])
        
        # Pattern for voter ID: 3 letters + 7 digits
        voter_id_pattern = r'[A-Z]{3}[0-9]{7}'
        
        for annotation in text_annotations[1:]:  # Skip first (full text)
            text = annotation.get('description', '').strip()
            
            # Check if text matches voter ID pattern
            if re.search(voter_id_pattern, text.upper()):
                bounding_poly = annotation.get('boundingPoly', {})
                vertices = bounding_poly.get('vertices', [])
                
                if len(vertices) >= 2:
                    # Get bounding box from vertices
                    x_coords = [v.get('x', 0) for v in vertices]
                    y_coords = [v.get('y', 0) for v in vertices]
                    
                    x = min(x_coords)
                    y = min(y_coords)
                    width = max(x_coords) - x
                    height = max(y_coords) - y
                    
                    voter_id_boxes.append({
                        'x': int(x),
                        'y': int(y),
                        'width': int(width),
                        'height': int(height),
                        'confidence': 0.8,
                        'text': text
                    })
        
        return voter_id_boxes
    
    def _extract_photo_boxes(self, response_data: Dict, image_width: int, image_height: int) -> List[Dict]:
        """Extract photo boxes from object localization"""
        photo_boxes = []
        localized_objects = response_data.get('localizedObjectAnnotations', [])
        
        for obj in localized_objects:
            name = obj.get('name', '').lower()
            
            # Look for person/face objects (likely photos)
            if 'person' in name or 'face' in name or 'head' in name:
                bounding_poly = obj.get('boundingPoly', {})
                normalized_vertices = bounding_poly.get('normalizedVertices', [])
                
                if len(normalized_vertices) >= 2:
                    # Convert normalized coordinates to pixel coordinates
                    x_coords = [v.get('x', 0) * image_width for v in normalized_vertices]
                    y_coords = [v.get('y', 0) * image_height for v in normalized_vertices]
                    
                    x = min(x_coords)
                    y = min(y_coords)
                    width = max(x_coords) - x
                    height = max(y_coords) - y
                    
                    photo_boxes.append({
                        'x': int(x),
                        'y': int(y),
                        'width': int(width),
                        'height': int(height),
                        'confidence': obj.get('score', 0.7)
                    })
        
        return photo_boxes
    
    def _detect_grid_structure(self, voter_id_boxes: List[Dict], photo_boxes: List[Dict], 
                               image_width: int, image_height: int) -> Dict:
        """Detect grid structure from detected boxes"""
        # Simple grid detection: check if boxes are arranged in rows/columns
        grid_detected = False
        grid_rows = 0
        grid_columns = 0
        grid_boundary = {'x': 0, 'y': 0, 'width': image_width, 'height': image_height}
        
        if len(voter_id_boxes) > 1:
            # Group boxes by Y position (rows)
            y_positions = sorted(set([box['y'] for box in voter_id_boxes]))
            x_positions = sorted(set([box['x'] for box in voter_id_boxes]))
            
            # If boxes are aligned, we likely have a grid
            if len(y_positions) > 1 and len(x_positions) > 1:
                grid_detected = True
                grid_rows = len(y_positions)
                grid_columns = len(x_positions)
                
                # Calculate grid boundary
                all_boxes = voter_id_boxes + photo_boxes
                if all_boxes:
                    min_x = min([b['x'] for b in all_boxes])
                    min_y = min([b['y'] for b in all_boxes])
                    max_x = max([b['x'] + b['width'] for b in all_boxes])
                    max_y = max([b['y'] + b['height'] for b in all_boxes])
                    
                    grid_boundary = {
                        'x': int(min_x),
                        'y': int(min_y),
                        'width': int(max_x - min_x),
                        'height': int(max_y - min_y)
                    }
        
        return {
            'gridDetected': grid_detected,
            'gridRows': grid_rows,
            'gridColumns': grid_columns,
            'gridBoundary': grid_boundary
        }
    
    def detect_from_pdf_page(self, pdf_bytes: bytes, page_num: int, scale: float = 2.0) -> Dict:
        """
        Detect regions from a specific PDF page
        
        Args:
            pdf_bytes: PDF file as bytes
            page_num: Page number (0-indexed)
            scale: Rendering scale for better detection (default 2.0)
        
        Returns:
            Dictionary with detected regions
        """
        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import io
            
            # Open PDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            if page_num >= len(doc):
                raise ValueError(f"Page {page_num} does not exist in PDF (total pages: {len(doc)})")
            
            # Get page
            page = doc[page_num]
            
            # Render page to image at higher resolution
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image then to bytes
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            print(f"Rendered page {page_num + 1} at {pix.width}x{pix.height} pixels")
            
            # Detect regions
            detected = self.detect_voter_regions(img_bytes, pix.width, pix.height)
            
            # Scale coordinates back to original PDF coordinates
            detected_scaled = self._scale_coordinates(detected, 1.0 / scale)
            
            doc.close()
            
            return detected_scaled
            
        except Exception as e:
            print(f"Error detecting from PDF page: {str(e)}")
            raise
    
    def _scale_coordinates(self, detected: Dict, scale: float) -> Dict:
        """Scale detected coordinates by a factor"""
        
        result = detected.copy()
        
        # Scale voter ID boxes
        if 'voterIdBoxes' in result:
            for box in result['voterIdBoxes']:
                box['x'] = int(box['x'] * scale)
                box['y'] = int(box['y'] * scale)
                box['width'] = int(box['width'] * scale)
                box['height'] = int(box['height'] * scale)
        
        # Scale photo boxes
        if 'photoBoxes' in result:
            for box in result['photoBoxes']:
                box['x'] = int(box['x'] * scale)
                box['y'] = int(box['y'] * scale)
                box['width'] = int(box['width'] * scale)
                box['height'] = int(box['height'] * scale)
        
        # Scale grid boundary
        if 'gridBoundary' in result:
            gb = result['gridBoundary']
            gb['x'] = int(gb['x'] * scale)
            gb['y'] = int(gb['y'] * scale)
            gb['width'] = int(gb['width'] * scale)
            gb['height'] = int(gb['height'] * scale)
        
        return result


# Test function
if __name__ == '__main__':
    print("Testing Google Vision Service...")
    
    try:
        service = GoogleVisionService()
        print("OK: Service initialized successfully")
        print(f"OK: API URL configured")
        print("OK: Ready to detect voter regions")
        
    except Exception as e:
        print(f"FAIL: Error: {str(e)}")
        print("\nPlease ensure:")
        print("1. .env file exists in the project root")
        print("2. GOOGLE_VISION_API_KEY is set")

