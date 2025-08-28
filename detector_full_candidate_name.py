import csv
import json
import re
import sys
from typing import Dict, Any

# Field Identifiers

PHONE_RELATED_FIELDS = {"phone", "contact", "alt_phone", "mobile"}
AADHAAR_RELATED_FIELDS = {"aadhar", "aadhaar"}
PASSPORT_RELATED_FIELDS = {"passport"}
UPI_RELATED_FIELDS = {"upi", "upi_id"}
EMAIL_RELATED_FIELDS = {"email", "alt_email", "username"}
FULL_NAME_FIELDS = {"name"}
GIVEN_NAME_FIELD = "first_name"
SURNAME_FIELD = "last_name"
LOCATION_FIELDS = {"address"}
NETWORK_IP_FIELDS = {"ip", "ip_address"}
HARDWARE_ID_FIELDS = {"device_id"}

# Regex pattern definitions
email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
upi_pattern = re.compile(r"\b[a-zA-Z0-9._-]{2,}@[a-zA-Z]{2,}\b")
passport_pattern = re.compile(r"\b[A-Z][0-9]{7}\b")
decimal_ten_pattern = re.compile(r"\b\d{10}\b")
decimal_twelve_pattern = re.compile(r"\b\d{12}\b")
postal_code_pattern = re.compile(r"\b\d{6}\b")  # Indian postal code format

def obfuscate_phone_number(value_str: str) -> str:
    #Mask phone number
    match_obj = re.search(r"\d{10}", value_str)
    if not match_obj: 
        return value_str
    matched_sequence = match_obj.group(0)
    return value_str.replace(matched_sequence, f"{matched_sequence[:2]}XXXXXX{matched_sequence[-2:]}")

def obfuscate_aadhaar_number(value_str: str) -> str:
    #Mask Aadhaar number 
    match_obj = re.search(r"\d{12}", value_str)
    if not match_obj:
        return value_str
    matched_sequence = match_obj.group(0)
    return value_str.replace(matched_sequence, f"{matched_sequence[:4]}XXXX{matched_sequence[-4:]}")

def obfuscate_passport_number(value_str: str) -> str:
    #Mask passport number
    match_obj = passport_pattern.search(value_str)
    if not match_obj:
        return value_str
    matched_sequence = match_obj.group(0)
    return value_str.replace(matched_sequence, matched_sequence[0] + "XXXXXXX")

def obfuscate_upi_identifier(value_str: str) -> str:
    #Mask UPI ID
    if "@" not in value_str:
        return "[REDACTED_PII]"
    username_part, domain_part = value_str.split("@", 1)
    if len(username_part) <= 2:
        masked_username = "XX"
    else:
        masked_username = username_part[:2] + "XXX"
    return f"{masked_username}@{domain_part}"

def obfuscate_email_address(value_str: str) -> str:
    #Mask email address
    if "@" not in value_str:
        return value_str
    local_part, domain_part = value_str.split("@", 1)
    if len(local_part) <= 2:
        masked_local = "XX"
    else:
        masked_local = local_part[:2] + "XXX"
    return f"{masked_local}@{domain_part}"

def obfuscate_personal_name(value_str: str) -> str:
    #Mask name components
    word_tokens = [token for token in value_str.split() if token]
    return " ".join(token[0] + "X" * (len(token) - 1) for token in word_tokens)

def obfuscate_physical_address(value_str: str) -> str:
    #Mask address while
    postal_code = None
    postal_match = postal_code_pattern.search(value_str)
    if postal_match:
        postal_code = postal_match.group(0)
    
    address_prefix = value_str[:3] + "XXX" if len(value_str) >= 3 else "XXX"
    postal_suffix = f", {postal_code}" if postal_code else ""
    return f"{address_prefix}...{postal_suffix}"

def obfuscate_ip_address(value_str: str) -> str:
    #Mask IP address
    try:
        octet_a, octet_b, octet_c, octet_d = value_str.split(".")
        return f"{octet_a}.XXX.XXX.{octet_d}"
    except Exception:
        return "[REDACTED_PII]"

def obfuscate_device_identifier(value_str: str) -> str:
    #Mask device ID
    string_value = str(value_str)
    if len(string_value) <= 6:
        return "XXXXXX"
    return string_value[:3] + "XXX" + string_value[-3:]

