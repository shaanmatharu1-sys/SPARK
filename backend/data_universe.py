"""
data_universe.py — Equity universe with GICS sector + sub-industry tags.
Source: S&P 500 constituents (public dataset) + curated large/mid-cap additions.
Sub-industry is used as the economic-linkage layer for the relationship map.
"""

UNIVERSE = {
"MMM":{
"name":"3M",
"sector":"Industrials",
"sub":"Industrial Conglomerates"
},
"AOS":{
"name":"A. O. Smith",
"sector":"Industrials",
"sub":"Building Products"
},
"ABT":{
"name":"Abbott Laboratories",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"ABBV":{
"name":"AbbVie",
"sector":"Health Care",
"sub":"Biotechnology"
},
"ACN":{
"name":"Accenture",
"sector":"Information Technology",
"sub":"IT Consulting & Other Services"
},
"ADBE":{
"name":"Adobe Inc.",
"sector":"Information Technology",
"sub":"Application Software"
},
"AMD":{
"name":"Advanced Micro Devices",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"AES":{
"name":"AES Corporation",
"sector":"Utilities",
"sub":"Independent Power Producers & Energy Traders"
},
"AFL":{
"name":"Aflac",
"sector":"Financials",
"sub":"Life & Health Insurance"
},
"A":{
"name":"Agilent Technologies",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"APD":{
"name":"Air Products",
"sector":"Materials",
"sub":"Industrial Gases"
},
"ABNB":{
"name":"Airbnb",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"AKAM":{
"name":"Akamai Technologies",
"sector":"Information Technology",
"sub":"Internet Services & Infrastructure"
},
"ALB":{
"name":"Albemarle Corporation",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"ARE":{
"name":"Alexandria Real Estate Equities",
"sector":"Real Estate",
"sub":"Office REITs"
},
"ALGN":{
"name":"Align Technology",
"sector":"Health Care",
"sub":"Health Care Supplies"
},
"ALLE":{
"name":"Allegion",
"sector":"Industrials",
"sub":"Building Products"
},
"LNT":{
"name":"Alliant Energy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"ALL":{
"name":"Allstate",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"GOOGL":{
"name":"Alphabet Inc. (Class A)",
"sector":"Communication Services",
"sub":"Interactive Media & Services"
},
"GOOG":{
"name":"Alphabet Inc. (Class C)",
"sector":"Communication Services",
"sub":"Interactive Media & Services"
},
"MO":{
"name":"Altria",
"sector":"Consumer Staples",
"sub":"Tobacco"
},
"AMZN":{
"name":"Amazon",
"sector":"Consumer Discretionary",
"sub":"Broadline Retail"
},
"AMCR":{
"name":"Amcor",
"sector":"Materials",
"sub":"Paper & Plastic Packaging Products & Materials"
},
"AEE":{
"name":"Ameren",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"AEP":{
"name":"American Electric Power",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"AXP":{
"name":"American Express",
"sector":"Financials",
"sub":"Consumer Finance"
},
"AIG":{
"name":"American International Group",
"sector":"Financials",
"sub":"Multi-line Insurance"
},
"AMT":{
"name":"American Tower",
"sector":"Real Estate",
"sub":"Telecom Tower REITs"
},
"AWK":{
"name":"American Water Works",
"sector":"Utilities",
"sub":"Water Utilities"
},
"AMP":{
"name":"Ameriprise Financial",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"AME":{
"name":"Ametek",
"sector":"Industrials",
"sub":"Electrical Components & Equipment"
},
"AMGN":{
"name":"Amgen",
"sector":"Health Care",
"sub":"Biotechnology"
},
"APH":{
"name":"Amphenol",
"sector":"Information Technology",
"sub":"Electronic Components"
},
"ADI":{
"name":"Analog Devices",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"AON":{
"name":"Aon plc",
"sector":"Financials",
"sub":"Insurance Brokers"
},
"APA":{
"name":"APA Corporation",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"APO":{
"name":"Apollo Global Management",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"AAPL":{
"name":"Apple Inc.",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"AMAT":{
"name":"Applied Materials",
"sector":"Information Technology",
"sub":"Semiconductor Materials & Equipment"
},
"APP":{
"name":"AppLovin",
"sector":"Information Technology",
"sub":"Application Software"
},
"APTV":{
"name":"Aptiv",
"sector":"Consumer Discretionary",
"sub":"Automotive Parts & Equipment"
},
"ACGL":{
"name":"Arch Capital Group",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"ADM":{
"name":"Archer Daniels Midland",
"sector":"Consumer Staples",
"sub":"Agricultural Products & Services"
},
"ARES":{
"name":"Ares Management",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"ANET":{
"name":"Arista Networks",
"sector":"Information Technology",
"sub":"Communications Equipment"
},
"AJG":{
"name":"Arthur J. Gallagher & Co.",
"sector":"Financials",
"sub":"Insurance Brokers"
},
"AIZ":{
"name":"Assurant",
"sector":"Financials",
"sub":"Multi-line Insurance"
},
"T":{
"name":"AT&T",
"sector":"Communication Services",
"sub":"Integrated Telecommunication Services"
},
"ATO":{
"name":"Atmos Energy",
"sector":"Utilities",
"sub":"Gas Utilities"
},
"ADSK":{
"name":"Autodesk",
"sector":"Information Technology",
"sub":"Application Software"
},
"ADP":{
"name":"Automatic Data Processing",
"sector":"Industrials",
"sub":"Human Resource & Employment Services"
},
"AZO":{
"name":"AutoZone",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"AVB":{
"name":"AvalonBay Communities",
"sector":"Real Estate",
"sub":"Multi-Family Residential REITs"
},
"AVY":{
"name":"Avery Dennison",
"sector":"Materials",
"sub":"Paper & Plastic Packaging Products & Materials"
},
"AXON":{
"name":"Axon Enterprise",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"BKR":{
"name":"Baker Hughes",
"sector":"Energy",
"sub":"Oil & Gas Equipment & Services"
},
"BALL":{
"name":"Ball Corporation",
"sector":"Materials",
"sub":"Metal, Glass & Plastic Containers"
},
"BAC":{
"name":"Bank of America",
"sector":"Financials",
"sub":"Diversified Banks"
},
"BAX":{
"name":"Baxter International",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"BDX":{
"name":"Becton Dickinson",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"BRK-B":{
"name":"Berkshire Hathaway",
"sector":"Financials",
"sub":"Multi-Sector Holdings"
},
"BBY":{
"name":"Best Buy",
"sector":"Consumer Discretionary",
"sub":"Computer & Electronics Retail"
},
"TECH":{
"name":"Bio-Techne",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"BIIB":{
"name":"Biogen",
"sector":"Health Care",
"sub":"Biotechnology"
},
"BLK":{
"name":"BlackRock",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"BX":{
"name":"Blackstone Inc.",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"XYZ":{
"name":"Block, Inc.",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"BNY":{
"name":"BNY Mellon",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"BA":{
"name":"Boeing",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"BKNG":{
"name":"Booking Holdings",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"BSX":{
"name":"Boston Scientific",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"BMY":{
"name":"Bristol Myers Squibb",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"AVGO":{
"name":"Broadcom",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"BR":{
"name":"Broadridge Financial Solutions",
"sector":"Industrials",
"sub":"Data Processing & Outsourced Services"
},
"BRO":{
"name":"Brown & Brown",
"sector":"Financials",
"sub":"Insurance Brokers"
},
"BF-B":{
"name":"Brown\u2013Forman",
"sector":"Consumer Staples",
"sub":"Distillers & Vintners"
},
"BLDR":{
"name":"Builders FirstSource",
"sector":"Industrials",
"sub":"Building Products"
},
"BG":{
"name":"Bunge Global",
"sector":"Consumer Staples",
"sub":"Agricultural Products & Services"
},
"BXP":{
"name":"BXP, Inc.",
"sector":"Real Estate",
"sub":"Office REITs"
},
"CHRW":{
"name":"C.H. Robinson",
"sector":"Industrials",
"sub":"Air Freight & Logistics"
},
"CDNS":{
"name":"Cadence Design Systems",
"sector":"Information Technology",
"sub":"Application Software"
},
"CPT":{
"name":"Camden Property Trust",
"sector":"Real Estate",
"sub":"Multi-Family Residential REITs"
},
"CPB":{
"name":"Campbell's Company (The)",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"COF":{
"name":"Capital One",
"sector":"Financials",
"sub":"Consumer Finance"
},
"CAH":{
"name":"Cardinal Health",
"sector":"Health Care",
"sub":"Health Care Distributors"
},
"CCL":{
"name":"Carnival Corporation",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"CARR":{
"name":"Carrier Global",
"sector":"Industrials",
"sub":"Building Products"
},
"CVNA":{
"name":"Carvana",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"CASY":{
"name":"Casey's",
"sector":"Consumer Staples",
"sub":"Food Retail"
},
"CAT":{
"name":"Caterpillar Inc.",
"sector":"Industrials",
"sub":"Construction Machinery & Heavy Transportation Equipment"
},
"CBOE":{
"name":"Cboe Global Markets",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"CBRE":{
"name":"CBRE Group",
"sector":"Real Estate",
"sub":"Real Estate Services"
},
"CDW":{
"name":"CDW Corporation",
"sector":"Information Technology",
"sub":"Technology Distributors"
},
"COR":{
"name":"Cencora",
"sector":"Health Care",
"sub":"Health Care Distributors"
},
"CNC":{
"name":"Centene Corporation",
"sector":"Health Care",
"sub":"Managed Health Care"
},
"CNP":{
"name":"CenterPoint Energy",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"CF":{
"name":"CF Industries",
"sector":"Materials",
"sub":"Fertilizers & Agricultural Chemicals"
},
"CRL":{
"name":"Charles River Laboratories",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"SCHW":{
"name":"Charles Schwab Corporation",
"sector":"Financials",
"sub":"Investment Banking & Brokerage"
},
"CHTR":{
"name":"Charter Communications",
"sector":"Communication Services",
"sub":"Cable & Satellite"
},
"CVX":{
"name":"Chevron Corporation",
"sector":"Energy",
"sub":"Integrated Oil & Gas"
},
"CMG":{
"name":"Chipotle Mexican Grill",
"sector":"Consumer Discretionary",
"sub":"Restaurants"
},
"CB":{
"name":"Chubb Limited",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"CHD":{
"name":"Church & Dwight",
"sector":"Consumer Staples",
"sub":"Household Products"
},
"CIEN":{
"name":"Ciena",
"sector":"Information Technology",
"sub":"Communications Equipment"
},
"CI":{
"name":"Cigna",
"sector":"Health Care",
"sub":"Health Care Services"
},
"CINF":{
"name":"Cincinnati Financial",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"CTAS":{
"name":"Cintas",
"sector":"Industrials",
"sub":"Diversified Support Services"
},
"CSCO":{
"name":"Cisco",
"sector":"Information Technology",
"sub":"Communications Equipment"
},
"C":{
"name":"Citigroup",
"sector":"Financials",
"sub":"Diversified Banks"
},
"CFG":{
"name":"Citizens Financial Group",
"sector":"Financials",
"sub":"Regional Banks"
},
"CLX":{
"name":"Clorox",
"sector":"Consumer Staples",
"sub":"Household Products"
},
"CME":{
"name":"CME Group",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"CMS":{
"name":"CMS Energy",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"KO":{
"name":"Coca-Cola Company (The)",
"sector":"Consumer Staples",
"sub":"Soft Drinks & Non-alcoholic Beverages"
},
"CTSH":{
"name":"Cognizant",
"sector":"Information Technology",
"sub":"IT Consulting & Other Services"
},
"COHR":{
"name":"Coherent Corp.",
"sector":"Information Technology",
"sub":"Electronic Components"
},
"COIN":{
"name":"Coinbase",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"CL":{
"name":"Colgate-Palmolive",
"sector":"Consumer Staples",
"sub":"Household Products"
},
"CMCSA":{
"name":"Comcast",
"sector":"Communication Services",
"sub":"Cable & Satellite"
},
"FIX":{
"name":"Comfort Systems USA",
"sector":"Industrials",
"sub":"Construction & Engineering"
},
"CAG":{
"name":"Conagra Brands",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"COP":{
"name":"ConocoPhillips",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"ED":{
"name":"Consolidated Edison",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"STZ":{
"name":"Constellation Brands",
"sector":"Consumer Staples",
"sub":"Distillers & Vintners"
},
"CEG":{
"name":"Constellation Energy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"COO":{
"name":"Cooper Companies (The)",
"sector":"Health Care",
"sub":"Health Care Supplies"
},
"CPRT":{
"name":"Copart",
"sector":"Industrials",
"sub":"Diversified Support Services"
},
"GLW":{
"name":"Corning Inc.",
"sector":"Information Technology",
"sub":"Electronic Components"
},
"CPAY":{
"name":"Corpay",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"CTVA":{
"name":"Corteva",
"sector":"Materials",
"sub":"Fertilizers & Agricultural Chemicals"
},
"CSGP":{
"name":"CoStar Group",
"sector":"Real Estate",
"sub":"Real Estate Services"
},
"COST":{
"name":"Costco",
"sector":"Consumer Staples",
"sub":"Consumer Staples Merchandise Retail"
},
"CRH":{
"name":"CRH plc",
"sector":"Materials",
"sub":"Construction Materials"
},
"CRWD":{
"name":"CrowdStrike",
"sector":"Information Technology",
"sub":"Systems Software"
},
"CCI":{
"name":"Crown Castle",
"sector":"Real Estate",
"sub":"Telecom Tower REITs"
},
"CSX":{
"name":"CSX Corporation",
"sector":"Industrials",
"sub":"Rail Transportation"
},
"CMI":{
"name":"Cummins",
"sector":"Industrials",
"sub":"Construction Machinery & Heavy Transportation Equipment"
},
"CVS":{
"name":"CVS Health",
"sector":"Health Care",
"sub":"Health Care Services"
},
"DHR":{
"name":"Danaher Corporation",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"DRI":{
"name":"Darden Restaurants",
"sector":"Consumer Discretionary",
"sub":"Restaurants"
},
"DDOG":{
"name":"Datadog",
"sector":"Information Technology",
"sub":"Application Software"
},
"DVA":{
"name":"DaVita",
"sector":"Health Care",
"sub":"Health Care Services"
},
"DECK":{
"name":"Deckers Brands",
"sector":"Consumer Discretionary",
"sub":"Footwear"
},
"DE":{
"name":"Deere & Company",
"sector":"Industrials",
"sub":"Agricultural & Farm Machinery"
},
"DELL":{
"name":"Dell Technologies",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"DAL":{
"name":"Delta Air Lines",
"sector":"Industrials",
"sub":"Passenger Airlines"
},
"DVN":{
"name":"Devon Energy",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"DXCM":{
"name":"Dexcom",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"FANG":{
"name":"Diamondback Energy",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"DLR":{
"name":"Digital Realty",
"sector":"Real Estate",
"sub":"Data Center REITs"
},
"DG":{
"name":"Dollar General",
"sector":"Consumer Staples",
"sub":"Consumer Staples Merchandise Retail"
},
"DLTR":{
"name":"Dollar Tree",
"sector":"Consumer Staples",
"sub":"Consumer Staples Merchandise Retail"
},
"D":{
"name":"Dominion Energy",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"DPZ":{
"name":"Domino's",
"sector":"Consumer Discretionary",
"sub":"Restaurants"
},
"DASH":{
"name":"DoorDash",
"sector":"Consumer Discretionary",
"sub":"Specialized Consumer Services"
},
"DOV":{
"name":"Dover Corporation",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"DOW":{
"name":"Dow Inc.",
"sector":"Materials",
"sub":"Commodity Chemicals"
},
"DHI":{
"name":"D. R. Horton",
"sector":"Consumer Discretionary",
"sub":"Homebuilding"
},
"DTE":{
"name":"DTE Energy",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"DUK":{
"name":"Duke Energy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"DD":{
"name":"DuPont",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"ETN":{
"name":"Eaton Corporation",
"sector":"Industrials",
"sub":"Electrical Components & Equipment"
},
"EBAY":{
"name":"eBay Inc.",
"sector":"Consumer Discretionary",
"sub":"Broadline Retail"
},
"SATS":{
"name":"EchoStar",
"sector":"Communication Services",
"sub":"Wireless Telecommunication Services"
},
"ECL":{
"name":"Ecolab",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"EIX":{
"name":"Edison International",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"EW":{
"name":"Edwards Lifesciences",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"EA":{
"name":"Electronic Arts",
"sector":"Communication Services",
"sub":"Interactive Home Entertainment"
},
"ELV":{
"name":"Elevance Health",
"sector":"Health Care",
"sub":"Managed Health Care"
},
"EME":{
"name":"Emcor",
"sector":"Industrials",
"sub":"Construction & Engineering"
},
"EMR":{
"name":"Emerson Electric",
"sector":"Industrials",
"sub":"Electrical Components & Equipment"
},
"ETR":{
"name":"Entergy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"EOG":{
"name":"EOG Resources",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"EQT":{
"name":"EQT Corporation",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"EFX":{
"name":"Equifax",
"sector":"Industrials",
"sub":"Research & Consulting Services"
},
"EQIX":{
"name":"Equinix",
"sector":"Real Estate",
"sub":"Data Center REITs"
},
"EQR":{
"name":"Equity Residential",
"sector":"Real Estate",
"sub":"Multi-Family Residential REITs"
},
"ERIE":{
"name":"Erie Indemnity",
"sector":"Financials",
"sub":"Insurance Brokers"
},
"ESS":{
"name":"Essex Property Trust",
"sector":"Real Estate",
"sub":"Multi-Family Residential REITs"
},
"EL":{
"name":"Est\u00e9e Lauder Companies (The)",
"sector":"Consumer Staples",
"sub":"Personal Care Products"
},
"EG":{
"name":"Everest Group",
"sector":"Financials",
"sub":"Reinsurance"
},
"EVRG":{
"name":"Evergy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"ES":{
"name":"Eversource Energy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"EXC":{
"name":"Exelon",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"EXE":{
"name":"Expand Energy",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"EXPE":{
"name":"Expedia Group",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"EXPD":{
"name":"Expeditors International",
"sector":"Industrials",
"sub":"Air Freight & Logistics"
},
"EXR":{
"name":"Extra Space Storage",
"sector":"Real Estate",
"sub":"Self-Storage REITs"
},
"XOM":{
"name":"ExxonMobil",
"sector":"Energy",
"sub":"Integrated Oil & Gas"
},
"FFIV":{
"name":"F5, Inc.",
"sector":"Information Technology",
"sub":"Communications Equipment"
},
"FDS":{
"name":"FactSet",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"FICO":{
"name":"Fair Isaac",
"sector":"Information Technology",
"sub":"Application Software"
},
"FAST":{
"name":"Fastenal",
"sector":"Industrials",
"sub":"Trading Companies & Distributors"
},
"FRT":{
"name":"Federal Realty Investment Trust",
"sector":"Real Estate",
"sub":"Retail REITs"
},
"FDX":{
"name":"FedEx",
"sector":"Industrials",
"sub":"Air Freight & Logistics"
},
"FDXF":{
"name":"FedEx Freight",
"sector":"Industrials",
"sub":"Cargo Ground Transportation"
},
"FIS":{
"name":"Fidelity National Information Services",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"FITB":{
"name":"Fifth Third Bancorp",
"sector":"Financials",
"sub":"Regional Banks"
},
"FSLR":{
"name":"First Solar",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"FE":{
"name":"FirstEnergy",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"FISV":{
"name":"Fiserv",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"F":{
"name":"Ford Motor Company",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"FTNT":{
"name":"Fortinet",
"sector":"Information Technology",
"sub":"Systems Software"
},
"FTV":{
"name":"Fortive",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"FOXA":{
"name":"Fox Corporation (Class A)",
"sector":"Communication Services",
"sub":"Broadcasting"
},
"FOX":{
"name":"Fox Corporation (Class B)",
"sector":"Communication Services",
"sub":"Broadcasting"
},
"BEN":{
"name":"Franklin Resources",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"FCX":{
"name":"Freeport-McMoRan",
"sector":"Materials",
"sub":"Copper"
},
"GRMN":{
"name":"Garmin",
"sector":"Consumer Discretionary",
"sub":"Consumer Electronics"
},
"IT":{
"name":"Gartner",
"sector":"Information Technology",
"sub":"IT Consulting & Other Services"
},
"GE":{
"name":"GE Aerospace",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"GEHC":{
"name":"GE HealthCare",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"GEV":{
"name":"GE Vernova",
"sector":"Industrials",
"sub":"Heavy Electrical Equipment"
},
"GEN":{
"name":"Gen Digital",
"sector":"Information Technology",
"sub":"Systems Software"
},
"GNRC":{
"name":"Generac",
"sector":"Industrials",
"sub":"Electrical Components & Equipment"
},
"GD":{
"name":"General Dynamics",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"GIS":{
"name":"General Mills",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"GM":{
"name":"General Motors",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"GPC":{
"name":"Genuine Parts Company",
"sector":"Consumer Discretionary",
"sub":"Distributors"
},
"GILD":{
"name":"Gilead Sciences",
"sector":"Health Care",
"sub":"Biotechnology"
},
"GPN":{
"name":"Global Payments",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"GL":{
"name":"Globe Life",
"sector":"Financials",
"sub":"Life & Health Insurance"
},
"GDDY":{
"name":"GoDaddy",
"sector":"Information Technology",
"sub":"Internet Services & Infrastructure"
},
"GS":{
"name":"Goldman Sachs",
"sector":"Financials",
"sub":"Investment Banking & Brokerage"
},
"HAL":{
"name":"Halliburton",
"sector":"Energy",
"sub":"Oil & Gas Equipment & Services"
},
"HIG":{
"name":"Hartford (The)",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"HAS":{
"name":"Hasbro",
"sector":"Consumer Discretionary",
"sub":"Leisure Products"
},
"HCA":{
"name":"HCA Healthcare",
"sector":"Health Care",
"sub":"Health Care Facilities"
},
"DOC":{
"name":"Healthpeak Properties",
"sector":"Real Estate",
"sub":"Health Care REITs"
},
"HSIC":{
"name":"Henry Schein",
"sector":"Health Care",
"sub":"Health Care Distributors"
},
"HSY":{
"name":"Hershey Company (The)",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"HPE":{
"name":"Hewlett Packard Enterprise",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"HLT":{
"name":"Hilton Worldwide",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"HD":{
"name":"Home Depot (The)",
"sector":"Consumer Discretionary",
"sub":"Home Improvement Retail"
},
"HON":{
"name":"Honeywell",
"sector":"Industrials",
"sub":"Industrial Conglomerates"
},
"HRL":{
"name":"Hormel Foods",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"HST":{
"name":"Host Hotels & Resorts",
"sector":"Real Estate",
"sub":"Hotel & Resort REITs"
},
"HWM":{
"name":"Howmet Aerospace",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"HPQ":{
"name":"HP Inc.",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"HUBB":{
"name":"Hubbell Incorporated",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"HUM":{
"name":"Humana",
"sector":"Health Care",
"sub":"Managed Health Care"
},
"HBAN":{
"name":"Huntington Bancshares",
"sector":"Financials",
"sub":"Regional Banks"
},
"HII":{
"name":"Huntington Ingalls Industries",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"IBM":{
"name":"IBM",
"sector":"Information Technology",
"sub":"IT Consulting & Other Services"
},
"IEX":{
"name":"IDEX Corporation",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"IDXX":{
"name":"Idexx Laboratories",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"ITW":{
"name":"Illinois Tool Works",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"INCY":{
"name":"Incyte",
"sector":"Health Care",
"sub":"Biotechnology"
},
"IR":{
"name":"Ingersoll Rand",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"PODD":{
"name":"Insulet Corporation",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"INTC":{
"name":"Intel",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"IBKR":{
"name":"Interactive Brokers",
"sector":"Financials",
"sub":"Investment Banking & Brokerage"
},
"ICE":{
"name":"Intercontinental Exchange",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"IFF":{
"name":"International Flavors & Fragrances",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"IP":{
"name":"International Paper",
"sector":"Materials",
"sub":"Paper & Plastic Packaging Products & Materials"
},
"INTU":{
"name":"Intuit",
"sector":"Information Technology",
"sub":"Application Software"
},
"ISRG":{
"name":"Intuitive Surgical",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"IVZ":{
"name":"Invesco",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"INVH":{
"name":"Invitation Homes",
"sector":"Real Estate",
"sub":"Single-Family Residential REITs"
},
"IQV":{
"name":"IQVIA",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"IRM":{
"name":"Iron Mountain",
"sector":"Real Estate",
"sub":"Other Specialized REITs"
},
"JBHT":{
"name":"J.B. Hunt",
"sector":"Industrials",
"sub":"Cargo Ground Transportation"
},
"JBL":{
"name":"Jabil",
"sector":"Information Technology",
"sub":"Electronic Manufacturing Services"
},
"JKHY":{
"name":"Jack Henry & Associates",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"J":{
"name":"Jacobs Solutions",
"sector":"Industrials",
"sub":"Construction & Engineering"
},
"JNJ":{
"name":"Johnson & Johnson",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"JCI":{
"name":"Johnson Controls",
"sector":"Industrials",
"sub":"Building Products"
},
"JPM":{
"name":"JPMorgan Chase",
"sector":"Financials",
"sub":"Diversified Banks"
},
"KVUE":{
"name":"Kenvue",
"sector":"Consumer Staples",
"sub":"Personal Care Products"
},
"KDP":{
"name":"Keurig Dr Pepper",
"sector":"Consumer Staples",
"sub":"Soft Drinks & Non-alcoholic Beverages"
},
"KEY":{
"name":"KeyCorp",
"sector":"Financials",
"sub":"Regional Banks"
},
"KEYS":{
"name":"Keysight Technologies",
"sector":"Information Technology",
"sub":"Electronic Equipment & Instruments"
},
"KMB":{
"name":"Kimberly-Clark",
"sector":"Consumer Staples",
"sub":"Household Products"
},
"KIM":{
"name":"Kimco Realty",
"sector":"Real Estate",
"sub":"Retail REITs"
},
"KMI":{
"name":"Kinder Morgan",
"sector":"Energy",
"sub":"Oil & Gas Storage & Transportation"
},
"KKR":{
"name":"KKR & Co.",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"KLAC":{
"name":"KLA Corporation",
"sector":"Information Technology",
"sub":"Semiconductor Materials & Equipment"
},
"KHC":{
"name":"Kraft Heinz",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"KR":{
"name":"Kroger",
"sector":"Consumer Staples",
"sub":"Food Retail"
},
"LHX":{
"name":"L3Harris",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"LH":{
"name":"Labcorp",
"sector":"Health Care",
"sub":"Health Care Services"
},
"LRCX":{
"name":"Lam Research",
"sector":"Information Technology",
"sub":"Semiconductor Materials & Equipment"
},
"LVS":{
"name":"Las Vegas Sands",
"sector":"Consumer Discretionary",
"sub":"Casinos & Gaming"
},
"LDOS":{
"name":"Leidos",
"sector":"Industrials",
"sub":"Diversified Support Services"
},
"LEN":{
"name":"Lennar",
"sector":"Consumer Discretionary",
"sub":"Homebuilding"
},
"LII":{
"name":"Lennox International",
"sector":"Industrials",
"sub":"Building Products"
},
"LLY":{
"name":"Lilly (Eli)",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"LIN":{
"name":"Linde plc",
"sector":"Materials",
"sub":"Industrial Gases"
},
"LYV":{
"name":"Live Nation Entertainment",
"sector":"Communication Services",
"sub":"Movies & Entertainment"
},
"LMT":{
"name":"Lockheed Martin",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"L":{
"name":"Loews Corporation",
"sector":"Financials",
"sub":"Multi-line Insurance"
},
"LOW":{
"name":"Lowe's",
"sector":"Consumer Discretionary",
"sub":"Home Improvement Retail"
},
"LULU":{
"name":"Lululemon Athletica",
"sector":"Consumer Discretionary",
"sub":"Apparel, Accessories & Luxury Goods"
},
"LITE":{
"name":"Lumentum",
"sector":"Information Technology",
"sub":"Communications Equipment"
},
"LYB":{
"name":"LyondellBasell",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"MTB":{
"name":"M&T Bank",
"sector":"Financials",
"sub":"Regional Banks"
},
"MPC":{
"name":"Marathon Petroleum",
"sector":"Energy",
"sub":"Oil & Gas Refining & Marketing"
},
"MAR":{
"name":"Marriott International",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"MRSH":{
"name":"Marsh McLennan",
"sector":"Financials",
"sub":"Insurance Brokers"
},
"MLM":{
"name":"Martin Marietta Materials",
"sector":"Materials",
"sub":"Construction Materials"
},
"MAS":{
"name":"Masco",
"sector":"Industrials",
"sub":"Building Products"
},
"MA":{
"name":"Mastercard",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"MKC":{
"name":"McCormick & Company",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"MCD":{
"name":"McDonald's",
"sector":"Consumer Discretionary",
"sub":"Restaurants"
},
"MCK":{
"name":"McKesson Corporation",
"sector":"Health Care",
"sub":"Health Care Distributors"
},
"MDT":{
"name":"Medtronic",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"MRK":{
"name":"Merck & Co.",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"META":{
"name":"Meta Platforms",
"sector":"Communication Services",
"sub":"Interactive Media & Services"
},
"MET":{
"name":"MetLife",
"sector":"Financials",
"sub":"Life & Health Insurance"
},
"MTD":{
"name":"Mettler Toledo",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"MGM":{
"name":"MGM Resorts",
"sector":"Consumer Discretionary",
"sub":"Casinos & Gaming"
},
"MCHP":{
"name":"Microchip Technology",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"MU":{
"name":"Micron Technology",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"MSFT":{
"name":"Microsoft",
"sector":"Information Technology",
"sub":"Systems Software"
},
"MAA":{
"name":"Mid-America Apartment Communities",
"sector":"Real Estate",
"sub":"Multi-Family Residential REITs"
},
"MRNA":{
"name":"Moderna",
"sector":"Health Care",
"sub":"Biotechnology"
},
"TAP":{
"name":"Molson Coors Beverage Company",
"sector":"Consumer Staples",
"sub":"Brewers"
},
"MDLZ":{
"name":"Mondelez International",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"MPWR":{
"name":"Monolithic Power Systems",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"MNST":{
"name":"Monster Beverage",
"sector":"Consumer Staples",
"sub":"Soft Drinks & Non-alcoholic Beverages"
},
"MCO":{
"name":"Moody's Corporation",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"MS":{
"name":"Morgan Stanley",
"sector":"Financials",
"sub":"Investment Banking & Brokerage"
},
"MOS":{
"name":"Mosaic Company (The)",
"sector":"Materials",
"sub":"Fertilizers & Agricultural Chemicals"
},
"MSI":{
"name":"Motorola Solutions",
"sector":"Information Technology",
"sub":"Communications Equipment"
},
"MSCI":{
"name":"MSCI Inc.",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"NDAQ":{
"name":"Nasdaq, Inc.",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"NTAP":{
"name":"NetApp",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"NFLX":{
"name":"Netflix",
"sector":"Communication Services",
"sub":"Movies & Entertainment"
},
"NEM":{
"name":"Newmont",
"sector":"Materials",
"sub":"Gold"
},
"NWSA":{
"name":"News Corp (Class A)",
"sector":"Communication Services",
"sub":"Publishing"
},
"NWS":{
"name":"News Corp (Class B)",
"sector":"Communication Services",
"sub":"Publishing"
},
"NEE":{
"name":"NextEra Energy",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"NKE":{
"name":"Nike, Inc.",
"sector":"Consumer Discretionary",
"sub":"Apparel, Accessories & Luxury Goods"
},
"NI":{
"name":"NiSource",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"NDSN":{
"name":"Nordson Corporation",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"NSC":{
"name":"Norfolk Southern",
"sector":"Industrials",
"sub":"Rail Transportation"
},
"NTRS":{
"name":"Northern Trust",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"NOC":{
"name":"Northrop Grumman",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"NCLH":{
"name":"Norwegian Cruise Line Holdings",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"NRG":{
"name":"NRG Energy",
"sector":"Utilities",
"sub":"Independent Power Producers & Energy Traders"
},
"NUE":{
"name":"Nucor",
"sector":"Materials",
"sub":"Steel"
},
"NVDA":{
"name":"Nvidia",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"NVR":{
"name":"NVR, Inc.",
"sector":"Consumer Discretionary",
"sub":"Homebuilding"
},
"NXPI":{
"name":"NXP Semiconductors",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"ORLY":{
"name":"O\u2019Reilly Automotive",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"OXY":{
"name":"Occidental Petroleum",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"ODFL":{
"name":"Old Dominion",
"sector":"Industrials",
"sub":"Cargo Ground Transportation"
},
"OMC":{
"name":"Omnicom Group",
"sector":"Communication Services",
"sub":"Advertising"
},
"ON":{
"name":"ON Semiconductor",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"OKE":{
"name":"Oneok",
"sector":"Energy",
"sub":"Oil & Gas Storage & Transportation"
},
"ORCL":{
"name":"Oracle Corporation",
"sector":"Information Technology",
"sub":"Application Software"
},
"OTIS":{
"name":"Otis Worldwide",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"PCAR":{
"name":"Paccar",
"sector":"Industrials",
"sub":"Construction Machinery & Heavy Transportation Equipment"
},
"PKG":{
"name":"Packaging Corporation of America",
"sector":"Materials",
"sub":"Paper & Plastic Packaging Products & Materials"
},
"PLTR":{
"name":"Palantir Technologies",
"sector":"Information Technology",
"sub":"Application Software"
},
"PANW":{
"name":"Palo Alto Networks",
"sector":"Information Technology",
"sub":"Systems Software"
},
"PSKY":{
"name":"Paramount Skydance Corporation",
"sector":"Communication Services",
"sub":"Movies & Entertainment"
},
"PH":{
"name":"Parker Hannifin",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"PAYX":{
"name":"Paychex",
"sector":"Industrials",
"sub":"Human Resource & Employment Services"
},
"PYPL":{
"name":"PayPal",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"PNR":{
"name":"Pentair",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"PEP":{
"name":"PepsiCo",
"sector":"Consumer Staples",
"sub":"Soft Drinks & Non-alcoholic Beverages"
},
"PFE":{
"name":"Pfizer",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"PCG":{
"name":"PG&E Corporation",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"PM":{
"name":"Philip Morris International",
"sector":"Consumer Staples",
"sub":"Tobacco"
},
"PSX":{
"name":"Phillips 66",
"sector":"Energy",
"sub":"Oil & Gas Refining & Marketing"
},
"PNW":{
"name":"Pinnacle West Capital",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"PNC":{
"name":"PNC Financial Services",
"sector":"Financials",
"sub":"Diversified Banks"
},
"POOL":{
"name":"Pool Corporation",
"sector":"Consumer Discretionary",
"sub":"Distributors"
},
"PPG":{
"name":"PPG Industries",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"PPL":{
"name":"PPL Corporation",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"PFG":{
"name":"Principal Financial Group",
"sector":"Financials",
"sub":"Life & Health Insurance"
},
"PG":{
"name":"Procter & Gamble",
"sector":"Consumer Staples",
"sub":"Personal Care Products"
},
"PGR":{
"name":"Progressive Corporation",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"PLD":{
"name":"Prologis",
"sector":"Real Estate",
"sub":"Industrial REITs"
},
"PRU":{
"name":"Prudential Financial",
"sector":"Financials",
"sub":"Life & Health Insurance"
},
"PEG":{
"name":"Public Service Enterprise Group",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"PTC":{
"name":"PTC Inc.",
"sector":"Information Technology",
"sub":"Application Software"
},
"PSA":{
"name":"Public Storage",
"sector":"Real Estate",
"sub":"Self-Storage REITs"
},
"PHM":{
"name":"PulteGroup",
"sector":"Consumer Discretionary",
"sub":"Homebuilding"
},
"PWR":{
"name":"Quanta Services",
"sector":"Industrials",
"sub":"Construction & Engineering"
},
"QCOM":{
"name":"Qualcomm",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"DGX":{
"name":"Quest Diagnostics",
"sector":"Health Care",
"sub":"Health Care Services"
},
"Q":{
"name":"Qnity Electronics",
"sector":"Information Technology",
"sub":"Semiconductor Materials & Equipment"
},
"RL":{
"name":"Ralph Lauren Corporation",
"sector":"Consumer Discretionary",
"sub":"Apparel, Accessories & Luxury Goods"
},
"RJF":{
"name":"Raymond James Financial",
"sector":"Financials",
"sub":"Investment Banking & Brokerage"
},
"RTX":{
"name":"RTX Corporation",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"O":{
"name":"Realty Income",
"sector":"Real Estate",
"sub":"Retail REITs"
},
"REG":{
"name":"Regency Centers",
"sector":"Real Estate",
"sub":"Retail REITs"
},
"REGN":{
"name":"Regeneron Pharmaceuticals",
"sector":"Health Care",
"sub":"Biotechnology"
},
"RF":{
"name":"Regions Financial Corporation",
"sector":"Financials",
"sub":"Regional Banks"
},
"RSG":{
"name":"Republic Services",
"sector":"Industrials",
"sub":"Environmental & Facilities Services"
},
"RMD":{
"name":"ResMed",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"RVTY":{
"name":"Revvity",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"HOOD":{
"name":"Robinhood Markets",
"sector":"Financials",
"sub":"Investment Banking & Brokerage"
},
"ROK":{
"name":"Rockwell Automation",
"sector":"Industrials",
"sub":"Electrical Components & Equipment"
},
"ROL":{
"name":"Rollins, Inc.",
"sector":"Industrials",
"sub":"Environmental & Facilities Services"
},
"ROP":{
"name":"Roper Technologies",
"sector":"Information Technology",
"sub":"Electronic Equipment & Instruments"
},
"ROST":{
"name":"Ross Stores",
"sector":"Consumer Discretionary",
"sub":"Apparel Retail"
},
"RCL":{
"name":"Royal Caribbean Group",
"sector":"Consumer Discretionary",
"sub":"Hotels, Resorts & Cruise Lines"
},
"SPGI":{
"name":"S&P Global",
"sector":"Financials",
"sub":"Financial Exchanges & Data"
},
"CRM":{
"name":"Salesforce",
"sector":"Information Technology",
"sub":"Application Software"
},
"SNDK":{
"name":"Sandisk",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"SBAC":{
"name":"SBA Communications",
"sector":"Real Estate",
"sub":"Telecom Tower REITs"
},
"SLB":{
"name":"Schlumberger",
"sector":"Energy",
"sub":"Oil & Gas Equipment & Services"
},
"STX":{
"name":"Seagate Technology",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"SRE":{
"name":"Sempra",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"NOW":{
"name":"ServiceNow",
"sector":"Information Technology",
"sub":"Systems Software"
},
"SHW":{
"name":"Sherwin-Williams",
"sector":"Materials",
"sub":"Specialty Chemicals"
},
"SPG":{
"name":"Simon Property Group",
"sector":"Real Estate",
"sub":"Retail REITs"
},
"SWKS":{
"name":"Skyworks Solutions",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"SJM":{
"name":"J.M. Smucker Company (The)",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"SW":{
"name":"Smurfit Westrock",
"sector":"Materials",
"sub":"Paper & Plastic Packaging Products & Materials"
},
"SNA":{
"name":"Snap-on",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"SOLV":{
"name":"Solventum",
"sector":"Health Care",
"sub":"Health Care Technology"
},
"SO":{
"name":"Southern Company",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"LUV":{
"name":"Southwest Airlines",
"sector":"Industrials",
"sub":"Passenger Airlines"
},
"SWK":{
"name":"Stanley Black & Decker",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"SBUX":{
"name":"Starbucks",
"sector":"Consumer Discretionary",
"sub":"Restaurants"
},
"STT":{
"name":"State Street Corporation",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"STLD":{
"name":"Steel Dynamics",
"sector":"Materials",
"sub":"Steel"
},
"STE":{
"name":"Steris",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"SYK":{
"name":"Stryker Corporation",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"SMCI":{
"name":"Supermicro",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"SYF":{
"name":"Synchrony Financial",
"sector":"Financials",
"sub":"Consumer Finance"
},
"SNPS":{
"name":"Synopsys",
"sector":"Information Technology",
"sub":"Application Software"
},
"SYY":{
"name":"Sysco",
"sector":"Consumer Staples",
"sub":"Food Distributors"
},
"TMUS":{
"name":"T-Mobile US",
"sector":"Communication Services",
"sub":"Wireless Telecommunication Services"
},
"TROW":{
"name":"T. Rowe Price",
"sector":"Financials",
"sub":"Asset Management & Custody Banks"
},
"TTWO":{
"name":"Take-Two Interactive",
"sector":"Communication Services",
"sub":"Interactive Home Entertainment"
},
"TPR":{
"name":"Tapestry, Inc.",
"sector":"Consumer Discretionary",
"sub":"Apparel, Accessories & Luxury Goods"
},
"TRGP":{
"name":"Targa Resources",
"sector":"Energy",
"sub":"Oil & Gas Storage & Transportation"
},
"TGT":{
"name":"Target Corporation",
"sector":"Consumer Staples",
"sub":"Consumer Staples Merchandise Retail"
},
"TEL":{
"name":"TE Connectivity",
"sector":"Information Technology",
"sub":"Electronic Manufacturing Services"
},
"TDY":{
"name":"Teledyne Technologies",
"sector":"Information Technology",
"sub":"Electronic Equipment & Instruments"
},
"TER":{
"name":"Teradyne",
"sector":"Information Technology",
"sub":"Semiconductor Materials & Equipment"
},
"TSLA":{
"name":"Tesla, Inc.",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"TXN":{
"name":"Texas Instruments",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"TPL":{
"name":"Texas Pacific Land Corporation",
"sector":"Energy",
"sub":"Oil & Gas Exploration & Production"
},
"TXT":{
"name":"Textron",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"TMO":{
"name":"Thermo Fisher Scientific",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"TJX":{
"name":"TJX Companies",
"sector":"Consumer Discretionary",
"sub":"Apparel Retail"
},
"TKO":{
"name":"TKO Group Holdings",
"sector":"Communication Services",
"sub":"Movies & Entertainment"
},
"TTD":{
"name":"Trade Desk (The)",
"sector":"Communication Services",
"sub":"Advertising"
},
"TSCO":{
"name":"Tractor Supply",
"sector":"Consumer Discretionary",
"sub":"Other Specialty Retail"
},
"TT":{
"name":"Trane Technologies",
"sector":"Industrials",
"sub":"Building Products"
},
"TDG":{
"name":"TransDigm Group",
"sector":"Industrials",
"sub":"Aerospace & Defense"
},
"TRV":{
"name":"Travelers Companies (The)",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"TRMB":{
"name":"Trimble Inc.",
"sector":"Information Technology",
"sub":"Application Software"
},
"TFC":{
"name":"Truist Financial",
"sector":"Financials",
"sub":"Diversified Banks"
},
"TYL":{
"name":"Tyler Technologies",
"sector":"Information Technology",
"sub":"Application Software"
},
"TSN":{
"name":"Tyson Foods",
"sector":"Consumer Staples",
"sub":"Packaged Foods & Meats"
},
"USB":{
"name":"U.S. Bancorp",
"sector":"Financials",
"sub":"Diversified Banks"
},
"UBER":{
"name":"Uber",
"sector":"Industrials",
"sub":"Passenger Ground Transportation"
},
"UDR":{
"name":"UDR, Inc.",
"sector":"Real Estate",
"sub":"Multi-Family Residential REITs"
},
"ULTA":{
"name":"Ulta Beauty",
"sector":"Consumer Discretionary",
"sub":"Other Specialty Retail"
},
"UNP":{
"name":"Union Pacific Corporation",
"sector":"Industrials",
"sub":"Rail Transportation"
},
"UAL":{
"name":"United Airlines Holdings",
"sector":"Industrials",
"sub":"Passenger Airlines"
},
"UPS":{
"name":"United Parcel Service",
"sector":"Industrials",
"sub":"Air Freight & Logistics"
},
"URI":{
"name":"United Rentals",
"sector":"Industrials",
"sub":"Trading Companies & Distributors"
},
"UNH":{
"name":"UnitedHealth Group",
"sector":"Health Care",
"sub":"Managed Health Care"
},
"UHS":{
"name":"Universal Health Services",
"sector":"Health Care",
"sub":"Health Care Facilities"
},
"VLO":{
"name":"Valero Energy",
"sector":"Energy",
"sub":"Oil & Gas Refining & Marketing"
},
"VEEV":{
"name":"Veeva Systems",
"sector":"Health Care",
"sub":"Health Care Technology"
},
"VTR":{
"name":"Ventas",
"sector":"Real Estate",
"sub":"Health Care REITs"
},
"VLTO":{
"name":"Veralto",
"sector":"Industrials",
"sub":"Environmental & Facilities Services"
},
"VRSN":{
"name":"Verisign",
"sector":"Information Technology",
"sub":"Internet Services & Infrastructure"
},
"VRSK":{
"name":"Verisk Analytics",
"sector":"Industrials",
"sub":"Research & Consulting Services"
},
"VZ":{
"name":"Verizon",
"sector":"Communication Services",
"sub":"Integrated Telecommunication Services"
},
"VRTX":{
"name":"Vertex Pharmaceuticals",
"sector":"Health Care",
"sub":"Biotechnology"
},
"VRT":{
"name":"Vertiv",
"sector":"Industrials",
"sub":"Electrical Components & Equipment"
},
"VTRS":{
"name":"Viatris",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"VICI":{
"name":"Vici Properties",
"sector":"Real Estate",
"sub":"Hotel & Resort REITs"
},
"V":{
"name":"Visa Inc.",
"sector":"Financials",
"sub":"Transaction & Payment Processing Services"
},
"VST":{
"name":"Vistra Corp.",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"VMC":{
"name":"Vulcan Materials Company",
"sector":"Materials",
"sub":"Construction Materials"
},
"WRB":{
"name":"W. R. Berkley Corporation",
"sector":"Financials",
"sub":"Property & Casualty Insurance"
},
"GWW":{
"name":"W. W. Grainger",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"WAB":{
"name":"Wabtec",
"sector":"Industrials",
"sub":"Construction Machinery & Heavy Transportation Equipment"
},
"WMT":{
"name":"Walmart",
"sector":"Consumer Staples",
"sub":"Consumer Staples Merchandise Retail"
},
"DIS":{
"name":"Walt Disney Company (The)",
"sector":"Communication Services",
"sub":"Movies & Entertainment"
},
"WBD":{
"name":"Warner Bros. Discovery",
"sector":"Communication Services",
"sub":"Broadcasting"
},
"WM":{
"name":"Waste Management",
"sector":"Industrials",
"sub":"Environmental & Facilities Services"
},
"WAT":{
"name":"Waters Corporation",
"sector":"Health Care",
"sub":"Life Sciences Tools & Services"
},
"WEC":{
"name":"WEC Energy Group",
"sector":"Utilities",
"sub":"Electric Utilities"
},
"WFC":{
"name":"Wells Fargo",
"sector":"Financials",
"sub":"Diversified Banks"
},
"WELL":{
"name":"Welltower",
"sector":"Real Estate",
"sub":"Health Care REITs"
},
"WST":{
"name":"West Pharmaceutical Services",
"sector":"Health Care",
"sub":"Health Care Supplies"
},
"WDC":{
"name":"Western Digital",
"sector":"Information Technology",
"sub":"Technology Hardware, Storage & Peripherals"
},
"WY":{
"name":"Weyerhaeuser",
"sector":"Real Estate",
"sub":"Timber REITs"
},
"WSM":{
"name":"Williams-Sonoma, Inc.",
"sector":"Consumer Discretionary",
"sub":"Homefurnishing Retail"
},
"WMB":{
"name":"Williams Companies",
"sector":"Energy",
"sub":"Oil & Gas Storage & Transportation"
},
"WTW":{
"name":"Willis Towers Watson",
"sector":"Financials",
"sub":"Insurance Brokers"
},
"WDAY":{
"name":"Workday, Inc.",
"sector":"Information Technology",
"sub":"Application Software"
},
"WYNN":{
"name":"Wynn Resorts",
"sector":"Consumer Discretionary",
"sub":"Casinos & Gaming"
},
"XEL":{
"name":"Xcel Energy",
"sector":"Utilities",
"sub":"Multi-Utilities"
},
"XYL":{
"name":"Xylem Inc.",
"sector":"Industrials",
"sub":"Industrial Machinery & Supplies & Components"
},
"YUM":{
"name":"Yum! Brands",
"sector":"Consumer Discretionary",
"sub":"Restaurants"
},
"ZBRA":{
"name":"Zebra Technologies",
"sector":"Information Technology",
"sub":"Electronic Equipment & Instruments"
},
"ZBH":{
"name":"Zimmer Biomet",
"sector":"Health Care",
"sub":"Health Care Equipment"
},
"ZTS":{
"name":"Zoetis",
"sector":"Health Care",
"sub":"Pharmaceuticals"
},
"RIVN":{
"name":"Rivian Automotive",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"LCID":{
"name":"Lucid Group",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"MGA":{
"name":"Magna International",
"sector":"Consumer Discretionary",
"sub":"Automotive Parts & Equipment"
},
"LEA":{
"name":"Lear Corp",
"sector":"Consumer Discretionary",
"sub":"Automotive Parts & Equipment"
},
"ALV":{
"name":"Autoliv",
"sector":"Consumer Discretionary",
"sub":"Automotive Parts & Equipment"
},
"DAN":{
"name":"Dana Inc",
"sector":"Consumer Discretionary",
"sub":"Automotive Parts & Equipment"
},
"AXL":{
"name":"American Axle",
"sector":"Consumer Discretionary",
"sub":"Automotive Parts & Equipment"
},
"AN":{
"name":"AutoNation",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"LAD":{
"name":"Lithia Motors",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"PAG":{
"name":"Penske Automotive",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"GPI":{
"name":"Group 1 Automotive",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"ABG":{
"name":"Asbury Automotive",
"sector":"Consumer Discretionary",
"sub":"Automotive Retail"
},
"HTZ":{
"name":"Hertz Global",
"sector":"Industrials",
"sub":"Trucking"
},
"CAR":{
"name":"Avis Budget Group",
"sector":"Industrials",
"sub":"Trucking"
},
"TSM":{
"name":"Taiwan Semiconductor",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"ASML":{
"name":"ASML Holding",
"sector":"Information Technology",
"sub":"Semiconductor Materials & Equipment"
},
"ARM":{
"name":"Arm Holdings",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"MRVL":{
"name":"Marvell Technology",
"sector":"Information Technology",
"sub":"Semiconductors"
},
"JBLU":{
"name":"JetBlue Airways",
"sector":"Industrials",
"sub":"Passenger Airlines"
},
"SAVE":{
"name":"Spirit Airlines",
"sector":"Industrials",
"sub":"Passenger Airlines"
},
"NIO":{
"name":"NIO Inc",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"XPEV":{
"name":"XPeng",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
},
"LI":{
"name":"Li Auto",
"sector":"Consumer Discretionary",
"sub":"Automobile Manufacturers"
}
}

SYMBOLS = list(UNIVERSE.keys())
