"""Tracked plants, DCs, and public development headlines for the company map.

Coordinates are metro centroids; the seeder applies a small jitter so sites
in the same CBSA do not stack. Headlines are a curated public-development
tracker (not a live wire).
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

COMPANIES: list[dict] = [
    # Automotive
    {"id": "gm-detroit", "name": "General Motors", "industry": "automotive", "metro": "Detroit", "city": "Detroit", "segment": "OEM", "site": "HQ, Factory ZERO, and supplier park"},
    {"id": "gm-spring-hill", "name": "GM Spring Hill", "industry": "automotive", "metro": "Nashville", "city": "Spring Hill", "segment": "OEM", "site": "Assembly and Ultium-related production"},
    {"id": "ford-dearborn", "name": "Ford Motor Company", "industry": "automotive", "metro": "Detroit", "city": "Dearborn", "segment": "OEM", "site": "HQ and Rouge complex"},
    {"id": "ford-louisville", "name": "Ford Kentucky Truck", "industry": "automotive", "metro": "Louisville", "city": "Louisville", "segment": "OEM", "site": "Super Duty / large truck assembly"},
    {"id": "ford-kc", "name": "Ford Claycomo", "industry": "automotive", "metro": "Kansas City", "city": "Claycomo", "segment": "OEM", "site": "Transit and F-150 operations"},
    {"id": "stellantis-toledo", "name": "Stellantis Toledo Assembly", "industry": "automotive", "metro": "Toledo", "city": "Toledo", "segment": "OEM", "site": "Jeep Wrangler / Gladiator"},
    {"id": "honda-marysville", "name": "Honda Marysville", "industry": "automotive", "metro": "Dayton", "city": "Marysville", "segment": "OEM", "site": "Auto assembly in the Dayton labor shed"},
    {"id": "toyota-san-antonio", "name": "Toyota Motor Manufacturing Texas", "industry": "automotive", "metro": "San Antonio", "city": "San Antonio", "segment": "OEM", "site": "Tundra and Sequoia"},
    {"id": "mazda-toyota-huntsville", "name": "Mazda Toyota Manufacturing", "industry": "automotive", "metro": "Huntsville", "city": "Huntsville", "segment": "OEM", "site": "Joint assembly plant"},
    {"id": "nissan-smyrna", "name": "Nissan Smyrna", "industry": "automotive", "metro": "Nashville", "city": "Smyrna", "segment": "OEM", "site": "Highest-volume Nissan US plant"},
    {"id": "vw-chattanooga", "name": "Volkswagen Chattanooga", "industry": "automotive", "metro": "Chattanooga", "city": "Chattanooga", "segment": "OEM", "site": "Atlas, ID. Buzz path, and supplier campus"},
    {"id": "bmw-spartanburg", "name": "BMW Spartanburg", "industry": "automotive", "metro": "Greenville SC", "city": "Spartanburg", "segment": "OEM", "site": "Largest BMW plant globally"},
    {"id": "mercedes-vance", "name": "Mercedes-Benz Vance", "industry": "automotive", "metro": "Birmingham", "city": "Vance", "segment": "OEM", "site": "SUV assembly"},
    {"id": "volvo-charleston", "name": "Volvo Cars Charleston", "industry": "automotive", "metro": "Charleston", "city": "Ridgeville", "segment": "OEM", "site": "S60 / EX90 production"},
    {"id": "hyundai-savannah", "name": "Hyundai Metaplant America", "industry": "automotive", "metro": "Savannah", "city": "Bryan County", "segment": "OEM", "site": "EV assembly campus"},
    {"id": "tesla-giga-texas", "name": "Tesla Giga Texas", "industry": "automotive", "metro": "Austin", "city": "Austin", "segment": "OEM", "site": "Cybertruck, Model Y, and energy"},
    {"id": "subaru-lafayette", "name": "Subaru of Indiana", "industry": "automotive", "metro": "Indianapolis", "city": "Lafayette", "segment": "OEM", "site": "US assembly in the Indy labor shed"},
    # Battery
    {"id": "panasonic-reno", "name": "Panasonic Energy Nevada", "industry": "battery_manufacturing", "metro": "Reno", "city": "Sparks", "segment": "Cells", "site": "Gigafactory Nevada with Tesla"},
    {"id": "tesla-energy-reno", "name": "Tesla Gigafactory Nevada", "industry": "battery_manufacturing", "metro": "Reno", "city": "Sparks", "segment": "Cells / energy", "site": "Cells, packs, and Megapack path"},
    {"id": "blueoval-sk", "name": "BlueOval SK", "industry": "battery_manufacturing", "metro": "Louisville", "city": "Glendale", "segment": "Cells", "site": "Ford–SK On joint venture"},
    {"id": "ultium-cells", "name": "Ultium Cells", "industry": "battery_manufacturing", "metro": "Detroit", "city": "Warren / Lordstown corridor", "segment": "Cells", "site": "GM–LG joint cell production"},
    {"id": "sk-hyundai-ga", "name": "SK On / Hyundai battery campus", "industry": "battery_manufacturing", "metro": "Savannah", "city": "Bryan County", "segment": "Cells", "site": "Co-located with Metaplant"},
    {"id": "lg-holland", "name": "LG Energy Solution Michigan", "industry": "battery_manufacturing", "metro": "Grand Rapids", "city": "Holland", "segment": "Cells", "site": "Long-running US cell plant"},
    {"id": "toyota-nc-battery", "name": "Toyota Battery Manufacturing", "industry": "battery_manufacturing", "metro": "Greensboro", "city": "Liberty", "segment": "Cells", "site": "North Carolina cell plant in the Piedmont shed"},
    # Semiconductors
    {"id": "tsmc-phoenix", "name": "TSMC Arizona", "industry": "semiconductors", "metro": "Phoenix", "city": "Phoenix", "segment": "Fab", "site": "Leading-edge wafer fabs"},
    {"id": "intel-chandler", "name": "Intel Arizona", "industry": "semiconductors", "metro": "Phoenix", "city": "Chandler / Ocotillo", "segment": "Fab", "site": "Logic fabs and expansion"},
    {"id": "intel-ohio", "name": "Intel Ohio", "industry": "semiconductors", "metro": "Columbus OH", "city": "New Albany", "segment": "Fab", "site": "CHIPS mega-campus"},
    {"id": "intel-hillsboro", "name": "Intel Oregon", "industry": "semiconductors", "metro": "Portland", "city": "Hillsboro", "segment": "Fab / R&D", "site": "Longest-running US Intel campus"},
    {"id": "intel-rio-rancho", "name": "Intel New Mexico", "industry": "semiconductors", "metro": "Albuquerque", "city": "Rio Rancho", "segment": "Fab", "site": "Existing Intel campus"},
    {"id": "samsung-taylor", "name": "Samsung Austin Semiconductor", "industry": "semiconductors", "metro": "Austin", "city": "Taylor / Austin", "segment": "Fab", "site": "Taylor mega-fab plus Austin operations"},
    {"id": "ti-dallas", "name": "Texas Instruments", "industry": "semiconductors", "metro": "Dallas", "city": "Richardson / Sherman", "segment": "Fab", "site": "Analog 300mm expansion"},
    {"id": "micron-boise", "name": "Micron Boise", "industry": "semiconductors", "metro": "Boise", "city": "Boise", "segment": "Fab / HQ", "site": "Memory HQ and manufacturing"},
    {"id": "micron-clay", "name": "Micron Central New York", "industry": "semiconductors", "metro": "Albany", "city": "Clay", "segment": "Fab", "site": "CHIPS memory mega-fab in the Albany shed"},
    {"id": "globalfoundries-malta", "name": "GlobalFoundries Fab 8", "industry": "semiconductors", "metro": "Albany", "city": "Malta", "segment": "Fab", "site": "300mm foundry"},
    {"id": "wolfspeed-durham", "name": "Wolfspeed", "industry": "semiconductors", "metro": "Raleigh", "city": "Durham / RTP", "segment": "SiC / materials", "site": "Silicon carbide devices"},
    # Food
    {"id": "tyson-nwa", "name": "Tyson Foods", "industry": "food_manufacturing", "metro": "NW Arkansas", "city": "Springdale", "segment": "Protein", "site": "HQ and processing gravity"},
    {"id": "cargill-omaha", "name": "Cargill", "industry": "food_manufacturing", "metro": "Omaha", "city": "Omaha / Schuyler", "segment": "Protein / grain", "site": "Beef and ingredient processing"},
    {"id": "cargill-msp", "name": "Cargill Minnetonka", "industry": "food_manufacturing", "metro": "Minneapolis", "city": "Minnetonka", "segment": "HQ / ingredients", "site": "Global HQ and food ingredients"},
    {"id": "general-mills", "name": "General Mills", "industry": "food_manufacturing", "metro": "Minneapolis", "city": "Golden Valley", "segment": "CPG", "site": "HQ and cereal / CPG plants"},
    {"id": "conagra-chicago", "name": "Conagra Brands", "industry": "food_manufacturing", "metro": "Chicago", "city": "Chicago", "segment": "CPG", "site": "HQ and Midwest processing"},
    {"id": "kraft-heinz", "name": "Kraft Heinz", "industry": "food_manufacturing", "metro": "Chicago", "city": "Chicago", "segment": "CPG", "site": "HQ and food manufacturing network"},
    {"id": "anheuser-stlouis", "name": "Anheuser-Busch", "industry": "food_manufacturing", "metro": "St. Louis", "city": "St. Louis", "segment": "Beverage", "site": "Flagship brewery"},
    {"id": "pepsico-dallas", "name": "PepsiCo / Frito-Lay", "industry": "food_manufacturing", "metro": "Dallas", "city": "Plano / Dallas", "segment": "Snacks / beverage", "site": "HQ campus and snack plants"},
    {"id": "kellogg-gr", "name": "WK Kellogg / Kellanova", "industry": "food_manufacturing", "metro": "Grand Rapids", "city": "Battle Creek / GR shed", "segment": "Cereal / snacks", "site": "Cereal belt manufacturing"},
    {"id": "adm-decatur", "name": "ADM", "industry": "food_manufacturing", "metro": "St. Louis", "city": "Decatur corridor", "segment": "Grain processing", "site": "Crush and ingredient complex in the St. Louis shed"},
    {"id": "jbs-greeley", "name": "JBS USA", "industry": "food_manufacturing", "metro": "Denver", "city": "Greeley", "segment": "Protein", "site": "Beef processing in the Front Range shed"},
    # Warehousing
    {"id": "prologis-ie", "name": "Prologis Inland Empire", "industry": "warehousing", "metro": "Inland Empire", "city": "Ontario / San Bernardino", "segment": "Industrial REIT", "site": "Largest US warehouse landlord concentration"},
    {"id": "prologis-dfw", "name": "Prologis DFW", "industry": "warehousing", "metro": "Dallas", "city": "Dallas–Fort Worth", "segment": "Industrial REIT", "site": "Spec and BTS industrial parks"},
    {"id": "prologis-lehigh", "name": "Prologis Lehigh Valley", "industry": "warehousing", "metro": "Allentown", "city": "Allentown / Bethlehem", "segment": "Industrial REIT", "site": "I-78 warehouse alley"},
    {"id": "lineage-chicago", "name": "Lineage Logistics", "industry": "warehousing", "metro": "Chicago", "city": "Chicago", "segment": "Cold storage", "site": "Temperature-controlled network"},
    {"id": "lineage-omaha", "name": "Lineage Logistics Omaha", "industry": "warehousing", "metro": "Omaha", "city": "Omaha", "segment": "Cold storage", "site": "Protein-corridor cold chain"},
    {"id": "nfi-indianapolis", "name": "NFI Indianapolis", "industry": "warehousing", "metro": "Indianapolis", "city": "Indianapolis", "segment": "3PL", "site": "Dedicated contract warehousing"},
    {"id": "ryder-atlanta", "name": "Ryder Atlanta", "industry": "warehousing", "metro": "Atlanta", "city": "Atlanta", "segment": "3PL", "site": "Dedicated and shared warehousing"},
    {"id": "xpo-gso", "name": "XPO / GXO Piedmont", "industry": "warehousing", "metro": "Greensboro", "city": "Greensboro", "segment": "3PL", "site": "Carolinas contract logistics"},
    # Distribution
    {"id": "fedex-memphis", "name": "FedEx SuperHub", "industry": "distribution_centers", "metro": "Memphis", "city": "Memphis", "segment": "Air cargo / parcel", "site": "World's largest air-cargo hub"},
    {"id": "ups-worldport", "name": "UPS Worldport", "industry": "distribution_centers", "metro": "Louisville", "city": "Louisville", "segment": "Air cargo / parcel", "site": "Global air hub"},
    {"id": "amazon-indy", "name": "Amazon Indianapolis", "industry": "distribution_centers", "metro": "Indianapolis", "city": "Indianapolis / Plainfield", "segment": "Fulfillment", "site": "FC and sortation cluster"},
    {"id": "amazon-dfw", "name": "Amazon Dallas–Fort Worth", "industry": "distribution_centers", "metro": "Dallas", "city": "Fort Worth / Haslet", "segment": "Fulfillment", "site": "Multi-node FC network"},
    {"id": "amazon-atl", "name": "Amazon Atlanta", "industry": "distribution_centers", "metro": "Atlanta", "city": "Atlanta / Union City", "segment": "Fulfillment", "site": "SE fulfillment and air hub adjacency"},
    {"id": "amazon-cbus", "name": "Amazon Columbus", "industry": "distribution_centers", "metro": "Columbus OH", "city": "Lockbourne / Etna", "segment": "Fulfillment", "site": "Rickenbacker-adjacent FCs"},
    {"id": "amazon-ie", "name": "Amazon Inland Empire", "industry": "distribution_centers", "metro": "Inland Empire", "city": "San Bernardino", "segment": "Fulfillment", "site": "Import-gateway FCs"},
    {"id": "walmart-nwa", "name": "Walmart Home Office + DCs", "industry": "distribution_centers", "metro": "NW Arkansas", "city": "Bentonville", "segment": "Retail logistics", "site": "HQ gravity and supplier campus"},
    {"id": "homedepot-atl", "name": "Home Depot", "industry": "distribution_centers", "metro": "Atlanta", "city": "Atlanta", "segment": "Retail logistics", "site": "HQ and rapid-deployment DCs"},
    {"id": "target-msp", "name": "Target", "industry": "distribution_centers", "metro": "Minneapolis", "city": "Minneapolis", "segment": "Retail logistics", "site": "HQ and Midwest DC network"},
    {"id": "jbhunt-nwa", "name": "J.B. Hunt", "industry": "distribution_centers", "metro": "NW Arkansas", "city": "Lowell", "segment": "Intermodal / 3PL", "site": "Intermodal and dedicated contract"},
    {"id": "amazon-allentown", "name": "Amazon Lehigh Valley", "industry": "distribution_centers", "metro": "Allentown", "city": "Breinigsville / Fogelsville", "segment": "Fulfillment", "site": "Northeast two-day coverage FCs"},
    {"id": "amazon-reno", "name": "Amazon Reno / TRIC", "industry": "distribution_centers", "metro": "Reno", "city": "Sparks / TRIC", "segment": "Fulfillment", "site": "California-overflow DCs"},
    # Materials handling & forklifts — public OEM campuses (lat/lon are published sites)
    {"id": "crown-new-bremen", "name": "Crown Equipment", "industry": "materials_handling", "metro": "Dayton", "city": "New Bremen", "segment": "Lift trucks", "site": "Global HQ and manufacturing campus", "lat": 40.4364, "lon": -84.3797},
    {"id": "toyota-mh-columbus", "name": "Toyota Material Handling", "industry": "materials_handling", "metro": "Indianapolis", "city": "Columbus", "segment": "Lift trucks", "site": "North American HQ and production", "lat": 39.2014, "lon": -85.9214},
    {"id": "hyster-yale-fairview", "name": "Hyster-Yale", "industry": "materials_handling", "metro": "Portland", "city": "Fairview", "segment": "Lift trucks", "site": "HQ campus in the Portland shed", "lat": 45.5404, "lon": -122.4390},
    {"id": "raymond-greene", "name": "The Raymond Corporation", "industry": "materials_handling", "metro": "Albany", "city": "Greene", "segment": "Lift trucks", "site": "Narrow-aisle truck manufacturing", "lat": 42.3292, "lon": -75.7702},
    {"id": "jungheinrich-houston", "name": "Jungheinrich", "industry": "materials_handling", "metro": "Houston", "city": "Houston", "segment": "Warehouse equipment", "site": "US operations campus", "lat": 29.9420, "lon": -95.3657},
    {"id": "mitsubishi-logisnext-houston", "name": "Mitsubishi Logisnext Americas", "industry": "materials_handling", "metro": "Houston", "city": "Houston", "segment": "Lift trucks", "site": "Americas HQ", "lat": 29.9375, "lon": -95.3988},
    {"id": "yale-greenville", "name": "Yale Materials Handling", "industry": "materials_handling", "metro": "Greensboro", "city": "Greenville", "segment": "Lift trucks", "site": "Hyster-Yale production in eastern NC", "lat": 35.6127, "lon": -77.3663},
    {"id": "unicarriers-marengo", "name": "UniCarriers Americas", "industry": "materials_handling", "metro": "Chicago", "city": "Marengo", "segment": "Lift trucks", "site": "Midwest manufacturing campus", "lat": 42.2486, "lon": -88.6084},
    {"id": "komatsu-forklift-covington", "name": "Komatsu Forklift", "industry": "materials_handling", "metro": "Atlanta", "city": "Covington", "segment": "Lift trucks", "site": "Southeast industrial truck operations", "lat": 33.5968, "lon": -83.8602},
]

NEWS: list[dict] = [
    {"company_id": "hyundai-savannah", "date": "2026-05-12", "headline": "Hyundai Metaplant ramps Ioniq production as Georgia supplier park fills in", "summary": "OEM output at Bryan County continues to pull battery, stamping, and logistics occupancy into the Savannah metro.", "source": "Company / state EDO tracker", "url": "https://www.hyundai.com"},
    {"company_id": "sk-hyundai-ga", "date": "2026-04-08", "headline": "SK On cell lines at the Metaplant campus remain the Southeast's largest battery co-location", "summary": "Cell-to-vehicle adjacency is the site-selection template other EV OEMs are copying along I-16 and I-95.", "source": "Public project filings", "url": "https://www.sk-on.com"},
    {"company_id": "tsmc-phoenix", "date": "2026-03-20", "headline": "TSMC Arizona continues volume ramp on early nodes while later fabs stay in the construction cycle", "summary": "Supplier hotels, ultrapure water, and construction labor remain the binding constraints, not land.", "source": "TSMC disclosures", "url": "https://www.tsmc.com"},
    {"company_id": "intel-ohio", "date": "2026-02-18", "headline": "Intel Ohio campus stays a multi-year CHIPS build, with supplier follow-on already leasing in Licking County", "summary": "Even with a slower wafer start than first announced, industrial and housing demand around New Albany is live.", "source": "Intel / Ohio EDC", "url": "https://www.intel.com"},
    {"company_id": "intel-chandler", "date": "2025-11-06", "headline": "Intel Arizona expansions keep the Phoenix east valley as the densest US logic cluster after TSMC", "summary": "Ocotillo and Chandler remain the installed-base counterpart to TSMC's greenfield.", "source": "Intel", "url": "https://www.intel.com"},
    {"company_id": "samsung-taylor", "date": "2026-01-22", "headline": "Samsung Taylor fab construction continues as Austin industrial vacancy stays tighter than the Texas average", "summary": "Taylor is the expansion valve for a metro that already hosts Tesla and a deep electronics bench.", "source": "Samsung / Texas", "url": "https://www.samsung.com"},
    {"company_id": "tesla-giga-texas", "date": "2026-06-03", "headline": "Giga Texas remains the largest single auto-energy campus in the South, with Cybertruck and energy storage on site", "summary": "Inbound logistics on SH-130 and power availability, not labor headcount, are the operating constraint.", "source": "Tesla updates", "url": "https://www.tesla.com"},
    {"company_id": "panasonic-reno", "date": "2026-03-01", "headline": "Panasonic Energy Nevada adds cell capacity as TRIC stays the West's battery-plus-warehouse overlay", "summary": "Nevada's no-inventory-tax warehouse market keeps absorbing California overflow next to the gigafactory.", "source": "Panasonic Energy", "url": "https://www.panasonic.com"},
    {"company_id": "blueoval-sk", "date": "2026-04-21", "headline": "BlueOval SK Kentucky moves through commissioning as Louisville logistics (UPS Worldport) captures inbound materials", "summary": "The plant is rural Glendale; the labor and air-cargo shed is Louisville.", "source": "Ford / SK On", "url": "https://www.ford.com"},
    {"company_id": "gm-detroit", "date": "2026-02-11", "headline": "GM continues EV and ICE mix production in SE Michigan as Ultium utilization becomes the 2026 watch item", "summary": "Detroit still has the densest North American supplier radius even when national EV rates fluctuate.", "source": "GM", "url": "https://www.gm.com"},
    {"company_id": "bmw-spartanburg", "date": "2025-12-09", "headline": "BMW Spartanburg remains the company's global volume leader, anchoring the I-85 auto alley", "summary": "Supplier parks in Greenville-Spartanburg keep winning follow-on industrial leases.", "source": "BMW Group", "url": "https://www.bmwgroup.com"},
    {"company_id": "fedex-memphis", "date": "2026-07-09", "headline": "FedEx SuperHub volumes track the Q2 2026 industrial reset as air cargo and 3PL demand firm", "summary": "Memphis still sets the overnight coverage standard; warehouse occupancy around the airport moved with national absorption.", "source": "FedEx / Colliers context", "url": "https://www.fedex.com"},
    {"company_id": "ups-worldport", "date": "2026-07-09", "headline": "UPS Worldport stays the East-Central air node as manufacturing users return to industrial leasing", "summary": "Colliers' Q2 2026 demand-over-supply print is visible first in air-adjacent 3PL buildings.", "source": "UPS / Colliers U.S. Industrial Outlook Q2 2026", "url": "https://www.ups.com"},
    {"company_id": "amazon-dfw", "date": "2026-05-28", "headline": "Amazon's DFW node network keeps adding sortation as North Texas industrial demand turns positive", "summary": "DFW remains the Sun Belt fulfillment machine; big-box residual demand is now manufacturing- and 3PL-led, not only e-commerce.", "source": "Market reports", "url": "https://www.aboutamazon.com"},
    {"company_id": "amazon-indy", "date": "2026-05-15", "headline": "Indianapolis FCs stay a national two-day coverage play as Indiana industrial land stays cheaper than coastal gateways", "summary": "Crossroads highway geometry plus available land is still the Amazon thesis here.", "source": "Market reports", "url": "https://www.aboutamazon.com"},
    {"company_id": "walmart-nwa", "date": "2026-06-18", "headline": "Walmart supplier campus and DC growth in Northwest Arkansas continues to pull food and import 3PLs", "summary": "HQ gravity remains a unique logistics cluster that QCEW 493 understates if you only look at warehouses.", "source": "Walmart", "url": "https://corporate.walmart.com"},
    {"company_id": "tyson-nwa", "date": "2026-01-30", "headline": "Tyson and the Ozarks protein complex keep cold-storage demand elevated along I-49", "summary": "Food manufacturing here is a logistics story as much as a plant story.", "source": "Tyson Foods", "url": "https://www.tysonfoods.com"},
    {"company_id": "micron-boise", "date": "2026-02-04", "headline": "Micron Boise remains HQ and a CHIPS-era expansion site as Idaho power and land stay competitive", "summary": "Memory capex is multi-year; Boise's labor in-migration is the supporting tell.", "source": "Micron", "url": "https://www.micron.com"},
    {"company_id": "micron-clay", "date": "2025-10-14", "headline": "Micron's Central New York memory fab stays one of the largest CHIPS awards in the Albany–Syracuse shed", "summary": "Construction labor and transmission, not incentives, are the 2026 bottleneck.", "source": "Micron / New York", "url": "https://www.micron.com"},
    {"company_id": "globalfoundries-malta", "date": "2026-03-11", "headline": "GlobalFoundries Malta continues to run as the US specialty foundry complement to Intel and TSMC", "summary": "NY CREATES adjacency still matters for tools and technicians.", "source": "GlobalFoundries", "url": "https://gf.com"},
    {"company_id": "prologis-ie", "date": "2026-07-10", "headline": "Inland Empire vacancy works off 2023–24 deliveries as national industrial demand exceeds supply", "summary": "Colliers' Q2 2026 national print (59M SF absorption, 7.3% vacancy) is most relevant in the densest warehouse market.", "source": "Colliers U.S. Industrial Outlook Q2 2026", "url": "https://www.colliers.com/en/research/nrep-usind-us-industrial-market-outlook-q2-2026"},
    {"company_id": "ti-dallas", "date": "2026-01-08", "headline": "TI Sherman / Richardson 300mm analog expansion keeps DFW in the semiconductor map without a leading-edge foundry", "summary": "Analog capacity is a different site-selection problem than TSMC: water and chemicals more than EUV technicians.", "source": "Texas Instruments", "url": "https://www.ti.com"},
    {"company_id": "vw-chattanooga", "date": "2025-09-17", "headline": "Volkswagen Chattanooga and Scout Motors keep the I-75 Tennessee auto spine in expansion mode", "summary": "Battery and body-shop suppliers are the follow-on industrial demand.", "source": "Volkswagen", "url": "https://www.vw.com"},
    {"company_id": "honda-marysville", "date": "2026-04-02", "headline": "Honda's Ohio auto triangle (Marysville, East Liberty, Anna) still sets Dayton–Columbus manufacturing occupancy", "summary": "ICE and hybrid mix changes less than EV headlines imply for this installed base.", "source": "Honda", "url": "https://www.honda.com"},
    {"company_id": "cargill-omaha", "date": "2026-03-27", "headline": "Cargill and the Platte protein corridor keep Omaha among the highest food-manufacturing LQs in the panel", "summary": "Cold storage and rail, not e-commerce boxes, are the industrial product.", "source": "Cargill", "url": "https://www.cargill.com"},
    {"company_id": "pepsico-dallas", "date": "2026-02-25", "headline": "PepsiCo Plano campus and Frito-Lay plants remain a CPG manufacturing-plus-DC stack in North Texas", "summary": "Food and beverage users were named in Colliers' Q2 2026 demand mix.", "source": "PepsiCo / Colliers", "url": "https://www.pepsico.com"},
    {"company_id": "homedepot-atl", "date": "2026-06-01", "headline": "Home Depot's Atlanta rapid-deployment network tracks housing permits more than e-commerce peak-season", "summary": "A useful reminder that DC demand is not only Amazon.", "source": "Home Depot", "url": "https://corporate.homedepot.com"},
    {"company_id": "target-msp", "date": "2026-05-06", "headline": "Target's Midwest DC footprint stays anchored on Minneapolis HQ even as Sun Belt nodes grow faster", "summary": "Sortation labor and last-mile, not industrial land, bind this market.", "source": "Target", "url": "https://corporate.target.com"},
    {"company_id": "lg-holland", "date": "2025-08-19", "headline": "LG Energy Solution Michigan remains one of the few at-scale US cell plants predating the IRA wave", "summary": "Grand Rapids manufacturing culture is the labor story, not a greenfield desert site.", "source": "LG Energy Solution", "url": "https://www.lgensol.com"},
    {"company_id": "toyota-nc-battery", "date": "2026-01-14", "headline": "Toyota's North Carolina battery plant continues hiring into the Piedmont Triad labor shed", "summary": "Greensboro's warehouse scores and this cell plant are the same I-40 story.", "source": "Toyota", "url": "https://www.toyota.com"},
    {"company_id": "amazon-cbus", "date": "2026-04-16", "headline": "Amazon's Rickenbacker-area FCs sit next to Intel Ohio supplier demand — a rare DC-plus-fab overlay", "summary": "Columbus is one of the few metros that scores in both semiconductors and distribution.", "source": "Market reports", "url": "https://www.aboutamazon.com"},
    {"company_id": "jbhunt-nwa", "date": "2026-03-05", "headline": "J.B. Hunt intermodal volumes firm with the 2026 industrial goods rebound", "summary": "Northwest Arkansas is HQ for both the largest retailer and a top intermodal carrier.", "source": "J.B. Hunt", "url": "https://www.jbhunt.com"},
    {"company_id": "lineage-chicago", "date": "2026-02-20", "headline": "Lineage and Chicago cold storage remain the food-system warehouse overlay that dry big-box indices miss", "summary": "Protein and CPG users were part of Colliers' 2026 demand mix.", "source": "Lineage", "url": "https://www.lineagelogistics.com"},
    {"company_id": "ford-louisville", "date": "2026-05-07", "headline": "Kentucky Truck and BlueOval SK together make Louisville a truck-plus-battery metro, not only a UPS story", "summary": "Air cargo, auto, and cells now share one labor shed.", "source": "Ford", "url": "https://www.ford.com"},
    {"company_id": "stellantis-toledo", "date": "2025-11-21", "headline": "Toledo Assembly keeps Jeep volume on I-75 while cell and glass suppliers occupy adjacent industrial land", "summary": "A classic OEM town where logistics scores understate manufacturing intensity.", "source": "Stellantis", "url": "https://www.stellantis.com"},
]

PROJECTS: list[dict] = [
    {"id": "p-tsmc-az", "company": "TSMC Arizona", "metro": "Phoenix", "industry": "semiconductors", "year": 2026, "capex_b": 65.0, "jobs": 6000, "status": "Ramping / under construction", "notes": "Multi-fab CHIPS campus"},
    {"id": "p-intel-oh", "company": "Intel Ohio", "metro": "Columbus OH", "industry": "semiconductors", "year": 2026, "capex_b": 28.0, "jobs": 3000, "status": "Under construction", "notes": "New Albany mega-site"},
    {"id": "p-samsung-tx", "company": "Samsung Taylor", "metro": "Austin", "industry": "semiconductors", "year": 2026, "capex_b": 25.0, "jobs": 2000, "status": "Under construction", "notes": "Leading-edge and advanced packaging path"},
    {"id": "p-micron-ny", "company": "Micron Clay", "metro": "Albany", "industry": "semiconductors", "year": 2026, "capex_b": 20.0, "jobs": 9000, "status": "Early construction", "notes": "Memory fab, multi-year"},
    {"id": "p-hyundai-ga", "company": "Hyundai Metaplant", "metro": "Savannah", "industry": "automotive", "year": 2026, "capex_b": 7.6, "jobs": 8500, "status": "Ramping", "notes": "EV assembly plus suppliers"},
    {"id": "p-sk-ga", "company": "SK On Georgia", "metro": "Savannah", "industry": "battery_manufacturing", "year": 2026, "capex_b": 5.0, "jobs": 2600, "status": "Ramping", "notes": "Co-located cells"},
    {"id": "p-blueoval", "company": "BlueOval SK", "metro": "Louisville", "industry": "battery_manufacturing", "year": 2026, "capex_b": 5.6, "jobs": 5000, "status": "Commissioning", "notes": "Glendale KY / Louisville shed"},
    {"id": "p-toyota-nc", "company": "Toyota NC Battery", "metro": "Greensboro", "industry": "battery_manufacturing", "year": 2026, "capex_b": 13.9, "jobs": 5000, "status": "Ramping", "notes": "Liberty NC"},
    {"id": "p-gm-springhill", "company": "GM Spring Hill EV", "metro": "Nashville", "industry": "automotive", "year": 2025, "capex_b": 2.0, "jobs": 1600, "status": "Operating / retooling", "notes": "EV truck path"},
    {"id": "p-ti-sherman", "company": "TI Sherman", "metro": "Dallas", "industry": "semiconductors", "year": 2026, "capex_b": 11.0, "jobs": 900, "status": "Under construction", "notes": "300mm analog"},
    {"id": "p-scout-sc", "company": "Scout Motors", "metro": "Columbia SC", "industry": "automotive", "year": 2026, "capex_b": 2.0, "jobs": 4000, "status": "Under construction", "notes": "Blythewood / Columbia shed"},
    {"id": "p-panasonic-nv", "company": "Panasonic Energy Nevada", "metro": "Reno", "industry": "battery_manufacturing", "year": 2025, "capex_b": 4.0, "jobs": 1500, "status": "Operating / expanding", "notes": "Additional cell lines"},
]

# Model industrial vacancy (%), not licensed CoStar/Colliers microdata.
# National print was 7.3% in Colliers Q2 2026; local values are relative tilts.
VACANCY_TILT: dict[str, float] = {
    "Inland Empire": 8.8,
    "Dallas": 7.9,
    "Atlanta": 7.6,
    "Phoenix": 8.1,
    "Austin": 8.4,
    "Indianapolis": 6.2,
    "Columbus OH": 6.4,
    "Memphis": 6.8,
    "Louisville": 6.5,
    "Allentown": 6.1,
    "Harrisburg": 6.0,
    "Chicago": 7.4,
    "Los Angeles": 5.8,
    "Savannah": 5.9,
    "Greenville SC": 5.7,
    "Detroit": 6.9,
    "Nashville": 6.6,
    "Reno": 6.3,
    "Kansas City": 6.4,
    "Houston": 7.8,
    "Jacksonville": 7.1,
    "Charlotte": 6.7,
    "Raleigh": 6.5,
    "Portland": 7.2,
    "Seattle": 6.9,
    "Boston": 6.0,
    "San Jose": 5.4,
    "NW Arkansas": 5.8,
}

# Official homepages for curated campuses (id → URL). Public TRI/FSIS/ITA files
# have no website field — never invent a domain for those rows.
CURATED_WEBSITES: dict[str, str] = {
    "gm-detroit": "https://www.gm.com",
    "gm-spring-hill": "https://www.gm.com",
    "ford-dearborn": "https://www.ford.com",
    "ford-louisville": "https://www.ford.com",
    "ford-kc": "https://www.ford.com",
    "stellantis-toledo": "https://www.stellantis.com",
    "honda-marysville": "https://www.honda.com",
    "toyota-san-antonio": "https://www.toyota.com",
    "mazda-toyota-huntsville": "https://www.mazdatoyota.com",
    "nissan-smyrna": "https://www.nissanusa.com",
    "vw-chattanooga": "https://www.vw.com",
    "bmw-spartanburg": "https://www.bmwgroup.com",
    "mercedes-vance": "https://www.mbusa.com",
    "volvo-charleston": "https://www.volvocars.com",
    "hyundai-savannah": "https://www.hyundai.com",
    "tesla-giga-texas": "https://www.tesla.com",
    "subaru-lafayette": "https://www.subaru.com",
    "panasonic-reno": "https://www.panasonic.com",
    "tesla-energy-reno": "https://www.tesla.com",
    "blueoval-sk": "https://www.ford.com",
    "ultium-cells": "https://www.ultiumcells.com",
    "sk-hyundai-ga": "https://www.sk-on.com",
    "lg-holland": "https://www.lgensol.com",
    "toyota-nc-battery": "https://www.toyota.com",
    "tsmc-phoenix": "https://www.tsmc.com",
    "intel-chandler": "https://www.intel.com",
    "intel-ohio": "https://www.intel.com",
    "intel-hillsboro": "https://www.intel.com",
    "intel-rio-rancho": "https://www.intel.com",
    "samsung-taylor": "https://www.samsung.com",
    "ti-dallas": "https://www.ti.com",
    "micron-boise": "https://www.micron.com",
    "micron-clay": "https://www.micron.com",
    "globalfoundries-malta": "https://gf.com",
    "wolfspeed-durham": "https://www.wolfspeed.com",
    "tyson-nwa": "https://www.tysonfoods.com",
    "cargill-omaha": "https://www.cargill.com",
    "cargill-msp": "https://www.cargill.com",
    "general-mills": "https://www.generalmills.com",
    "conagra-chicago": "https://www.conagrabrands.com",
    "kraft-heinz": "https://www.kraftheinz.com",
    "anheuser-stlouis": "https://www.anheuser-busch.com",
    "pepsico-dallas": "https://www.pepsico.com",
    "kellogg-gr": "https://www.kellanova.com",
    "adm-decatur": "https://www.adm.com",
    "jbs-greeley": "https://jbsfoodsgroup.com",
    "prologis-ie": "https://www.prologis.com",
    "prologis-dfw": "https://www.prologis.com",
    "prologis-lehigh": "https://www.prologis.com",
    "lineage-chicago": "https://www.lineagelogistics.com",
    "lineage-omaha": "https://www.lineagelogistics.com",
    "nfi-indianapolis": "https://www.nfiindustries.com",
    "ryder-atlanta": "https://www.ryder.com",
    "xpo-gso": "https://gxo.com",
    "fedex-memphis": "https://www.fedex.com",
    "ups-worldport": "https://www.ups.com",
    "amazon-indy": "https://www.amazon.com",
    "amazon-dfw": "https://www.amazon.com",
    "amazon-atl": "https://www.amazon.com",
    "amazon-cbus": "https://www.amazon.com",
    "amazon-ie": "https://www.amazon.com",
    "walmart-nwa": "https://corporate.walmart.com",
    "homedepot-atl": "https://corporate.homedepot.com",
    "target-msp": "https://corporate.target.com",
    "jbhunt-nwa": "https://www.jbhunt.com",
    "amazon-allentown": "https://www.amazon.com",
    "amazon-reno": "https://www.amazon.com",
    "crown-new-bremen": "https://www.crown.com",
    "toyota-mh-columbus": "https://www.toyotaforklift.com",
    "hyster-yale-fairview": "https://www.hyster-yale.com",
    "raymond-greene": "https://www.raymondcorp.com",
    "jungheinrich-houston": "https://www.jungheinrich.com",
    "mitsubishi-logisnext-houston": "https://www.logisnextamericas.com",
    "yale-greenville": "https://www.yale.com",
    "unicarriers-marengo": "https://www.unicarriersamericas.com",
    "komatsu-forklift-covington": "https://www.komatsu.com",
}

# Parent/name needles for public ingest. More specific patterns first.
_OFFICIAL_DOMAIN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"TOYOTA MATERIALS? HANDL|TOYOTA FORKLIFT", re.I), "https://www.toyotaforklift.com"),
    (re.compile(r"CROWN EQUIPMENT", re.I), "https://www.crown.com"),
    (re.compile(r"HYSTER[\s-]?YALE", re.I), "https://www.hyster-yale.com"),
    (re.compile(r"RAYMOND CORP|THE RAYMOND", re.I), "https://www.raymondcorp.com"),
    (re.compile(r"JUNGHEINRICH", re.I), "https://www.jungheinrich.com"),
    (re.compile(r"MITSUBISHI LOGISNEXT|LOGISNEXT", re.I), "https://www.logisnextamericas.com"),
    (re.compile(r"YALE MATERIALS|YALE LIFT", re.I), "https://www.yale.com"),
    (re.compile(r"UNI[\s-]?CARRIERS", re.I), "https://www.unicarriersamericas.com"),
    (re.compile(r"KOMATSU FORKLIFT", re.I), "https://www.komatsu.com"),
    (re.compile(r"\bTESLA\b", re.I), "https://www.tesla.com"),
    (re.compile(r"\bTSMC\b|TAIWAN SEMICONDUCTOR", re.I), "https://www.tsmc.com"),
    (re.compile(r"\bHYUNDAI\b", re.I), "https://www.hyundai.com"),
    (re.compile(r"\bAMAZON\b", re.I), "https://www.amazon.com"),
    (re.compile(r"\bFEDEX\b|FEDERAL EXPRESS", re.I), "https://www.fedex.com"),
    (re.compile(r"UNITED PARCEL|\bUPS\b", re.I), "https://www.ups.com"),
    (re.compile(r"GENERAL MOTORS|\bGM\b", re.I), "https://www.gm.com"),
    (re.compile(r"FORD MOTOR|\bFORD\b", re.I), "https://www.ford.com"),
    (re.compile(r"\bSTELLANTIS\b|\bCHRYSLER\b|\bJEEP\b", re.I), "https://www.stellantis.com"),
    (re.compile(r"\bHONDA\b", re.I), "https://www.honda.com"),
    (re.compile(r"\bNISSAN\b", re.I), "https://www.nissanusa.com"),
    (re.compile(r"VOLKSWAGEN|\bVW\b", re.I), "https://www.vw.com"),
    (re.compile(r"\bBMW\b", re.I), "https://www.bmwgroup.com"),
    (re.compile(r"MERCEDES", re.I), "https://www.mbusa.com"),
    (re.compile(r"VOLVO", re.I), "https://www.volvocars.com"),
    (re.compile(r"\bSUBARU\b", re.I), "https://www.subaru.com"),
    (re.compile(r"\bTOYOTA\b", re.I), "https://www.toyota.com"),
    (re.compile(r"\bINTEL\b", re.I), "https://www.intel.com"),
    (re.compile(r"\bSAMSUNG\b", re.I), "https://www.samsung.com"),
    (re.compile(r"TEXAS INSTRUMENTS", re.I), "https://www.ti.com"),
    (re.compile(r"\bMICRON\b", re.I), "https://www.micron.com"),
    (re.compile(r"GLOBALFOUNDRIES", re.I), "https://gf.com"),
    (re.compile(r"\bWOLFSPEED\b", re.I), "https://www.wolfspeed.com"),
    (re.compile(r"PANASONIC", re.I), "https://www.panasonic.com"),
    (re.compile(r"\bSK ON\b|SK[- ]?BATTERY", re.I), "https://www.sk-on.com"),
    (re.compile(r"LG ENERGY", re.I), "https://www.lgensol.com"),
    (re.compile(r"ULTIUM", re.I), "https://www.ultiumcells.com"),
    (re.compile(r"TYSON FOODS|\bTYSON\b", re.I), "https://www.tysonfoods.com"),
    (re.compile(r"\bCARGILL\b", re.I), "https://www.cargill.com"),
    (re.compile(r"GENERAL MILLS", re.I), "https://www.generalmills.com"),
    (re.compile(r"\bCONAGRA\b", re.I), "https://www.conagrabrands.com"),
    (re.compile(r"KRAFT HEINZ", re.I), "https://www.kraftheinz.com"),
    (re.compile(r"ANHEUSER", re.I), "https://www.anheuser-busch.com"),
    (re.compile(r"PEPSICO|FRITO[\s-]?LAY", re.I), "https://www.pepsico.com"),
    (re.compile(r"KELLOGG|KELLANOVA", re.I), "https://www.kellanova.com"),
    (re.compile(r"\bADM\b|ARCHER DANIELS", re.I), "https://www.adm.com"),
    (re.compile(r"\bJBS\b", re.I), "https://jbsfoodsgroup.com"),
    (re.compile(r"\bPROLOGIS\b", re.I), "https://www.prologis.com"),
    (re.compile(r"LINEAGE LOGISTICS|\bLINEAGE\b", re.I), "https://www.lineagelogistics.com"),
    (re.compile(r"\bWALMART\b|\bWAL[\s-]?MART\b", re.I), "https://corporate.walmart.com"),
    (re.compile(r"HOME DEPOT", re.I), "https://corporate.homedepot.com"),
    (re.compile(r"\bTARGET\b", re.I), "https://corporate.target.com"),
    (re.compile(r"J\.?B\.?\s*HUNT", re.I), "https://www.jbhunt.com"),
    (re.compile(r"\bRYDER\b", re.I), "https://www.ryder.com"),
    (re.compile(r"\bGXO\b|\bXPO\b", re.I), "https://gxo.com"),
    (re.compile(r"\bNFI\b", re.I), "https://www.nfiindustries.com"),
]


def official_website(name: str, parent: str = "") -> str | None:
    hay = f"{name} {parent}".strip()
    if not hay:
        return None
    for pat, url in _OFFICIAL_DOMAIN_PATTERNS:
        if pat.search(hay):
            return url
    return None


def google_search_url(name: str, city: str = "", state: str = "") -> str:
    query = " ".join(part for part in (name, city, state) if part)
    return f"https://www.google.com/search?q={quote_plus(query)}"


def resolve_website(
    name: str,
    parent: str = "",
    city: str = "",
    state: str = "",
    official: str | None = None,
) -> str:
    if official:
        return official
    found = official_website(name, parent)
    if found:
        return found
    return google_search_url(name, city, state)


def is_search_website(url: str | None) -> bool:
    if not url:
        return False
    return "google.com/search" in str(url).lower()


for _company in COMPANIES:
    _company["website"] = (
        _company.get("website")
        or CURATED_WEBSITES.get(_company["id"])
        or resolve_website(_company["name"], _company["name"], _company["city"])
    )
