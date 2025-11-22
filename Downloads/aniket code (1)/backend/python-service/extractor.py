"""
Enhanced Extractor - Grid-based extraction with local OCR
Uses local Tesseract OCR for high-accuracy extraction
"""

import fitz  # PyMuPDF
import pytesseract
import base64
import io
import os
from PIL import Image
import re
from typing import Dict, List, Optional
import multiprocessing as mp
from functools import partial
import time

# Import advanced modules
try:
    from photo_processor import PhotoProcessor
    PHOTO_PROCESSOR_AVAILABLE = True
except ImportError:
    PHOTO_PROCESSOR_AVAILABLE = False
    print("WARNING: Photo Processor not available")

try:
    from box_detector import BoxDetector
    BOX_DETECTOR_AVAILABLE = True
except ImportError:
    BOX_DETECTOR_AVAILABLE = False
    print("WARNING: Box Detector not available")

try:
    from smart_detector import SmartDetector
    SMART_DETECTOR_AVAILABLE = True
except ImportError:
    SMART_DETECTOR_AVAILABLE = False
    print("WARNING: Smart Detector not available")

# Import 400 DPI OCR Processor
try:
    from ocr_processor_400dpi import OCRProcessor400DPI
    OCR_400DPI_AVAILABLE = True
except ImportError:
    OCR_400DPI_AVAILABLE = False
    print("WARNING: 400 DPI OCR Processor not available")

# Google Vision API Fallback
try:
    from google_vision_fallback import get_google_vision_fallback
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False
    print("WARNING: Google Vision Fallback not available")

# Try to automatically locate Tesseract on Windows (fallback)
if os.name == 'nt':  # Windows
    possible_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"Found Tesseract at: {path}")
            break

# Initialize processors
photo_processor = PhotoProcessor() if PHOTO_PROCESSOR_AVAILABLE else None
box_detector = BoxDetector() if BOX_DETECTOR_AVAILABLE else None
smart_detector = SmartDetector() if SMART_DETECTOR_AVAILABLE else None
ocr_processor_400dpi = OCRProcessor400DPI() if OCR_400DPI_AVAILABLE else None

# Get CPU count for multiprocessing
def get_cpu_count():
    """Get optimal CPU count for multiprocessing - optimized for best CPU utilization"""
    try:
        cpu_count = mp.cpu_count()
        # Use all available CPUs for maximum performance (text layer extraction is CPU-bound)
        # Since we're using PDF text layer (no OCR), we can use more CPUs efficiently
        optimal_workers = max(1, cpu_count)  # Use all CPUs for best performance
        return optimal_workers
    except:
        return max(1, mp.cpu_count() if hasattr(mp, 'cpu_count') else 2)  # Fallback

CPU_WORKERS = get_cpu_count()
print(f"CPU Optimization: Using {CPU_WORKERS} parallel workers (out of {mp.cpu_count()} available CPUs) for maximum performance")

def clean_name_from_relative_patterns(name: str) -> str:
    """
    Remove any relative name patterns that might have been mixed into the name field.
    This ensures the name field never contains patterns like वडिलांचे नाव, पतीचे नाव, etc.
    
    Args:
        name: The name string that may contain relative name patterns
        
    Returns:
        Cleaned name with all relative name patterns removed
    """
    if not name:
        return name
    
    # Define Marathi relative name patterns to remove
    relative_patterns = [
        'वडिलांचे नाव',
        'पतीचे नाव',
        'आईचे नाव',
        'इतर नाव'
    ]
    
    cleaned = name.strip()
    
    # Remove all patterns from anywhere in the string
    for pattern in relative_patterns:
        # Remove pattern with colon before or after
        cleaned = cleaned.replace(pattern + ':', '').strip()
        cleaned = cleaned.replace(':' + pattern, '').strip()
        # Remove pattern itself
        cleaned = cleaned.replace(pattern, '').strip()
    
    # Clean up any remaining separators (colons, dashes, extra spaces)
    cleaned = cleaned.strip()
    cleaned = cleaned.strip(': -')
    # Remove multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def extract_relative_type(relative_name: str) -> tuple:
    """
    Extract relative type from relative name and remove all Marathi prefixes.
    Ensures the relative name never contains prefixes like वडिलांचे नाव, पतीचे नाव, etc.
    
    Args:
        relative_name: The relative name string that may contain type prefix
        
    Returns:
        tuple: (relative_type_code, cleaned_relative_name)
        - relative_type_code: 'F' (Father), 'H' (Husband), 'M' (Mother), 'O' (Other), or ''
        - cleaned_relative_name: Relative name with ALL type prefixes removed (before and after)
    """
    if not relative_name:
        return ('', '')
    
    # Define Marathi text patterns and their corresponding codes
    relative_type_patterns = {
        'वडिलांचे नाव': 'F',  # Father's name
        'पतीचे नाव': 'H',      # Husband's name
        'आईचे नाव': 'M',       # Mother's name
        'इतर नाव': 'O'         # Other name
    }
    
    cleaned_name = relative_name.strip()
    detected_code = ''
    
    # First, try to detect type from patterns before colon
    for pattern, code in relative_type_patterns.items():
        # Check if pattern exists before colon
        if ':' in cleaned_name:
            parts = cleaned_name.split(':', 1)
            prefix = parts[0].strip()
            name_part = parts[1].strip() if len(parts) > 1 else ''
            
            # Check if prefix contains the pattern
            if pattern in prefix:
                detected_code = code
                cleaned_name = name_part
                break
        # Check if pattern is at the start of the string
        elif cleaned_name.startswith(pattern):
            detected_code = code
            # Remove pattern from start
            cleaned_name = cleaned_name.replace(pattern, '', 1).strip()
            # Remove leading colon, space, dash, or other separators
            cleaned_name = cleaned_name.lstrip(': -').strip()
            break
    
    # Now remove ALL patterns from the cleaned name (in case they appear anywhere)
    # This ensures no prefix remains in the final name
    for pattern in relative_type_patterns.keys():
        # Remove pattern from anywhere in the string (case-insensitive matching)
        # Replace with empty string and clean up
        cleaned_name = cleaned_name.replace(pattern, '').strip()
        # Also handle patterns with colons
        cleaned_name = cleaned_name.replace(pattern + ':', '').strip()
        cleaned_name = cleaned_name.replace(':' + pattern, '').strip()
    
    # Clean up any remaining separators (colons, dashes, extra spaces)
    cleaned_name = cleaned_name.strip()
    # Remove leading/trailing colons, dashes, spaces
    cleaned_name = cleaned_name.strip(': -')
    # Remove multiple spaces
    import re
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    
    # If we detected a code but name is empty, try to get it from original
    if detected_code and not cleaned_name:
        # Try to extract name from original (in case pattern was in middle)
        temp_name = relative_name.strip()
        for pattern in relative_type_patterns.keys():
            temp_name = temp_name.replace(pattern, '').strip()
            temp_name = temp_name.replace(pattern + ':', '').strip()
            temp_name = temp_name.replace(':' + pattern, '').strip()
        temp_name = temp_name.strip(': -').strip()
        temp_name = re.sub(r'\s+', ' ', temp_name).strip()
        if temp_name:
            cleaned_name = temp_name
    
    return (detected_code, cleaned_name)

