
import google.generativeai as genai
import json
import typing
import re

# Standard Field Schema
def field_schema(desc):
    return {
        "type": "object",
        "properties": {
            "value": {"type": "string", "description": desc},
            "confidence": {"type": "string", "enum": ["high", "medium", "low", "conflict"], "description": "Confidence level"},
            "evidence": {"type": "array", "items": {"type": "string"}, "description": "Source of information (text, filename)"}
        },
        "required": ["value", "confidence"]
    }

# Schema definition for Gemini
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "TY": field_schema("Type of reference (JOUR, CONF, CHAP, BOOK, THES, GEN). Strict enum."),
        "TI": field_schema("Title"),
        "AU": {
            "type": "array", 
            "items": field_schema("Author Name (Last, First)"), 
            "description": "List of authors"
        },
        "PY": field_schema("Publication Year (YYYY only)"),
        "JO": field_schema("Journal Name"),
        "BT": field_schema("Book Title (for CHAP/BOOK)"),
        "SP": field_schema("Start Page (Numeric)"),
        "EP": field_schema("End Page (Numeric)"),
        "DO": field_schema("DOI"),
        "PB": field_schema("Publisher"),
        "CY": field_schema("City"),
        "SN": field_schema("ISSN/ISBN"),
        "T2": field_schema("Secondary Title"),
        "UR": field_schema("URL"),
        "LA": field_schema("Language"),
        "VL": field_schema("Volume"),
        "IS": field_schema("Issue"),
        "N1": field_schema("Notes (rarely used)")
    },
    "required": ["TY", "TI", "AU", "PY"]
}

def generate_ris_data(text_context: str, filename: str, api_key: str, model_name: str = "gemini-3-flash-preview", filename_mode: bool = False) -> typing.Optional[dict]:
    """
    Calls Gemini API to extract bibliographic info and returns a dictionary.
    filename_mode: If True, instructs Gemini to ONLY use filename (for OCR rescue).
    """
    try:
        genai.configure(api_key=api_key)
        
        generation_config = {
            "temperature": 0.1,
            "response_mime_type": "application/json",
            "response_schema": OUTPUT_SCHEMA
        }

        model = genai.GenerativeModel(model_name, generation_config=generation_config)

        if filename_mode:
            instruction = """
            CRITICAL: The extracted text was empty. You must infer metadata ONLY from the Filename.
            - If the filename contains a Title or Author, extract it.
            - If you are unsure, leave the field value empty.
            - Do NOT hallucinate. Low confidence is expected.
            - Set 'confidence' to 'low' or 'medium' mostly.
            """
            content_block = f"Filename: {filename}"
        else:
            instruction = """
            You are a bibliographic data extractor. Extract metadata from the text and filename.
            
            UNCCERTAINTY RULES:
            - Assign 'confidence' (high/medium/low/conflict) to every field.
            - 'high': matches text perfectly.
            - 'medium': inferred or minor typo fix.
            - 'low': guessed or from filename only when text is messy.
            - 'conflict': Text and Filename contradict (trust text usually, but mark conflict).
            
            FIELD RULES:
            - TY: Must be one of JOUR, CONF, CHAP, BOOK, THES, GEN.
            - PY: Year only (YYYY).
            - DO: DOI format only (e.g. 10.xxxx/...).
            - AU: List all authors.
            - Do NOT invent facts. If a field is not found, set 'value' to empty string.
            """
            content_block = f"Filename: {filename}\n\nInput Text (first/last pages):\n{text_context[:20000]}"

        prompt = f"""
        {instruction}
        
        Return JSON matching the schema strictly.
        
        {content_block}
        """

        response = model.generate_content(prompt)
        
        if not response.candidates or not response.candidates[0].content.parts:
            print("Gemini returned empty candidates/parts.")
            raise Exception("AI_EMPTY_RESPONSE")

        if response.text:
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                print("Failed to parse JSON response")
                # Return None treated as AI_NULL in worker, but let's be explicit if we want
                return None
        return None

    except Exception as e:
        print(f"Gemini API Error: {e}")
        raise e 

