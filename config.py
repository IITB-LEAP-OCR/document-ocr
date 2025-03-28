layouts = {
    "Caption": "CAP",
    "Code": "COD",
    "Equation": "EQU",
    "Picture": "PIC",
    "Footer": "FTR",
    "Handwriting": "HWR",
    "Header": "HDR",
    "Image": "IMG",
    "List": "LST",
    "ListItem": "LTI",
    "ListGroup": "LTG",
    "PageNumber": "PNR",
    "PageFooter": "PFR",
    "SectionHeader": "SHD",
    "Table": "TBL",
    "Text": "TXT",
    "Title": "TTL"
}

PDF_NAME = "1_54"
INPUT_FILE = f"samples/{PDF_NAME}.pdf"

# OCR Config
LANGUAGES = "hi,en"
OUTPUT_FORMAT = "json"


# Output Config
OUTPUT_DIR = "1_page"
INPUT_JSON_FILE = f"{OUTPUT_DIR}/{PDF_NAME}/{PDF_NAME}.json"
OUTPUT_JSON_FILE = f"{OUTPUT_DIR}/{PDF_NAME}/{PDF_NAME}_extracted.json"
OUTPUT_IMAGE_DIR = f"{OUTPUT_DIR}/{PDF_NAME}/images"