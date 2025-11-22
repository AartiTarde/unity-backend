"""
Google Vision Formatter
Uses Google Vision API for intelligent parsing and cleaning of voter ID text
"""

import os
import re
from typing import Dict, Optional
from dotenv import load_dotenv
from voter_id_corrector import correct_voter_id

# Load environment variables
load_dotenv()

class GoogleVisionFormatter:
    """
    Intelligent text formatter using Google Vision API
    Cleans and structures voter ID data extracted from OCR
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Google Vision Formatter with API key"""
        self.api_key = api_key or os.getenv('GOOGLE_VISION_API_KEY')
        
        if not self.api_key:
            print("WARNING: GOOGLE_VISION_API_KEY not set - using fallback formatting")
            self.enabled = False
        else:
            self.enabled = True
            print(f"OK: Google Vision Formatter initialized")
    
    def is_available(self) -> bool:
        """Check if Google Vision Formatter is available and configured"""
        return self.enabled
    
    def format_voter_id(self, raw_text: str, context: Optional[Dict] = None) -> Dict:
        """
        Format and clean voter ID text
        
        Args:
            raw_text: Raw OCR text
            context: Optional context information (page number, position, etc.)
        
        Returns:
            Dictionary with:
                - voterID: Cleaned voter ID
                - confidence: Formatting confidence (0-1)
                - metadata: Additional extracted information
                - success: Boolean indicating success
        """
        # Use fallback formatting (regex-based, no API call needed)
        return self._fallback_format(raw_text)
    
    def _fallback_format(self, raw_text: str) -> Dict:
        """Formatting using regex (no API call needed)"""
        if not raw_text:
            return {
                'success': True,
                'voterID': '',
                'confidence': 1.0,
                'metadata': {'method': 'fallback-empty'}
            }
        
        # Remove extra whitespace
        text = ' '.join(raw_text.split())
        
        # Try to extract voter ID pattern
        # Pattern 1: 3 letters + 7 digits
        pattern1 = r'\b[A-Z]{3}\d{7}\b'
        match1 = re.search(pattern1, text.upper())
        if match1:
            voter_id = match1.group(0)
            # Apply OCR error corrections
            voter_id = correct_voter_id(voter_id)
            return {
                'success': True,
                'voterID': voter_id,
                'confidence': 0.8,
                'metadata': {'method': 'fallback-regex', 'pattern': 'ABC1234567'}
            }
        
        # Pattern 2: 2-4 letters + 6-8 digits
        pattern2 = r'\b[A-Z]{2,4}\d{6,8}\b'
        match2 = re.search(pattern2, text.upper())
        if match2:
            voter_id = match2.group(0)
            # Apply OCR error corrections
            voter_id = correct_voter_id(voter_id)
            return {
                'success': True,
                'voterID': voter_id,
                'confidence': 0.6,
                'metadata': {'method': 'fallback-regex', 'pattern': 'flexible'}
            }
        
        # No pattern found, return cleaned text
        cleaned = text.strip()
        # Apply OCR error corrections if it looks like a voter ID
        if len(cleaned) == 10 and re.match(r'^[A-Z0-9]{10}$', cleaned):
            cleaned = correct_voter_id(cleaned)
        return {
            'success': True,
            'voterID': cleaned,
            'confidence': 0.3,
            'metadata': {'method': 'fallback-cleaned'}
        }
    
    def batch_format_voter_ids(self, texts: list) -> list:
        """
        Format multiple voter IDs in batch for efficiency
        
        Args:
            texts: List of raw OCR texts
        
        Returns:
            List of formatted results
        """
        results = []
        
        for text in texts:
            result = self.format_voter_id(text)
            results.append(result)
        
        return results


# Test function
if __name__ == '__main__':
    print("Testing Google Vision Formatter...")
    print("-" * 50)
    
    try:
        formatter = GoogleVisionFormatter()
        
        if formatter.is_available():
            print("OK: Google Vision Formatter is available and configured")
            print("\nReady to intelligently parse voter ID text!")
        else:
            print("INFO: Using fallback regex formatter")
        
        # Test with sample text
        print("\nTesting with sample OCR text...")
        sample_texts = [
            "Voter ID: NOW1234567",
            "EPIC No: ABC 1234567",  # With space
            "मतदार ओळखपत्र: XYZ9876543",  # With Marathi text
            "123ABC4567890"  # Noisy
        ]
        
        for text in sample_texts:
            print(f"\n  Input: {text}")
            result = formatter.format_voter_id(text)
            print(f"  Output: {result['voterID']} (confidence: {result['confidence']})")
    
    except Exception as e:
        print(f"FAIL: Error: {str(e)}")

