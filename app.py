from __future__ import annotations

import csv
import dataclasses
import importlib
import os
import re
import tempfile
import threading
import traceback
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, filedialog, messagebox, ttk
import tkinter as tk


APP_TITLE = "D Analytical Credit Form - Python OCR"

BUSINESS_FIELDS = [
    ("businessName", "Business Legal Name"),
    ("businessDbaName", "Business DBA Name"),
    ("businessAddress", "Business Address"),
    ("businessState", "State"),
    ("businessCity", "City"),
    ("businessZip", "Zip"),
    ("businessPhone", "Business Phone Number"),
    ("businessEmail", "Business Gmail"),
    ("einNumber", "Tax ID (TIN #)"),
]

OWNER_FIELDS = [
    ("ownerName", "Owner Name"),
    ("ownerDob", "Owner DOB"),
    ("ownerAddress", "Home Address"),
    ("ownerState", "State"),
    ("ownerCity", "City"),
    ("ownerZip", "Zip"),
    ("ssn", "SSN#"),
]

OWNER2_FIELDS = [
    ("owner2Name", "2nd Owner Name"),
    ("owner2Dob", "2nd Owner DOB"),
    ("owner2Address", "2nd Owner Home Address"),
    ("owner2State", "2nd Owner State"),
    ("owner2City", "2nd Owner City"),
    ("owner2Zip", "2nd Owner Zip"),
    ("owner2Ssn", "2nd Owner SSN#"),
]

OWNER3_FIELDS = [
    ("owner3Name", "3rd Owner Name"),
    ("owner3Dob", "3rd Owner DOB"),
    ("owner3Address", "3rd Owner Home Address"),
    ("owner3State", "3rd Owner State"),
    ("owner3City", "3rd Owner City"),
    ("owner3Zip", "3rd Owner Zip"),
    ("owner3Ssn", "3rd Owner SSN#"),
]

OWNER4_FIELDS = [
    ("owner4Name", "4th Owner Name"),
    ("owner4Dob", "4th Owner DOB"),
    ("owner4Address", "4th Owner Home Address"),
    ("owner4State", "4th Owner State"),
    ("owner4City", "4th Owner City"),
    ("owner4Zip", "4th Owner Zip"),
    ("owner4Ssn", "4th Owner SSN#"),
]

FIELD_GROUPS = [
    ("Business Information", BUSINESS_FIELDS),
    ("Owner 1 Information", OWNER_FIELDS),
    ("2nd Owner Information", OWNER2_FIELDS),
    ("3rd Owner Information", OWNER3_FIELDS),
    ("4th Owner Information", OWNER4_FIELDS),
]

ALL_FIELDS = [item for _, fields in FIELD_GROUPS for item in fields]
FIXED_BUSINESS_CONTACT = {
    "businessPhone": "6468459754",
    "businessEmail": "contracts@tvtcapital.com",
}
FIXED_CONTACT_KEYS = set(FIXED_BUSINESS_CONTACT)

OCR_MODES = ["Text PDF", "Image", "Handwriting"]

SENSITIVE_KEYS = {"einNumber", "ssn", "owner2Ssn", "owner3Ssn", "owner4Ssn"}
DATE_KEYS = {"ownerDob", "owner2Dob", "owner3Dob", "owner4Dob"}
ZIP_KEYS = {"businessZip", "ownerZip", "owner2Zip", "owner3Zip", "owner4Zip"}
PHONE_KEYS = {"businessPhone"}
EMAIL_KEYS = {"businessEmail"}
STATE_KEYS = {"businessState", "ownerState", "owner2State", "owner3State", "owner4State"}

STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "IA", "ID",
    "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT",
    "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY", "DC",
}

STATE_NAME_CODES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX",
    "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
}


def clean_output(value: object) -> str:
    return re.sub(r"^[\s:.\-]+|[\s:.\-]+$", "", re.sub(r"\s+([,.:;])", r"\1", re.sub(r"\s+", " ", str(value or "")))).strip()


def clean_row(value: object) -> str:
    return re.sub(r"^[\s.\-]+|[\s.\-]+$", "", re.sub(r"\s+([,.:;])", r"\1", re.sub(r"\s+", " ", str(value or "")))).strip()


def normalize_text(text: str) -> str:
    return (
        str(text or "")
        .replace("\u00a0", " ")
        .replace("|", " ")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(label or "").lower())).strip()


def numeric_ocr_cleanup(value: str) -> str:
    table = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5"})
    return str(value or "").translate(table)


def format_ein(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))[:9]
    return digits if len(digits) <= 2 else f"{digits[:2]}-{digits[2:]}"


