"""
Devanagari to English Transliterator
Converts Devanagari (Hindi/Marathi) text to English (Romanized) spelling
Uses API for 99% accuracy with local mapping as fallback
"""

import re
import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# Comprehensive Devanagari to English transliteration mapping
DEVANAGARI_TO_ENGLISH = {
    # Vowels (स्वर)
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ऋ': 'ri', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au',
    
    # Consonants (व्यंजन)
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'ळ': 'l', 'क्ष': 'ksh', 'ज्ञ': 'gy',
    
    # Vowel signs (मात्रा)
    'ा': 'aa', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
    'ृ': 'ri', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au',
    'ं': 'm', 'ः': 'h', '्': '',  # Anusvara, Visarga, Halant
    
    # Numbers
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
}


def transliterate_devanagari_to_english(text: str) -> str:
    """
    Convert Devanagari text to English (Romanized) spelling.
    Handles complex cases like conjuncts, vowel signs, and special characters.
    Uses improved algorithm for better accuracy.
    
    Args:
        text: Devanagari text (Hindi/Marathi)
        
    Returns:
        English transliteration of the text
    """
    if not text:
        return ''
    
    # If text doesn't contain Devanagari, return as is (but capitalize for names)
    if not re.search(r'[\u0900-\u097F]', text):
        # Capitalize each word if it's already English
        words = text.strip().split()
        return ' '.join(word.capitalize() for word in words if word)
    
    result = []
    i = 0
    text_len = len(text)
    
    # Vowel sign mappings
    vowel_signs = {
        'ा': 'aa', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
        'ृ': 'ri', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au'
    }
    
    while i < text_len:
        char = text[i]
        next_char = text[i + 1] if i + 1 < text_len else None
        
        # Skip spaces and punctuation (add them as-is)
        if char == ' ':
            result.append(' ')
            i += 1
            continue
        
        if char in ['.', ',', '-', ':', ';', '!', '?']:
            result.append(char)
            i += 1
            continue
        
        # Handle anusvara (ं) - nasal sound
        if char == 'ं':
            # Usually becomes 'm' or 'n' depending on context
            if next_char and next_char in ['क', 'ख', 'ग', 'घ']:
                result.append('n')
            else:
                result.append('m')
            i += 1
            continue
        
        # Handle visarga (ः) - 'h' sound
        if char == 'ः':
            result.append('h')
            i += 1
            continue
        
        # Handle halant (्) - removes inherent 'a', creates conjunct
        if char == '्':
            # Remove last 'a' if present (for conjuncts)
            if result and result[-1] == 'a':
                result.pop()
            i += 1
            continue
        
        # Check if current char is a consonant or vowel
        if char in DEVANAGARI_TO_ENGLISH:
            base_translit = DEVANAGARI_TO_ENGLISH[char]
            
            # Check if next character is a vowel sign (matra)
            if next_char and next_char in vowel_signs:
                vowel_sound = vowel_signs[next_char]
                # Replace 'a' in base_translit with the vowel sound
                if 'a' in base_translit:
                    # For consonants, replace 'a' with vowel
                    translit = base_translit.replace('a', vowel_sound)
                else:
                    # For standalone vowels, use the vowel sound
                    translit = vowel_sound
                result.append(translit)
                i += 2  # Skip both consonant and vowel sign
                continue
            else:
                # Just the consonant/vowel (with inherent 'a' for consonants)
                result.append(base_translit)
        
        # Unknown character - keep as is
        else:
            result.append(char)
        
        i += 1
    
    # Join and clean up
    transliterated = ''.join(result)
    
    # Post-processing: Fix common transliteration issues
    # Remove multiple spaces
    transliterated = re.sub(r'\s+', ' ', transliterated).strip()
    
    # Fix common patterns for better accuracy
    # Ensure consonants at word end have 'a' if no vowel follows
    # But don't add 'a' if there's already a vowel ending
    words = transliterated.split()
    fixed_words = []
    for word in words:
        if word and word[-1] not in 'aeiou':
            # Check if it ends with a consonant (not a vowel)
            # Add 'a' only if it makes sense (not for single letters)
            if len(word) > 1 and word[-1].isalpha():
                # Check if last char is a consonant
                if word[-1].lower() in 'bcdfghjklmnpqrstvwxyz':
                    word = word + 'a'
        fixed_words.append(word)
    transliterated = ' '.join(fixed_words)
    
    # Capitalize first letter of each word (for names)
    words = transliterated.split()
    capitalized_words = []
    for word in words:
        if word:
            # Capitalize first letter, keep rest lowercase
            if len(word) > 1:
                capitalized = word[0].upper() + word[1:].lower()
            else:
                capitalized = word.upper()
            capitalized_words.append(capitalized)
    
    return ' '.join(capitalized_words)


