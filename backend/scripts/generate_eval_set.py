"""
Generate a 300-example labeled evaluation dataset for SecureFlow AI.
Each example has text + expected_pii annotations with type labels.

Usage:
    cd backend
    python scripts/generate_eval_set.py
"""
import json, random, itertools
from pathlib import Path

random.seed(42)

# ── Indian first / last names ─────────────────────────────────────
FIRST = ["Rahul","Priya","Amit","Sunita","Vikram","Neha","Deepak","Kavita",
         "Sanjay","Meera","Rohan","Anita","Arjun","Pooja","Rajesh","Divya",
         "Kiran","Lakshmi","Suresh","Rekha","Manish","Swati","Arun","Geeta",
         "Nikhil","Rashmi","Vinay","Nandini","Pankaj","Seema"]
LAST = ["Sharma","Patel","Singh","Verma","Gupta","Rao","Nair","Joshi",
        "Mishra","Kumar","Reddy","Iyer","Das","Chopra","Mehta","Bhat",
        "Desai","Pillai","Menon","Saxena"]
DOMAINS = ["gmail.com","yahoo.co.in","hotmail.com","outlook.com",
           "infosys.com","wipro.com","tcs.com","company.in"]
UPI_HANDLES = ["paytm","ybl","oksbi","okicici","okhdfcbank","apl","ibl"]
STATES_DL = ["DL","MH","KA","TN","UP","RJ","GJ","WB","AP","KL"]
IFSC_BANKS = ["SBIN","HDFC","ICIC","UTIB","PUNB","BARB","CNRB","UBIN"]
ORGS = ["Flipkart","Infosys","TCS","Wipro","Reliance","Tata Motors",
        "Bajaj Finance","HDFC Bank","ICICI Bank","SBI"]

def rand_name():
    return random.choice(FIRST), random.choice(LAST)

def rand_aadhaar():
    d = str(random.randint(2,9))
    for _ in range(11): d += str(random.randint(0,9))
    return f"{d[0:4]} {d[4:8]} {d[8:12]}"

def rand_pan():
    c1 = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ",k=3))
    c2 = random.choice("ABCFGHLJPT")
    c3 = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    d = ''.join(random.choices("0123456789",k=4))
    c4 = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{c1}{c2}{c3}{d}{c4}"

def rand_phone():
    p = random.choice(["","+91 ","0"])
    d1 = str(random.randint(6,9))
    rest = ''.join(random.choices("0123456789",k=9))
    if p == "+91 ":
        return f"+91 {d1}{rest[:4]} {rest[4:]}"
    elif p == "0":
        return f"0{d1}{rest}"
    return f"{d1}{rest}"

def rand_email():
    f,l = rand_name()
    sep = random.choice([".","-","_",""])
    return f"{f.lower()}{sep}{l.lower()}@{random.choice(DOMAINS)}"

def rand_cc():
    prefix = random.choice(["4","51","52","53","37"])
    if prefix == "4":
        rest = ''.join(random.choices("0123456789",k=15))
    elif prefix == "37":
        rest = ''.join(random.choices("0123456789",k=13))
    else:
        rest = ''.join(random.choices("0123456789",k=14))
    return prefix + rest

def rand_ifsc():
    return random.choice(IFSC_BANKS) + "0" + ''.join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",k=6))

def rand_upi():
    f,l = rand_name()
    handle = random.choice(UPI_HANDLES)
    return f"{f.lower()}.{l.lower()}@{handle}"

def rand_passport():
    letter = random.choice("ABCDEFGHJKLMNPRSTUVWY")
    d = str(random.randint(1,9)) + ''.join(random.choices("0123456789",k=6))
    return f"{letter}{d}"

def rand_voter():
    letters = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ",k=3))
    digits = ''.join(random.choices("0123456789",k=7))
    return f"{letters}{digits}"

def rand_dl():
    st = random.choice(STATES_DL)
    code = f"{random.randint(1,99):02d}"
    yr = random.choice(["2018","2019","2020","2021","2022"])
    seq = ''.join(random.choices("0123456789",k=7))
    return f"{st}-{code}-{yr}{seq}"

def rand_gstin():
    st = f"{random.randint(1,37):02d}"
    pan = rand_pan()
    d = str(random.randint(1,9))
    c = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    return f"{st}{pan}{d}Z{c}"

def rand_dob():
    d = f"{random.randint(1,28):02d}"
    m = f"{random.randint(1,12):02d}"
    y = random.randint(1960,2005)
    return f"{d}/{m}/{y}"

