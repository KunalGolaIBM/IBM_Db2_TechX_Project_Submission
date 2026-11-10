import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models import Department, Grievance, GrievanceUpdate

logger = logging.getLogger("uvicorn.error")

DEPARTMENTS_SEED: List[Dict[str, str]] = [
    {
        "code": "water",
        "name": "Delhi Jal Board / Ministry of Jal Shakti",
        "description": "Potable water supply, sewer pipeline maintenance, water meter billing, and contamination redressal.",
        "nodal_email": "nodal.water@gov.in"
    },
    {
        "code": "electricity",
        "name": "BSES / Tata Power / Ministry of Power",
        "description": "Grid stability, high/low voltage surges, transformer outages, street lighting, and smart meters.",
        "nodal_email": "nodal.power@gov.in"
    },
    {
        "code": "roads",
        "name": "Public Works Department (PWD) / Municipal Road Division",
        "description": "Pothole repair, road surfacing, flyover maintenance, drainage desilting, and road safety infrastructure.",
        "nodal_email": "nodal.roads@pwd.delhi.gov.in"
    },
    {
        "code": "sanitation",
        "name": "Municipal Corporation of Delhi (Sanitation Division)",
        "description": "Solid waste management, garbage collection, landfill management, drain cleaning, and public hygiene.",
        "nodal_email": "nodal.sanitation@mcd.gov.in"
    },
    {
        "code": "health",
        "name": "Directorate of Health Services / MoHFW",
        "description": "Public health clinics, essential medicine supply, dengue/malaria fogging, and hospital infrastructure.",
        "nodal_email": "nodal.health@gov.in"
    },
    {
        "code": "food",
        "name": "Department of Food, Supplies & Consumer Affairs",
        "description": "Public Distribution System (PDS), ration card verification, biometric FPS distribution, and grain quota.",
        "nodal_email": "nodal.food@delhi.gov.in"
    },
    {
        "code": "pension",
        "name": "Department of Social Welfare & Pension Welfare",
        "description": "Old age pension, disability pension, widow support schemes, and digital life certificate processing.",
        "nodal_email": "nodal.pension@gov.in"
    }
]