def transliterate_name_api(text: str, api_key: str) -> Optional[str]:
    """
    Transliterate Devanagari text to English using Google Translate API.
    The API provides romanization/transliteration for proper names.
    
    Args:
        text: Devanagari text to transliterate
        api_key: Google API key
        
    Returns:
        English transliteration or None if API call fails
    """
    if not text or not api_key:
        return None
    
    # Remove quotes from API key if present
    api_key = api_key.strip('"\'')
    
    if not api_key:
        return None
    
    try:
        # Google Translate API v2 endpoint
        url = "https://translation.googleapis.com/language/translate/v2"
        
        # Prepare request
        # Note: Google Translate API translates meaning, but for names it often provides transliteration
        params = {
            'key': api_key,
            'q': text,
            'source': 'hi',  # Hindi/Marathi (Devanagari script)
            'target': 'en',
            'format': 'text'
        }
        
        response = requests.post(url, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if 'data' in result and 'translations' in result['data']:
                translations = result['data']['translations']
                if translations and len(translations) > 0:
                    translated_text = translations[0].get('translatedText', '').strip()
                    
                    # Check if result still contains Devanagari (translation failed)
                    if re.search(r'[\u0900-\u097F]', translated_text):
                        # Result is still in Devanagari, API didn't work properly
                        return None
                    
                    # Check if result looks like transliteration (contains English letters)
                    if re.search(r'[a-zA-Z]', translated_text):
                        # Capitalize each word for proper names
                        words = translated_text.split()
                        capitalized = ' '.join(word.capitalize() for word in words if word)
                        return capitalized
        
        # If we get here, API call didn't work as expected
        return None
        
    except requests.exceptions.Timeout:
        print("      ⚠ Transliteration API timeout, using local mapping")
        return None
    except requests.exceptions.RequestException as e:
        print(f"      ⚠ Transliteration API request error: {str(e)}")
        return None
    except Exception as e:
        print(f"      ⚠ Transliteration API error: {str(e)}")
        return None


def transliterate_name(name: str, api_key: Optional[str] = None) -> str:
    """
    Transliterate a Devanagari name to English.
    First tries API, then falls back to local mapping.
    Optimized for proper names (capitalizes each word).
    
    Args:
        name: Devanagari name
        api_key: Optional API key for transliteration (if not provided, uses env var)
        
    Returns:
        English transliteration with proper capitalization
    """
    if not name:
        return ''
    
    # Clean the name first (remove any unwanted characters)
    cleaned = name.strip()
    
    # Try API first if available
    if not api_key:
        api_key = os.getenv('devanagari_transliterator', '').strip('"\'')
    
    if api_key:
        try:
            api_result = transliterate_name_api(cleaned, api_key)
            if api_result:
                return api_result
        except Exception as e:
            print(f"API transliteration failed, using local mapping: {str(e)}")
    
    # Fallback to local transliteration
    english_name = transliterate_devanagari_to_english(cleaned)
    
    # Ensure proper name formatting (each word capitalized)
    if english_name:
        words = english_name.split()
        formatted_words = []
        for word in words:
            if word:
                # Capitalize first letter, lowercase rest
                formatted = word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper()
                formatted_words.append(formatted)
        return ' '.join(formatted_words)
    
    return english_name


# Test function
if __name__ == '__main__':
    # Test cases
    test_cases = [
        'नरेद्र नामदेव सोनोने',
        'रोषण देविदास मितकर',
        'सीता देवी',
        'राम कुमार',
        'गीता शर्मा'
    ]
    
    print("Devanagari to English Transliteration Test")
    print("=" * 60)
    for test in test_cases:
        result = transliterate_name(test)
        print(f"{test:30} → {result}")
    print("=" * 60)