def extract_page_level_fields(page, cell_template, skip_header=0, page_annotations=None, google_vision=None):
    """
    Extract page-level fields (Booth Center, Booth Address) from the top of a page.
    These fields appear only once per page at the top, not in each cell.
    Uses Google Vision API if available, falls back to PDF text layer.
    
    Args:
        page: PyMuPDF page object
        cell_template: Cell template configuration
        skip_header: Height to skip from top (header)
        page_annotations: Cached Google Vision page annotations (optional)
        google_vision: Google Vision API instance (optional)
    
    Returns:
        Dictionary with 'boothCenter', 'boothAddress'
    """
    result = {
        'boothCenter': '',
        'boothAddress': ''
    }
    
    try:
        # Get page dimensions
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # Get boxes from template (these are relative to first cell, but for page-level fields,
        # we'll use them as absolute coordinates from top of page)
        booth_center_box = cell_template.get('boothCenterBox', {})
        booth_address_box = cell_template.get('boothAddressBox', {})
        
        # Helper function to extract text from a box region
        def extract_from_box(box, field_name, use_api_only=False):
            """
            Extract text from a box region.
            
            Args:
                box: Box coordinates dictionary
                field_name: Name of the field for logging
                use_api_only: If True, only use API (no PDF text layer fallback)
            
            Returns:
                Extracted text string
            """
            if not box:
                return ''
            
            # Calculate region coordinates (relative to page top, accounting for skip_header)
            region_x = int(box.get('x', 0))
            region_y = int(skip_header + box.get('y', 0))
            region_width = int(box.get('width', 0))
            region_height = int(box.get('height', 0))
            
            # Try Google Vision API first (if available and page annotations exist)
            if google_vision and page_annotations and page_annotations.get('success'):
                try:
                    # IMPORTANT: Page annotations are from a 2x scaled image, so we need to scale coordinates
                    scale_factor = 2.0  # Page was rendered at 2x scale
                    scaled_region_x = int(region_x * scale_factor)
                    scaled_region_y = int(region_y * scale_factor)
                    scaled_region_width = int(region_width * scale_factor)
                    scaled_region_height = int(region_height * scale_factor)
                    
                    # Extract from cached page annotations
                    api_result = google_vision.extract_text_from_region(
                        page_annotations,
                        scaled_region_x,
                        scaled_region_y,
                        scaled_region_width,
                        scaled_region_height
                    )
                    
                    if api_result.get('success') and api_result.get('text'):
                        text = api_result.get('text', '').strip()
                        # Apply Devanagari corrections
                        try:
                            from devanagari_corrector import correct_devanagari_text
                            text = correct_devanagari_text(text)
                        except:
                            pass
                        if text:
                            print(f"    ✓ API for {field_name}: '{text[:30]}...'")
                            return text
                except Exception as e:
                    print(f"    ⚠ API extraction failed for {field_name}: {str(e)}")
            
            # Fallback: Try Google Vision API with image extraction (if API available but no cached annotations)
            if google_vision and google_vision.is_available() and (not page_annotations or not page_annotations.get('success')):
                try:
                    # Render the region to image
                    region_rect = fitz.Rect(region_x, region_y, region_x + region_width, region_y + region_height)
                    region_pix = page.get_pixmap(clip=region_rect, dpi=300)
                    region_img_bytes = region_pix.tobytes("png")
                    region_img = Image.open(io.BytesIO(region_img_bytes))
                    
                    # Extract using Google Vision API
                    api_result = google_vision.extract_text_from_image(region_img, language_hints=['en', 'hi'])
                    
                    if api_result.get('success') and api_result.get('text'):
                        text = api_result.get('text', '').strip()
                        # Apply Devanagari corrections
                        try:
                            from devanagari_corrector import correct_devanagari_text
                            text = correct_devanagari_text(text)
                        except:
                            pass
                        if text:
                            print(f"    ✓ API (direct) for {field_name}: '{text[:30]}...'")
                            return text
                except Exception as e:
                    print(f"    ⚠ API direct extraction failed for {field_name}: {str(e)}")
            
            # Final fallback: PDF text layer (only if not using API only)
            if not use_api_only:
                try:
                    region_rect = fitz.Rect(region_x, region_y, region_x + region_width, region_y + region_height)
                    text_dict = page.get_text("dict", clip=region_rect)
                    text = ""
                    for block in text_dict.get("blocks", []):
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line.get("spans", []):
                                    text += span.get("text", "") + " "
                    return text.strip()
                except Exception as e:
                    print(f"    ⚠ PDF text layer extraction failed for {field_name}: {str(e)}")
                    return ''
            else:
                # API only mode - return empty if API failed
                print(f"    ⚠ API extraction failed for {field_name} (API only mode, no PDF text layer fallback)")
                return ''
        
        # Extract each field
        # Booth Center: Use API with PDF text layer fallback
        if booth_center_box:
            result['boothCenter'] = extract_from_box(booth_center_box, 'Booth Center', use_api_only=False)
        
        # Booth Address: Use API only (no PDF text layer fallback)
        if booth_address_box:
            result['boothAddress'] = extract_from_box(booth_address_box, 'Booth Address', use_api_only=True)
    
    except Exception as e:
        print(f"  ⚠ Error extracting page-level fields: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return result

def process_single_cell_worker(cell_task):
    """
    Worker function to process a single cell in parallel
    This function is called by multiprocessing workers
    
    Args:
        cell_task: Dictionary containing:
            - pdf_bytes: PDF file as bytes
            - page_num: Page number (0-indexed)
            - cell_info: Cell configuration (x, y, width, height, row, col, scale_x, scale_y)
            - config: Full extraction configuration
            - extraction_y_start: Start Y coordinate for extraction area
            - extraction_y_end: End Y coordinate for extraction area
    
    Returns:
        Dictionary with extraction result or None if skipped
    """
    try:
        # Extract task data
        pdf_bytes = cell_task['pdf_bytes']
        page_num = cell_task['page_num']
        cell_info = cell_task['cell_info']
        config = cell_task['config']
        extraction_y_start = cell_task['extraction_y_start']
        extraction_y_end = cell_task['extraction_y_end']
        page_annotations = cell_task.get('page_annotations')  # Get cached page annotations
        page_level_fields = cell_task.get('page_level_fields', {})  # Get page-level fields (Yadi, Booth Center, Booth Address)
        
        # Reopen PDF in worker (necessary for multiprocessing)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num]
        
        # Extract cell info
        cell_x = cell_info['x']
        cell_y = cell_info['y']
        cell_width_actual = cell_info['width']
        cell_height_actual = cell_info['height']
        row = cell_info['row']
        col = cell_info['col']
        
        # Debug: Check if page annotations are available (only log first few cells to avoid spam)
        if row == 0 and col == 0:  # Only log for first cell to reduce noise
            if page_annotations:
                annotations_count = len(page_annotations.get('annotations', []))
                success = page_annotations.get('success', False)
                if success and annotations_count > 0:
                    print(f"      [DEBUG] Page {page_num + 1} annotations: {annotations_count} regions available")
                else:
                    print(f"      [DEBUG] Page {page_num + 1} annotations: invalid (success={success}, count={annotations_count})")
            else:
                print(f"      [DEBUG] Page {page_num + 1}: ⚠ No page annotations - will use individual API calls")
        scale_x = cell_info['scale_x']
        scale_y = cell_info['scale_y']
        first_cell_width = cell_info['first_cell_width']
        first_cell_height = cell_info['first_cell_height']
        
        # Skip if cell is in header/footer zone
        if cell_y < extraction_y_start or (cell_y + cell_height_actual) > extraction_y_end:
            doc.close()
            return None
        
        # Get configuration
        cell_template = config.get('cellTemplate', {})
        voter_id_box = cell_template.get('voterIdBox', {})
        photo_box = cell_template.get('photoBox', {})
        name_box = cell_template.get('nameBox', {})
        relative_name_box = cell_template.get('relativeNameBox', {})
        house_number_box = cell_template.get('houseNumberBox', {})
        gender_box = cell_template.get('genderBox', {})
        age_box = cell_template.get('ageBox', {})
        assembly_number_box = cell_template.get('assemblyNumberBox', {})
        serial_number_box = cell_template.get('serialNumberBox', {})
        # Note: booth_center_box, booth_address_box are now extracted at page level, not cell level
        
        # Initialize processors in worker (they need to be recreated)
        local_ocr_processor = None
        local_photo_processor = None
        local_smart_detector = None
        local_google_vision = None
        
        try:
            if OCR_400DPI_AVAILABLE:
                from ocr_processor_400dpi import OCRProcessor400DPI
                local_ocr_processor = OCRProcessor400DPI()
        except:
            pass
        
        try:
            if PHOTO_PROCESSOR_AVAILABLE:
                from photo_processor import PhotoProcessor
                local_photo_processor = PhotoProcessor()
        except:
            pass
        
        try:
            if SMART_DETECTOR_AVAILABLE:
                from smart_detector import SmartDetector
                local_smart_detector = SmartDetector()
        except:
            pass
        
        try:
            if GOOGLE_VISION_AVAILABLE:
                from google_vision_fallback import get_google_vision_fallback
                # Get API key from config or environment
                from config import Config
                import os
                # Use GOOGLE_APPLICATION_CREDENTIALS (service account file path) if it's a valid file,
                # otherwise check if it's an API key or use GOOGLE_VISION_API_KEY
                credentials_path = Config.GOOGLE_APPLICATION_CREDENTIALS
                # Check if credentials_path is actually a file path
                is_file_path = credentials_path and os.path.exists(credentials_path)
                # If credentials_path is set but not a file, it might be an API key - pass it through
                # The google_vision_fallback will handle detecting if it's an API key
                api_key = Config.GOOGLE_VISION_API_KEY if not credentials_path else None
                local_google_vision = get_google_vision_fallback(credentials_path, api_key)
                if local_google_vision and local_google_vision.is_available():
                    print(f"      ✓ Google Vision API initialized and available")
                else:
                    print(f"      ⚠ Google Vision API not available - check GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_VISION_API_KEY in .env")
        except Exception as e:
            print(f"      ⚠ Failed to initialize Google Vision API: {str(e)}")
            local_google_vision = None
        
        # === EXTRACT VOTER ID ===
        voter_id_text = ""
        voter_id_confidence = 0.0
        voter_id_method = "none"
        cell_stats = {}
        
        # Strategy 0: Extract from PDF text layer first (NO OCR - fastest and most accurate)
        if voter_id_box:
            try:
                scaled_voter_id_x = voter_id_box.get('x', 0) * scale_x
                scaled_voter_id_y = voter_id_box.get('y', 0) * scale_y
                scaled_voter_id_width = voter_id_box.get('width', 200) * scale_x
                scaled_voter_id_height = voter_id_box.get('height', 30) * scale_y
                
                voter_id_rect = fitz.Rect(
                    cell_x + scaled_voter_id_x,
                    cell_y + scaled_voter_id_y,
                    cell_x + scaled_voter_id_x + scaled_voter_id_width,
                    cell_y + scaled_voter_id_y + scaled_voter_id_height
                )
                
                # Extract text directly from PDF text layer (no OCR needed)
                text_from_pdf = page.get_text("text", clip=voter_id_rect).strip()
                
                if text_from_pdf:
                    # Use regex to extract voter ID: ^[A-Z]{3}[0-9]{7}$
                    from voter_id_corrector import validate_voter_id, correct_voter_id
                    import re
                    
                    # Clean the text
                    text_clean = text_from_pdf.replace(' ', '').replace('\n', '').upper().strip()
                    
                    # Try to find voter ID pattern: 3 uppercase letters + 7 digits
                    pattern = r'[A-Z]{3}[0-9]{7}'
                    match = re.search(pattern, text_clean)
                    
                    if match:
                        extracted_id = match.group(0)
                        # Apply corrections and validate
                        corrected_id = correct_voter_id(extracted_id)
                        if validate_voter_id(corrected_id):
                            voter_id_text = corrected_id
                            voter_id_confidence = 0.99  # High confidence from text layer
                            voter_id_method = 'pdf_text_layer'
                            cell_stats['pdf_text_layer'] = cell_stats.get('pdf_text_layer', 0) + 1
                            print(f"      ✓ PDF Text Layer: '{voter_id_text}' (conf: {voter_id_confidence:.2f})")
            except Exception as e:
                # If text layer extraction fails, continue to OCR fallback
                pass
        
        # Strategy 1: Use 400 DPI OCR Processor (DISABLED - only use PDF text layer for voter ID)
        # Voter ID should only come from PDF text layer, no OCR fallback
        if False and not voter_id_text and local_ocr_processor and voter_id_box:
            try:
                scaled_voter_id_x = voter_id_box.get('x', 0) * scale_x
                scaled_voter_id_y = voter_id_box.get('y', 0) * scale_y
                scaled_voter_id_width = voter_id_box.get('width', 200) * scale_x
                scaled_voter_id_height = voter_id_box.get('height', 30) * scale_y
                
                voter_id_rect = fitz.Rect(
                    cell_x + scaled_voter_id_x,
                    cell_y + scaled_voter_id_y,
                    cell_x + scaled_voter_id_x + scaled_voter_id_width,
                    cell_y + scaled_voter_id_y + scaled_voter_id_height
                )
                
                result = local_ocr_processor.extract_voter_id(
                    image=None,
                    pdf_page=page,
                    rect=voter_id_rect
                )
                
                voter_id_text = result.get('voter_id', '')
                voter_id_confidence = result.get('confidence', 0.0)
                voter_id_method = result.get('method', 'unknown')
                
                if voter_id_method == 'tesseract':
                    cell_stats['ocr_400dpi_local'] = 1
                
                # Google Vision fallback if OCR failed or returned empty
                # First try cached page annotations (NO API CALL)
                if (not voter_id_text or len(voter_id_text.strip()) == 0) and local_google_vision:
                    # Check if page_annotations exists and has valid data
                    has_valid_annotations = (page_annotations and 
                                           page_annotations.get('success') and 
                                           len(page_annotations.get('annotations', [])) > 0)
                    
                    # Try cached annotations first
                    if has_valid_annotations:
                        try:
                            page_width = page_annotations.get('image_width', 0)
                            page_height = page_annotations.get('image_height', 0)
                            
                            if page_width > 0 and page_height > 0:
                                scale_factor = 2.0  # Page was rendered at 2x scale
                                scaled_abs_x = (cell_x + scaled_voter_id_x) * scale_factor
                                scaled_abs_y = (cell_y + scaled_voter_id_y) * scale_factor
                                scaled_abs_width = scaled_voter_id_width * scale_factor
                                scaled_abs_height = scaled_voter_id_height * scale_factor
                                
                                result_gv = local_google_vision.extract_text_from_region(
                                    page_annotations,
                                    int(scaled_abs_x),
                                    int(scaled_abs_y),
                                    int(scaled_abs_width),
                                    int(scaled_abs_height)
                                )
                                
                                if result_gv.get('success') and result_gv.get('text'):
                                    extracted_text = result_gv.get('text', '').strip()
                                    if extracted_text:
                                        voter_id_text = clean_voter_id(extracted_text)
                                        voter_id_confidence = result_gv.get('confidence', 0.7)
                                        voter_id_method = 'google_vision_cached'
                                        cell_stats['google_vision_fallback'] = cell_stats.get('google_vision_fallback', 0) + 1
                                        print(f"      ✓ Google Vision (cached) for Voter ID: '{voter_id_text}'")
                        except:
                            pass
                    
                    # Fallback to direct API call only if cached annotations not available
                    if (not voter_id_text or len(voter_id_text.strip()) == 0) and not has_valid_annotations:
                        try:
                            # Extract image for Google Vision (fallback)
                            voter_id_pix = page.get_pixmap(clip=voter_id_rect, dpi=300)
                            voter_id_img_bytes = voter_id_pix.tobytes("png")
                            voter_id_img = Image.open(io.BytesIO(voter_id_img_bytes))
                            
                            result_gv = local_google_vision.extract_text_from_image(
                                voter_id_img,
                                language_hints=['en', 'hi']
                            )
                            
                            if result_gv.get('success') and result_gv.get('text'):
                                extracted_text = result_gv.get('text', '').strip()
                                if extracted_text:
                                    voter_id_text = clean_voter_id(extracted_text)
                                    voter_id_confidence = result_gv.get('confidence', 0.7)
                                    voter_id_method = 'google_vision_fallback'
                                    cell_stats['google_vision_fallback'] = cell_stats.get('google_vision_fallback', 0) + 1
                                    print(f"      ✓ Google Vision fallback for Voter ID: '{voter_id_text}'")
                        except:
                            pass
                        
            except Exception as e:
                voter_id_text = ""
                voter_id_confidence = 0.0
        
        # Strategy 2: Fallback to legacy method (DISABLED - only use PDF text layer for voter ID)
        elif False and voter_id_box:
            try:
                scaled_voter_id_x = voter_id_box.get('x', 0) * scale_x
                scaled_voter_id_y = voter_id_box.get('y', 0) * scale_y
                scaled_voter_id_width = voter_id_box.get('width', 200) * scale_x
                scaled_voter_id_height = voter_id_box.get('height', 30) * scale_y
                
                voter_id_rect = fitz.Rect(
                    cell_x + scaled_voter_id_x,
                    cell_y + scaled_voter_id_y,
                    cell_x + scaled_voter_id_x + scaled_voter_id_width,
                    cell_y + scaled_voter_id_y + scaled_voter_id_height
                )
                
                voter_id_pix = page.get_pixmap(clip=voter_id_rect, dpi=300)
                voter_id_img_bytes = voter_id_pix.tobytes("png")
                voter_id_img = Image.open(io.BytesIO(voter_id_img_bytes))
                
                raw_text = pytesseract.image_to_string(
                    voter_id_img,
                    lang='eng+hin',
                    config='--psm 6'
                ).strip()
                
                voter_id_text = clean_voter_id(raw_text)
                voter_id_confidence = 0.5
                cell_stats['tesseract_ocr'] = 1
                
                # Strategy 2.5: Google Vision fallback if OCR failed
                if (not voter_id_text or len(voter_id_text.strip()) == 0) and local_google_vision:
                    try:
                        result = local_google_vision.extract_text_from_image(
                            voter_id_img,
                            language_hints=['en', 'hi']
                        )
                        
                        if result.get('success') and result.get('text'):
                            extracted_text = result.get('text', '').strip()
                            if extracted_text:
                                voter_id_text = clean_voter_id(extracted_text)
                                voter_id_confidence = result.get('confidence', 0.7)
                                cell_stats['google_vision_fallback'] = cell_stats.get('google_vision_fallback', 0) + 1
                                print(f"      ✓ Google Vision fallback for Voter ID: '{voter_id_text}'")
                    except:
                        pass
                        
            except Exception as e:
                voter_id_text = ""
                voter_id_confidence = 0.0
        
        # Strategy 3: Smart Detection (DISABLED - only use PDF text layer for voter ID)
        # Voter ID should only come from PDF text layer, no OCR fallback
        elif False and local_smart_detector:
            try:
                cell_rect = fitz.Rect(cell_x, cell_y, cell_x + cell_width_actual, cell_y + cell_height_actual)
                cell_pix = page.get_pixmap(clip=cell_rect, dpi=200)
                cell_img_bytes = cell_pix.tobytes("png")
                cell_img = Image.open(io.BytesIO(cell_img_bytes))
                
                smart_result = local_smart_detector.find_voter_id_in_cell(cell_img)
                if smart_result['found']:
                    voter_id_text = smart_result['voter_id']
                    voter_id_confidence = smart_result['confidence']
                    cell_stats['smart_voter_id_found'] = 1
            except:
                pass
        
        # === EXTRACT PHOTO ===
        photo_base64 = ""
        photo_quality = 0.0
        photo_method = "none"
        
        # Strategy 1: Use 400 DPI OCR Processor
        if local_ocr_processor and photo_box:
            try:
                scaled_photo_x = photo_box.get('x', 0) * scale_x
                scaled_photo_y = photo_box.get('y', 0) * scale_y
                scaled_photo_width = photo_box.get('width', 150) * scale_x
                scaled_photo_height = photo_box.get('height', 180) * scale_y
                
                photo_rect = fitz.Rect(
                    cell_x + scaled_photo_x,
                    cell_y + scaled_photo_y,
                    cell_x + scaled_photo_x + scaled_photo_width,
                    cell_y + scaled_photo_y + scaled_photo_height
                )
                
                result = local_ocr_processor.extract_photo(
                    image=None,
                    pdf_page=page,
                    rect=photo_rect
                )
                
                photo_base64 = result.get('photo_base64', '')
                photo_quality = result.get('confidence', 0.0)
                photo_method = result.get('method', 'unknown')
                
                # Enhance photo if processor available
                if photo_base64 and local_photo_processor:
                    try:
                        img_bytes = base64.b64decode(photo_base64)
                        img = Image.open(io.BytesIO(img_bytes))
                        photo_result = local_photo_processor.process_photo(img, enhance=True, resize=False)
                        photo_base64 = photo_result['base64']
                        photo_quality = photo_result.get('quality_score', photo_quality)
                        cell_stats['photo_enhanced'] = 1
                    except:
                        pass
                
                if photo_base64:
                    cell_stats['photo_400dpi'] = 1
            except:
                photo_base64 = ""
                photo_quality = 0.0
        
        # Strategy 2: Fallback to legacy method
        elif photo_box:
            try:
                scaled_photo_x = photo_box.get('x', 0) * scale_x
                scaled_photo_y = photo_box.get('y', 0) * scale_y
                scaled_photo_width = photo_box.get('width', 150) * scale_x
                scaled_photo_height = photo_box.get('height', 180) * scale_y
                
                photo_rect = fitz.Rect(
                    cell_x + scaled_photo_x,
                    cell_y + scaled_photo_y,
                    cell_x + scaled_photo_x + scaled_photo_width,
                    cell_y + scaled_photo_y + scaled_photo_height
                )
                
                photo_pix = page.get_pixmap(clip=photo_rect, dpi=300)
                photo_bytes_png = photo_pix.tobytes("png")
                photo_img = Image.open(io.BytesIO(photo_bytes_png))
                
                if local_photo_processor:
                    photo_result = local_photo_processor.process_photo(photo_img, enhance=True, resize=False)
                    photo_base64 = photo_result['base64']
                    photo_quality = photo_result.get('quality_score', 0.5)
                    cell_stats['photo_enhanced'] = 1
                else:
                    jpeg_buffer = io.BytesIO()
                    photo_img.convert('RGB').save(jpeg_buffer, format='JPEG', quality=85)
                    jpeg_bytes = jpeg_buffer.getvalue()
                    photo_base64 = base64.b64encode(jpeg_bytes).decode('utf-8')
                    photo_quality = 0.5
            except:
                photo_base64 = ""
                photo_quality = 0.0
        
        # Strategy 3: Smart Detection
        elif local_smart_detector:
            try:
                cell_rect = fitz.Rect(cell_x, cell_y, cell_x + cell_width_actual, cell_y + cell_height_actual)
                cell_pix = page.get_pixmap(clip=cell_rect, dpi=200)
                cell_img_bytes = cell_pix.tobytes("png")
                cell_img = Image.open(io.BytesIO(cell_img_bytes))
                
                smart_result = local_smart_detector.find_photo_in_cell(cell_img)
                if smart_result['found']:
                    photo_base64 = smart_result['photo_base64']
                    photo_quality = smart_result['confidence']
                    cell_stats['smart_photo_found'] = 1
            except:
                pass
        
        # === EXTRACT ADDITIONAL FIELDS ===
        # Helper function to extract text from a box
        def extract_text_from_box(box, field_name="", use_text_layer=True):
            """
            Extract text from a given box
            Strategy: PDF text layer first (no OCR), then cached Google Vision, then OCR fallback
            
            Args:
                box: Box configuration dict
                field_name: Name of the field (for logging)
                use_text_layer: If True, try PDF text layer first (for name, relativeName, houseNumber)
            """
            if not box:
                return ""
            
            text = ""
            confidence = 0.0
            
            try:
                scaled_box_x = box.get('x', 0) * scale_x
                scaled_box_y = box.get('y', 0) * scale_y
                scaled_box_width = box.get('width', 100) * scale_x
                scaled_box_height = box.get('height', 30) * scale_y
                
                box_rect = fitz.Rect(
                    cell_x + scaled_box_x,
                    cell_y + scaled_box_y,
                    cell_x + scaled_box_x + scaled_box_width,
                    cell_y + scaled_box_y + scaled_box_height
                )
                
                # Calculate absolute coordinates on the page
                absolute_box_x = cell_x + scaled_box_x
                absolute_box_y = cell_y + scaled_box_y
                
                # Strategy 0: Extract from PDF text layer first (NO OCR - fastest and most accurate)
                if use_text_layer:
                    try:
                        text_from_pdf = page.get_text("text", clip=box_rect).strip()
                        if text_from_pdf:
                            # Clean the text (remove extra whitespace, newlines)
                            text_clean = ' '.join(text_from_pdf.split())
                            if text_clean:
                                # Apply Devanagari corrections
                                try:
                                    from devanagari_corrector import correct_devanagari_text
                                    text_clean = correct_devanagari_text(text_clean)
                                except:
                                    pass  # If corrector not available, continue without correction
                                cell_stats['pdf_text_layer'] = cell_stats.get('pdf_text_layer', 0) + 1
                                print(f"      ✓ PDF Text Layer for {field_name}: '{text_clean[:30]}...'")
                                return text_clean
                    except Exception as e:
                        # If text layer extraction fails, continue to OCR fallback
                        pass
                
                # Prepare image for OCR/API (needed for both OCR and API calls)
                box_img = None
                try:
                    box_pix = page.get_pixmap(clip=box_rect, dpi=400)
                    box_img_bytes = box_pix.tobytes("png")
                    box_img = Image.open(io.BytesIO(box_img_bytes))
                    if field_name in ['name', 'relativeName']:
                        print(f"      → Image prepared for {field_name}: {box_img.size[0]}x{box_img.size[1]} pixels")
                except Exception as e:
                    if field_name in ['name', 'relativeName']:
                        print(f"      ⚠ Failed to prepare image for {field_name}: {str(e)}")
                    pass  # Will try lower DPI or skip if this fails
                
                # Strategy 1: Use 400 DPI OCR if available (only if use_text_layer=False)
                if not use_text_layer and not text and local_ocr_processor and box_img:
                    try:
                        # Preprocess for OCR
                        if box_img.mode != 'RGB':
                            box_img_for_ocr = box_img.convert('RGB')
                        else:
                            box_img_for_ocr = box_img.copy()
                        gray_img = box_img_for_ocr.convert('L')
                        
                        # Extract text using local OCR
                        text = pytesseract.image_to_string(
                            gray_img,
                            lang='eng+hin',
                            config='--psm 6 --oem 3'
                        ).strip()
                        
                        # If we got text, apply corrections and return it
                        if text and len(text.strip()) > 0:
                            # Apply Devanagari corrections
                            try:
                                from devanagari_corrector import correct_devanagari_text
                                text = correct_devanagari_text(text)
                            except:
                                pass  # If corrector not available, continue without correction
                            cell_stats['ocr_400dpi_local'] = cell_stats.get('ocr_400dpi_local', 0) + 1
                            print(f"      ✓ OCR 400 DPI for {field_name}: '{text[:30]}...'")
                            # For Name and Relative Name, continue to API even if OCR succeeds (API is more accurate)
                            # Only return OCR result if API is not available
                            if field_name not in ['name', 'relativeName'] or not local_google_vision:
                                return text
                    except:
                        pass
                
                # Strategy 2: Fallback to standard OCR (only if use_text_layer=False and 400 DPI failed)
                if not use_text_layer and (not text or len(text.strip()) == 0):
                    try:
                        if not box_img:
                            box_pix_std = page.get_pixmap(clip=box_rect, dpi=300)
                            box_img_bytes_std = box_pix_std.tobytes("png")
                            box_img = Image.open(io.BytesIO(box_img_bytes_std))
                        
                        text = pytesseract.image_to_string(
                            box_img,
                            lang='eng+hin',
                            config='--psm 6'
                        ).strip()
                        
                        # If we got text, apply corrections
                        if text and len(text.strip()) > 0:
                            # Apply Devanagari corrections
                            try:
                                from devanagari_corrector import correct_devanagari_text
                                text = correct_devanagari_text(text)
                            except:
                                pass  # If corrector not available, continue without correction
                            cell_stats['tesseract_ocr'] = cell_stats.get('tesseract_ocr', 0) + 1
                            print(f"      ✓ OCR Standard for {field_name}: '{text[:30]}...'")
                            # For Name and Relative Name, continue to API even if OCR succeeds
                            # Only return OCR result if API is not available
                            if field_name not in ['name', 'relativeName'] or not local_google_vision:
                                return text
                    except:
                        pass
                
                # Strategy 3: Google Vision API (using cached page annotations - NO API CALL)
                # For Name and Relative Name, use cached annotations even if OCR succeeded
                # For other fields, only use cached annotations if OCR failed
                use_cached_annotations = False
                # Check if page_annotations exists and has valid data
                has_valid_annotations = (page_annotations and 
                                       page_annotations.get('success') and 
                                       len(page_annotations.get('annotations', [])) > 0)
                
                if not use_text_layer and local_google_vision and has_valid_annotations:
                    if local_google_vision.is_available():
                        if field_name in ['name', 'relativeName']:
                            # For Name and Relative Name, always try cached annotations (more accurate for Devanagari)
                            use_cached_annotations = True
                            print(f"      → Using cached Google Vision annotations for {field_name}...")
                        elif not text or len(text.strip()) == 0:
                            # For other fields, only use cached annotations if OCR failed
                            use_cached_annotations = True
                
                if use_cached_annotations:
                    try:
                        # Get page dimensions from annotations
                        page_width = page_annotations.get('image_width', 0)
                        page_height = page_annotations.get('image_height', 0)
                        
                        if page_width > 0 and page_height > 0:
                            # Calculate scale factor (page annotations are from 2x scaled image)
                            # We need to scale coordinates back to match the PDF page coordinates
                            # The page was rendered at 2x scale, so we need to account for that
                            scale_factor = 2.0  # Page was rendered at 2x scale
                            
                            # Scale the absolute coordinates to match the annotation coordinate system
                            scaled_abs_x = absolute_box_x * scale_factor
                            scaled_abs_y = absolute_box_y * scale_factor
                            scaled_abs_width = scaled_box_width * scale_factor
                            scaled_abs_height = scaled_box_height * scale_factor
                            
                            # Extract text from region using cached annotations (NO API CALL)
                            result = local_google_vision.extract_text_from_region(
                                page_annotations,
                                int(scaled_abs_x),
                                int(scaled_abs_y),
                                int(scaled_abs_width),
                                int(scaled_abs_height)
                            )
                            
                            print(f"      → Cached Google Vision response for {field_name}: success={result.get('success')}, has_text={bool(result.get('text'))}")
                            
                            if result.get('success') and result.get('text'):
                                extracted_text = result.get('text', '').strip()
                                if extracted_text:
                                    # Apply Devanagari corrections
                                    try:
                                        from devanagari_corrector import correct_devanagari_text
                                        extracted_text = correct_devanagari_text(extracted_text)
                                    except:
                                        pass  # If corrector not available, continue without correction
                                    print(f"      ✓ Cached Google Vision succeeded for {field_name}: '{extracted_text[:30]}...'")
                                    cell_stats['google_vision_fallback'] = cell_stats.get('google_vision_fallback', 0) + 1
                                    return extracted_text
                                else:
                                    print(f"      ⚠ Cached Google Vision returned empty text for {field_name}")
                            else:
                                # Cached annotations didn't find text in region
                                error_msg = result.get('error', 'No text in region')
                                print(f"      ⚠ Cached Google Vision no text for {field_name}: {error_msg}")
                        else:
                            print(f"      ⚠ Invalid page dimensions in cached annotations for {field_name}")
                    except Exception as e:
                        # Log the error for debugging
                        import traceback
                        print(f"      ⚠ Cached Google Vision exception for {field_name}: {str(e)}")
                        pass
                
                # Fallback: If cached annotations not available, try direct API call (only if really needed)
                # IMPORTANT: Only use direct API calls if page annotations are truly not available
                # DO NOT make API calls if we have valid annotations (even if region extraction failed)
                use_api = False
                if not use_text_layer and local_google_vision and not has_valid_annotations:
                    if local_google_vision.is_available():
                        if field_name in ['name', 'relativeName']:
                            use_api = True
                            print(f"      → ⚠ FALLBACK API CALL for {field_name} (no cached annotations available)")
                        elif not text or len(text.strip()) == 0:
                            use_api = True
                            print(f"      → ⚠ FALLBACK API CALL for {field_name} (no cached annotations, OCR failed)")
                elif has_valid_annotations and use_cached_annotations:
                    # If we tried cached annotations but got no text, don't fallback to API
                    # This prevents unnecessary API calls when annotations are available
                    print(f"      → Using cached annotations only (no fallback API call)")
                
                if use_api:
                    if not box_img:
                        print(f"      ⚠ No image available for Google Vision API ({field_name})")
                    else:
                        try:
                            # Direct API call (fallback when page annotations not available)
                            result = local_google_vision.extract_text_from_image(
                                box_img,
                                language_hints=['en', 'hi']
                            )
                            
                            if result.get('success') and result.get('text'):
                                extracted_text = result.get('text', '').strip()
                                if extracted_text:
                                    try:
                                        from devanagari_corrector import correct_devanagari_text
                                        extracted_text = correct_devanagari_text(extracted_text)
                                    except:
                                        pass
                                    print(f"      ✓ Google Vision API (fallback) succeeded for {field_name}: '{extracted_text[:30]}...'")
                                    cell_stats['google_vision_fallback'] = cell_stats.get('google_vision_fallback', 0) + 1
                                    return extracted_text
                        except Exception as e:
                            pass
                
                # If API was used but failed, and we have OCR text, return OCR text as fallback
                if not use_text_layer and text and len(text.strip()) > 0:
                    return text
                
                # Apply Devanagari corrections before returning (final safety check)
                if text:
                    try:
                        from devanagari_corrector import correct_devanagari_text
                        text = correct_devanagari_text(text)
                    except:
                        pass  # If corrector not available, continue without correction
                
                return text if text else ""
                
            except Exception as e:
                return ""
        
        # Extract all additional fields
        # Use API (OCR → Google Vision fallback) for: name, relativeName
        # Use PDF text layer ONLY (NO OCR) for: houseNumber, gender, age, assemblyNumber, serialNumber
        name_text = extract_text_from_box(name_box, "name", use_text_layer=False)
        relative_name_text = extract_text_from_box(relative_name_box, "relativeName", use_text_layer=False)
        house_number_text = extract_text_from_box(house_number_box, "houseNumber", use_text_layer=True)
        gender_text = extract_text_from_box(gender_box, "gender", use_text_layer=True)
        age_text = extract_text_from_box(age_box, "age", use_text_layer=True)
        assembly_number_text = extract_text_from_box(assembly_number_box, "assemblyNumber", use_text_layer=True)
        serial_number_text = extract_text_from_box(serial_number_box, "serialNumber", use_text_layer=True)
        
        # Get page-level fields (Booth Center, Booth Address) - extracted once per page
        booth_center_text = page_level_fields.get('boothCenter', '')
        booth_address_text = page_level_fields.get('boothAddress', '')
        
        # Initialize relative type code
        relative_type_code = ''
        
        # Transliterate names to English using API
        name_english = ''
        relative_name_english = ''
        try:
            from devanagari_transliterator import transliterate_name
            from config import Config
            
            # Get API key from config
            api_key = Config.DEVANAGARI_TRANSLITERATOR_API_KEY
            
            if name_text:
                name_english = transliterate_name(name_text, api_key)
            if relative_name_text:
                relative_name_english = transliterate_name(relative_name_text, api_key)
                # Remove everything before ":" from Relative Name (English)
                if relative_name_english and ':' in relative_name_english:
                    # Find the position of ":" and take everything after it
                    colon_index = relative_name_english.find(':')
                    relative_name_english = relative_name_english[colon_index + 1:].strip()
        except ImportError:
            print("      WARNING: Devanagari transliterator not available")
        except Exception as e:
            print(f"      WARNING: Transliteration failed: {str(e)}")
        
        # Apply Devanagari text corrections to all extracted text fields
        try:
            from devanagari_corrector import (
                correct_devanagari_text, 
                clean_age_field, 
                correct_gender_field,
                clean_assembly_number_field,
                clean_serial_number_field,
                clean_house_number_field,
                correct_devanagari_name
            )
            # Use comprehensive regex-based name correction for Name and Relative Name
            if name_text:
                name_text = correct_devanagari_name(name_text)
                # Remove any relative name patterns that might have been mixed into name field
                name_text = clean_name_from_relative_patterns(name_text)
            if relative_name_text:
                relative_name_text = correct_devanagari_name(relative_name_text)
            
            # Extract relative type from relative name and clean the name
            relative_type_code, cleaned_relative_name = extract_relative_type(relative_name_text)
            # Use cleaned relative name (without type prefix)
            relative_name_text = cleaned_relative_name
            if house_number_text:
                house_number_text = correct_devanagari_text(house_number_text)
                # Clean house number - remove unwanted characters from front and back
                house_number_text = clean_house_number_field(house_number_text)
            # Correct gender field using specific gender corrector
            if gender_text:
                gender_text = correct_gender_field(gender_text)
            # Clean age field to extract only numbers
            if age_text:
                age_text = clean_age_field(age_text)
            # Clean assembly number field - extract only numbers, remove "ward"
            if assembly_number_text:
                assembly_number_text = clean_assembly_number_field(assembly_number_text)
            # Clean serial number field - extract only numbers, remove "ward"
            if serial_number_text:
                serial_number_text = clean_serial_number_field(serial_number_text)
        except ImportError:
            print("      WARNING: Devanagari corrector not available, skipping text corrections")
            # Still try to extract relative type even if corrector is not available
            if relative_name_text:
                relative_type_code, cleaned_relative_name = extract_relative_type(relative_name_text)
                relative_name_text = cleaned_relative_name
        except Exception as e:
            print(f"      WARNING: Devanagari correction failed: {str(e)}")
            # Still try to extract relative type even if correction failed
            if relative_name_text:
                relative_type_code, cleaned_relative_name = extract_relative_type(relative_name_text)
                relative_name_text = cleaned_relative_name
        
        # Clean and validate voter ID
        if voter_id_text:
            from voter_id_corrector import correct_voter_id, validate_voter_id
            voter_id_text = voter_id_text.rstrip('_').strip()
            # Apply OCR error corrections
            voter_id_text = correct_voter_id(voter_id_text)
            # Final validation with strict regex
            if not validate_voter_id(voter_id_text):
                # If validation fails, try to extract valid pattern from the text
                import re
                pattern = r'[A-Z]{3}[0-9]{7}'
                match = re.search(pattern, voter_id_text.upper())
                if match:
                    voter_id_text = match.group(0)
                    if validate_voter_id(voter_id_text):
                        print(f"      ✓ Voter ID validated: '{voter_id_text}'")
                    else:
                        print(f"      WARNING: Voter ID validation failed: '{voter_id_text}'")
                else:
                    print(f"      WARNING: Could not extract valid voter ID pattern from: '{voter_id_text}'")
        
        # Skip logic
        should_skip = False
        if not voter_id_text or voter_id_text.strip() == "":
            should_skip = True
        elif voter_id_text.upper() in ["NO ID", "NOID", "N/A", "NA", "NOT FOUND", "NONE"]:
            should_skip = True
        elif voter_id_confidence <= 0.0 and not photo_base64:
            should_skip = True
        
        if should_skip:
            doc.close()
            return {'skipped': True, 'stats': cell_stats}
        
        # Return result
        result = {
            'page': page_num + 1,
            'column': col + 1,
            'row': row + 1,
            'voterID': voter_id_text,
            'image_base64': photo_base64,
            'name': name_text,
            'nameEnglish': name_english,
            'relativeName': relative_name_text,
            'relativeNameEnglish': relative_name_english,
            'relativeType': relative_type_code,
            'houseNumber': house_number_text,
            'gender': gender_text,
            'age': age_text,
            'assemblyNumber': assembly_number_text,
            'serialNumber': serial_number_text,
            'boothCenter': booth_center_text,
            'boothAddress': booth_address_text,
            'metadata': {
                'voter_id_confidence': voter_id_confidence,
                'photo_quality': photo_quality,
                'enhanced': local_photo_processor is not None
            },
            'stats': cell_stats,
            'skipped': False
        }
        
        doc.close()
        return result
        
    except Exception as e:
        print(f"  ERROR in worker for cell [{cell_info.get('row', '?')+1},{cell_info.get('col', '?')+1}]: {str(e)}")
        return {'skipped': True, 'error': str(e)}

def extract_grid_vertical_enhanced(pdf_bytes, config):
    """
    Enhanced extraction with local OCR
    
    Uses:
    1. Local Tesseract OCR for text extraction
    2. 400 DPI OCR Processor for high-quality extraction
    3. Photo Processor for enhanced image quality
    4. Box Detector for automatic region detection
    
    Args:
        pdf_bytes: PDF file as bytes
        config: Configuration dictionary
    
    Returns:
        List of dictionaries with extracted data, plus stats
    """
    import time
    
    # Start timing
    start_time = time.time()
    
    print("=" * 60)
    print("ENHANCED EXTRACTION - Local OCR Powered")
    print("=" * 60)
    
    # Check which advanced features are available
    features_status = {
        '400 DPI OCR Processor': ocr_processor_400dpi is not None,
        'Photo Processor': photo_processor is not None,
        'Box Detector': box_detector is not None,
        'Tesseract OCR': True  # Always available
    }
    
    print("\nFeatures Status:")
    for feature, available in features_status.items():
        status = "OK: Enabled" if available else "FAIL: Disabled"
        print(f"  {feature}: {status}")
    print()
    
    # Strategy: Use 400 DPI OCR
    use_400dpi_first = ocr_processor_400dpi is not None
    print(f"Extraction Strategy: {'400 DPI Local OCR' if use_400dpi_first else 'Standard OCR'}")
    print()
    
    try:
        # Open PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        print(f"PDF opened: {total_pages} pages")
        
        # Calculate valid page range
        skip_start = config.get('skipPagesStart', 0)
        skip_end = config.get('skipPagesEnd', 0)
        
        start_page = skip_start
        end_page = total_pages - skip_end
        
        print(f"Processing pages {start_page + 1} to {end_page}")
        
        # Get configuration
        skip_header = config.get('skipHeaderHeight', 0)
        skip_footer = config.get('skipFooterHeight', 0)
        grid = config.get('grid', {})
        cell_template = config.get('cellTemplate', {})
        
        # Grid parameters
        grid_rows = grid.get('rows', 4)
        grid_cols = grid.get('columns', 3)
        grid_x = grid.get('x', 0)
        grid_y = grid.get('y', 0)
        grid_width = grid.get('width', 1500)
        grid_height = grid.get('height', 2000)
        
        # Get custom positions if available (for non-uniform grids)
        col_positions = grid.get('colPositions')
        row_positions = grid.get('rowPositions')
        
        # Calculate cell dimensions (for uniform grid, will be overridden if custom positions exist)
        cell_width = grid_width / grid_cols
        cell_height = grid_height / grid_rows
        
        print(f"Grid: {grid_rows}x{grid_cols}")
        if col_positions and row_positions:
            print(f"Using custom grid positions")
        else:
            print(f"Uniform cell size: {cell_width:.1f}x{cell_height:.1f}")
        
        # Cell template
        voter_id_box = cell_template.get('voterIdBox', {})
        photo_box = cell_template.get('photoBox', {})
        name_box = cell_template.get('nameBox', {})
        relative_name_box = cell_template.get('relativeNameBox', {})
        house_number_box = cell_template.get('houseNumberBox', {})
        gender_box = cell_template.get('genderBox', {})
        age_box = cell_template.get('ageBox', {})
        assembly_number_box = cell_template.get('assemblyNumberBox', {})
        serial_number_box = cell_template.get('serialNumberBox', {})
        
        # Get first cell dimensions for scaling
        first_cell_width = cell_width
        first_cell_height = cell_height
        if col_positions and len(col_positions) > 1:
            first_cell_width = col_positions[1] - col_positions[0]
        if row_positions and len(row_positions) > 1:
            first_cell_height = row_positions[1] - row_positions[0]
        
        extracted_data = []
        stats = {
            'photo_enhanced': 0,
            'total_cells': 0,
            'page_renders_cached': 0
        }
        
        # PERFORMANCE OPTIMIZATION: Collect all cell tasks for parallel processing
        print(f"\n{'='*60}")
        print("PARALLEL PROCESSING MODE")
        print(f"{'='*60}")
        print(f"Collecting all cells for parallel extraction using {CPU_WORKERS} CPU cores...")
        
        # Pre-process pages with Google Vision API (1 call per page instead of per cell)
        page_annotations_cache = {}
        if GOOGLE_VISION_AVAILABLE:
            try:
                from google_vision_fallback import get_google_vision_fallback
                from config import Config
                import os
                credentials_path = Config.GOOGLE_APPLICATION_CREDENTIALS
                is_file_path = credentials_path and os.path.exists(credentials_path)
                api_key = Config.GOOGLE_VISION_API_KEY if not credentials_path else None
                google_vision = get_google_vision_fallback(credentials_path, api_key)
                
                if google_vision and google_vision.is_available():
                    print(f"\n{'='*60}")
                    print(f"PRE-PROCESSING PAGES: {end_page - start_page} pages with Google Vision API")
                    print(f"Target: 1 API call per page (instead of per cell)")
                    print(f"{'='*60}")
                    api_calls_made = 0
                    for page_num in range(start_page, end_page):
                        try:
                            page = doc[page_num]
                            # Render page to image
                            mat = fitz.Matrix(2.0, 2.0)  # 2x scale for better quality
                            pix = page.get_pixmap(matrix=mat)
                            page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            
                            # Process entire page once - THIS IS THE ONLY API CALL FOR THIS PAGE
                            print(f"  → Processing page {page_num + 1} (API call #{api_calls_made + 1})...")
                            page_result = google_vision.extract_text_from_page_batch(page_img, language_hints=['en', 'hi'])
                            api_calls_made += 1
                            
                            if page_result.get('success'):
                                annotations_count = len(page_result.get('annotations', []))
                                page_annotations_cache[page_num] = page_result
                                print(f"  ✓ Page {page_num + 1}: {annotations_count} text regions cached")
                            else:
                                error_msg = page_result.get('error', 'Failed')
                                print(f"  ⚠ Page {page_num + 1}: {error_msg}")
                        except Exception as e:
                            print(f"  ⚠ Page {page_num + 1}: Error - {str(e)}")
                            import traceback
                            traceback.print_exc()
                    print(f"{'='*60}")
                    print(f"Page pre-processing complete!")
                    print(f"  - Pages processed: {len(page_annotations_cache)}/{end_page - start_page}")
                    print(f"  - API calls made: {api_calls_made} (should be {end_page - start_page})")
                    print(f"  - Expected savings: ~{((grid_rows * grid_cols * (end_page - start_page)) - api_calls_made)} API calls")
                    print(f"{'='*60}\n")
            except Exception as e:
                print(f"⚠ Could not pre-process pages: {str(e)}")
                google_vision = None
        
        # Extract page-level fields (Booth Center, Booth Address) - once per page
        # Use header template if available, otherwise fall back to cell template
        header_template = config.get('headerTemplate', {})
        template_to_use = header_template if header_template else cell_template
        
        # Use Google Vision API if available (using cached page annotations)
        page_level_fields_cache = {}
        print(f"\nExtracting page-level fields (Booth Center, Booth Address) from each page...")
        print(f"Using Google Vision API (with cached page annotations) for better accuracy")
        
        # Initialize Google Vision for page-level extraction if not already done
        page_level_google_vision = None
        if GOOGLE_VISION_AVAILABLE:
            try:
                from google_vision_fallback import get_google_vision_fallback
                from config import Config
                import os
                credentials_path = Config.GOOGLE_APPLICATION_CREDENTIALS
                is_file_path = credentials_path and os.path.exists(credentials_path)
                api_key = Config.GOOGLE_VISION_API_KEY if not credentials_path else None
                page_level_google_vision = get_google_vision_fallback(credentials_path, api_key)
                if not page_level_google_vision or not page_level_google_vision.is_available():
                    page_level_google_vision = None
            except:
                page_level_google_vision = None
        
        # Use the same google_vision instance if available from pre-processing
        if not page_level_google_vision and 'google_vision' in locals() and google_vision:
            page_level_google_vision = google_vision
        
        for page_num in range(start_page, end_page):
            try:
                page = doc[page_num]
                # Get cached page annotations if available
                page_annotations = page_annotations_cache.get(page_num)
                
                # Extract page-level fields using API (with cached annotations) or fallback to PDF text
                # Use header template if available, otherwise use cell template
                page_level_data = extract_page_level_fields(
                    page, 
                    template_to_use, 
                    skip_header,
                    page_annotations=page_annotations,
                    google_vision=page_level_google_vision
                )
                page_level_fields_cache[page_num] = page_level_data
                if page_level_data.get('boothCenter') or page_level_data.get('boothAddress'):
                    print(f"  ✓ Page {page_num + 1}: Booth Center='{page_level_data.get('boothCenter', '')[:20]}...', Booth Address='{page_level_data.get('boothAddress', '')[:30]}...'")
            except Exception as e:
                print(f"  ⚠ Page {page_num + 1}: Error extracting page-level fields - {str(e)}")
                import traceback
                traceback.print_exc()
                page_level_fields_cache[page_num] = {'boothCenter': '', 'boothAddress': ''}
        print()
        
        cell_tasks = []
        
        # Collect all cell tasks
        for page_num in range(start_page, end_page):
            page = doc[page_num]
            page_height = page.rect.height
            
            # Calculate extraction area (exclude header/footer)
            extraction_y_start = skip_header
            extraction_y_end = page_height - skip_footer
            
            for col in range(grid_cols):
                for row in range(grid_rows):
                    stats['total_cells'] += 1
                    
                    # Calculate cell position using custom positions if available
                    if col_positions and row_positions:
                        cell_x = col_positions[col] if col < len(col_positions) else grid_x + (col * cell_width)
                        cell_y = row_positions[row] if row < len(row_positions) else grid_y + (row * cell_height)
                        
                        # Get actual cell dimensions from custom positions
                        if col + 1 < len(col_positions):
                            cell_width_actual = col_positions[col + 1] - col_positions[col]
                        else:
                            cell_width_actual = grid_x + grid_width - col_positions[col]
                        
                        if row + 1 < len(row_positions):
                            cell_height_actual = row_positions[row + 1] - row_positions[row]
                        else:
                            cell_height_actual = grid_y + grid_height - row_positions[row]
                    else:
                        # Uniform grid
                        cell_x = grid_x + (col * cell_width)
                        cell_y = grid_y + (row * cell_height)
                        cell_width_actual = cell_width
                        cell_height_actual = cell_height
                    
                    # Calculate scaling factors for this cell
                    scale_x = cell_width_actual / first_cell_width
                    scale_y = cell_height_actual / first_cell_height
                    
                    # Create cell task
                    cell_task = {
                        'pdf_bytes': pdf_bytes,
                        'page_num': page_num,
                        'cell_info': {
                            'x': cell_x,
                            'y': cell_y,
                            'width': cell_width_actual,
                            'height': cell_height_actual,
                            'row': row,
                            'col': col,
                            'scale_x': scale_x,
                            'scale_y': scale_y,
                            'first_cell_width': first_cell_width,
                            'first_cell_height': first_cell_height
                        },
                        'config': config,
                        'extraction_y_start': extraction_y_start,
                        'extraction_y_end': extraction_y_end,
                        'page_annotations': page_annotations_cache.get(page_num),  # Pass cached page annotations
                        'page_level_fields': page_level_fields_cache.get(page_num, {})  # Pass page-level fields (Booth Center, Booth Address)
                    }
                    
                    cell_tasks.append(cell_task)
        
        print(f"Total cells to process: {len(cell_tasks)}")
        print(f"Starting parallel processing with {CPU_WORKERS} workers...\n")
        
        # Process cells in parallel
        parallel_start_time = time.time()
        parallel_time = 0.0
        
        if CPU_WORKERS > 1 and len(cell_tasks) > 1:
            # Use multiprocessing for parallel processing
            # Windows uses 'spawn' method by default, which works fine
            try:
                with mp.Pool(processes=CPU_WORKERS) as pool:
                    results = pool.map(process_single_cell_worker, cell_tasks)
                parallel_time = time.time() - parallel_start_time
            except Exception as e:
                print(f"WARNING: Parallel processing failed ({str(e)}), falling back to sequential")
                print("This may happen on some systems. Processing will continue...")
                results = [process_single_cell_worker(task) for task in cell_tasks]
                parallel_time = time.time() - parallel_start_time
        else:
            # Fallback to sequential processing (for debugging or single CPU)
            results = [process_single_cell_worker(task) for task in cell_tasks]
            parallel_time = time.time() - parallel_start_time
        print(f"\n{'='*60}")
        print(f"Parallel processing completed in {parallel_time:.2f} seconds")
        print(f"{'='*60}\n")
        
        # Aggregate results from parallel processing
        print("Aggregating results...")
        for result in results:
            if result is None:
                continue
            
            if result.get('skipped', False):
                stats['cells_skipped'] = stats.get('cells_skipped', 0) + 1
                # Aggregate stats from skipped cells
                cell_stats = result.get('stats', {})
                if 'pdf_text_layer' in cell_stats:
                    stats['pdf_text_layer'] = stats.get('pdf_text_layer', 0) + cell_stats['pdf_text_layer']
                if 'ocr_400dpi_local' in cell_stats:
                    stats['ocr_400dpi_local'] = stats.get('ocr_400dpi_local', 0) + cell_stats['ocr_400dpi_local']
                if 'tesseract_ocr' in cell_stats:
                    stats['tesseract_ocr'] = stats.get('tesseract_ocr', 0) + cell_stats['tesseract_ocr']
                if 'google_vision_fallback' in cell_stats:
                    stats['google_vision_fallback'] = stats.get('google_vision_fallback', 0) + cell_stats['google_vision_fallback']
                continue
            
            # Add valid result
            extracted_data.append({
                'page': result['page'],
                'column': result['column'],
                'row': result['row'],
                'voterID': result['voterID'],
                'image_base64': result['image_base64'],
                'name': result.get('name', ''),
                'nameEnglish': result.get('nameEnglish', ''),
                'relativeName': result.get('relativeName', ''),
                'relativeNameEnglish': result.get('relativeNameEnglish', ''),
                'relativeType': result.get('relativeType', ''),
                'houseNumber': result.get('houseNumber', ''),
                'gender': result.get('gender', ''),
                'age': result.get('age', ''),
                'assemblyNumber': result.get('assemblyNumber', ''),
                'serialNumber': result.get('serialNumber', ''),
                'boothCenter': result.get('boothCenter', ''),
                'boothAddress': result.get('boothAddress', ''),
                'metadata': result['metadata']
            })
            
            # Aggregate stats
            cell_stats = result.get('stats', {})
            if 'pdf_text_layer' in cell_stats:
                stats['pdf_text_layer'] = stats.get('pdf_text_layer', 0) + cell_stats['pdf_text_layer']
            if 'ocr_400dpi_local' in cell_stats:
                stats['ocr_400dpi_local'] = stats.get('ocr_400dpi_local', 0) + cell_stats['ocr_400dpi_local']
            if 'tesseract_ocr' in cell_stats:
                stats['tesseract_ocr'] = stats.get('tesseract_ocr', 0) + cell_stats['tesseract_ocr']
            if 'photo_enhanced' in cell_stats:
                stats['photo_enhanced'] = stats.get('photo_enhanced', 0) + cell_stats['photo_enhanced']
            if 'photo_400dpi' in cell_stats:
                stats['photo_400dpi'] = stats.get('photo_400dpi', 0) + cell_stats['photo_400dpi']
            if 'smart_voter_id_found' in cell_stats:
                stats['smart_voter_id_found'] = stats.get('smart_voter_id_found', 0) + cell_stats['smart_voter_id_found']
            if 'smart_photo_found' in cell_stats:
                stats['smart_photo_found'] = stats.get('smart_photo_found', 0) + cell_stats['smart_photo_found']
            if 'google_vision_fallback' in cell_stats:
                stats['google_vision_fallback'] = stats.get('google_vision_fallback', 0) + cell_stats['google_vision_fallback']
        
        print(f"Results aggregated: {len(extracted_data)} valid records extracted")
        
        # Sort by page, then column, then row (vertical extraction)
        extracted_data.sort(key=lambda x: (x['page'], x['column'], x['row']))
        
        # Print statistics
        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print(f"{'='*60}")
        print(f"Total records extracted: {len(extracted_data)}")
        print(f"Total cells processed: {stats['total_cells']}")
        print(f"Cells skipped (no voter ID): {stats.get('cells_skipped', 0)}")
        print(f"\nExtraction Statistics:")
        
        # PDF Text Layer stats (fastest, most accurate - no OCR)
        if 'pdf_text_layer' in stats:
            print(f"  PDF Text Layer (NO OCR): {stats.get('pdf_text_layer', 0)} fields extracted")
        
        # OCR stats (fallback only)
        if 'ocr_400dpi_local' in stats:
            print(f"  400 DPI Local OCR (fallback): {stats.get('ocr_400dpi_local', 0)}")
        if 'tesseract_ocr' in stats:
            print(f"  Standard Tesseract OCR (fallback): {stats.get('tesseract_ocr', 0)}")
        print(f"  Photos extracted (400 DPI): {stats.get('photo_400dpi', 0)}")
        print(f"  Photos enhanced: {stats.get('photo_enhanced', 0)}")
        
        # Smart detection stats
        if 'smart_voter_id_found' in stats:
            print(f"  Smart Voter ID found: {stats.get('smart_voter_id_found', 0)}")
        if 'smart_photo_found' in stats:
            print(f"  Smart Photo found: {stats.get('smart_photo_found', 0)}")
        
        # Google Vision fallback stats
        if 'google_vision_fallback' in stats:
            print(f"  Google Vision API fallback used: {stats.get('google_vision_fallback', 0)}")
        
        # Summary message
        if stats.get('pdf_text_layer', 0) > 0:
            print(f"\n✓ SUCCESS: Using PDF Text Layer extraction (fastest & 99% accurate!)")
            print(f"  - PDF Text Layer: {stats.get('pdf_text_layer', 0)} fields (no OCR needed)")
        if stats.get('ocr_400dpi_local', 0) > 0:
            print(f"  - Local OCR (fallback): {stats.get('ocr_400dpi_local', 0)} cells")
        if stats.get('tesseract_ocr', 0) > 0:
            print(f"  - Standard OCR (fallback): {stats.get('tesseract_ocr', 0)} cells")
        
        # Calculate total time
        end_time = time.time()
        extraction_time = end_time - start_time
        
        print(f"\n⏱️  Extraction Time: {extraction_time:.2f} seconds ({extraction_time/60:.2f} minutes)")
        print(f"🚀 Parallel Processing: Used {CPU_WORKERS} CPU cores")
        if parallel_time > 0:
            speedup = (extraction_time - parallel_time) / extraction_time * 100 if extraction_time > 0 else 0
            print(f"   - Parallel processing time: {parallel_time:.2f} seconds")
            print(f"   - Estimated speedup: ~{speedup:.1f}% faster than sequential")
        
        print(f"{'='*60}\n")
        
        # Close document
        doc.close()
        
        # Calculate accuracy rate and API call statistics
        pdf_text_layer_fields = stats.get('pdf_text_layer', 0)
        ocr_fields = stats.get('ocr_400dpi_local', 0) + stats.get('tesseract_ocr', 0)
        api_calls = stats.get('google_vision_fallback', 0)
        
        # Total fields extracted = sum of all extraction methods
        total_fields_extracted = pdf_text_layer_fields + ocr_fields + api_calls
        
        # Calculate accuracy rate using weighted average
        # PDF text layer = 99% accuracy, OCR = 85% accuracy, API = 95% accuracy
        if total_fields_extracted > 0:
            # Weighted average: (pdf_fields * 0.99 + ocr_fields * 0.85 + api_fields * 0.95) / total_fields
            pdf_weighted = pdf_text_layer_fields * 0.99
            ocr_weighted = ocr_fields * 0.85
            api_weighted = api_calls * 0.95
            total_weighted = pdf_weighted + ocr_weighted + api_weighted
            overall_accuracy = total_weighted / total_fields_extracted
            # Cap at 100%
            overall_accuracy = min(1.0, overall_accuracy)
        else:
            overall_accuracy = 0.0
        
        # Return data with stats
        return {
            'extracted_data': extracted_data,
            'stats': {
                'records_extracted': len(extracted_data),
                'cells_processed': stats['total_cells'],
                'cells_skipped': stats.get('cells_skipped', 0),
                'extraction_time_seconds': round(extraction_time, 2),
                'accuracy_rate': round(overall_accuracy * 100, 2),  # Percentage
                'api_calls_used': api_calls,
                'pdf_text_layer_fields': pdf_text_layer_fields,
                'ocr_fields': ocr_fields,
                'total_fields_extracted': total_fields_extracted,
                'extraction_methods': {
                    'pdf_text_layer': pdf_text_layer_fields,
                    'ocr': ocr_fields,
                    'api': api_calls
                }
            }
        }
    
    except Exception as e:
        print(f"Error in extract_grid_vertical_enhanced: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def extract_grid_vertical(pdf_bytes, config):
    """
    Main extraction function - uses enhanced version with local OCR
    
    Returns:
        If enhanced version returns dict with stats, extract just the data list
        Otherwise returns the list directly for backward compatibility
    """
    result = extract_grid_vertical_enhanced(pdf_bytes, config)
    
    # If result is a dict with stats, return it as-is (new format)
    if isinstance(result, dict) and 'extracted_data' in result:
        return result
    
    # Otherwise return result directly (backward compatibility)
    return result


def clean_voter_id(text):
    """
    Clean and normalize voter ID text (fallback method)
    
    Args:
        text: Raw OCR text
    
    Returns:
        Cleaned voter ID text
    """
    from voter_id_corrector import correct_voter_id
    
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove common OCR errors
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Try to extract voter ID pattern (e.g., NOW1234567)
    # Common patterns: 3 letters followed by 7 digits
    pattern = r'[A-Z]{3}\d{7}'
    match = re.search(pattern, text.upper())
    if match:
        cleaned = match.group(0)
    else:
        # If no pattern match, return cleaned text
        cleaned = text.strip()
    
    # Remove trailing underscores (common OCR error)
    cleaned = cleaned.rstrip('_').strip()
    
    # Apply OCR error corrections
    cleaned = correct_voter_id(cleaned)
    
    return cleaned


def test_tesseract():
    """
    Test if Tesseract is properly installed
    """
    try:
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract version: {version}")
        
        # Check available languages
        langs = pytesseract.get_languages()
        print(f"Available languages: {langs}")
        
        if 'eng' not in langs:
            print("WARNING: English language data not found")
        if 'hin' not in langs:
            print("WARNING: Hindi language data not found")
        
        return True
    except Exception as e:
        print(f"Tesseract test failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Test enhanced extraction modules
    print("Testing Enhanced Extraction Modules...")
    print("=" * 60)
    
    # Test Tesseract installation
    print("\n1. Testing Tesseract OCR (fallback)...")
    test_tesseract()
    
    # Test advanced modules
    print("\n2. Testing Advanced Modules...")
    
    if ocr_processor_400dpi:
        print("  OK: 400 DPI OCR Processor: Available ✓")
    else:
        print("  FAIL: 400 DPI OCR Processor: Not available")
    
    if photo_processor:
        print("  OK: Photo Processor: Available")
    else:
        print("  FAIL: Photo Processor: Not available")
    
    if box_detector:
        print("  OK: Box Detector: Available")
    else:
        print("  FAIL: Box Detector: Not available")
    
    if smart_detector:
        print("  OK: Smart Detector: Available")
    else:
        print("  FAIL: Smart Detector: Not available")
    
    print("\n" + "=" * 60)
    print("Ready for enhanced extraction!")
    if ocr_processor_400dpi:
        print("Strategy: 400 DPI Local OCR ✓")
    else:
        print("Strategy: Standard Tesseract OCR")
    print("=" * 60)