def appears_as_complete_name(value_str: str) -> bool:
    #Check if string contains at least two alphabetic word tokens
    alphabetic_tokens = [token for token in re.findall(r"[A-Za-z]+", value_str)]
    return len(alphabetic_tokens) >= 2

def contains_complete_address(record_data: Dict[str, Any]) -> bool:
    #Determine if record contains complete physical address information
    address_content = ""
    for field_name in LOCATION_FIELDS:
        if field_name in record_data and record_data[field_name]:
            address_content += str(record_data[field_name]) + " "
    
    # Check for address combined with location indicators
    city_value = str(record_data.get("city", "")).strip()
    state_value = str(record_data.get("state", "")).strip()
    postal_value = str(record_data.get("pin_code", "")).strip()
    
    if address_content and (city_value or state_value or postal_value or postal_code_pattern.search(address_content)):
        return True
    return False

def contains_individual_pii(record_data: Dict[str, Any]) -> bool:
    # Check for PII that qualifies as standalone identification
    # Check phone numbers in designated phone fields only
    for field_key in record_data:
        field_lower = field_key.lower()
        field_value = str(record_data[field_key])
        if field_lower in PHONE_RELATED_FIELDS and decimal_ten_pattern.search(field_value):
            return True
    
    # Check Aadhaar numbers
    for field_key in record_data:
        if field_key.lower() in AADHAAR_RELATED_FIELDS and decimal_twelve_pattern.search(str(record_data[field_key])):
            return True
    
    # Check passport numbers
    for field_key in record_data:
        if field_key.lower() in PASSPORT_RELATED_FIELDS and passport_pattern.search(str(record_data[field_key])):
            return True
    
    # Check UPI identifiers
    for field_key in record_data:
        if field_key.lower() in UPI_RELATED_FIELDS and upi_pattern.search(str(record_data[field_key])):
            return True
    
    return False

def count_combinatorial_elements(record_data: Dict[str, Any]) -> int:
    #Count the number of combinatorial PII elements present in record
    element_count = 0
    
    # Check for complete name presence
    has_complete_name = False
    if any(field_name in record_data and record_data[field_name] for field_name in FULL_NAME_FIELDS):
        if appears_as_complete_name(str(next(record_data[field_name] for field_name in FULL_NAME_FIELDS if field_name in record_data))):
            has_complete_name = True
    
    if GIVEN_NAME_FIELD in record_data and SURNAME_FIELD in record_data and record_data[GIVEN_NAME_FIELD] and record_data[SURNAME_FIELD]:
        has_complete_name = True
    
    if has_complete_name:
        element_count += 1
    
    # Check for email presence
    has_email_address = any(field_name in record_data and record_data[field_name] and email_pattern.search(str(record_data[field_name])) 
                           for field_name in EMAIL_RELATED_FIELDS)
    if has_email_address:
        element_count += 1
    
    # Check for complete physical address
    if contains_complete_address(record_data):
        element_count += 1
    
    # Check for device identifier with user context
    has_device_id = any(field_name in record_data and record_data[field_name] for field_name in HARDWARE_ID_FIELDS)
    has_user_context = has_complete_name or has_email_address or any(field_name in record_data for field_name in PHONE_RELATED_FIELDS)
    if has_device_id and has_user_context:
        element_count += 1
    
    # Check for IP address with user context
    has_ip_address = any(field_name in record_data and record_data[field_name] for field_name in NETWORK_IP_FIELDS)
    if has_ip_address and has_user_context:
        element_count += 1
    
    return element_count

