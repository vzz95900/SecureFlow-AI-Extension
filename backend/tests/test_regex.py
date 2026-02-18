"""
Tests for the regex-based PII detector (India-focused).
"""
import pytest
from app.pipeline.regex_detector import detect


@pytest.mark.asyncio
async def test_detect_aadhaar():
    text = "My Aadhaar number is 4567 8901 2345."
    entities = await detect(text, sensitivity="high")
    aadhaar = [e for e in entities if e.type == "AADHAAR"]
    assert len(aadhaar) >= 1
    assert aadhaar[0].risk == "HIGH"


@pytest.mark.asyncio
async def test_detect_pan():
    text = "PAN card ABCPD1234E for tax filing."
    entities = await detect(text, sensitivity="high")
    pan = [e for e in entities if e.type == "PAN"]
    assert len(pan) >= 1
    assert pan[0].text == "ABCPD1234E"
    assert pan[0].risk == "HIGH"


@pytest.mark.asyncio
async def test_detect_indian_phone():
    text = "Call me at +91 98765 43210 for details."
    entities = await detect(text, sensitivity="high")
    phone = [e for e in entities if e.type == "PHONE"]
    assert len(phone) >= 1


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
async def test_detect_indian_passport():
    text = "Passport number J8369854 issued in Delhi."
    entities = await detect(text, sensitivity="high")
    passport = [e for e in entities if e.type == "PASSPORT"]
    assert len(passport) >= 1


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


@pytest.mark.asyncio
async def test_no_detections_clean_text():
    text = "The monsoon in Kerala brings heavy rainfall every year."
    entities = await detect(text, sensitivity="high")
    assert len(entities) == 0


@pytest.mark.asyncio
async def test_sensitivity_filtering():
    text = "Aadhaar 4567 8901 2345 and IP 192.168.1.1"
    # Low sensitivity: only HIGH risk (Aadhaar yes, IP no)
    entities = await detect(text, sensitivity="low")
    types = {e.type for e in entities}
    assert "AADHAAR" in types
    assert "IP_ADDRESS" not in types