def rand_ip():
    return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

def rand_medical():
    prefix = random.choice(["MRN","UHID","MR"])
    num = ''.join(random.choices("0123456789",k=random.randint(6,10)))
    sep = random.choice([" ","#"," #"])
    return f"{prefix}{sep}{num}"

# ── Negative sentences (no PII) ──────────────────────────────────
NEGATIVES = [
    "The weather forecast shows rain across Karnataka this week.",
    "India's GDP growth rate exceeded expectations in Q3.",
    "The new metro line will connect Whitefield to the airport.",
    "Cricket World Cup 2027 schedule has been announced.",
    "Bangalore traffic congestion worsened during peak hours today.",
    "The government announced a new education policy for rural schools.",
    "Monsoon arrived in Kerala earlier than expected this year.",
    "Stock markets showed positive trends in the IT sector.",
    "The ISRO mission successfully deployed three satellites into orbit.",
    "Electric vehicle adoption is growing rapidly in Indian cities.",
    "The new expressway will reduce travel time between Delhi and Jaipur.",
    "Renewable energy capacity in India crossed 150 GW milestone.",
    "The Reserve Bank maintained the repo rate at current levels.",
    "Indian startups raised record funding in the SaaS segment.",
    "The agriculture sector contributed significantly to GDP growth.",
    "A new wildlife sanctuary was established in the Western Ghats.",
    "Digital payments volume in India surpassed 10 billion transactions.",
    "The Supreme Court delivered a landmark judgment on data privacy.",
    "Indian Railways introduced new Vande Bharat routes this quarter.",
    "The textile industry reported strong export growth numbers.",
    "Air quality index in Delhi showed improvement after rain.",
    "The pharmaceutical sector expanded generics production capacity.",
    "A major tech conference will be held in Hyderabad next month.",
    "The food processing industry saw 15% growth year over year.",
    "Coastal erosion along the Konkan coast is a growing concern.",
    "UPI transactions volume continues to break monthly records.",
    "The automobile sector reported highest ever monthly sales.",
    "India signed a trade agreement with ASEAN nations.",
    "The fisheries sector showed robust growth in aquaculture.",
    "Solar panel installations doubled in the residential segment.",
]

examples = []

# ── SINGLE-ENTITY EXAMPLES ───────────────────────────────────────

# PERSON (20)
templates_person = [
    "Please contact {name} regarding the project update.",
    "{name} has been assigned as the new team lead.",
    "The document was signed by {name} on Monday.",
    "Forward this report to {name} for review.",
    "Meeting scheduled with {name} at 3 PM today.",
    "{name} submitted the quarterly performance review.",
    "Approval pending from {name} for budget allocation.",
    "Send the invoice copy to {name} immediately.",
    "{name} will be leading the client presentation.",
    "Verify the credentials of {name} before onboarding.",
]
for i in range(20):
    f,l = rand_name()
    name = f"{f} {l}"
    t = random.choice(templates_person).format(name=name)
    examples.append({"text": t, "expected_pii": [{"text": name, "type": "PERSON"}]})

# AADHAAR (20)
templates_aadhaar = [
    "My Aadhaar number is {aadhaar}.",
    "Please verify Aadhaar {aadhaar} for KYC.",
    "Aadhaar card showing {aadhaar} was submitted.",
    "Link Aadhaar {aadhaar} with the bank account.",
    "Update Aadhaar {aadhaar} in the system records.",
]
for i in range(20):
    a = rand_aadhaar()
    t = random.choice(templates_aadhaar).format(aadhaar=a)
    examples.append({"text": t, "expected_pii": [{"text": a, "type": "AADHAAR"}]})

# PAN (20)
templates_pan = [
    "PAN card number {pan} for tax filing.",
    "Please verify PAN {pan} in the records.",
    "Submit PAN {pan} for income tax return.",
    "PAN {pan} is linked to the demat account.",
    "Update PAN {pan} for the mutual fund folio.",
]
for i in range(20):
    p = rand_pan()
    t = random.choice(templates_pan).format(pan=p)
    examples.append({"text": t, "expected_pii": [{"text": p, "type": "PAN"}]})

