"""
Voter ID Corrector
Automatically fixes common OCR errors in voter IDs:
- First 3 characters should be letters (A-Z): Replace numbers that look like letters (1→I, 0→O, etc.)
- Last 7 characters should be digits (0-9): Replace letters that look like numbers (O/o→0, I→1, etc.)
"""

import re
from typing import Optional


def validate_voter_id(voter_id: str) -> bool:
    """
    Validate voter ID using strict regex pattern
    
    Pattern: ^[A-Z]{3}[0-9]{7}$
    - First 3 characters must be uppercase letters (A-Z)
    - Last 7 characters must be digits (0-9)
    - Total length: exactly 10 characters
    
    Args:
        voter_id: Voter ID string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not voter_id:
        return False
    
    # Strict regex validation: 3 uppercase letters + 7 digits
    pattern = r'^[A-Z]{3}[0-9]{7}$'
    return bool(re.match(pattern, voter_id))


def correct_voter_id(voter_id: str) -> str:
    """
    Correct OCR errors in voter ID
    
    Rules:
    - Voter ID is always 10 characters alphanumeric
    - First 3 characters are always letters (A-Z)
    - Last 7 characters are always digits (0-9)
    
    OCR Error Corrections:
    - In first 3 positions: 1→I, 0→O, 5→S (if context suggests letter)
    - In last 7 positions: O/o→0, I→1, S→5, Z→2 (if context suggests digit)
    
    Args:
        voter_id: Raw voter ID string from OCR
        
    Returns:
        Corrected voter ID string
    """
    if not voter_id:
        return ""
    
    # Remove spaces and convert to uppercase
    voter_id = voter_id.replace(' ', '').replace('\n', '').upper().strip()
    
    # Remove trailing underscores (common OCR error)
    voter_id = voter_id.rstrip('_').strip()
    
    # Try to extract valid voter ID pattern first (3 letters + 7 digits)
    strict_pattern = r'[A-Z]{3}[0-9]{7}'
    match = re.search(strict_pattern, voter_id)
    if match:
        voter_id = match.group(0)
        # Validate the extracted ID
        if validate_voter_id(voter_id):
            return voter_id
    
    # If not 10 characters, try to extract 10-character pattern
    if len(voter_id) != 10:
        # Try to find a 10-character alphanumeric sequence
        match = re.search(r'[A-Z0-9]{10}', voter_id)
        if match:
            voter_id = match.group(0)
        else:
            # If we can't find exact 10 chars, return as-is (will be handled by pattern matching)
            return voter_id
    
    # Now correct the 10-character voter ID
    corrected = list(voter_id)
    
    # First 3 characters should be letters
    # Common OCR errors: 1→I, 0→O, 5→S, 8→B
    letter_replacements = {
        '1': 'I',  # Number 1 looks like letter I
        '0': 'O',  # Number 0 looks like letter O
        '5': 'S',  # Number 5 looks like letter S (less common)
        '8': 'B',  # Number 8 looks like letter B (less common)
    }
    
    for i in range(min(3, len(corrected))):
        char = corrected[i]
        # If it's a number that could be a letter, replace it
        if char in letter_replacements:
            corrected[i] = letter_replacements[char]
        # Ensure it's a letter (A-Z)
        elif not char.isalpha():
            # If it's not a letter and not in our replacement map, try to keep it
            # but log that it's unusual
            pass
    
    # Last 7 characters should be digits
    # Common OCR errors: O→0, o→0, I→1, l→1, S→5, Z→2
    digit_replacements = {
        'O': '0',  # Letter O looks like number 0
        'I': '1',  # Letter I looks like number 1
        'S': '5',  # Letter S looks like number 5
        'Z': '2',  # Letter Z looks like number 2 (less common)
        'L': '1',  # Letter L looks like number 1 (less common)
    }
    
    for i in range(3, len(corrected)):
        char = corrected[i]
        # If it's a letter that could be a digit, replace it
        if char in digit_replacements:
            corrected[i] = digit_replacements[char]
        # Ensure it's a digit (0-9)
        elif not char.isdigit():
            # If it's not a digit and not in our replacement map, try to keep it
            # but log that it's unusual
            pass
    
    corrected_id = ''.join(corrected)
    
    # Final validation: ensure it matches the strict pattern
    if validate_voter_id(corrected_id):
        return corrected_id
    
    # If validation fails, return corrected version anyway (might need further processing)
    return corrected_id


def correct_voter_id_flexible(voter_id: str) -> str:
    """
    Correct OCR errors in voter ID with flexible length handling
    
    This version handles voter IDs that might not be exactly 10 characters
    but follows the same pattern: letters first, then digits
    
    Args:
        voter_id: Raw voter ID string from OCR
        
    Returns:
        Corrected voter ID string
    """
    if not voter_id:
        return ""
    
    # Remove spaces and convert to uppercase
    voter_id = voter_id.replace(' ', '').replace('\n', '').upper().strip()
    voter_id = voter_id.rstrip('_').strip()
    
    if not voter_id:
        return ""
    
    # Try to identify the pattern: letters followed by digits
    # Pattern: [A-Z]{2,4}[0-9]{6,8} or similar
    match = re.match(r'^([A-Z0-9]{2,4})([A-Z0-9]{6,8})$', voter_id)
    if not match:
        # Try to find letters and digits separately
        letters = re.findall(r'[A-Z]', voter_id[:4])  # First few chars should be letters
        digits = re.findall(r'[0-9A-Z]', voter_id[3:]) if len(voter_id) > 3 else []
        
        if len(letters) >= 2 and len(digits) >= 6:
            # We have a pattern: letters + digits
            letter_part = ''.join(letters)
            digit_part = ''.join(digits)
            
            # Correct letter part
            letter_replacements = {'1': 'I', '0': 'O', '5': 'S', '8': 'B'}
            corrected_letters = ''.join(letter_replacements.get(c, c) if c.isdigit() else c for c in letter_part)
            
            # Correct digit part
            digit_replacements = {'O': '0', 'I': '1', 'S': '5', 'Z': '2', 'L': '1'}
            corrected_digits = ''.join(digit_replacements.get(c, c) if c.isalpha() else c for c in digit_part)
            
            return corrected_letters + corrected_digits
    
    # If we can't identify pattern, try standard 10-char correction
    if len(voter_id) == 10:
        return correct_voter_id(voter_id)
    
    # Fallback: apply corrections character by character
    corrected = list(voter_id)
    
    # Try to find where letters end and digits begin
    # Usually first 2-4 chars are letters, rest are digits
    letter_end = 0
    for i, char in enumerate(voter_id):
        if char.isdigit() and i > 0:
            letter_end = i
            break
        elif i >= 3:  # Assume max 4 letters
            letter_end = 3
            break
    
    if letter_end == 0:
        letter_end = min(3, len(voter_id))
    
    # Correct letter part
    letter_replacements = {'1': 'I', '0': 'O', '5': 'S', '8': 'B'}
    for i in range(letter_end):
        if corrected[i] in letter_replacements:
            corrected[i] = letter_replacements[corrected[i]]
    
    # Correct digit part
    digit_replacements = {'O': '0', 'I': '1', 'S': '5', 'Z': '2', 'L': '1'}
    for i in range(letter_end, len(corrected)):
        if corrected[i] in digit_replacements:
            corrected[i] = digit_replacements[corrected[i]]
    
    return ''.join(corrected)


# Test function
if __name__ == '__main__':
    print("Testing Voter ID Corrector...")
    print("=" * 60)
    
    test_cases = [
        # (input, expected_output, description)
        ("ABC1234567", "ABC1234567", "Perfect format"),
        ("1BC1234567", "IBC1234567", "1 instead of I in first position"),
        ("AB11234567", "ABI1234567", "1 instead of I in third position"),
        ("ABC12345O7", "ABC1234507", "O instead of 0 in digit part"),
        ("ABC123456o", "ABC1234560", "lowercase o instead of 0"),
        ("ABC1234I67", "ABC1234167", "I instead of 1 in digit part"),
        ("1BCO123456", "IBC0123456", "Multiple errors (1->I, O->0)"),
        ("ABC12345SO", "ABC1234550", "S and O in digit part"),
    ]
    
    for input_id, expected, description in test_cases:
        result = correct_voter_id(input_id)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status} {description}")
        print(f"   Input:    {input_id}")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")
        if result != expected:
            print(f"   WARNING: Mismatch!")
        print()