def normalize_state_code(value: str) -> str:
    raw = clean_output(value).upper().replace("FI", "FL").replace("F1", "FL")
    raw = re.sub(r"[^A-Z ]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if raw in STATE_CODES:
        return raw
    match = re.search(r"\b[A-Z]{2}\b", raw)
    if match and match.group(0) in STATE_CODES:
        return match.group(0)
    return STATE_NAME_CODES.get(raw, clean_output(value))


def clean_sensitive_number(value: str, key: str = "") -> str:
    text = numeric_ocr_cleanup(clean_output(value))
    match = re.search(r"\b(\d{3}-\d{2}-\d{4}|\d{2}-\d{7}|\d{9})\b", text)
    if not match:
        digits = re.sub(r"\D", "", text)
        match_value = digits if len(digits) == 9 else ""
    else:
        match_value = re.sub(r"\D", "", match.group(1))
    if not match_value:
        return ""
    return f"{match_value[:2]}-{match_value[2:]}" if key == "einNumber" else match_value


def clean_phone_number(value: str) -> str:
    text = clean_output(value)
    match = re.search(r"\+?\(?\d[\d\s().-]{6,}\d", text)
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else re.sub(r"[^\d+(). -]", "", text).strip()


def clean_email(value: str) -> str:
    match = re.search(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", clean_output(value), re.I)
    return match.group(0) if match else clean_output(value)


def clean_value_for_key(key: str, value: str) -> str:
    if key in FIXED_CONTACT_KEYS:
        return FIXED_BUSINESS_CONTACT[key]
    cleaned = clean_output(value)
    cleaned = re.sub(r"\s+(Business DBA Name|DBA Name|Owner Information|Owner\(s\)|Apt\s*/\s*Suite\s*/\s*Floor)$", "", cleaned, flags=re.I).strip()
    if len(cleaned) > 150 or re.match(r"By signing|Each of the above|You authorize", cleaned, re.I):
        return ""
    if re.match(r"^(Apt\s*/\s*Suite\s*/\s*Floor|Ownership Percent|Entity Type|Legal Entity|Industry|Started Date)$", cleaned, re.I):
        return ""
    if key in SENSITIVE_KEYS:
        return clean_sensitive_number(cleaned, key)
    if key in PHONE_KEYS:
        return clean_phone_number(cleaned)
    if key in EMAIL_KEYS:
        return clean_email(cleaned)
    if key in STATE_KEYS:
        return normalize_state_code(cleaned)
    if key in ZIP_KEYS:
        match = re.search(r"\b\d{5}(?:-\d{4})?\b", cleaned)
        return match.group(0) if match else ""
    if key in DATE_KEYS:
        text = numeric_ocr_cleanup(cleaned).replace(".", "/").replace("-", "/")
        match = re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)
        return match.group(0) if match else cleaned
    return cleaned


def previous_month_name() -> str:
    names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    today = date.today()
    return names[(today.month + 10) % 12]


def normalize_revenue_month(value: str) -> str:
    aliases = {
        "jan": "January", "january": "January", "feb": "February", "february": "February",
        "febuary": "February", "mar": "March", "march": "March", "apr": "April",
        "april": "April", "may": "May", "jun": "June", "june": "June", "jul": "July",
        "july": "July", "aug": "August", "august": "August", "sep": "September",
        "sept": "September", "september": "September", "oct": "October",
        "october": "October", "nov": "November", "november": "November", "dec": "December",
        "december": "December",
    }
    key = re.sub(r"[^a-z]", "", str(value or "").lower())
    return aliases.get(key, "")


def parse_pricing_scrub(text: str) -> dict[str, str]:
    normalized = str(text or "").replace("\r", "\n")
    lines = [clean_output(line) for line in normalized.splitlines() if clean_output(line)]
    tier = lines[0] if lines else ""
    tier = re.split(r"\bDeposits?(?:\s*\([^)]*\))?\s*:", tier, maxsplit=1, flags=re.I)[0]
    if re.search(r"^(Deposits|Industry|TIB|State|Datamerch|Company\s+Website|Proceed)\b", tier, re.I):
        tier = ""

    def read(pattern: str) -> str:
        match = re.search(pattern, normalized, re.I)
        return clean_output(match.group(1)) if match else ""

    deposits_match = re.search(r"\bDeposits?(?:\s*\(([^)]*)\))?\s*:\s*(.*?)(?:,\s*Industry\s*:|\n|\r|$)", normalized, re.I)
    website = read(r"Company\s+Website\s*:\s*([^\n\r]*)")
    return {
        "tier": clean_output(tier),
        "deposits": clean_output(deposits_match.group(2)) if deposits_match else "",
        "revenueMonth": normalize_revenue_month(deposits_match.group(1) if deposits_match else "") or previous_month_name(),
        "industry": read(r"Industry\s*:\s*([^,\n\r]*)"),
        "tib": read(r"\bTIB\s*:\s*([^,\n\r]*)"),
        "state": read(r"\bState\s*:\s*([^,\n\r]*)"),
        "website": website if website and not re.search(r"^not\s+found$", website, re.I) else "Not Found",
    }


def google_search_line(name: str, state_value: str) -> str:
    name = clean_output(name)
    if not name:
        return ""
    query = clean_output(f"{name} {normalize_state_code(state_value)}")
    return f"{query} Google Search"


@dataclasses.dataclass
class ExtractedState:
    values: dict[str, str] = dataclasses.field(default_factory=lambda: {key: "" for key, _ in ALL_FIELDS})
    low_confidence: dict[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        self.values.update(FIXED_BUSINESS_CONTACT)

    def save(self, key: str, value: str, force: bool = False, low: str = "") -> bool:
        if not key:
            return False
        if key in FIXED_CONTACT_KEYS:
            self.values[key] = FIXED_BUSINESS_CONTACT[key]
            self.low_confidence.pop(key, None)
            return True
        cleaned = clean_value_for_key(key, value)
        if not cleaned or looks_like_only_labels(cleaned):
            return False
        if self.values.get(key) and not force:
            return False
        self.values[key] = cleaned
        if low:
            self.low_confidence[key] = low
        elif key in self.low_confidence:
            del self.low_confidence[key]
        return True


BLANK_LABELS = {
    "business dba name", "dba name", "dba", "business legal name", "legal company name",
    "company name", "full name", "owner name", "primary owner name", "date of birth",
    "owner dob", "dob", "home address", "owner address", "business address",
    "city state zip", "city", "state", "zip", "zip code", "ssn", "social security",
    "tax id", "tin", "ein", "phone", "phone number", "email", "gmail",
    "apt suite floor", "ownership percent", "entity type", "legal entity", "industry",
    "started date",
}


def looks_like_only_labels(value: str) -> bool:
    normalized = normalize_label(value)
    compact = normalized.replace(" ", "")
    if not normalized or normalized in BLANK_LABELS:
        return True
    if re.search(r"^(2nd|second|3rd|third|4th|fourth)\s+owner\s+(name|dob|address|ssn)$", normalized):
        return True
    return compact in {"businesslegalname", "businessdbaname", "homeaddress", "zipcode"}


def owner_prefix(number: int) -> str:
    return "owner" if number == 1 else f"owner{number}"


def owner_ssn_key(number: int) -> str:
    return "ssn" if number == 1 else f"owner{number}Ssn"


def section_from_line(line: str, current: str) -> str:
    text = normalize_label(line)
    if re.search(r"\b(4th|fourth|owner 4|owner4|owner information 4)\b", text):
        return "owner4"
    if re.search(r"\b(3rd|third|owner 3|owner3|owner information 3)\b", text):
        return "owner3"
    if re.search(r"\b(2nd|second|owner 2|owner2|owner information 2)\b", text):
        return "owner2"
    if re.search(r"\b(1st|first|owner 1|owner1|owner information 1|owner|principal|guarantor|officer|member)\b", text):
        return "owner"
    if re.search(r"\b(company information|business information|merchant information|applicant information)\b", text):
        return "business"
    if ":" in str(line or "") and current.startswith("owner"):
        return current
    if re.search(r"\b(business|merchant|company|applicant)\b", text):
        return "business"
    return current


def key_for_label(label: str, section: str) -> str:
    text = normalize_label(label)
    compact = text.replace(" ", "")
    owner_number = 0
    if section.startswith("owner"):
        owner_number = 1 if section == "owner" else int(section[-1])
    if re.search(r"\b(4th|fourth|owner 4|4 owner)\b", text):
        owner_number = 4
    elif re.search(r"\b(3rd|third|owner 3|3 owner)\b", text):
        owner_number = 3
    elif re.search(r"\b(2nd|second|owner 2|2 owner)\b", text):
        owner_number = 2
    elif re.search(r"\b(owner|principal|guarantor|member|officer)\b", text):
        owner_number = 1
    prefix = owner_prefix(owner_number or 1)

    if any(skip in text for skip in [
        "state of incorporation", "legal entity", "company type industry", "business inception",
        "annual income", "annual business revenue", "average bank balance", "monthly credit card volume",
        "cash amount requested", "desired pay term", "rent or own", "landlord", "outstanding merchant",
        "separate business bank account", "accepted credit cards", "business ownership", "home phone",
        "cell phone", "email", "ownership percent", "apt suite floor", "entity type", "started date",
    ]) and not re.fullmatch(r"(business\s+email|business\s+gmail|email\s+address)", text):
        return ""
    if ("dba" in text or "doing business" in text or "trade name" in text) and not owner_number:
        return "businessDbaName"
    if text == "business owner":
        return "ownerName"
    if ("business" in text or "merchant" in text or "company" in text or "legal" in text) and "name" in text and not owner_number:
        return "businessName"
    if "businesslegalname" in compact:
        return "businessName"
    if "businessdbaname" in compact:
        return "businessDbaName"
    if re.search(r"\b(ein|fein|tin|tax id|federal tax|taxpayer)\b", text):
        return "einNumber"
    if re.search(r"\b(ssn|s sn|social security|ssi)\b", text):
        return owner_ssn_key(owner_number or 1)
    if re.search(r"\b(dob|date of birth|birth date|d o b)\b", text):
        return f"{prefix}Dob" if owner_number else "ownerDob"
    if "address" in text or "street" in text or "physical" in text or "residential" in text:
        return f"{prefix}Address" if owner_number else "businessAddress"
    if re.fullmatch(r".*(city).*", text):
        return f"{prefix}City" if owner_number else "businessCity"
    if re.fullmatch(r".*(state|sate).*", text):
        return f"{prefix}State" if owner_number else "businessState"
    if "zip" in text or "postal" in text:
        return f"{prefix}Zip" if owner_number else "businessZip"
    if ("phone" in text or "mobile" in text or "telephone" in text or "contact" in text) and not owner_number:
        return "businessPhone"
    if ("email" in text or "mail" in text or "gmail" in text) and not owner_number:
        return "businessEmail"
    if "name" in text:
        return f"{prefix}Name" if owner_number else "businessName"
    return ""


FIELD_LABELS = [
    "Business Legal Name", "Legal Business Name", "Business DBA Name", "Legal Company Name", "Company Name",
    "Legal Company", "Merchant Legal Name", "Merchant Name", "Business Owner", "DBA Name", "DBA", "Doing Business As (DBA)",
    "Doing Business As", "Business Address", "Physical Address (no PO Boxes)", "Physical Address",
    "Company Address", "Merchant Address",
    "Street Address", "City", "State", "Zip Code", "Zip", "Business Phone Number",
    "Business Phone", "Company Phone", "Merchant Phone", "Business Email",
    "Business Gmail", "Email Address", "Federal Tax ID", "Tax ID", "TIN", "EIN",
    "FEIN", "Employer Identification Number", "Owner Name", "Full Name",
    "Principal Name", "Guarantor Name", "Primary Owner", "First name", "Last name", "MI",
    "2nd Owner Name",
    "Second Owner Name", "3rd Owner Name", "Third Owner Name", "4th Owner Name",
    "Fourth Owner Name", "Owner DOB", "Date of Birth", "DOB", "Birth Date",
    "Owner Address", "Home address (no PO Boxes)", "Home Address", "Residential Address",
    "SSN", "SSN#", "SSN Number", "SSI Number",
    "Social Security Number", "2nd Owner SSN", "3rd Owner SSN", "4th Owner SSN",
    "City State Zip", "City/State/ZIP", "City, State Zip",
    "State of Incorporation", "Legal Entity", "Entity Type", "Company Type / Industry", "Business Inception Date",
    "Annual income", "Annual business revenue", "Average bank balance", "Monthly credit card volume",
    "Cash amount requested", "Desired pay term", "Rent or own", "Landlord name", "Landlord phone",
    "Business ownership %", "Ownership Percent", "Apt / Suite / Floor", "Started Date", "Industry",
]

FIELD_LABEL_PATTERN = "|".join(re.escape(label).replace(r"\ ", r"\s+") for label in sorted(FIELD_LABELS, key=len, reverse=True))
GENERIC_LABEL_ROW = re.compile(r"^[A-Za-z][A-Za-z0-9\s/#%().,&-]{1,70}:\s*$")
GENERIC_LABEL_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9\s/#%().,&-]{1,70}:")


def rows_from_text(text: str) -> list[str]:
    normalized = normalize_text(text).replace("\r", "\n")
    rows = [clean_row(line) for line in normalized.splitlines() if clean_row(line)]
    if len(rows) > 1:
        return rows
    synthetic = re.sub(
        r"\s+(?=(Business|Company|Legal|DBA|City|State|Zip|Tax|EIN|Full|Date|Home|SSN|Phone|Email|Owner|2nd|3rd|4th)\b)",
        "\n",
        normalized,
        flags=re.I,
    )
    return [clean_row(line) for line in synthetic.splitlines() if clean_row(line)]


def value_after_label(source: str, label_regex: str, stop_regex: str = r"$") -> str:
    match = re.search(label_regex, source, re.I)
    if not match:
        return ""
    value = source[match.end():]
    stop = re.search(stop_regex, value, re.I)
    if stop:
        value = value[: stop.start()]
    return clean_output(value)


def parse_city_state_zip(state: ExtractedState, target: str, value: str, force: bool = False) -> bool:
    text = clean_output(value)
    patterns = [
        r"^(.+?),\s*([A-Za-z .'\-]+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
        r"^(.+?),\s*([A-Za-z .'\-]+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
        r"^(.+?),\s*([A-Za-z .'\-]+?),\s*([A-Za-z ]+),\s*(\d{5}(?:-\d{4})?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            state.save(f"{target}Address", match.group(1), force=force)
            state.save(f"{target}City", match.group(2), force=force)
            state.save(f"{target}State", normalize_state_code(match.group(3)), force=force)
            state.save(f"{target}Zip", match.group(4), force=force)
            return True
    match = re.search(r"^([A-Za-z .'\-]+?)[,\s]+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$", text, re.I)
    if match:
        state.save(f"{target}City", match.group(1), force=force)
        state.save(f"{target}State", match.group(2), force=force)
        state.save(f"{target}Zip", match.group(3), force=force)
        return True
    return False


def parse_address_block(state: ExtractedState, target: str, value: str, force: bool = False) -> None:
    lines = [clean_output(line) for line in str(value or "").split("\n") if clean_output(line)]
    if not lines:
        return
    if len(lines) == 1:
        if not parse_city_state_zip(state, target, lines[0], force=force):
            state.save(f"{target}Address", lines[0], force=force)
        return

    state.save(f"{target}Address", lines[0], force=force)
    location = clean_output(" ".join(lines[1:]))
    location = re.sub(r",\s*", ", ", location)
    match = re.search(r"^([A-Za-z .'\-]+),?\s+([A-Za-z]{2,}|[A-Z]{2}),?\s+(\d{5}(?:-\d{4})?)$", location, re.I)
    if match:
        state.save(f"{target}City", match.group(1), force=force)
        state.save(f"{target}State", normalize_state_code(match.group(2)), force=force)
        state.save(f"{target}Zip", match.group(3), force=force)
        return
    parse_city_state_zip(state, target, clean_output(f"{lines[0]}, {location}"), force=force)


def apply_single_line_address(state: ExtractedState, target: str, value: str, force: bool = False) -> None:
    text = clean_output(value)
    match = re.search(r"^(.+?)\s+([A-Za-z .'-]+),?\s+([A-Z]{2}|[A-Za-z ]+)\s+(\d{5}(?:-\d{4})?)$", text, re.I)
    if match:
        state.save(f"{target}Address", match.group(1), force=force)
        state.save(f"{target}City", match.group(2), force=force)
        state.save(f"{target}State", normalize_state_code(match.group(3)), force=force)
        state.save(f"{target}Zip", match.group(4), force=force)
        return
    match = re.search(r"^(.+?)\s+([A-Z]{2}|[A-Za-z ]+)\s+(\d{5}(?:-\d{4})?)$", text, re.I)
    if match:
        state.save(f"{target}Address", match.group(1), force=force)
        state.save(f"{target}State", normalize_state_code(match.group(2)), force=force)
        state.save(f"{target}Zip", match.group(3), force=force)
        return
    state.save(f"{target}Address", text, force=force)


def owner_number_from_section(section: str) -> int:
    if section == "owner4":
        return 4
    if section == "owner3":
        return 3
    if section == "owner2":
        return 2
    if section == "owner":
        return 1
    return 0


def save_label_value(state: ExtractedState, label: str, value: str, section: str, force: bool = False) -> None:
    normalized = normalize_label(label)
    owner_number = owner_number_from_section(section)
    if normalized == "business owner":
        owner_number = 1
    if re.search(r"\b(4th|fourth|owner 4)\b", normalized):
        owner_number = 4
    elif re.search(r"\b(3rd|third|owner 3)\b", normalized):
        owner_number = 3
    elif re.search(r"\b(2nd|second|owner 2)\b", normalized):
        owner_number = 2
    elif "owner" in normalized or normalized in {"first name", "last name", "mi"}:
        owner_number = owner_number or 1
    prefix = owner_prefix(owner_number or 1)

    if normalized == "mi":
        return
    if normalized == "first name" and owner_number:
        first = clean_value_for_key(f"{prefix}Name", value)
        if first and not looks_like_only_labels(first):
            existing = state.values.get(f"{prefix}Name", "")
            if not existing or force:
                state.values[f"{prefix}Name"] = first
        return
    if normalized == "last name" and owner_number:
        last = clean_value_for_key(f"{prefix}Name", value)
        if last and not looks_like_only_labels(last):
            existing = state.values.get(f"{prefix}Name", "")
            if existing and last.lower() not in existing.lower().split():
                state.values[f"{prefix}Name"] = clean_output(f"{existing} {last}")
            elif not existing or force:
                state.values[f"{prefix}Name"] = last
        return

    key = key_for_label(label, section)
    if not key:
        return
    if re.search(r"city\s*[/,]?\s*state\s*[/,]?\s*zip", normalized, re.I):
        parse_city_state_zip(state, "owner" if section == "owner" else section, value, force=force)
        return
    if key.endswith("Address"):
        target = key[:-7]
        parse_address_block(state, target, value, force=force)
        return
    state.save(key, value, force=force)


def parse_inline_labels(state: ExtractedState, row: str, section: str) -> None:
    matches = list(re.finditer(rf"\b({FIELD_LABEL_PATTERN})\s*:", row, re.I))
    if not matches:
        return
    for index, match in enumerate(matches):
        label = match.group(1)
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(row)
        value = clean_output(row[value_start:value_end])
        save_label_value(state, label, value, section)


def parse_next_line_labels(state: ExtractedState, rows: list[str]) -> None:
    section = "business"
    label_only = re.compile(rf"^\s*({FIELD_LABEL_PATTERN})\s*:\s*$", re.I)
    for index, row in enumerate(rows[:-1]):
        section = section_from_line(row, section)
        match = label_only.match(row)
        if not match:
            continue
        next_row = rows[index + 1]
        if (
            label_only.match(next_row)
            or GENERIC_LABEL_ROW.match(next_row)
            or GENERIC_LABEL_PREFIX.match(next_row)
            or len(next_row) > 120
            or re.match(r"By signing|Each of the above|You authorize", next_row, re.I)
        ):
            continue
        save_label_value(state, match.group(1), next_row, section)


def parse_label_blocks(state: ExtractedState, rows: list[str]) -> None:
    section = "business"
    label_row = re.compile(rf"^\s*({FIELD_LABEL_PATTERN})\s*:\s*(.*?)\s*$", re.I)
    index = 0
    while index < len(rows):
        row = rows[index]
        section = section_from_line(row, section)
        match = label_row.match(row)
        if not match:
            index += 1
            continue

        label = match.group(1)
        inline_value = clean_output(match.group(2))
        value_lines: list[str] = [inline_value] if inline_value else []
        next_index = index + 1
        while next_index < len(rows):
            next_row = rows[next_index]
            if label_row.match(next_row) or GENERIC_LABEL_PREFIX.match(next_row):
                break
            if re.match(r"^(Business Information|Owner Information|2nd Owner Information|Verification|By signing)", next_row, re.I):
                break
            if clean_output(next_row):
                value_lines.append(clean_output(next_row))
            next_index += 1

        value = "\n".join(value_lines).strip()
        if value:
            save_label_value(state, label, value, section)
        index = max(next_index, index + 1)


def apply_regex_fallbacks(state: ExtractedState, text: str, rows: list[str]) -> None:
    flat = clean_output(normalize_text(text).replace("\n", " "))
    low_note = "Fallback regex match - please verify."
    email = re.search(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", flat, re.I)
    if email:
        state.save("businessEmail", email.group(0), low=low_note)
    phone = re.search(r"(?:Business|Company|Merchant|Office|Work|Phone|Telephone|Contact)[^A-Z0-9]{0,15}(\+?1?[\s.\-]?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})", flat, re.I)
    if phone:
        state.save("businessPhone", phone.group(1), low=low_note)
    ein = re.search(r"(?:EIN|FEIN|TIN|Federal\s+Tax\s+ID|Tax\s+ID|Taxpayer\s+ID)\s*#?\s*:?\s*(\d{2}-?\d{7})", numeric_ocr_cleanup(flat), re.I)
    if ein:
        state.save("einNumber", ein.group(1), low="Tax ID matched after OCR cleanup - please verify.")

    section = "business"
    for row in rows:
        section = section_from_line(row, section)
        target = "owner" if section == "owner" else section
        if target != "business":
            dob = re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", numeric_ocr_cleanup(row))
            ssn = re.search(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b", numeric_ocr_cleanup(row))
            if re.search(r"(dob|birth)", row, re.I) and dob:
                state.save(f"{target}Dob", dob.group(0), low=low_note)
            if re.search(r"(ssn|social)", row, re.I) and ssn:
                state.save(owner_ssn_key(1 if target == "owner" else int(target[-1])), ssn.group(0), low=low_note)
        parse_city_state_zip(state, target, row)


def apply_flat_patterns(state: ExtractedState, text: str) -> None:
    flat = clean_output(normalize_text(text).replace("\n", " "))

    def grab(label: str, stops: str) -> str:
        return value_after_label(flat, label, stops)

    business_stop = (
        r"Business\s+DBA\s+Name|DBA\s+Name|Address|City\s*:|State\s*:|Zip|"
        r"Federal\s+Tax|Tax\s*ID|TIN|EIN|Owner|Principal|Guarantor|Phone|Email|$"
    )
    state.save("businessName", grab(r"Business\s+Legal\s+Name\s*:?\s*", business_stop))
    state.save("businessName", grab(r"Legal\s+Company\s+Name\s*:?\s*", business_stop), force=False)
    state.save("businessDbaName", grab(r"(?:Business\s+)?DBA\s+Name\s*:?\s*", r"Entity\s+Type|Legal\s+Entity|Industry|Started\s+Date|Business\s+Address|Physical\s+Address|Company\s+Address|Merchant\s+Address|Address|City\s*:|State\s*:|Zip|Tax|EIN|Owner|Principal|$"))
    state.save("businessAddress", grab(r"(?:Business|Physical|Company|Merchant)\s+Address\s*:?\s*", r"City\s*:|State\s*:|Zip|Phone|Tax|EIN|Owner|Principal|$"))
    state.save("businessCity", grab(r"\bCity\s*:?\s*", r"State\s*:|Zip|Phone|Email|Tax|Owner|$"))
    state.save("businessState", grab(r"\bState\s*:?\s*", r"Zip|Phone|Email|Tax|Owner|$"))
    state.save("businessZip", grab(r"\bZip(?:\s+Code)?\s*:?\s*", r"Phone|Email|Tax|Owner|$"))
    state.save("businessPhone", grab(r"Business\s+(?:Phone|Mobile|Contact\s+Number)\s*:?\s*", r"Business\s+(?:Email|Gmail|E-?mail)|Tax|EIN|Owner|$"))
    state.save("businessEmail", grab(r"Business\s+(?:Email|Gmail|E-?mail)\s*:?\s*", r"Tax|EIN|Owner|$"))
    state.save("einNumber", grab(r"(?:Tax\s*ID|TIN|EIN|Federal\s+Tax\s+ID)\s*#?\s*:?\s*", r"Owner|Principal|Guarantor|Business\s+Start|$"))

    owner_markers = [
        (1, r"(Owner\s+1\s+Information|Principal\s+Owner|Owner\s+Information|Primary\s+Owner|Owner\s+Name)"),
        (2, r"(Owner\s+2\s+Information|2nd\s+Owner|Second\s+Owner)"),
        (3, r"(Owner\s+3\s+Information|3rd\s+Owner|Third\s+Owner)"),
        (4, r"(Owner\s+4\s+Information|4th\s+Owner|Fourth\s+Owner)"),
    ]
    for number, marker in owner_markers:
        start = re.search(marker, flat, re.I)
        if not start and number > 1:
            continue
        end = len(flat)
        for next_number, next_marker in owner_markers:
            if next_number <= number:
                continue
            next_start = re.search(next_marker, flat[start.end() if start else 0 :], re.I)
            if next_start:
                end = (start.end() if start else 0) + next_start.start()
                break
        area = flat[start.start():end] if start else flat
        prefix = owner_prefix(number)
        state.save(f"{prefix}Name", value_after_label(area, r"(?:Owner\s+Name|Full\s+Name|Name)\s*:\s*", r"Title|Ownership|DOB|Date\s+of\s+Birth|Address|City|State|Zip|SSN|Social|Phone|Email|$"))
        state.save(f"{prefix}Dob", value_after_label(area, r"(?:DOB|Date\s+of\s+Birth|Birth\s+Date)\s*:\s*", r"SSN|Social|Address|City|State|Zip|Phone|Email|$"))
        state.save(f"{prefix}Address", value_after_label(area, r"(?:Home\s+Address|Owner\s+Address|Residential\s+Address|Address)\s*:\s*", r"City|State|Zip|SSN|Social|Phone|Email|$"))
        state.save(f"{prefix}City", value_after_label(area, r"\bCity\s*:\s*", r"State|Zip|SSN|Social|Phone|Email|$"))
        state.save(f"{prefix}State", value_after_label(area, r"\bState\s*:\s*", r"Zip|SSN|Social|Phone|Email|$"))
        state.save(f"{prefix}Zip", value_after_label(area, r"\bZip(?:\s+Code)?\s*:\s*", r"SSN|Social|Phone|Email|$"))
        state.save(owner_ssn_key(number), value_after_label(area, r"(?:SSN\s*#?|SSI\s+Number|SSN\s+Number|Social\s+Security(?:\s+Number)?)\s*:\s*", r"Phone|Email|Owner|$"))


def sanitize_values(state: ExtractedState) -> None:
    for target in ["business", "owner", "owner2", "owner3", "owner4"]:
        address_key = f"{target}Address"
        if address_key in state.values:
            parse_city_state_zip(state, target, state.values[address_key], force=True)
    for key in ["businessName", "businessDbaName", "ownerName", "owner2Name", "owner3Name", "owner4Name"]:
        state.values[key] = re.sub(r"\s+(Owner\(s\)|Owner\s+\d+\s+Information|Owner\s+Information|Last\s+name).*$", "", clean_output(state.values.get(key, "")), flags=re.I).strip()
    state.values["einNumber"] = format_ein(state.values.get("einNumber", ""))
    state.values.update(FIXED_BUSINESS_CONTACT)
    for number in [2, 3, 4]:
        prefix = f"owner{number}"
        ssn_key = f"{prefix}Ssn"
        group_keys = [f"{prefix}Name", f"{prefix}Dob", f"{prefix}Address", f"{prefix}State", f"{prefix}City", f"{prefix}Zip", ssn_key]
        if not state.values.get(f"{prefix}Name") and not state.values.get(ssn_key):
            for key in group_keys:
                state.values[key] = ""


def apply_broadway_tcpdf_values(state: ExtractedState, text: str) -> None:
    normalized = normalize_text(text).replace("\r", "\n")
    if "Powered by TCPDF" not in normalized or "COMPANY INFORMATION" not in normalized:
        return
    marker = re.search(r"\bID:\s*\d+\s+Signed:\s*[^\n]+\n", normalized, re.I)
    if not marker:
        return
    value_area = normalized[marker.end():]
    value_area = value_area.split("---PAGE---", 1)[0]
    value_area = value_area.split("Completion Certificate", 1)[0]
    lines = [clean_output(line) for line in value_area.splitlines() if clean_output(line)]
    if lines and re.fullmatch(r"Date\s+of\s+Birth", lines[0], re.I):
        lines = lines[1:]
    if len(lines) < 30:
        return

    def line(index: int) -> str:
        return lines[index] if index < len(lines) else ""

    industry_lines = [line(3)]
    next_index = 4
    if line(4).lower() in {"kids", "services", "products"} or len(line(4).split()) <= 3:
        industry_lines.append(line(4))
        next_index = 5

    business_address = line(next_index)
    state_index = next_index + 2
    zip_index = next_index + 3
    city_index = next_index + 4
    phone_index = next_index + 5

    owner_start = None
    for index, value in enumerate(lines):
        if value.lower() == "no" and index + 12 < len(lines):
            owner_start = index + 1
            break
    if owner_start is None:
        return

    has_middle_noise = line(owner_start).lower() == "middle" and line(owner_start + 1).lower() == "name"
    if has_middle_noise:
        owner_first_index = owner_start + 2
    else:
        owner_first_index = owner_start

    state.save("businessName", line(0), force=True)
    state.save("einNumber", line(2), force=True)
    state.save("businessAddress", business_address, force=True)
    state.save("businessState", line(state_index), force=True)
    state.save("businessZip", line(zip_index), force=True)
    state.save("businessCity", line(city_index), force=True)
    state.save("businessPhone", line(phone_index), force=True)

    owner_first = line(owner_first_index)
    owner_last = line(owner_first_index + 1)
    state.save("ownerName", clean_output(f"{owner_first} {owner_last}"), force=True)
    state.save("ssn", line(owner_first_index + 5), force=True)
    state.save("ownerDob", line(owner_first_index + 6), force=True)
    state.save("ownerAddress", line(owner_first_index + 8), force=True)
    state.save("ownerCity", line(owner_first_index + 9), force=True)
    state.save("ownerState", line(owner_first_index + 10), force=True)
    state.save("ownerZip", line(owner_first_index + 11), force=True)


def apply_bridgepoint_sequential_values(state: ExtractedState, text: str) -> None:
    normalized = normalize_text(text).replace("\r", "\n")
    if "PRE-QUALIFICATION AUTHORIZATION" not in normalized or "BridgePoint Capital" not in normalized:
        return
    marker = re.search(r"Date\s+of\s+Birth:\s*\n", normalized, re.I)
    if not marker:
        return
    value_area = normalized[marker.end():]
    value_area = value_area.split("---PAGE---", 1)[0]
    value_area = value_area.split("Signed at:", 1)[0]
    lines = [clean_output(line) for line in value_area.splitlines() if clean_output(line)]
    if lines and re.fullmatch(r"Date\s+of\s+Birth", lines[0], re.I):
        lines = lines[1:]
    if len(lines) < 30:
        return

    def line(index: int) -> str:
        return lines[index] if index < len(lines) else ""

    state.save("businessName", line(0), force=True)
    state.save("businessDbaName", line(1), force=True)
    state.save("businessAddress", line(2), force=True)
    state.save("businessCity", line(3), force=True)
    state.save("businessState", line(4), force=True)
    state.save("businessZip", line(5), force=True)
    state.save("businessPhone", line(6), force=True)
    state.save("einNumber", line(10), force=True)
    state.save("ownerName", line(14), force=True)
    state.save("ownerDob", line(17), force=True)
    state.save("ownerAddress", line(18), force=True)
    state.save("ownerCity", line(20), force=True)
    state.save("ownerState", line(22), force=True)
    state.save("ownerZip", line(23), force=True)
    state.save("ssn", line(25), force=True)


def apply_handwriting_table_values(state: ExtractedState, text: str) -> None:
    normalized = normalize_text(text)
    if "Hand Writing Credit App" not in normalized or "Field" not in normalized or "Value" not in normalized:
        return
    lines = [clean_output(line) for line in normalized.splitlines() if clean_output(line)]
    label_to_key = {
        "Business Legal Name": "businessName",
        "Business DBA Name": "businessDbaName",
        "Business Address": "businessAddress",
        "Business City": "businessCity",
        "Business State": "businessState",
        "Business Zip": "businessZip",
        "Tax ID / EIN": "einNumber",
        "Owner Name": "ownerName",
        "DOB": "ownerDob",
        "Owner Address": "ownerAddress",
        "Owner City": "ownerCity",
        "Owner State": "ownerState",
        "Owner Zip": "ownerZip",
        "SSN": "ssn",
    }
    labels = set(label_to_key)
    for index, line in enumerate(lines[:-1]):
        if line not in labels:
            continue
        next_value = lines[index + 1]
        if next_value in labels or next_value in {"Field", "Value", "Owner Information", "Business Information", "Additional Details"}:
            continue
        state.save(label_to_key[line], next_value, force=True)


def apply_shopfunder_values(state: ExtractedState, text: str) -> None:
    normalized = normalize_text(text)
    if "ShopFunder Application" not in normalized:
        return
    lines = [clean_output(line) for line in normalized.splitlines() if clean_output(line)]

    def value_after(label: str) -> str:
        for index, line in enumerate(lines[:-1]):
            if line.lower() == label.lower():
                return lines[index + 1]
        return ""

    state.save("businessName", value_after("Company Name"), force=True)
    state.save("businessAddress", value_after("Business Address"), force=True)
    state.save("businessCity", value_after("City"), force=True)
    state.save("businessState", value_after("State"), force=True)
    state.save("businessZip", value_after("ZIP Code"), force=True)
    state.save("einNumber", value_after("Federal Tax ID"), force=True)
    state.save("ownerName", value_after("Owner Name"), force=True)
    owner_address = value_after("Owner Home Address")
    business_address = state.values.get("businessAddress", "")
    if business_address and owner_address.lower().startswith(business_address.lower()):
        owner_address = business_address
    state.save("ownerAddress", owner_address, force=True)

    owner_section = lines[lines.index("Owner Information"):] if "Owner Information" in lines else lines
    def owner_value_after(label: str) -> str:
        for index, line in enumerate(owner_section[:-1]):
            if line.lower() == label.lower():
                return owner_section[index + 1]
        return ""

    state.save("ownerCity", owner_value_after("City"), force=True)
    state.save("ownerState", owner_value_after("State"), force=True)
    state.save("ownerZip", owner_value_after("ZIP Code"), force=True)
    state.save("businessEmail", owner_value_after("Email"), force=True)
    state.save("businessPhone", owner_value_after("Phone Number"), force=True)
    birthday = owner_value_after("Birthday")
    date_match = re.search(r"\b([A-Za-z]+,\s*)?([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b", birthday)
    if date_match:
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
            "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
        }
        month = months.get(date_match.group(2).lower(), "")
        if month:
            state.save("ownerDob", f"{month}/{date_match.group(3).zfill(2)}/{date_match.group(4)}", force=True)
    state.save("ssn", owner_value_after("Social Security Number"), force=True)


def apply_fast_funds_tcpdf_values(state: ExtractedState, text: str) -> None:
    normalized = normalize_text(text).replace("\r", "\n")
    if "Merchant Pre-Qualification Form" not in normalized or "Fast Funds Group LLC" not in normalized:
        return
    lines = [clean_output(line) for line in normalized.splitlines() if clean_output(line)]
    try:
        start = lines.index("FFG")
    except ValueError:
        return
    if start + 18 >= len(lines):
        return

    state.save("businessDbaName", lines[start], force=True)
    state.save("businessName", lines[start + 1], force=True)
    apply_single_line_address(state, "business", lines[start + 2], force=True)
    state.save("einNumber", lines[start + 16], force=True)
    state.save("ownerName", lines[start + 7], force=True)
    city_state_zip = lines[start + 8]
    match = re.search(r"^([A-Za-z .'-]+)\s+([A-Z]{2}|[A-Za-z ]+)\s+(\d{5}(?:-\d{4})?)$", city_state_zip, re.I)
    if match:
        state.save("ownerCity", match.group(1), force=True)
        state.save("ownerState", match.group(2), force=True)
        state.save("ownerZip", match.group(3), force=True)
    state.save("ownerDob", lines[start + 9], force=True)
    state.save("ssn", lines[start + 10], force=True)
    state.save("ownerAddress", lines[start + 12], force=True)


def apply_airs_capital_values(state: ExtractedState, text: str) -> None:
    normalized = normalize_text(text)
    if "601 Heritage Dr" not in normalized or "Business DBA" not in normalized or "Desired Working Capital Amount" not in normalized:
        return
    lines = [clean_output(line) for line in normalized.splitlines() if clean_output(line)]
    try:
        start = lines.index("601 Heritage Dr")
    except ValueError:
        return
    if start + 34 >= len(lines):
        return

    value_start = start + 2
    state.save("businessDbaName", lines[value_start], force=True)
    state.save("businessName", lines[value_start + 1], force=True)
    state.save("einNumber", lines[value_start + 2], force=True)
    state.save("businessAddress", lines[value_start + 5], force=True)
    state.save("businessState", lines[value_start + 6], force=True)
    state.save("businessZip", lines[value_start + 7], force=True)
    state.save("businessCity", lines[value_start + 8], force=True)
    state.save("businessPhone", lines[value_start + 9], force=True)
    state.save("businessEmail", lines[value_start + 10].split(";")[0], force=True)

    owner_index = value_start + 23
    state.save("ownerName", lines[owner_index], force=True)
    parse_city_state_zip(state, "owner", f"{lines[owner_index + 1]}, {lines[owner_index + 2]}", force=True)
    state.save("ownerDob", lines[owner_index + 6], force=True)
    state.save("ssn", lines[owner_index + 7], force=True)


def provider_name(text: str) -> str:
    normalized = normalize_text(text)
    checks = [
        (r"Waterstone\s+Advance", "Waterstone Advance"),
        (r"Choice\s+Capital\s+Solutions", "Choice Capital Solutions"),
        (r"Sapphire\s+Capital", "Sapphire Capital Group"),
        (r"AIRS\s+CAPITAL", "AIRS Capital Funding"),
        (r"SPIN\s+CAPITAL|Merchant\s+Pre-Qualification\s+Form", "Spin Capital"),
        (r"Fintek\s+Capital", "Fintek"),
        (r"Bridge\s*Point\s*Capital|BridgePointCapital", "BridgePoint"),
        (r"Hand\s*Writing\s+Credit\s+App|Business\s+Information.*Owner\s+Information", "Hand Writing Credit App"),
        (r"Funding\s+Application", "Funding Application"),
    ]
    for pattern, name in checks:
        if re.search(pattern, normalized, re.I | re.S):
            return name
    return "Unknown"


def extract_details_from_text(text: str) -> ExtractedState:
    state = ExtractedState()
    rows = rows_from_text(text)
    parse_label_blocks(state, rows)
    parse_next_line_labels(state, rows)
    section = "business"
    for row in rows:
        section = section_from_line(row, section)
        parse_inline_labels(state, row, section)
    apply_flat_patterns(state, text)
    apply_regex_fallbacks(state, text, rows)
    apply_broadway_tcpdf_values(state, text)
    apply_bridgepoint_sequential_values(state, text)
    apply_handwriting_table_values(state, text)
    apply_shopfunder_values(state, text)
    apply_fast_funds_tcpdf_values(state, text)
    apply_airs_capital_values(state, text)
    sanitize_values(state)
    return state


def build_credit_scrub(values: dict[str, str], pricing_text: str) -> str:
    pricing = parse_pricing_scrub(pricing_text)
    scrub_state = values.get("businessState") or pricing.get("state", "")
    lines: list[str] = []
    if pricing["tier"]:
        lines.extend([pricing["tier"], ""])
    business_search = google_search_line(values.get("businessName") or values.get("businessDbaName", ""), scrub_state)
    people = [
        google_search_line(values.get(key, ""), scrub_state)
        for key in ["ownerName", "owner2Name", "owner3Name", "owner4Name"]
    ]
    people = [line for line in people if line]
    if business_search:
        lines.append(business_search)
    if business_search and people:
        lines.append("")
    lines.extend(people)
    if business_search or people:
        lines.append("")
    lines.extend([
        f"Company Website : {pricing['website'] or 'Not Found'}",
        "",
        "FICO :",
        f"{pricing['revenueMonth']} Revenue : {pricing['deposits']}",
        f"Industry : {pricing['industry']}",
        f"TIB : {pricing['tib']}",
        f"State : {normalize_state_code(scrub_state)}",
        "Datamerch : No Match",
        "Received : N",
        f"EIN : {format_ein(values.get('einNumber', ''))}",
        "Customer Id :",
    ])
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip()


class OCRPipeline:
    def __init__(self, progress) -> None:
        self.progress = progress
        self.temp_files: list[Path] = []

    def temp_path(self, prefix: str, suffix: str) -> Path:
        fd, filename = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)
        path = Path(filename)
        self.temp_files.append(path)
        return path

    def cleanup(self) -> None:
        for path in self.temp_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self.temp_files.clear()

    def preprocess_image(self, image_path: Path) -> Path:
        try:
            cv2 = importlib.import_module("cv2")
        except Exception:
            return image_path
        image = cv2.imread(str(image_path))
        if image is None:
            return image_path
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.fastNlMeansDenoising(gray, h=15)
        gray = cv2.resize(gray, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)
        output = self.temp_path("ocr_preprocessed_", ".png")
        cv2.imwrite(str(output), binary)
        return output

    def images_from_pdf(self, pdf_path: Path) -> list[Path]:
        try:
            fitz = importlib.import_module("fitz")
        except Exception as exc:
            raise RuntimeError("PDF OCR ke liye PyMuPDF install karo: pip install pymupdf") from exc
        doc = fitz.open(str(pdf_path))
        paths: list[Path] = []
        for page_index, page in enumerate(doc, start=1):
            self.progress(f"Rendering PDF page {page_index}/{len(doc)}")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2.4, 2.4), alpha=False)
            image_path = self.temp_path(f"pdf_page_{page_index}_", ".png")
            pixmap.save(str(image_path))
            paths.append(image_path)
        return paths

    def pdf_text_layer(self, pdf_path: Path) -> str:
        try:
            fitz = importlib.import_module("fitz")
        except Exception:
            return ""
        try:
            doc = fitz.open(str(pdf_path))
            return "\n".join(page.get_text("text") for page in doc).strip()
        except Exception:
            return ""

    def input_images(self, file_path: Path) -> tuple[str, list[Path]]:
        if file_path.suffix.lower() == ".pdf":
            text_layer = self.pdf_text_layer(file_path)
            return text_layer, self.images_from_pdf(file_path)
        return "", [file_path]

    def run(self, file_path: Path, engine: str) -> str:
        text_layer, image_paths = self.input_images(file_path)
        mode = engine if engine in OCR_MODES else "Image"
        if mode == "Text PDF" and text_layer:
            return text_layer
        if mode == "Text PDF":
            engines = ["Tesseract OCR", "PaddleOCR", "EasyOCR"]
        elif mode == "Handwriting":
            engines = ["TrOCR", "EasyOCR", "Tesseract OCR", "PaddleOCR", "DocTR"]
        else:
            engines = ["Tesseract OCR", "PaddleOCR", "EasyOCR", "DocTR"]
        chunks = [text_layer] if text_layer else []
        errors: list[str] = []
        for selected in engines:
            try:
                self.progress(f"{selected} running...")
                result = self.run_engine(selected, image_paths)
                if clean_output(result):
                    chunks.append(result)
                    if mode != "Handwriting":
                        break
            except Exception as exc:
                errors.append(f"{selected}: {exc}")
        output = "\n\n".join(chunk for chunk in chunks if clean_output(chunk))
        if output:
            return output
        if errors:
            raise RuntimeError("\n".join(errors))
        return ""

    def run_engine(self, engine: str, image_paths: list[Path]) -> str:
        if engine == "Tesseract OCR":
            return self.tesseract(image_paths)
        if engine == "PaddleOCR":
            return self.paddle(image_paths)
        if engine == "EasyOCR":
            return self.easyocr(image_paths)
        if engine == "DocTR":
            return self.doctr(image_paths)
        if engine == "TrOCR":
            return self.trocr(image_paths)
        raise RuntimeError(f"Unknown OCR engine: {engine}")

    def tesseract(self, image_paths: list[Path]) -> str:
        try:
            pytesseract = importlib.import_module("pytesseract")
            image_module = importlib.import_module("PIL.Image")
        except Exception as exc:
            raise RuntimeError("pytesseract/Pillow install nahi hai.") from exc
        tesseract_cmd = os.getenv("TESSERACT_CMD")
        common_tesseract_paths = [
            tesseract_cmd,
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
        ]
        for candidate in common_tesseract_paths:
            if candidate and Path(candidate).exists():
                pytesseract.pytesseract.tesseract_cmd = candidate
                break
        chunks = []
        for image_path in image_paths:
            processed = self.preprocess_image(image_path)
            chunks.append(pytesseract.image_to_string(image_module.open(processed), lang="eng", config="--psm 6"))
        return "\n".join(chunks)

    def paddle(self, image_paths: list[Path]) -> str:
        try:
            paddleocr = importlib.import_module("paddle" + "ocr")
        except Exception as exc:
            raise RuntimeError("Paddle OCR install nahi hai.") from exc
        ocr = paddleocr.PaddleOCR(use_angle_cls=True, lang="en")
        lines = []
        for image_path in image_paths:
            result = ocr.ocr(str(self.preprocess_image(image_path)), cls=True)
            for page in result or []:
                for item in page or []:
                    try:
                        lines.append(item[1][0])
                    except Exception:
                        pass
        return "\n".join(lines)

    def easyocr(self, image_paths: list[Path]) -> str:
        try:
            easyocr = importlib.import_module("easyocr")
        except Exception as exc:
            raise RuntimeError("easyocr install nahi hai.") from exc
        reader = easyocr.Reader(["en"], gpu=False)
        lines = []
        for image_path in image_paths:
            lines.extend(reader.readtext(str(self.preprocess_image(image_path)), detail=0, paragraph=True))
        return "\n".join(lines)

    def doctr(self, image_paths: list[Path]) -> str:
        try:
            doctr_io = importlib.import_module("doctr.io")
            doctr_models = importlib.import_module("doctr.models")
        except Exception as exc:
            raise RuntimeError("python-doctr install nahi hai.") from exc
        predictor = doctr_models.ocr_predictor(pretrained=True)
        document = doctr_io.DocumentFile.from_images([str(self.preprocess_image(path)) for path in image_paths])
        result = predictor(document)
        exported = result.export()
        lines = []
        for page in exported.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    lines.append(" ".join(word.get("value", "") for word in line.get("words", [])))
        return "\n".join(clean_output(line) for line in lines if clean_output(line))

    def trocr(self, image_paths: list[Path]) -> str:
        try:
            torch = importlib.import_module("torch")
            image_module = importlib.import_module("PIL.Image")
            transformers = importlib.import_module("transformers")
        except Exception as exc:
            raise RuntimeError("transformers/torch/Pillow install nahi hai.") from exc
        processor = transformers.TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        model = transformers.VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        lines = []
        for image_path in image_paths:
            image = image_module.open(self.preprocess_image(image_path)).convert("RGB")
            pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
            generated_ids = model.generate(pixel_values)
            lines.append(processor.batch_decode(generated_ids, skip_special_tokens=True)[0])
        return "\n".join(lines)


class CreditOcrApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1260x820")
        self.minsize(980, 680)
        self.file_path: Path | None = None
        self.raw_text = ""
        self.values = {key: "" for key, _ in ALL_FIELDS}
        self.values.update(FIXED_BUSINESS_CONTACT)
        self.inputs: dict[str, ttk.Entry] = {}
        self.status_var = tk.StringVar(value="Ready")
        self.engine_var = tk.StringVar(value="Text PDF")
        self.file_var = tk.StringVar(value="No file selected")
        self._build_ui()
        self.refresh_fields()
        self.refresh_credit_scrub()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=12)
        left.grid(row=0, column=0, sticky="ns")
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Pricing Scrub").grid(row=0, column=0, sticky="w")
        self.pricing_text = tk.Text(left, height=11, width=38, wrap="word")
        self.pricing_text.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        self.pricing_text.bind("<KeyRelease>", lambda _event: self.refresh_credit_scrub())

        ttk.Label(left, text="Credit Scrub").grid(row=2, column=0, sticky="w")
        self.credit_text = tk.Text(left, height=22, width=38, wrap="word")
        self.credit_text.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        left.rowconfigure(3, weight=1)
        ttk.Button(left, text="Copy Credit Scrub", command=self.copy_credit_scrub).grid(row=4, column=0, sticky="ew")

        right = ttk.Frame(self, padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        header = ttk.Frame(right)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status_var).grid(row=0, column=1, sticky="e")

        controls = ttk.Frame(right)
        controls.grid(row=1, column=0, sticky="ew", pady=12)
        controls.columnconfigure(1, weight=1)
        ttk.Button(controls, text="Select PDF / Image", command=self.select_file).grid(row=0, column=0, padx=(0, 8))
        ttk.Label(controls, textvariable=self.file_var).grid(row=0, column=1, sticky="ew")
        ttk.Combobox(
            controls,
            textvariable=self.engine_var,
            values=OCR_MODES,
            state="readonly",
            width=20,
        ).grid(row=0, column=2, padx=8)
        ttk.Button(controls, text="Extract Details", command=self.extract_file).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(controls, text="Download Excel", command=self.export_excel).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(controls, text="Clear", command=self.clear_all).grid(row=0, column=5)

        notebook = ttk.Notebook(right)
        notebook.grid(row=3, column=0, sticky="nsew")

        fields_tab = ttk.Frame(notebook, padding=10)
        raw_tab = ttk.Frame(notebook, padding=10)
        notebook.add(fields_tab, text="Extracted Fields")
        notebook.add(raw_tab, text="Raw OCR Text")

        canvas = tk.Canvas(fields_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(fields_tab, orient="vertical", command=canvas.yview)
        self.fields_frame = ttk.Frame(canvas)
        self.fields_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.fields_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.raw_text_widget = tk.Text(raw_tab, wrap="word")
        self.raw_text_widget.pack(fill=BOTH, expand=True)
        ttk.Button(raw_tab, text="Parse Raw Text", command=self.parse_raw_text).pack(fill=X, pady=(8, 0))

    def set_status(self, message: str) -> None:
        self.after(0, lambda: self.status_var.set(message))

    def refresh_fields(self) -> None:
        for widget in self.fields_frame.winfo_children():
            widget.destroy()
        row = 0
        for group_name, fields in FIELD_GROUPS:
            ttk.Label(self.fields_frame, text=group_name, font=("Segoe UI", 11, "bold")).grid(row=row, column=0, columnspan=4, sticky="w", pady=(10, 4))
            row += 1
            for index, (key, label) in enumerate(fields):
                col = (index % 2) * 2
                if index and index % 2 == 0:
                    row += 1
                ttk.Label(self.fields_frame, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=3)
                entry = ttk.Entry(self.fields_frame, width=34)
                entry.grid(row=row, column=col + 1, sticky="ew", padx=(0, 16), pady=3)
                entry.insert(0, self.values.get(key, ""))
                if key in FIXED_CONTACT_KEYS:
                    entry.configure(state="readonly")
                entry.bind("<KeyRelease>", lambda _event, k=key, e=entry: self.on_field_change(k, e.get()))
                self.inputs[key] = entry
            row += 1
        for col in [1, 3]:
            self.fields_frame.columnconfigure(col, weight=1)

    def on_field_change(self, key: str, value: str) -> None:
        if key in FIXED_CONTACT_KEYS:
            self.values.update(FIXED_BUSINESS_CONTACT)
            self.refresh_inputs()
            return
        self.values[key] = clean_output(value)
        self.refresh_credit_scrub()

    def refresh_inputs(self) -> None:
        self.values.update(FIXED_BUSINESS_CONTACT)
        for key, entry in self.inputs.items():
            if key in FIXED_CONTACT_KEYS:
                entry.configure(state="normal")
            entry.delete(0, END)
            entry.insert(0, self.values.get(key, ""))
            if key in FIXED_CONTACT_KEYS:
                entry.configure(state="readonly")
        self.refresh_credit_scrub()

    def refresh_credit_scrub(self) -> None:
        text = build_credit_scrub(self.values, self.pricing_text.get("1.0", END))
        self.credit_text.delete("1.0", END)
        self.credit_text.insert("1.0", text)

    def copy_credit_scrub(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.credit_text.get("1.0", END).rstrip())
        self.set_status("Credit scrub copied")

    def select_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select PDF or Image",
            filetypes=[("PDF / Images", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp"), ("All files", "*.*")],
        )
        if not filename:
            return
        self.file_path = Path(filename)
        self.file_var.set(str(self.file_path))
        self.set_status("File ready")

    def extract_file(self) -> None:
        if not self.file_path:
            messagebox.showwarning(APP_TITLE, "Pehle PDF ya image select karo.")
            return
        threading.Thread(target=self._extract_worker, daemon=True).start()

    def _extract_worker(self) -> None:
        assert self.file_path is not None
        pipeline = OCRPipeline(self.set_status)
        try:
            self.set_status("OCR processing...")
            text = pipeline.run(self.file_path, self.engine_var.get())
            self.raw_text = text
            extracted = extract_details_from_text(text)
            self.values = extracted.values
            self.after(0, self._after_extract)
            low_count = len(extracted.low_confidence)
            self.set_status(f"{provider_name(text)} details extracted" + (f" - {low_count} low confidence" if low_count else ""))
        except Exception as exc:
            details = f"{exc}\n\n{traceback.format_exc(limit=2)}"
            self.after(0, lambda message=details: messagebox.showerror(APP_TITLE, message))
            self.set_status("Extraction failed")
        finally:
            pipeline.cleanup()

    def _after_extract(self) -> None:
        self.raw_text_widget.delete("1.0", END)
        self.raw_text_widget.insert("1.0", self.raw_text)
        self.refresh_inputs()

    def parse_raw_text(self) -> None:
        self.raw_text = self.raw_text_widget.get("1.0", END)
        extracted = extract_details_from_text(self.raw_text)
        self.values = extracted.values
        self.refresh_inputs()
        self.set_status(f"{provider_name(self.raw_text)} details parsed")

    def clear_all(self) -> None:
        self.file_path = None
        self.file_var.set("No file selected")
        self.raw_text = ""
        self.values = {key: "" for key, _ in ALL_FIELDS}
        self.values.update(FIXED_BUSINESS_CONTACT)
        self.raw_text_widget.delete("1.0", END)
        self.pricing_text.delete("1.0", END)
        self.refresh_inputs()
        self.set_status("Ready")

    def export_excel(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Save Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx"), ("CSV", "*.csv")],
            initialfile="business-owner-details.xlsx",
        )
        if not filename:
            return
        path = Path(filename)
        rows = [
            ["Business Legal Name", self.values.get("businessName", ""), "", "", ""],
            ["Business DBA Name", self.values.get("businessDbaName", ""), "", "", ""],
            ["Business Address", self.values.get("businessAddress", ""), "", "", ""],
            ["Business State", self.values.get("businessState", ""), "", "", ""],
            ["Business City", self.values.get("businessCity", ""), "", "", ""],
            ["Business Zip", self.values.get("businessZip", ""), "", "", ""],
            ["Business Phone Number", self.values.get("businessPhone", ""), "", "", ""],
            ["Business Gmail", self.values.get("businessEmail", ""), "", "", ""],
            ["Tax ID (TIN #)", format_ein(self.values.get("einNumber", "")), "", "", ""],
            ["Owner Name", self.values.get("ownerName", ""), self.values.get("owner2Name", ""), self.values.get("owner3Name", ""), self.values.get("owner4Name", "")],
            ["Owner DOB", self.values.get("ownerDob", ""), self.values.get("owner2Dob", ""), self.values.get("owner3Dob", ""), self.values.get("owner4Dob", "")],
            ["Home Address", self.values.get("ownerAddress", ""), self.values.get("owner2Address", ""), self.values.get("owner3Address", ""), self.values.get("owner4Address", "")],
            ["Owner State", self.values.get("ownerState", ""), self.values.get("owner2State", ""), self.values.get("owner3State", ""), self.values.get("owner4State", "")],
            ["Owner City", self.values.get("ownerCity", ""), self.values.get("owner2City", ""), self.values.get("owner3City", ""), self.values.get("owner4City", "")],
            ["Owner Zip", self.values.get("ownerZip", ""), self.values.get("owner2Zip", ""), self.values.get("owner3Zip", ""), self.values.get("owner4Zip", "")],
            ["SSN#", self.values.get("ssn", ""), self.values.get("owner2Ssn", ""), self.values.get("owner3Ssn", ""), self.values.get("owner4Ssn", "")],
        ]
        try:
            if path.suffix.lower() == ".csv":
                with path.open("w", newline="", encoding="utf-8") as handle:
                    csv.writer(handle).writerows(rows)
            else:
                self._write_xlsx(path, rows)
            self.set_status(f"Saved: {path.name}")
            if messagebox.askyesno(APP_TITLE, "File save ho gayi. Open karni hai?"):
                webbrowser.open(path.as_uri())
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _write_xlsx(self, path: Path, rows: list[list[str]]) -> None:
        try:
            openpyxl = importlib.import_module("openpyxl")
            openpyxl_styles = importlib.import_module("openpyxl.styles")
        except Exception as exc:
            raise RuntimeError("Excel export ke liye openpyxl install karo ya CSV save karo.") from exc
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Extracted Details"
        thin = openpyxl_styles.Side(style="thin", color="D9DEE7")
        for row in rows:
            sheet.append(row)
        for row in sheet.iter_rows():
            for index, cell in enumerate(row, start=1):
                cell.alignment = openpyxl_styles.Alignment(horizontal="left", vertical="center", wrap_text=True)
                cell.border = openpyxl_styles.Border(top=thin, bottom=thin, left=thin, right=thin)
                if index == 1:
                    cell.font = openpyxl_styles.Font(bold=True)
        widths = [28, 36, 36, 36, 36]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index)].width = width
        workbook.save(path)


def main() -> None:
    app = CreditOcrApp()
    app.mainloop()


if __name__ == "__main__":
    main()