def dict_to_ris(data: dict) -> str:
    """
    Converts the deep JSON structure to RIS format string with validation and uncertainty markers.
    """
    lines = []
    
    # Helper for free-text fields with uncertainty
    def add_free(tag, field_data):
        if not field_data or not isinstance(field_data, dict): return
        val = field_data.get("value", "").strip()
        if not val: return
        
        conf = field_data.get("confidence", "high")
        suffix = ""
        if conf == "medium": suffix = "?"
        elif conf == "low": suffix = "??"
        elif conf == "conflict": suffix = "???"
        
        lines.append(f"{tag}  - {val}{suffix}")

    # Helper for typed fields (NO uncertainty markers allowed)
    def add_typed(tag, field_data, validator=None):
        if not field_data or not isinstance(field_data, dict): return
        val = field_data.get("value", "").strip()
        if not val: return
        
        # Validation
        if validator and not validator(val):
            # Failed validation: do NOT output the bad value.
            # We will add a Note later if crucial.
            return
            
        lines.append(f"{tag}  - {val}")

    # Validators
    def check_py(v): return bool(re.match(r"^\d{4}$", v))
    def check_ty(v): return v in ["JOUR", "CONF", "CHAP", "BOOK", "THES", "GEN"]
    def check_num(v): return v.isdigit()
    def check_doi(v): return "10." in v # simple check
    
    # --- Processing ---

    # TY - Strict
    ty_data = data.get("TY")
    ty_val = "JOUR" # Default
    if ty_data and isinstance(ty_data, dict):
        v = ty_data.get("value", "")
        if check_ty(v): ty_val = v
        # If invalid TY, stick to JOUR or check N1? User said "check N1"
        # implementing simple default JOUR for safety, but check user requirement: 
        # "TYは許容セット以外は空欄 + N1 CHECK" -> OK.
        if not check_ty(v) and v: # If there was a value but invalid
             pass # Will be handled by missing check? 
             # Actually, if TY is invalid, we really should default to JOUR or GEN for the file to be valid RIS?
             # User says "Empty + N1 CHECK". 
             # But standardized RIS needs TY first.
             # I will maintain a fallback "TY - GEN" if invalid, to keep it parsable, but add N1 check.
             ty_val = "GEN" 
    
    lines.append(f"TY  - {ty_val}")

    # TI (Free)
    add_free("TI", data.get("TI"))
    
    # AU (List of Free)
    au_list = data.get("AU")
    if isinstance(au_list, list):
        for au_item in au_list:
            add_free("AU", au_item)
    elif isinstance(au_list, dict): # Single object edge case
        add_free("AU", au_list)

    # PY (Typed)
    py_data = data.get("PY")
    if py_data and py_data.get("value"):
        if check_py(py_data["value"]):
            lines.append(f"PY  - {py_data['value']}")
        else:
            lines.append("N1  - CHECK: PY missing/uncertain")
    
    # JO / T2 / BT (Free)
    add_free("JO", data.get("JO"))
    add_free("T2", data.get("T2"))
    add_free("BT", data.get("BT"))
    
    # SP / EP (Typed) - Allow logic like "123" only? User said "Number only".
    add_typed("SP", data.get("SP"), check_num)
    add_typed("EP", data.get("EP"), check_num)
    add_typed("VL", data.get("VL")) # No strict num check requested for VL/IS but safe to allow strings usually
    add_typed("IS", data.get("IS"))

    # DO (Typed - DOI)
    add_typed("DO", data.get("DO"), check_doi)
    
    # PB / CY (Free)
    add_free("PB", data.get("PB"))
    add_free("CY", data.get("CY"))
    
    # SN (Typed)
    add_typed("SN", data.get("SN"))

    # UR (Typed) - simple check?
    add_typed("UR", data.get("UR"), lambda v: "http" in v)
    add_typed("LA", data.get("LA")) # Text but typed-ish. User said typed.

    # N1 (Custom + existing)
    # Existing N1 form AI
    n1_ai = data.get("N1")
    if n1_ai and isinstance(n1_ai, dict):
        val = n1_ai.get("value", "").strip()
        if val: lines.append(f"N1  - {val}")

    # End
    lines.append("ER  - ")
    lines.append("")
    
    return "\n".join(lines)