def apply_redaction_rules(record_data: Dict[str, Any], is_sensitive_data: bool) -> Dict[str, Any]:
    #Apply appropriate redaction based on PII classification
    redacted_record = dict(record_data)
    
    # Apply standalone PII redactions unconditionally
    for field_key in list(redacted_record.keys()):
        field_value = redacted_record[field_key]
        if field_value is None:
            continue
        
        value_string = str(field_value)
        field_key_lower = field_key.lower()
        
        if field_key_lower in PHONE_RELATED_FIELDS and re.search(r"\d{10}", value_string):
            redacted_record[field_key] = obfuscate_phone_number(value_string)
        
        if field_key_lower in AADHAAR_RELATED_FIELDS and re.search(r"\d{12}", value_string):
            redacted_record[field_key] = obfuscate_aadhaar_number(value_string)
        
        if field_key_lower in PASSPORT_RELATED_FIELDS and passport_pattern.search(value_string):
            redacted_record[field_key] = obfuscate_passport_number(value_string)
        
        if field_key_lower in UPI_RELATED_FIELDS and upi_pattern.search(value_string):
            redacted_record[field_key] = obfuscate_upi_identifier(value_string)
    
    # Apply combinatorial redactions only when record qualifies as PII
    if is_sensitive_data and count_combinatorial_elements(record_data) >= 2:
        
        # Redact email addresses
        for field_name in EMAIL_RELATED_FIELDS:
            if field_name in redacted_record and redacted_record[field_name]:
                string_val = str(redacted_record[field_name])
                if email_pattern.search(string_val):
                    redacted_record[field_name] = obfuscate_email_address(string_val)
        
        # Redact complete names
        for field_name in FULL_NAME_FIELDS:
            if field_name in redacted_record and redacted_record[field_name] and appears_as_complete_name(str(redacted_record[field_name])):
                redacted_record[field_name] = obfuscate_personal_name(str(redacted_record[field_name]))
        
        # Redact first and last name combination
        if GIVEN_NAME_FIELD in redacted_record and SURNAME_FIELD in redacted_record and redacted_record[GIVEN_NAME_FIELD] and redacted_record[SURNAME_FIELD]:
            redacted_record[GIVEN_NAME_FIELD] = redacted_record[GIVEN_NAME_FIELD][0] + "X" * (len(str(redacted_record[GIVEN_NAME_FIELD])) - 1)
            redacted_record[SURNAME_FIELD] = redacted_record[SURNAME_FIELD][0] + "X" * (len(str(redacted_record[SURNAME_FIELD])) - 1)
        
        # Redact physical addresses
        for field_name in LOCATION_FIELDS:
            if field_name in redacted_record and redacted_record[field_name]:
                redacted_record[field_name] = obfuscate_physical_address(str(redacted_record[field_name]))
        
        # Redact IP addresses
        for field_name in NETWORK_IP_FIELDS:
            if field_name in redacted_record and redacted_record[field_name]:
                redacted_record[field_name] = obfuscate_ip_address(str(redacted_record[field_name]))
        
        # Redact device identifiers
        for field_name in HARDWARE_ID_FIELDS:
            if field_name in redacted_record and redacted_record[field_name]:
                redacted_record[field_name] = obfuscate_device_identifier(str(redacted_record[field_name]))
    
    return redacted_record

def execute_processing(input_csv_path: str, output_csv_path: str) -> None:
    # Main processing function for PII detection and redaction
    with open(input_csv_path, "r", encoding="utf-8") as input_file, open(output_csv_path, "w", encoding="utf-8", newline="") as output_file:
        csv_reader = csv.DictReader(input_file)
        csv_writer = csv.DictWriter(output_file, fieldnames=["record_id", "redacted_data_json", "is_pii"])
        csv_writer.writeheader()
        
        for data_row in csv_reader:
            record_identifier = str(data_row.get("record_id", ""))
            json_data_string = data_row.get("data_json") or data_row.get("Data_json") or data_row.get("Data_JSON")
            
            if not json_data_string:
                # Handle empty data with passthrough
                csv_writer.writerow({"record_id": record_identifier, "redacted_data_json": "{}", "is_pii": False})
                continue
            
            try:
                parsed_data = json.loads(json_data_string)
            except Exception:
                # Handle malformed JSON as non-PII passthrough
                csv_writer.writerow({"record_id": record_identifier, "redacted_data_json": json_data_string, "is_pii": False})
                continue

            # Determine PII classification
            is_sensitive_record = contains_individual_pii(parsed_data) or (count_combinatorial_elements(parsed_data) >= 2)

            # Apply appropriate redaction
            redacted_data = apply_redaction_rules(parsed_data, is_sensitive_record)
            
            csv_writer.writerow({
                "record_id": record_identifier,
                "redacted_data_json": json.dumps(redacted_data, ensure_ascii=False),
                "is_pii": bool(is_sensitive_record)
            })

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 detector_full_candidate_name.py iscp_pii_dataset.csv")
        sys.exit(1)
    
    input_csv_file = sys.argv[1]
    output_csv_file = "redacted_output_candidate_full_name.csv"
    
    execute_processing(input_csv_file, output_csv_file)
    print(f"OK: wrote {output_csv_file}")

if __name__ == "__main__":
    main()