# PHONE (20)
templates_phone = [
    "Call me at {phone} for further details.",
    "Reach out on {phone} during business hours.",
    "My mobile number is {phone}.",
    "Contact number: {phone} for delivery updates.",
    "Send OTP to {phone} for verification.",
]
for i in range(20):
    ph = rand_phone()
    t = random.choice(templates_phone).format(phone=ph)
    # only include if phone has prefix for reliable regex matching
    if ph.startswith("+91") or ph.startswith("0"):
        examples.append({"text": t, "expected_pii": [{"text": ph, "type": "PHONE"}]})
    else:
        examples.append({"text": t, "expected_pii": [{"text": ph, "type": "PHONE"}]})

# EMAIL (20)
templates_email = [
    "Send the documents to {email}.",
    "Email me at {email} for the contract.",
    "Reach me via {email} for queries.",
    "Confirmation will be sent to {email}.",
    "Reply to {email} with the signed copy.",
]
for i in range(20):
    e = rand_email()
    t = random.choice(templates_email).format(email=e)
    examples.append({"text": t, "expected_pii": [{"text": e, "type": "EMAIL"}]})

# CREDIT_CARD (15)
templates_cc = [
    "Credit card {cc} was used for the transaction.",
    "Card number {cc} has been flagged for fraud.",
    "Payment processed via card {cc}.",
    "Please verify card ending {cc}.",
    "Charge of Rs 5000 on card {cc}.",
]
for i in range(15):
    c = rand_cc()
    t = random.choice(templates_cc).format(cc=c)
    examples.append({"text": t, "expected_pii": [{"text": c, "type": "CREDIT_CARD"}]})

# IFSC (15)
templates_ifsc = [
    "Transfer to IFSC {ifsc} branch.",
    "Bank branch IFSC code: {ifsc}.",
    "NEFT transfer via {ifsc}.",
    "Verify IFSC {ifsc} for the beneficiary.",
    "RTGS payment to branch {ifsc}.",
]
for i in range(15):
    ifsc = rand_ifsc()
    t = random.choice(templates_ifsc).format(ifsc=ifsc)
    examples.append({"text": t, "expected_pii": [{"text": ifsc, "type": "IFSC"}]})

# UPI_ID (15)
templates_upi = [
    "Pay via UPI to {upi} for the order.",
    "UPI ID {upi} registered for refunds.",
    "Send payment to {upi}.",
    "Collect request from {upi}.",
    "UPI handle: {upi} for quick transfers.",
]
for i in range(15):
    u = rand_upi()
    t = random.choice(templates_upi).format(upi=u)
    examples.append({"text": t, "expected_pii": [{"text": u, "type": "UPI_ID"}]})

# PASSPORT (15)
templates_passport = [
    "Passport number {passport} for visa application.",
    "Submit passport {passport} copy for verification.",
    "Travel document: passport {passport}.",
    "Passport {passport} issued at RPO Delhi.",
    "Verify passport {passport} validity.",
]
for i in range(15):
    p = rand_passport()
    t = random.choice(templates_passport).format(passport=p)
    examples.append({"text": t, "expected_pii": [{"text": p, "type": "PASSPORT"}]})

# VOTER_ID (15)
templates_voter = [
    "Voter ID {vid} for identity proof.",
    "EPIC number {vid} submitted for KYC.",
    "Voter card {vid} is the address proof.",
    "Submit voter ID {vid} copy.",
    "Electoral ID: {vid} for verification.",
]
for i in range(15):
    v = rand_voter()
    t = random.choice(templates_voter).format(vid=v)
    examples.append({"text": t, "expected_pii": [{"text": v, "type": "VOTER_ID"}]})

# DRIVING_LICENCE (15)
templates_dl = [
    "Driving licence {dl} for address verification.",
    "DL number {dl} issued by RTO.",
    "Submit driving licence {dl} as ID proof.",
    "Licence {dl} is valid till 2030.",
    "Verify DL {dl} in the Parivahan portal.",
]
for i in range(15):
    d = rand_dl()
    t = random.choice(templates_dl).format(dl=d)
    examples.append({"text": t, "expected_pii": [{"text": d, "type": "DRIVING_LICENCE"}]})

# GSTIN (15)
templates_gstin = [
    "GSTIN {gstin} registered for the firm.",
    "GST number {gstin} for invoice generation.",
    "Verify GSTIN {gstin} on the portal.",
    "Tax filing under GSTIN {gstin}.",
    "Business registered with GSTIN {gstin}.",
]
for i in range(15):
    g = rand_gstin()
    t = random.choice(templates_gstin).format(gstin=g)
    examples.append({"text": t, "expected_pii": [{"text": g, "type": "GSTIN"}]})