# 65 Realistic Indian Civic Grievance Seed Records
SEED_GRIEVANCES_DATA: List[Dict[str, Any]] = [
    # Demo grievance (matching static portal reference)
    {
        "tracking_id": "GRV-2026-4821",
        "citizen_name": "Amitabh Verma",
        "contact": "9876543210 / amitabh.verma@example.com",
        "category": "water",
        "subject": "Severe Drinking Water Supply Contamination in Sector 14",
        "description": "For the past 12 days, municipal tap water has been visibly muddy with sewage odor due to a cracked underground pipe. Over 150 households affected.",
        "ward": "Ward 14 - Rohini East",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 12,
        "dept_code": "water",
        "pincode": "110085",
        "lat": 28.7152,
        "lon": 77.1215
    },
    # WATER CATEGORY (10 items)
    {
        "tracking_id": "GRV-2026-1001",
        "citizen_name": "Rajesh Kumar Sharma",
        "contact": "9810123456 / rajesh.sharma@gmail.com",
        "category": "water",
        "subject": "Main pipeline burst flooding residential lane",
        "description": "A 12-inch cast iron water supply pipe fractured outside house 45B. Clean drinking water has been gushing out onto the road since 5 AM.",
        "ward": "Ward 01 - Civil Lines",
        "priority": "Critical",
        "status": "Forwarded to Dept",
        "days_ago": 3,
        "dept_code": "water",
        "pincode": "110054",
        "lat": 28.6811,
        "lon": 77.2228
    },
    {
        "tracking_id": "GRV-2026-1002",
        "citizen_name": "Sunita Aggarwal",
        "contact": "9811234567 / sunita.aggarwal@yahoo.co.in",
        "category": "water",
        "subject": "Erratic water supply with zero water pressure on 2nd floor",
        "description": "Morning water supply lasts barely 15 minutes with negligible pressure. Residents are forced to purchase commercial private tankers daily.",
        "ward": "Ward 07 - Chandni Chowk",
        "priority": "High",
        "status": "Under Review",
        "days_ago": 8,
        "dept_code": "water",
        "pincode": "110006",
        "lat": 28.6506,
        "lon": 77.2303
    },
    {
        "tracking_id": "GRV-2026-1003",
        "citizen_name": "Praveen Goel",
        "contact": "9818345678 / praveen.goel@rediffmail.com",
        "category": "water",
        "subject": "Defective smart water meter registering inflated billing",
        "description": "Water meter replaced last month generated a quarterly bill of Rs 48,000 for a 3-member family dwelling. Meter spinning continuously without flow.",
        "ward": "Ward 12 - Karol Bagh",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 28,
        "dept_code": "water",
        "pincode": "110005",
        "lat": 28.6550,
        "lon": 77.1912
    },
    {
        "tracking_id": "GRV-2026-1004",
        "citizen_name": "Meenakshi Sundaram",
        "contact": "9871456789 / m.sundaram@hotmail.com",
        "category": "water",
        "subject": "Community tube well motor burned out in pocket D",
        "description": "Submersible pump motor failed after voltage spike. 400 families dependent on this community borehole are without potable water.",
        "ward": "Ward 35 - Mayur Vihar Phase 1",
        "priority": "High",
        "status": "Forwarded to Dept",
        "days_ago": 5,
        "dept_code": "water",
        "pincode": "110091",
        "lat": 28.6083,
        "lon": 77.2964
    },
    {
        "tracking_id": "GRV-2026-1005",
        "citizen_name": "Harpreet Singh",
        "contact": "9899567890 / hsingh.delhi@outlook.com",
        "category": "water",
        "subject": "Sewage backflow into drinking water underground reservoir",
        "description": "Cross-contamination verified by local lab report showing high coliform count. Residents report acute gastroenteritis cases among children.",
        "ward": "Ward 62 - Janakpuri West",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 4,
        "dept_code": "water",
        "pincode": "110058",
        "lat": 28.6297,
        "lon": 77.0818
    },
    {
        "tracking_id": "GRV-2026-1006",
        "citizen_name": "Pooja Deshmukh",
        "contact": "9812678901 / pooja.d@gmail.com",
        "category": "water",
        "subject": "New water connection pending inspection for 60 days",
        "description": "All demand note fees paid on 8 Sep. Inspection officer has rescheduled three times without showing up.",
        "ward": "Ward 58 - Dwarka Sector 6",
        "priority": "Low",
        "status": "Filed",
        "days_ago": 2,
        "dept_code": "water",
        "pincode": "110075",
        "lat": 28.5921,
        "lon": 77.0648
    },
    {
        "tracking_id": "GRV-2026-1007",
        "citizen_name": "Mohammad Rizwan",
        "contact": "9820789012 / rizwan.m@yahoo.com",
        "category": "water",
        "subject": "Leakage in main sluice valve causing massive road puddle",
        "description": "Sluice valve valve chamber at intersection is overflowing. Water volume is causing asphalt decay and two-wheeler skids.",
        "ward": "Ward 67 - Okhla Industrial Area",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 35,
        "dept_code": "water",
        "pincode": "110020",
        "lat": 28.5307,
        "lon": 77.2711
    },
    {
        "tracking_id": "GRV-2026-1008",
        "citizen_name": "Deepak Bhatt",
        "contact": "9831890123 / bhatt.deepak@gmail.com",
        "category": "water",
        "subject": "Absence of scheduled water tanker supply in slum cluster",
        "description": "Designated DJB water tanker has skipped scheduled visits on Tuesday and Thursday. Daily wage workers forced to stand in queue for hours.",
        "ward": "Ward 80 - Mehrauli",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 22,
        "dept_code": "water",
        "pincode": "110030",
        "lat": 28.5177,
        "lon": 77.1856
    },
    {
        "tracking_id": "GRV-2026-1009",
        "citizen_name": "Geeta Rani",
        "contact": "9842901234 / geeta.rani@rediffmail.com",
        "category": "water",
        "subject": "Rusted galvanized iron pipelines supplying yellow water",
        "description": "Old municipal lines have rusted thoroughly. Water contains visible rust flakes and heavy sediment.",
        "ward": "Ward 72 - Shahdara North",
        "priority": "Medium",
        "status": "Under Review",
        "days_ago": 15,
        "dept_code": "water",
        "pincode": "110032",
        "lat": 28.6738,
        "lon": 77.2917
    },
    {
        "tracking_id": "GRV-2026-1010",
        "citizen_name": "Anil Talwar",
        "contact": "9853012345 / anil.talwar@gmail.com",
        "category": "water",
        "subject": "Missing inspection chamber cover on footpath water line",
        "description": "Cast iron cover was stolen. Open pit is 4 feet deep directly on pedestrian walkway, hazard for evening walkers.",
        "ward": "Ward 22 - Connaught Place",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 40,
        "dept_code": "water",
        "pincode": "110001",
        "lat": 28.6328,
        "lon": 77.2197
    },

    # ELECTRICITY CATEGORY (10 items)
    {
        "tracking_id": "GRV-2026-1011",
        "citizen_name": "Vikram Sen",
        "contact": "9864123456 / vikram.sen@gmail.com",
        "category": "electricity",
        "subject": "Frequent 400V high-voltage surges burning household appliances",
        "description": "Fluctuations yesterday damaged televisions and refrigerators across 12 flats in pocket 3. Voltage measuring 280V phase-to-neutral.",
        "ward": "Ward 18 - Pitampura",
        "priority": "Critical",
        "status": "Forwarded to Dept",
        "days_ago": 6,
        "dept_code": "electricity",
        "pincode": "110034",
        "lat": 28.6990,
        "lon": 77.1384
    },
    {
        "tracking_id": "GRV-2026-1012",
        "citizen_name": "Shalini Nair",
        "contact": "9875234567 / shalini.nair@corp.in",
        "category": "electricity",
        "subject": "Distribution transformer oil leakage and loud sparking",
        "description": "Pole-mounted 250kVA transformer has been smoking and leaking dielectric oil onto the pavement. Heavy sparks during peak load.",
        "ward": "Ward 42 - Hauz Khas",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 1,
        "dept_code": "electricity",
        "pincode": "110016",
        "lat": 28.5494,
        "lon": 77.2001
    },
    {
        "tracking_id": "GRV-2026-1013",
        "citizen_name": "Gopal Krishna",
        "contact": "9886345678 / gopal.krishna@gmail.com",
        "category": "electricity",
        "subject": "Dangling high-tension 11kV cable snapped near children park",
        "description": "Storm branch severed overhead line, dangling 4 feet above ground level near MCD primary school gate.",
        "ward": "Ward 85 - Najafgarh",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 18,
        "dept_code": "electricity",
        "pincode": "110043",
        "lat": 28.6092,
        "lon": 76.9798
    },
    {
        "tracking_id": "GRV-2026-1014",
        "citizen_name": "Ritu Kapoor",
        "contact": "9897456789 / ritu.kapoor@gmail.com",
        "category": "electricity",
        "subject": "Entire residential block streetlights defunct for 3 weeks",
        "description": "All 18 sodium vapor streetlights on Marg 4 are non-operational. Paved area is pitch dark leading to multiple chain-snatching attempts.",
        "ward": "Ward 49 - Greater Kailash",
        "priority": "High",
        "status": "Forwarded to Dept",
        "days_ago": 11,
        "dept_code": "electricity",
        "pincode": "110048",
        "lat": 28.5367,
        "lon": 77.2410
    },
    {
        "tracking_id": "GRV-2026-1015",
        "citizen_name": "Sanjay Chawla",
        "contact": "9818567890 / schawla@rediffmail.com",
        "category": "electricity",
        "subject": "Incorrect meter reading leading to provisional penalty bill",
        "description": "Meter reader billed on estimated basis without physical inspection despite meter being mounted on external boundary wall.",
        "ward": "Ward 53 - Lajpat Nagar",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 45,
        "dept_code": "electricity",
        "pincode": "110024",
        "lat": 28.5677,
        "lon": 77.2433
    },
    {
        "tracking_id": "GRV-2026-1016",
        "citizen_name": "Nandita Joshi",
        "contact": "9829678901 / njoshi@gmail.com",
        "category": "electricity",
        "subject": "Unscheduled 6-hour power cuts daily in industrial estate",
        "description": "Small manufacturing units facing huge losses due to unnotified load shedding during morning shift.",
        "ward": "Ward 67 - Okhla Industrial Area",
        "priority": "High",
        "status": "Under Review",
        "days_ago": 7,
        "dept_code": "electricity",
        "pincode": "110020",
        "lat": 28.5307,
        "lon": 77.2711
    },
    {
        "tracking_id": "GRV-2026-1017",
        "citizen_name": "Kishore Pandey",
        "contact": "9830789012 / kishore.p@live.com",
        "category": "electricity",
        "subject": "Substation feeder trip causing phase drop in C-block",
        "description": "Two phases out of three have zero supply. Single phase cannot run fans or lights in the entire lane.",
        "ward": "Ward 28 - Patel Nagar",
        "priority": "High",
        "status": "Filed",
        "days_ago": 1,
        "dept_code": "electricity",
        "pincode": "110008",
        "lat": 28.6577,
        "lon": 77.1654
    },
    {
        "tracking_id": "GRV-2026-1018",
        "citizen_name": "Brijesh Mishra",
        "contact": "9841890123 / bmishra@delhi.in",
        "category": "electricity",
        "subject": "Underground LT cable punctured during optical fiber digging",
        "description": "Telecom agency trenching dug through DISCOM 415V LT feeder cable, knocking out power to 22 residences.",
        "ward": "Ward 14 - Rohini East",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 26,
        "dept_code": "electricity",
        "pincode": "110085",
        "lat": 28.7152,
        "lon": 77.1215
    },
    {
        "tracking_id": "GRV-2026-1019",
        "citizen_name": "Farhan Akhtar",
        "contact": "9852901234 / farhan.akhtar@gmail.com",
        "category": "electricity",
        "subject": "Solar net metering subsidy and bi-directional meter pending",
        "description": "Rooftop solar 5kW system installed and passed CEIG test on 14 Aug. DISCOM has not replaced the bi-directional export meter.",
        "ward": "Ward 35 - Mayur Vihar Phase 1",
        "priority": "Low",
        "status": "Forwarded to Dept",
        "days_ago": 19,
        "dept_code": "electricity",
        "pincode": "110091",
        "lat": 28.6083,
        "lon": 77.2964
    },
    {
        "tracking_id": "GRV-2026-1020",
        "citizen_name": "Manju Sethi",
        "contact": "9863012345 / manju.sethi@gmail.com",
        "category": "electricity",
        "subject": "Meter junction box door broken leaving busbars exposed",
        "description": "Rain water enters junction box on building stilt wall. Shocks felt on metallic staircase railing.",
        "ward": "Ward 12 - Karol Bagh",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 52,
        "dept_code": "electricity",
        "pincode": "110005",
        "lat": 28.6550,
        "lon": 77.1912
    },

    # ROADS CATEGORY (10 items)
    {
        "tracking_id": "GRV-2026-1021",
        "citizen_name": "Kavita Mehra",
        "contact": "9874123456 / kavita.m@gmail.com",
        "category": "roads",
        "subject": "Deep 2-foot crater pothole causing vehicle damage",
        "description": "Pothole near metro pillar 142 on main Outer Ring Road has damaged several rims and caused 3 motorcycle accidents.",
        "ward": "Ward 18 - Pitampura",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 5,
        "dept_code": "roads",
        "pincode": "110034",
        "lat": 28.6990,
        "lon": 77.1384
    },
    {
        "tracking_id": "GRV-2026-1022",
        "citizen_name": "Dharmendra Yadav",
        "contact": "9885234567 / dyadav.trans@gmail.com",
        "category": "roads",
        "subject": "Road cave-in following stormwater drain collapse",
        "description": "A 10-meter stretch of the left carriage-way has caved in by 18 inches. Traffic congested for over 2 kilometers.",
        "ward": "Ward 62 - Janakpuri West",
        "priority": "Critical",
        "status": "Forwarded to Dept",
        "days_ago": 3,
        "dept_code": "roads",
        "pincode": "110058",
        "lat": 28.6297,
        "lon": 77.0818
    },
    {
        "tracking_id": "GRV-2026-1023",
        "citizen_name": "Alok Srivastava",
        "contact": "9896345678 / alok.sri@yahoo.co.in",
        "category": "roads",
        "subject": "Unfinished road resurfacing leaving loose bitumen gravel",
        "description": "Contractor dumped blue gravel and tar 3 weeks ago without rolling. Loose gravel causes two-wheelers to slip during braking.",
        "ward": "Ward 58 - Dwarka Sector 6",
        "priority": "High",
        "status": "Under Review",
        "days_ago": 14,
        "dept_code": "roads",
        "pincode": "110075",
        "lat": 28.5921,
        "lon": 77.0648
    },
    {
        "tracking_id": "GRV-2026-1024",
        "citizen_name": "Zubair Hashmi",
        "contact": "9817456789 / zubair.h@outlook.com",
        "category": "roads",
        "subject": "Missing manhole cover on central carriageway",
        "description": "Open manhole covered only with a tree branch. Extremely hazardous for night commuters.",
        "ward": "Ward 07 - Chandni Chowk",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 31,
        "dept_code": "roads",
        "pincode": "110006",
        "lat": 28.6506,
        "lon": 77.2303
    },
    {
        "tracking_id": "GRV-2026-1025",
        "citizen_name": "Naveen Chawla",
        "contact": "9828567890 / nchawla@gmail.com",
        "category": "roads",
        "subject": "Absence of zebra crossing and speed breakers near hospital",
        "description": "Vehicles speed at 70 km/h outside Maharaja Agrasen Hospital. Senior citizens unable to cross the multi-lane road.",
        "ward": "Ward 28 - Patel Nagar",
        "priority": "Medium",
        "status": "Filed",
        "days_ago": 2,
        "dept_code": "roads",
        "pincode": "110008",
        "lat": 28.6577,
        "lon": 77.1654
    },
    {
        "tracking_id": "GRV-2026-1026",
        "citizen_name": "Tanya Singhal",
        "contact": "9839678901 / tanya.singhal@live.com",
        "category": "roads",
        "subject": "Pedestrian foot-overbridge elevator out of order",
        "description": "Both lifts at the FOB on Ring Road near South Extension are broken, forcing disabled citizens to navigate steep 60 stairs.",
        "ward": "Ward 53 - Lajpat Nagar",
        "priority": "Medium",
        "status": "Forwarded to Dept",
        "days_ago": 9,
        "dept_code": "roads",
        "pincode": "110024",
        "lat": 28.5677,
        "lon": 77.2433
    },
    {
        "tracking_id": "GRV-2026-1027",
        "citizen_name": "Mahesh Chand",
        "contact": "9840789012 / mchand@gmail.com",
        "category": "roads",
        "subject": "Waterlogged road under railway underpass after light rain",
        "description": "Drain pumps at the railway underbridge failed, submerging the road in 3 feet water and stranding cars.",
        "ward": "Ward 72 - Shahdara North",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 44,
        "dept_code": "roads",
        "pincode": "110032",
        "lat": 28.6738,
        "lon": 77.2917
    },
    {
        "tracking_id": "GRV-2026-1028",
        "citizen_name": "Ashok Khurana",
        "contact": "9851890123 / akhurana@yahoo.co.in",
        "category": "roads",
        "subject": "Encroachment on main service lane by unauthorized workshops",
        "description": "Automobile repair garages have occupied 70% of public road width with damaged scrap cars.",
        "ward": "Ward 35 - Mayur Vihar Phase 1",
        "priority": "Medium",
        "status": "Under Review",
        "days_ago": 21,
        "dept_code": "roads",
        "pincode": "110091",
        "lat": 28.6083,
        "lon": 77.2964
    },
    {
        "tracking_id": "GRV-2026-1029",
        "citizen_name": "Rekha Mathur",
        "contact": "9862901234 / rmathur@gmail.com",
        "category": "roads",
        "subject": "Broken concrete pavement slabs causing tripping hazard",
        "description": "Interlocking pavers cracked and protruding along commercial market corridor.",
        "ward": "Ward 42 - Hauz Khas",
        "priority": "Low",
        "status": "Resolved",
        "days_ago": 38,
        "dept_code": "roads",
        "pincode": "110016",
        "lat": 28.5494,
        "lon": 77.2001
    },
    {
        "tracking_id": "GRV-2026-1030",
        "citizen_name": "Kailash Narang",
        "contact": "9873012345 / knarang@gmail.com",
        "category": "roads",
        "subject": "Non-functional traffic signal at major 4-way intersection",
        "description": "Signal light cycling between green and dead black. Major gridlock during peak school transit hours.",
        "ward": "Ward 01 - Civil Lines",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 16,
        "dept_code": "roads",
        "pincode": "110054",
        "lat": 28.6811,
        "lon": 77.2228
    },

    # SANITATION CATEGORY (10 items)
    {
        "tracking_id": "GRV-2026-1031",
        "citizen_name": "Shyam Sunder",
        "contact": "9884123456 / ssunder@gmail.com",
        "category": "sanitation",
        "subject": "Municipal garbage dhalao overflowing onto arterial road",
        "description": "MCD waste compactor has not visited dhalao for 6 days. Solid waste spilling over 50 meters, attracting stray cattle and foul odor.",
        "ward": "Ward 04 - Timarpur",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 6,
        "dept_code": "sanitation",
        "pincode": "110054",
        "lat": 28.7011,
        "lon": 77.2185
    },
    {
        "tracking_id": "GRV-2026-1032",
        "citizen_name": "Vandana Bajaj",
        "contact": "9895234567 / vbajaj@yahoo.com",
        "category": "sanitation",
        "subject": "Choked underground sewer overflowing into market basements",
        "description": "Main commercial lane sewer backed up. Stagnant sewage water entered basement shops causing commercial inventory damage.",
        "ward": "Ward 12 - Karol Bagh",
        "priority": "Critical",
        "status": "Forwarded to Dept",
        "days_ago": 2,
        "dept_code": "sanitation",
        "pincode": "110005",
        "lat": 28.6550,
        "lon": 77.1912
    },
    {
        "tracking_id": "GRV-2026-1033",
        "citizen_name": "Balram Das",
        "contact": "9816345678 / bdas.delhi@gmail.com",
        "category": "sanitation",
        "subject": "Illegal open dumping and burning of plastic scrap",
        "description": "Unauthorized plastic waste segregation unit burns residual PVC wires nightly at 11 PM, releasing toxic fumes.",
        "ward": "Ward 67 - Okhla Industrial Area",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 4,
        "dept_code": "sanitation",
        "pincode": "110020",
        "lat": 28.5307,
        "lon": 77.2711
    },
    {
        "tracking_id": "GRV-2026-1034",
        "citizen_name": "Neelam Saxena",
        "contact": "9827456789 / nsaxena@rediffmail.com",
        "category": "sanitation",
        "subject": "Community public toilet complex locked and unmaintained",
        "description": "MCD toilet block built 2 years ago has been locked for 3 months due to lack of sanitation attendant and water connection.",
        "ward": "Ward 80 - Mehrauli",
        "priority": "High",
        "status": "Forwarded to Dept",
        "days_ago": 13,
        "dept_code": "sanitation",
        "pincode": "110030",
        "lat": 28.5177,
        "lon": 77.1856
    },
    {
        "tracking_id": "GRV-2026-1035",
        "citizen_name": "Jasbir Sodhi",
        "contact": "9838567890 / jsodhi@gmail.com",
        "category": "sanitation",
        "subject": "Door-to-door waste collection tipper vehicle skipping colony",
        "description": "MCD green/blue tipper auto has not entered Block C for 10 days. Residents forced to dump garbage in open plots.",
        "ward": "Ward 14 - Rohini East",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 29,
        "dept_code": "sanitation",
        "pincode": "110085",
        "lat": 28.7152,
        "lon": 77.1215
    },
    {
        "tracking_id": "GRV-2026-1036",
        "citizen_name": "Ananya Sen",
        "contact": "9849678901 / ananya.sen@gmail.com",
        "category": "sanitation",
        "subject": "Stormwater drain blocked with construction debris",
        "description": "Builders dumped concrete debris into open drain canal, blocking runoff and creating stagnant mosquito breeding grounds.",
        "ward": "Ward 49 - Greater Kailash",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 33,
        "dept_code": "sanitation",
        "pincode": "110048",
        "lat": 28.5367,
        "lon": 77.2410
    },
    {
        "tracking_id": "GRV-2026-1037",
        "citizen_name": "Chetan Anand",
        "contact": "9850789012 / canand@outlook.com",
        "category": "sanitation",
        "subject": "Dead animal carcass not removed despite 24h complaint",
        "description": "Stray dog carcass lying on sidewalk near park gate. Health hazard and intolerable smell.",
        "ward": "Ward 18 - Pitampura",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 20,
        "dept_code": "sanitation",
        "pincode": "110034",
        "lat": 28.6990,
        "lon": 77.1384
    },
    {
        "tracking_id": "GRV-2026-1038",
        "citizen_name": "Urmila Devi",
        "contact": "9861890123 / urmila.d@gmail.com",
        "category": "sanitation",
        "subject": "Absence of dustbins in weekly Sunday market ground",
        "description": "Vegetable and plastic waste left behind after weekly haat attracts packs of feral dogs and vultures.",
        "ward": "Ward 85 - Najafgarh",
        "priority": "Low",
        "status": "Filed",
        "days_ago": 2,
        "dept_code": "sanitation",
        "pincode": "110043",
        "lat": 28.6092,
        "lon": 76.9798
    },
    {
        "tracking_id": "GRV-2026-1039",
        "citizen_name": "Sudhir Aggarwal",
        "contact": "9872901234 / saggarwal@gmail.com",
        "category": "sanitation",
        "subject": "Manual scavenging activity observed on main trunk sewer",
        "description": "Private contractor seen employing workers without mechanized super-sucker equipment or safety gear. Immediate intervention needed.",
        "ward": "Ward 72 - Shahdara North",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 7,
        "dept_code": "sanitation",
        "pincode": "110032",
        "lat": 28.6738,
        "lon": 77.2917
    },
    {
        "tracking_id": "GRV-2026-1040",
        "citizen_name": "Priyanka Roy",
        "contact": "9883012345 / proy@gmail.com",
        "category": "sanitation",
        "subject": "Stagnant drainage pool near municipal primary school",
        "description": "Ditch accumulated green sewage water 20 feet from nursery school classroom. Extreme mosquito proliferation.",
        "ward": "Ward 35 - Mayur Vihar Phase 1",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 48,
        "dept_code": "sanitation",
        "pincode": "110091",
        "lat": 28.6083,
        "lon": 77.2964
    },

    # HEALTH CATEGORY (10 items)
    {
        "tracking_id": "GRV-2026-1041",
        "citizen_name": "Dr. Vinod Sehgal",
        "contact": "9894123456 / dr.vsehgal@gmail.com",
        "category": "health",
        "subject": "Acute shortage of anti-rabies vaccine at Primary Health Center",
        "description": "Civil Lines dispensary has had zero rabies vaccines for 3 weeks. Dog bite victims directed to Safdarjung Hospital 18 km away.",
        "ward": "Ward 01 - Civil Lines",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 5,
        "dept_code": "health",
        "pincode": "110054",
        "lat": 28.6811,
        "lon": 77.2228
    },
    {
        "tracking_id": "GRV-2026-1042",
        "citizen_name": "Kamla Rawat",
        "contact": "9815234567 / kamla.rawat@yahoo.com",
        "category": "health",
        "subject": "Mohalla Clinic doctor absent during published morning hours",
        "description": "Clinic displays timing 8 AM to 2 PM, but doctor arrives after 11:30 AM. Elderly patients forced to wait in heat.",
        "ward": "Ward 04 - Timarpur",
        "priority": "Medium",
        "status": "Forwarded to Dept",
        "days_ago": 10,
        "dept_code": "health",
        "pincode": "110054",
        "lat": 28.7011,
        "lon": 77.2185
    },
    {
        "tracking_id": "GRV-2026-1043",
        "citizen_name": "Subhash Chandra",
        "contact": "9826345678 / subhash.c@gmail.com",
        "category": "health",
        "subject": "Ultrasound and X-ray machine broken at polyclinic for 2 months",
        "description": "Radiology department non-functional. Pregnant women and fracture patients forced to visit private diagnostic labs charging high rates.",
        "ward": "Ward 62 - Janakpuri West",
        "priority": "High",
        "status": "Under Review",
        "days_ago": 16,
        "dept_code": "health",
        "pincode": "110058",
        "lat": 28.6297,
        "lon": 77.0818
    },
    {
        "tracking_id": "GRV-2026-1044",
        "citizen_name": "Anita Deshmukh",
        "contact": "9837456789 / anita.desh@gmail.com",
        "category": "health",
        "subject": "Dengue outbreak in ward: No anti-larval spray or fogging",
        "description": "Over 14 dengue cases diagnosed in pocket B within 10 days. MCD malaria inspector has not carried out chemical thermal fogging.",
        "ward": "Ward 58 - Dwarka Sector 6",
        "priority": "Critical",
        "status": "Forwarded to Dept",
        "days_ago": 4,
        "dept_code": "health",
        "pincode": "110075",
        "lat": 28.5921,
        "lon": 77.0648
    },
    {
        "tracking_id": "GRV-2026-1045",
        "citizen_name": "Manish Tiwari",
        "contact": "9848567890 / mtiwari@gmail.com",
        "category": "health",
        "subject": "Non-availability of free essential diabetes & BP medicines",
        "description": "Jan Aushadhi store attached to government dispensary running out of Metformin and Amlodipine regularly.",
        "ward": "Ward 28 - Patel Nagar",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 36,
        "dept_code": "health",
        "pincode": "110008",
        "lat": 28.6577,
        "lon": 77.1654
    },
    {
        "tracking_id": "GRV-2026-1046",
        "citizen_name": "Sultana Begum",
        "contact": "9859678901 / sultana.b@gmail.com",
        "category": "health",
        "subject": "Ambulance 102 response delay of 90 minutes for maternity labor",
        "description": "Emergency vehicle dispatched from 22 km away instead of local zonal hospital depot. Mother had to be transported in e-rickshaw.",
        "ward": "Ward 07 - Chandni Chowk",
        "priority": "Critical",
        "status": "Resolved",
        "days_ago": 25,
        "dept_code": "health",
        "pincode": "110006",
        "lat": 28.6506,
        "lon": 77.2303
    },
    {
        "tracking_id": "GRV-2026-1047",
        "citizen_name": "Yogesh Vohra",
        "contact": "9860789012 / yvohra@gmail.com",
        "category": "health",
        "subject": "Bio-medical waste discarded in open community municipal bin",
        "description": "Used syringes, blood sample vials, and saline drip sets from nursing home found dumped in public dustbin.",
        "ward": "Ward 42 - Hauz Khas",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 3,
        "dept_code": "health",
        "pincode": "110016",
        "lat": 28.5494,
        "lon": 77.2001
    },
    {
        "tracking_id": "GRV-2026-1048",
        "citizen_name": "Lata Krishnan",
        "contact": "9871890123 / lata.k@gmail.com",
        "category": "health",
        "subject": "Food adulteration in sweet shop: No response from food safety wing",
        "description": "Sample of mawa tested positive for synthetic starch. Formal complaint lodged with FSSAI Delhi branch on 12 Oct has seen zero action.",
        "ward": "Ward 53 - Lajpat Nagar",
        "priority": "Medium",
        "status": "Filed",
        "days_ago": 1,
        "dept_code": "health",
        "pincode": "110024",
        "lat": 28.5677,
        "lon": 77.2433
    },
    {
        "tracking_id": "GRV-2026-1049",
        "citizen_name": "Kishan Lal",
        "contact": "9882901234 / klal@gmail.com",
        "category": "health",
        "subject": "Ayushman Bharat Golden Card e-KYC rejection due to name mismatch",
        "description": "Hospital refusal to admit under PM-JAY scheme due to spelling variance between Aadhaar and ration card database.",
        "ward": "Ward 85 - Najafgarh",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 41,
        "dept_code": "health",
        "pincode": "110043",
        "lat": 28.6092,
        "lon": 76.9798
    },
    {
        "tracking_id": "GRV-2026-1050",
        "citizen_name": "Swati Mukherjee",
        "contact": "9893012345 / swati.m@gmail.com",
        "category": "health",
        "subject": "Lack of disabled ramp and wheelchair at maternity center",
        "description": "Entrance has 5 tall steps without handrail or ramp. Pregnant patients and wheelchair users struggle to enter.",
        "ward": "Ward 49 - Greater Kailash",
        "priority": "Low",
        "status": "Resolved",
        "days_ago": 55,
        "dept_code": "health",
        "pincode": "110048",
        "lat": 28.5367,
        "lon": 77.2410
    },

    # PUBLIC DISTRIBUTION / FOOD CATEGORY (8 items)
    {
        "tracking_id": "GRV-2026-1051",
        "citizen_name": "Munni Devi",
        "contact": "9814123456 / munni.devi@gmail.com",
        "category": "food",
        "subject": "Fair Price Shop dealer under-weighing ration quota by 2 kg per family",
        "description": "FPS Shop #3412 provides only 3 kg grain per member instead of 5 kg entitlement under National Food Security Act (NFSA).",
        "ward": "Ward 04 - Timarpur",
        "priority": "High",
        "status": "Under Review",
        "days_ago": 8,
        "dept_code": "food",
        "pincode": "110054",
        "lat": 28.7011,
        "lon": 77.2185
    },
    {
        "tracking_id": "GRV-2026-1052",
        "citizen_name": "Ram Prasad",
        "contact": "9825234567 / ramprasad@gmail.com",
        "category": "food",
        "subject": "e-PoS biometric fingerprint machine constantly malfunctioning",
        "description": "Elderly labor beneficiaries unable to register fingerprint on old optical scanner. FPS owner refuses manual OTP authentication.",
        "ward": "Ward 85 - Najafgarh",
        "priority": "High",
        "status": "Forwarded to Dept",
        "days_ago": 12,
        "dept_code": "food",
        "pincode": "110043",
        "lat": 28.6092,
        "lon": 76.9798
    },
    {
        "tracking_id": "GRV-2026-1053",
        "citizen_name": "Shabana Bano",
        "contact": "9836345678 / shabana.b@gmail.com",
        "category": "food",
        "subject": "Delay in new digital ration card issuance after field verification",
        "description": "Application submitted 4 months ago. Verification marked complete on portal, but physical/digital card not approved by Food Supply Officer.",
        "ward": "Ward 07 - Chandni Chowk",
        "priority": "Medium",
        "status": "Under Review",
        "days_ago": 20,
        "dept_code": "food",
        "pincode": "110006",
        "lat": 28.6506,
        "lon": 77.2303
    },
    {
        "tracking_id": "GRV-2026-1054",
        "citizen_name": "Jagdish Chandra",
        "contact": "9847456789 / jchandra@gmail.com",
        "category": "food",
        "subject": "Poor quality wheat with weevil infestation supplied at PDS outlet",
        "description": "Food grains distributed for October contains heavy husk, stone particles, and live weevil pests. Unfit for human consumption.",
        "ward": "Ward 72 - Shahdara North",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 30,
        "dept_code": "food",
        "pincode": "110032",
        "lat": 28.6738,
        "lon": 77.2917
    },
    {
        "tracking_id": "GRV-2026-1055",
        "citizen_name": "Basanti Bai",
        "contact": "9858567890 / basanti@gmail.com",
        "category": "food",
        "subject": "Fair Price Shop remains closed for 25 days in a month",
        "description": "Dealer opens outlet only on arbitrary days without advance notice, resulting in expiry of monthly allotment for poor families.",
        "ward": "Ward 80 - Mehrauli",
        "priority": "Critical",
        "status": "Forwarded to Dept",
        "days_ago": 6,
        "dept_code": "food",
        "pincode": "110030",
        "lat": 28.5177,
        "lon": 77.1856
    },
    {
        "tracking_id": "GRV-2026-1056",
        "citizen_name": "Kailash Chand",
        "contact": "9869678901 / kchand@gmail.com",
        "category": "food",
        "subject": "One Nation One Ration Card porting failure from Bihar to Delhi",
        "description": "Migrant construction worker denied ration porting despite active NFSA ration card from District Samastipur.",
        "ward": "Ward 67 - Okhla Industrial Area",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 37,
        "dept_code": "food",
        "pincode": "110020",
        "lat": 28.5307,
        "lon": 77.2711
    },
    {
        "tracking_id": "GRV-2026-1057",
        "citizen_name": "Savita Sharma",
        "contact": "9870789012 / savita.s@gmail.com",
        "category": "food",
        "subject": "Unauthorized fee demanded for laminated ration card booklet",
        "description": "Staff at circular food office demanding Rs 250 cash for printing physical duplicate card.",
        "ward": "Ward 14 - Rohini East",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 46,
        "dept_code": "food",
        "pincode": "110085",
        "lat": 28.7152,
        "lon": 77.1215
    },
    {
        "tracking_id": "GRV-2026-1058",
        "citizen_name": "Dinesh Gupta",
        "contact": "9881890123 / dgupta@gmail.com",
        "category": "food",
        "subject": "LPG subsidy not credited to linked bank account for 5 refills",
        "description": "DBTL subsidy missing since domestic cylinder purchase in June despite active Aadhaar-NPCI mapping.",
        "ward": "Ward 18 - Pitampura",
        "priority": "Low",
        "status": "Filed",
        "days_ago": 2,
        "dept_code": "food",
        "pincode": "110034",
        "lat": 28.6990,
        "lon": 77.1384
    },

    # PENSION & SOCIAL WELFARE CATEGORY (7 items)
    {
        "tracking_id": "GRV-2026-1059",
        "citizen_name": "Somnath Mukherjee",
        "contact": "9892123456 / somnath.m@gmail.com",
        "category": "pension",
        "subject": "Old Age pension disbursement stopped without notice for 4 months",
        "description": "78-year-old pensioner submitted Jeevan Pramaan digital life certificate successfully in November, but DBT credits stopped.",
        "ward": "Ward 01 - Civil Lines",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 14,
        "dept_code": "pension",
        "pincode": "110054",
        "lat": 28.6811,
        "lon": 77.2228
    },
    {
        "tracking_id": "GRV-2026-1060",
        "citizen_name": "Vidya Dhar Sharma",
        "contact": "9813234567 / vdsharma@yahoo.com",
        "category": "pension",
        "subject": "Delay in revision of 7th Pay Commission arrears calculation",
        "description": "Pension Payment Order (PPO #DL/PEN/48291) revision pending with Pay & Accounts Office since February.",
        "ward": "Ward 22 - Connaught Place",
        "priority": "Medium",
        "status": "Forwarded to Dept",
        "days_ago": 18,
        "dept_code": "pension",
        "pincode": "110001",
        "lat": 28.6328,
        "lon": 77.2197
    },
    {
        "tracking_id": "GRV-2026-1061",
        "citizen_name": "Champa Devi",
        "contact": "9824345678 / champa.d@gmail.com",
        "category": "pension",
        "subject": "Widow pension application pending verification for 180 days",
        "description": "Widow financial assistance application filed at District Social Welfare Office after spouse passing has not been processed.",
        "ward": "Ward 85 - Najafgarh",
        "priority": "High",
        "status": "Under Review",
        "days_ago": 9,
        "dept_code": "pension",
        "pincode": "110043",
        "lat": 28.6092,
        "lon": 76.9798
    },
    {
        "tracking_id": "GRV-2026-1062",
        "citizen_name": "Surjit Kaur",
        "contact": "9835456789 / surjit.k@gmail.com",
        "category": "pension",
        "subject": "Disability pension discontinued due to bank merger IFSC error",
        "description": "Corporation Bank merged into Union Bank. IFSC update was communicated to social welfare branch but credits bouncing.",
        "ward": "Ward 62 - Janakpuri West",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 32,
        "dept_code": "pension",
        "pincode": "110058",
        "lat": 28.6297,
        "lon": 77.0818
    },
    {
        "tracking_id": "GRV-2026-1063",
        "citizen_name": "Mahender Nath",
        "contact": "9846567890 / mnath@gmail.com",
        "category": "pension",
        "subject": "Commutation deduction continuing past the mandated 15-year period",
        "description": "Commuted portion of pension completed 15 years on 31 August 2026. Bank still making monthly recovery deduction of Rs 6,400.",
        "ward": "Ward 58 - Dwarka Sector 6",
        "priority": "Medium",
        "status": "Resolved",
        "days_ago": 50,
        "dept_code": "pension",
        "pincode": "110075",
        "lat": 28.5921,
        "lon": 77.0648
    },
    {
        "tracking_id": "GRV-2026-1064",
        "citizen_name": "Gurcharan Singh",
        "contact": "9857678901 / gsingh.delhi@gmail.com",
        "category": "pension",
        "subject": "Life certificate biometric facial recognition failure",
        "description": "85-year-old bedridden veteran unable to complete iris or face authentication on Jeevan Pramaan Android app.",
        "ward": "Ward 12 - Karol Bagh",
        "priority": "High",
        "status": "Resolved",
        "days_ago": 24,
        "dept_code": "pension",
        "pincode": "110005",
        "lat": 28.6550,
        "lon": 77.1912
    },
    {
        "tracking_id": "GRV-2026-1065",
        "citizen_name": "Sarla Saxena",
        "contact": "9868789012 / sarla.s@gmail.com",
        "category": "pension",
        "subject": "Family pension transfer delayed after death of primary pensioner",
        "description": "Form 14 and death certificate submitted to CPPC on 15 July. Pensioner account remains frozen without survivor benefits.",
        "ward": "Ward 28 - Patel Nagar",
        "priority": "Critical",
        "status": "Under Review",
        "days_ago": 11,
        "dept_code": "pension",
        "pincode": "110008",
        "lat": 28.6577,
        "lon": 77.1654
    }
]


