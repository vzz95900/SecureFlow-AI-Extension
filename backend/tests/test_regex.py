"""
Tests for the regex-based PII detector (India-focused).
Includes disambiguation tests for phone/Aadhaar overlap scenarios.
"""
import pytest
from app.pipeline.regex_detector import detect


# ── Core Detection Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_aadhaar_spaced():
    """Aadhaar in 4-4-4 format with spaces must be detected."""
    text = "My Aadhaar number is 4567 8901 2345."
    entities = await detect(text, sensitivity="high")
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(aadhaar) >= 1
    assert aadhaar[0].risk == "HIGH"


@pytest.mark.asyncio
async def test_detect_aadhaar_hyphenated():
    """Aadhaar in 4-4-4 format with hyphens must be detected."""
    text = "Aadhaar: 3456-7890-1234"
    entities = await detect(text, sensitivity="high")
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(aadhaar) >= 1


@pytest.mark.asyncio
async def test_detect_pan():
    text = "PAN card ABCPD1234E for tax filing."
    entities = await detect(text, sensitivity="high")
    pan = [e for e in entities if e.type == "PAN"]
    assert len(pan) >= 1
    assert pan[0].text == "ABCPD1234E"
    assert pan[0].risk == "HIGH"


@pytest.mark.asyncio
async def test_detect_indian_phone_with_prefix():
    """Phone with +91 prefix must be detected as PHONE."""
    text = "Call me at +91 98765 43210 for details."
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    assert len(phone) >= 1


@pytest.mark.asyncio
async def test_detect_indian_phone_bare():
    """Bare 10-digit mobile number must be detected as PHONE, not AADHAAR."""
    text = "My number is 9876543210."
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(phone) >= 1, "Expected PHONE detection for 10-digit mobile"
    assert len(aadhaar) == 0, "10-digit mobile should NOT be detected as AADHAAR"


@pytest.mark.asyncio
async def test_detect_email():
    text = "Send report to rahul.sharma@company.in please."
    entities = await detect(text, sensitivity="high")
    email = [e for e in entities if e.type == "EMAIL"]
    assert len(email) >= 1
    assert "rahul.sharma@company.in" in email[0].text


@pytest.mark.asyncio
async def test_detect_ifsc():
    text = "IFSC code is SBIN0001234 for the branch."
    entities = await detect(text, sensitivity="high")
    ifsc = [e for e in entities if e.type == "IFSC"]
    assert len(ifsc) >= 1
    assert ifsc[0].text == "SBIN0001234"


@pytest.mark.asyncio
async def test_detect_upi_id():
    text = "Pay via anil.kumar@paytm for the order."
    entities = await detect(text, sensitivity="high")
    upi = [e for e in entities if e.type == "UPI_ID"]
    assert len(upi) >= 1


@pytest.mark.asyncio
async def test_detect_voter_id():
    text = "Voter ID ABC1234567 verified."
    entities = await detect(text, sensitivity="high")
    voter = [e for e in entities if e.type == "VOTER_ID"]
    assert len(voter) >= 1
    assert voter[0].text == "ABC1234567"


@pytest.mark.asyncio
async def test_detect_credit_card():
    text = "Card number 4111111111111111 charged."
    entities = await detect(text, sensitivity="high")
    cc = [e for e in entities if e.type == "CREDIT_CARD"]
    assert len(cc) >= 1


@pytest.mark.asyncio
async def test_detect_dob_indian_format():
    text = "Date of birth 15/08/1990 for KYC."
    entities = await detect(text, sensitivity="high")
    dob = [e for e in entities if e.type == "DOB"]
    assert len(dob) >= 1
    assert dob[0].text == "15/08/1990"


# ── Disambiguation Tests (Phone vs Aadhaar) ──────────────────────

@pytest.mark.asyncio
async def test_phone_not_detected_as_aadhaar():
    """A bare 10-digit mobile must only be PHONE, never AADHAAR."""
    text = "Call me at 9876543210 for details."
    entities = await detect(text, sensitivity="high")
    types = {e.type for e in entities}
    assert "PHONE" in types, "10-digit mobile should be PHONE"
    assert "AADHAAR" not in types, "10-digit mobile must NOT be AADHAAR"


@pytest.mark.asyncio
async def test_aadhaar_not_detected_as_phone():
    """A 12-digit Aadhaar in 4-4-4 format must be AADHAAR, not PHONE."""
    text = "Aadhaar 4567 8901 2345 for verification."
    entities = await detect(text, sensitivity="high")
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(aadhaar) >= 1, "12-digit 4-4-4 should be AADHAAR"


@pytest.mark.asyncio
async def test_phone_with_plus91_prefix():
    """Phone numbers with +91 prefix should be PHONE."""
    text = "Reach me at +919876543210"
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    assert len(phone) >= 1, "+91 prefixed number should be PHONE"


@pytest.mark.asyncio
async def test_phone_with_zero_prefix():
    """Phone numbers with 0 prefix should be PHONE."""
    text = "Call 09876543210 now."
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    assert len(phone) >= 1, "0-prefixed number should be PHONE"


@pytest.mark.asyncio
async def test_mixed_phone_and_aadhaar():
    """Both phone and Aadhaar in same text should be correctly classified."""
    text = "Phone 9876543210 and Aadhaar 2345 6789 0123."
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(phone) >= 1, "Should detect PHONE"
    assert len(aadhaar) >= 1, "Should detect AADHAAR"


@pytest.mark.asyncio
async def test_short_number_no_match():
    """A 9-digit number should not be detected as PHONE or AADHAAR."""
    text = "Reference code 123456789 for your order."
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(phone) == 0, "9-digit number should NOT be PHONE"
    assert len(aadhaar) == 0, "9-digit number should NOT be AADHAAR"


@pytest.mark.asyncio
async def test_13_digit_number_no_aadhaar():
    """A 13-digit number should not match as Aadhaar (too long)."""
    text = "Transaction ID 2345678901234."
    entities = await detect(text, sensitivity="high")
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(aadhaar) == 0, "13-digit number should NOT be AADHAAR"


# ── Clean Text Test ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_detections_clean_text():
    text = "The monsoon in Kerala brings heavy rainfall every year."
    entities = await detect(text, sensitivity="high")
    assert len(entities) == 0


# ── Sensitivity Filtering Test ────────────────────────────────────

@pytest.mark.asyncio
async def test_sensitivity_filtering():
    text = "Aadhaar 4567 8901 2345 and IP 192.168.1.1"
    # Low sensitivity: only HIGH risk (Aadhaar yes, IP no)
    entities = await detect(text, sensitivity="low")
    types = {e.type for e in entities}
    assert "AADHAAR" in types
    assert "IP_ADDRESS" not in types