# DOB (15)
templates_dob = [
    "Date of birth: {dob} as per records.",
    "DOB {dob} mentioned in the application.",
    "Born on {dob} according to the certificate.",
    "Verify date of birth {dob} for the policy.",
    "Applicant's DOB is {dob}.",
]
for i in range(15):
    d = rand_dob()
    t = random.choice(templates_dob).format(dob=d)
    examples.append({"text": t, "expected_pii": [{"text": d, "type": "DOB"}]})

# IP_ADDRESS (10)
templates_ip = [
    "Server at {ip} is running the deployment.",
    "Access logs show requests from {ip}.",
    "Block IP address {ip} in the firewall.",
    "Connection from {ip} was flagged.",
    "Database hosted at {ip} needs patching.",
]
for i in range(10):
    ip = rand_ip()
    t = random.choice(templates_ip).format(ip=ip)
    examples.append({"text": t, "expected_pii": [{"text": ip, "type": "IP_ADDRESS"}]})

# MEDICAL_RECORD (10)
templates_med = [
    "Patient record {mr} needs to be updated.",
    "Hospital ID {mr} assigned to the patient.",
    "Retrieve records for {mr}.",
    "Lab results filed under {mr}.",
    "Discharge summary for {mr} is ready.",
]
for i in range(10):
    m = rand_medical()
    t = random.choice(templates_med).format(mr=m)
    examples.append({"text": t, "expected_pii": [{"text": m, "type": "MEDICAL_RECORD"}]})

# ── MULTI-ENTITY EXAMPLES (30) ───────────────────────────────────
for i in range(30):
    f,l = rand_name()
    name = f"{f} {l}"
    pii_list = [{"text": name, "type": "PERSON"}]

    combo = random.randint(0,5)
    if combo == 0:
        a = rand_aadhaar(); p = rand_pan()
        t = f"{name}, Aadhaar {a}, PAN {p}, for KYC verification."
        pii_list += [{"text": a, "type": "AADHAAR"}, {"text": p, "type": "PAN"}]
    elif combo == 1:
        e = rand_email(); ph = rand_phone()
        if ph.startswith("+91"):
            t = f"Contact {name} at {e} or {ph}."
        else:
            t = f"Reach {name} via email {e} or call {ph}."
        pii_list += [{"text": e, "type": "EMAIL"}, {"text": ph, "type": "PHONE"}]
    elif combo == 2:
        dob = rand_dob(); a = rand_aadhaar()
        t = f"Patient {name}, DOB {dob}, Aadhaar {a}, admitted today."
        pii_list += [{"text": dob, "type": "DOB"}, {"text": a, "type": "AADHAAR"}]
    elif combo == 3:
        pp = rand_passport(); dl = rand_dl()
        t = f"{name}, passport {pp}, driving licence {dl}, for travel booking."
        pii_list += [{"text": pp, "type": "PASSPORT"}, {"text": dl, "type": "DRIVING_LICENCE"}]
    elif combo == 4:
        upi = rand_upi(); ph = rand_phone()
        t = f"Pay {name} via UPI {upi}, mobile {ph}."
        pii_list += [{"text": upi, "type": "UPI_ID"}, {"text": ph, "type": "PHONE"}]
    else:
        e = rand_email(); vid = rand_voter()
        t = f"Send to {name}, email {e}, voter ID {vid}."
        pii_list += [{"text": e, "type": "EMAIL"}, {"text": vid, "type": "VOTER_ID"}]

    examples.append({"text": t, "expected_pii": pii_list})

# ── NEGATIVE EXAMPLES (30) ───────────────────────────────────────
for neg in NEGATIVES:
    examples.append({"text": neg, "expected_pii": []})

# ── Shuffle and save ─────────────────────────────────────────────
random.shuffle(examples)
out_path = Path(__file__).resolve().parent.parent / "data" / "eval_set_300.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(examples, f, indent=2, ensure_ascii=False)

# Stats
from collections import Counter
type_counts = Counter()
for ex in examples:
    for p in ex["expected_pii"]:
        type_counts[p["type"]] += 1

total_entities = sum(type_counts.values())
neg_count = sum(1 for ex in examples if not ex["expected_pii"])

print(f"\n[OK] Generated {len(examples)} examples -> {out_path.name}")
print(f"   Total PII entities: {total_entities}")
print(f"   Negative (no-PII) examples: {neg_count}")
print(f"\n   Entity type distribution:")
for t, c in type_counts.most_common():
    print(f"     {t:<20} {c:>4}")