def seed_departments(db: Session) -> Dict[str, int]:
    """
    Inserts departments if not present, returns mapping of code -> id
    """
    dept_map: Dict[str, int] = {}
    for d_data in DEPARTMENTS_SEED:
        existing = db.query(Department).filter(Department.code == d_data["code"]).first()
        if not existing:
            dept = Department(
                code=d_data["code"],
                name=d_data["name"],
                description=d_data["description"],
                nodal_email=d_data["nodal_email"],
                created_at=datetime.utcnow() - timedelta(days=90)
            )
            db.add(dept)
            db.flush()
            dept_map[d_data["code"]] = dept.id
        else:
            dept_map[d_data["code"]] = existing.id
    db.commit()
    return dept_map


def seed_grievances(db: Session):
    """
    Populates at least 65 realistic Indian civic grievances with rich status timeline
    """
    dept_map = seed_departments(db)
    existing_count = db.query(Grievance).count()
    if existing_count >= len(SEED_GRIEVANCES_DATA):
        logger.info(f"Database already populated with {existing_count} grievances. Skipping seed.")
        return existing_count

    now = datetime.utcnow()
    added_count = 0

    for item in SEED_GRIEVANCES_DATA:
        existing = db.query(Grievance).filter(Grievance.tracking_id == item["tracking_id"]).first()
        if existing:
            continue

        created_dt = now - timedelta(days=item["days_ago"], hours=item["days_ago"] % 12, minutes=item["days_ago"] * 3 % 60)
        resolved_dt = None
        if item["status"] == "Resolved":
            resolved_dt = created_dt + timedelta(days=min(item["days_ago"] - 1, 15), hours=4)

        dept_id = dept_map.get(item.get("dept_code", "water"))

        grv = Grievance(
            tracking_id=item["tracking_id"],
            citizen_name=item["citizen_name"],
            contact=item["contact"],
            category=item["category"],
            subject=item["subject"],
            description=item["description"],
            ward=item["ward"],
            priority=item["priority"],
            status=item["status"],
            created_at=created_dt,
            resolved_at=resolved_dt,
            department_id=dept_id,
            state="Delhi (NCT)",
            pincode=item.get("pincode", "110001"),
            latitude=item.get("lat"),
            longitude=item.get("lon")
        )
        db.add(grv)
        db.flush()

        # Build realistic audit timeline in grievance_updates table
        # 1. Always initial "Filed"
        upd1 = GrievanceUpdate(
            grievance_id=grv.id,
            previous_status=None,
            new_status="Filed",
            notes=f"Grievance officially registered via CPGRAMS Portal. Token #{grv.tracking_id} generated.",
            updated_by="Citizen Self-Service",
            created_at=created_dt
        )
        db.add(upd1)

        # 2. If Under Review, Forwarded, or Resolved -> add Under Review step
        if item["status"] in ["Under Review", "Forwarded to Dept", "Resolved"]:
            review_dt = created_dt + timedelta(hours=18)
            upd2 = GrievanceUpdate(
                grievance_id=grv.id,
                previous_status="Filed",
                new_status="Under Review",
                notes="Case docket acknowledged by Central Nodal Cell. Assigned to Zonal Redressal Officer.",
                updated_by="Nodal Officer",
                created_at=review_dt
            )
            db.add(upd2)

        # 3. If Forwarded to Dept or Resolved -> add Forwarded step
        if item["status"] in ["Forwarded to Dept", "Resolved"]:
            fwd_dt = created_dt + timedelta(days=2, hours=4)
            upd3 = GrievanceUpdate(
                grievance_id=grv.id,
                previous_status="Under Review",
                new_status="Forwarded to Dept",
                notes=f"Case file transferred to Executive Engineer / Field Unit ({item['ward']}) for on-site inspection.",
                updated_by="Zonal Desk",
                created_at=fwd_dt
            )
            db.add(upd3)

        # 4. If Resolved -> add Resolved step
        if item["status"] == "Resolved":
            upd4 = GrievanceUpdate(
                grievance_id=grv.id,
                previous_status="Forwarded to Dept",
                new_status="Resolved",
                notes="Field verification and corrective engineering work completed. Action taken report (ATR) approved by Competent Authority.",
                updated_by="Executive Engineer",
                created_at=resolved_dt or (created_dt + timedelta(days=5))
            )
            db.add(upd4)

        added_count += 1

    db.commit()
    logger.info(f"Successfully seeded {added_count} grievances with complete audit timeline into database.")
    return added_count


if __name__ == "__main__":
    from database import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    try:
        seed_grievances(db)
    finally:
        db.close()
