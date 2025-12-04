import os
import re
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional

import cv2
import numpy as np

try:
    import easyocr
except ImportError:  # pragma: no cover - handled at runtime
    easyocr = None


def _preprocess_image(image_path: str) -> np.ndarray:
    """
    Apply enhanced preprocessing to boost OCR quality for receipt images.
    Returns a preprocessed BGR image suitable for EasyOCR.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Unable to read image: {image_path}")

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for better contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Denoise using bilateral filter to preserve edges
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # Convert back to BGR for EasyOCR
        enhanced_bgr = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        
        return enhanced_bgr
    except Exception as e:
        print(f"Preprocessing failed: {e}, using original image")
        return cv2.imread(image_path)


@lru_cache(maxsize=1)
def _get_reader():
    if easyocr is None:
        raise RuntimeError(
            "easyocr is not installed. Install it to enable receipt processing."
        )
    return easyocr.Reader(["en"], gpu=False)


def _extract_text_lines(image_path: str) -> List[str]:
    """
    Extract text lines from receipt image using EasyOCR.
    Uses enhanced preprocessing for better OCR accuracy.
    """
    reader = _get_reader()
    
    # Preprocess the image (returns BGR image)
    processed_image = _preprocess_image(image_path)
    
    # Use EasyOCR with settings optimized for receipts
    print("Running OCR on preprocessed image...")
    results = reader.readtext(
        processed_image, 
        detail=1,
        paragraph=False,
        batch_size=1
    )
    
    # Extract text with confidence filtering
    lines: List[str] = []
    for detection in results:
        if len(detection) >= 2:
            text = detection[1]
            confidence = detection[2] if len(detection) > 2 else 1.0
            # Only include detections with confidence > 0.25
            if confidence > 0.25:
                lines.append(str(text))
                print(f"  OCR: '{text}' (confidence: {confidence:.2f})")
    
    # Normalize and clean lines
    normalized: List[str] = []
    for line in lines:
        for chunk in str(line).split("\n"):
            cleaned = chunk.strip()
            if cleaned:
                normalized.append(cleaned)
    
    print(f"Extracted {len(normalized)} text lines from receipt")
    return normalized


DATE_REGEX = re.compile(
    r"(?:PRINT\s*DATE[:\s]*)?(\d{1,2}[-/][A-Z]{3}[-/]\d{2,4})", re.IGNORECASE
)


def _parse_print_date(line: str) -> Optional[datetime]:
    match = DATE_REGEX.search(line.upper())
    if not match:
        return None
    raw = match.group(1)
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%d/%b/%Y"):
        try:
            return datetime.strptime(raw.title(), fmt)
        except ValueError:
            continue
    return None


def _to_float(value: str) -> Optional[float]:
    try:
        # remove commas and stray characters
        cleaned = value.replace(",", "").replace("₹", "")
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _normalize_key(line: str) -> str:
    return line.upper().replace(" ", "")


def parse_receipt_lines(lines: List[str]) -> Dict:
    """
    Parse OCR extracted text lines into structured receipt data.
    Handles various receipt formats and OCR inconsistencies.
    Uses multi-line lookahead for better accuracy.
    """
    data: Dict = {"nozzles": []}
    current_nozzle: Dict = {}
    
    print(f"Parsing {len(lines)} lines...")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        upper = line.upper()
        print(f"Line {i}: {line}")
        
        # Print date - look for date pattern or PRINT keyword followed by date
        if "PRINT" in upper and "DATE" not in upper:
            # Check next line for date
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip().upper()
                if re.search(r'\d{1,2}[-/][A-Z]{3}[-/]\d{2,4}', next_line, re.IGNORECASE):
                    parsed_date = _parse_print_date(next_line)
                    if parsed_date:
                        data["printDate"] = parsed_date.strftime("%d-%b-%Y")
                        print(f"  -> Found print date: {data['printDate']}")
                    i += 2
                    continue
        
        # Direct date match
        if re.search(r'\d{1,2}[-/][A-Z]{3}[-/]\d{2,4}', upper, re.IGNORECASE):
            parsed_date = _parse_print_date(upper)
            if parsed_date and "printDate" not in data:
                data["printDate"] = parsed_date.strftime("%d-%b-%Y")
                print(f"  -> Found print date: {data['printDate']}")
            i += 1
            continue
        
        # Pump serial - might be split across lines
        if "PUMP" in upper and "pumpSerialNumber" not in data:
            # Look for serial number in current or next lines
            serial = ""
            for offset in range(4):  # Check current and next 3 lines
                if i + offset < len(lines):
                    check_line = lines[i + offset].strip()
                    # Skip lines with just keywords
                    if check_line.upper() in ["SERIAL", "NUMBER", "SERIAL NUMBER", "PUMP"]:
                        continue
                    # Look for alphanumeric pattern that looks like serial (6+ chars, has both letters and numbers)
                    match = re.search(r'[A-Z0-9]{6,}', check_line.upper())
                    if match and "SERIAL" not in check_line.upper() and "MODEL" not in check_line.upper() and "PUMP" not in check_line.upper():
                        potential_serial = match.group(0)
                        # Verify it has both letters and numbers (typical serial pattern)
                        if re.search(r'[A-Z]', potential_serial) and re.search(r'\d', potential_serial):
                            serial = potential_serial
                            data["pumpSerialNumber"] = serial
                            print(f"  -> Found pump serial: {serial}")
                            break
            i += 1
            continue
        
        # Model
        if upper.startswith("MODEL") and "model" not in data:
            # Check current line and next line
            model_val = ""
            if ":" in line:
                model_val = line.split(":", 1)[1].strip()
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.match(r'^\d+$', next_line):
                    model_val = next_line
            
            if model_val:
                data["model"] = model_val
                print(f"  -> Found model: {model_val}")
            i += 1
            continue
        
        # Nozzle header
        if "NOZZLE" in upper and "TOT" not in upper:
            # Save previous nozzle
            if current_nozzle and current_nozzle.get("nozzle"):
                data["nozzles"].append(current_nozzle)
                print(f"  -> Saved nozzle: {current_nozzle}")
            
            # Extract nozzle number
            nozzle_num = ""
            if ":" in line:
                nozzle_num = line.split(":", 1)[1].strip()
            else:
                # Check if number is on same line
                match = re.search(r'\d+', line)
                if match:
                    nozzle_num = match.group(0)
                # Or check next line
                elif i + 1 < len(lines) and re.match(r'^\d+$', lines[i + 1].strip()):
                    nozzle_num = lines[i + 1].strip()
                    i += 1
            
            current_nozzle = {"nozzle": nozzle_num or str(len(data["nozzles"]) + 1)}
            print(f"  -> Started nozzle: {current_nozzle['nozzle']}")
            i += 1
            continue
        
        # A value - look for pattern with large numbers
        # Handles: "A:7703407.230", "7703407.230", "122038504. 040"
        if upper.startswith("A:"):
            value_str = line.split(":", 1)[1].strip() if ":" in line else ""
            if value_str and _to_float(value_str):
                current_nozzle["a"] = value_str
                current_nozzle["aValue"] = _to_float(value_str)
                print(f"  -> A value: {value_str}")
            i += 1
            continue
        # If we just started a nozzle and see a large number (likely A value)
        elif current_nozzle and "a" not in current_nozzle and "v" not in current_nozzle:
            # Look for numbers with 6+ digits (typical A values)
            match = re.match(r'^(\d{6,}[\d\s.,]*)$', line)
            if match:
                value_str = match.group(1).strip()
                if _to_float(value_str):
                    current_nozzle["a"] = value_str
                    current_nozzle["aValue"] = _to_float(value_str)
                    print(f"  -> A value (inferred): {value_str}")
                    i += 1
                    continue
        
        # V value - handles "V:98569.270", "V:" + next line, "V" + next lines (split numbers)
        if upper.startswith("V:"):
            value_str = line.split(":", 1)[1].strip() if ":" in line else ""
            
            # If V: has no number or just whitespace, look at next lines
            if not value_str or not re.search(r'\d', value_str):
                # Combine next 2-3 lines which might be parts of the number
                combined = []
                for offset in range(1, 4):
                    if i + offset < len(lines):
                        next_val = lines[i + offset].strip()
                        # Stop if we hit keywords
                        if any(kw in next_val.upper() for kw in ["TOT", "SALE", "NOZZLE", "MODEL", "PUMP"]):
                            break
                        # If it looks like a number, add it
                        if re.match(r'^[\d.,\s]+$', next_val):
                            combined.append(next_val)
                        else:
                            break
                
                if combined:
                    value_str = "".join(combined)
                    i += len(combined)
            
            if value_str and _to_float(value_str):
                current_nozzle["v"] = value_str
                current_nozzle["vValue"] = _to_float(value_str)
                print(f"  -> V value: {value_str}")
            i += 1
            continue
        
        # Total sales - extremely robust detection
        # Handle: "Tot SALES:71045", "TOT SALES:71045", "Tot SALES" + "71045", "Tot" + "SALES" + "71045"
        is_tot_sales_line = False
        if ("TOT" in upper and "SALE" in upper):
            is_tot_sales_line = True
        elif upper.startswith("TOT") and current_nozzle and "totSales" not in current_nozzle:
            is_tot_sales_line = True
        elif (upper == "SALES" or upper.startswith("SALE")) and current_nozzle and "totSales" not in current_nozzle:
            # Check if previous line was "Tot" or if this is after nozzle data
            if i > 0 and "TOT" in lines[i-1].upper():
                is_tot_sales_line = True
            elif "a" in current_nozzle or "v" in current_nozzle:
                # We have nozzle data, "SALES" likely indicates total sales
                is_tot_sales_line = True
        
        if is_tot_sales_line:
            value_str = ""
            skip_lines = 0
            
            # Try to extract from current line first
            if ":" in line:
                value_str = line.split(":", 1)[1].strip()
            
            # Look for number in current line
            if not value_str:
                match = re.search(r'(\d{4,}[\d.,]*)', line)  # At least 4 digits for sales values
                if match:
                    value_str = match.group(1)
            
            # Look ahead for SALES keyword and/or number
            if not value_str:
                for offset in range(1, 4):  # Check next 3 lines
                    if i + offset >= len(lines):
                        break
                    next_line = lines[i + offset].strip()
                    next_upper = next_line.upper()
                    
                    # Skip "SALES" keyword line
                    if next_upper in ["SALES", "SALE"] or (len(next_upper) < 10 and "SALE" in next_upper):
                        skip_lines = offset
                        continue
                    
                    # Found a number
                    match = re.search(r'^(\d{4,}[\d.,]*)$', next_line)
                    if match:
                        value_str = match.group(1)
                        skip_lines = offset
                        break
                    
                    # Stop if we hit another keyword
                    if any(kw in next_upper for kw in ["NOZZLE", "MODEL", "PUMP", "PRINT"]):
                        break
            
            if value_str:
                float_val = _to_float(value_str)
                if float_val and float_val > 0:  # Ensure it's a valid positive number
                    current_nozzle["totSales"] = value_str
                    current_nozzle["totSalesValue"] = float_val
                    print(f"  -> Tot Sales: {value_str}")
                    i += skip_lines
            
            i += 1
            continue
        
        i += 1
    
    # Save last nozzle
    if current_nozzle and current_nozzle.get("nozzle"):
        data["nozzles"].append(current_nozzle)
        print(f"  -> Saved final nozzle: {current_nozzle}")
    
    # Calculate total sales
    total_sales = sum(
        nozzle.get("totSalesValue") or 0 for nozzle in data.get("nozzles", [])
    )
    if total_sales:
        data["totalSales"] = total_sales
        print(f"Total sales calculated: {total_sales}")
    
    print(f"Final data: {data}")
    return data


def process_receipt(image_path: str) -> Dict:
    """
    High-level helper to run OCR and parse structured data from receipt images.
    Returns dict with keys: printDate, pumpSerialNumber, model, nozzles (list), totalSales.
    """
    print(f"Processing receipt: {image_path}")
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Receipt image not found: {image_path}")
    
    try:
        lines = _extract_text_lines(image_path)
        if not lines:
            raise ValueError("Unable to extract text from receipt image. Image may be too blurry or low quality.")
        
        print(f"Extracted {len(lines)} lines of text")
        result = parse_receipt_lines(lines)
        
        # Validate that we extracted meaningful data
        if not result.get("nozzles"):
            print("WARNING: No nozzle data extracted")
        if not result.get("printDate"):
            print("WARNING: No print date extracted")
            
        return result
    except Exception as e:
        print(f"Error processing receipt: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


