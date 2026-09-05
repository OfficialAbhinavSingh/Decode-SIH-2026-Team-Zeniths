"""The city registry the synthetic generator tiles. Owner: R1 (Satellite & Geo).

WHAT THIS IS
------------
A hand-maintained list of Indian cities, each with an approximate centre, its state, a
size tier, and a unique zone-id prefix. It exists so `seed_india.py` can produce the
Jaipur grid format for the whole country without touching the network.

WHAT IT IS NOT
--------------
Not a census, and not a gazetteer. The coordinates are city centres rounded to 4 decimal
places (~11 m) -- good enough to put a grid over the right city, not a survey reference.
There is deliberately NO population column: inventing a precise-looking figure for 200
cities and putting it on a slide is exactly the kind of number a judge asks the source
of. `TIER` is a coarse size band instead, and it only decides how many zones a city gets.

Every state and union territory is represented, because "pan-India" has to survive
someone in the audience checking for their own state. tests/test_synthetic_cities.py
enforces that, and enforces that the prefixes stay unique.
"""

from typing import NamedTuple

# Zones per city by size band. These are grid extents, not administrative facts: a mega
# city gets a wider net because its water network is wider, and that is the whole claim.
ZONES_PER_TIER = {"mega": 60, "large": 40, "mid": 30, "small": 18}


class City(NamedTuple):
    name: str
    state: str
    code: str  # zone-id prefix, e.g. "PUN" -> PUN-001
    lat: float
    lon: float
    tier: str

    @property
    def zone_count(self) -> int:
        return ZONES_PER_TIER[self.tier]


# Jaipur is pinned, on purpose, and must stay pinned.
#
# It is the city the live dashboard has always shown, and its zones are Z-001..Z-030 in a
# 6-column grid. Regenerating it under a new prefix or a new zone count would silently
# replace the one view the whole demo is built around -- which is precisely the failure
# that took the site down before. Pinning code="Z" and tier="mid" (30 zones, 6 cols) makes
# the generator reproduce today's Jaipur grid exactly; tests/test_synthetic_grid.py checks
# it against seed.py's original build_zones() so this cannot drift unnoticed.
CITIES: tuple[City, ...] = (
    # --- Andhra Pradesh
    City("Visakhapatnam", "Andhra Pradesh", "VSK", 17.6868, 83.2185, "large"),
    City("Vijayawada", "Andhra Pradesh", "VJW", 16.5062, 80.6480, "large"),
    City("Guntur", "Andhra Pradesh", "GNT", 16.3067, 80.4365, "mid"),
    City("Amaravati", "Andhra Pradesh", "AMR", 16.5730, 80.3570, "small"),
    City("Nellore", "Andhra Pradesh", "NLR", 14.4426, 79.9865, "mid"),
    City("Kurnool", "Andhra Pradesh", "KNL", 15.8281, 78.0373, "mid"),
    City("Rajahmundry", "Andhra Pradesh", "RJY", 17.0005, 81.8040, "mid"),
    City("Kakinada", "Andhra Pradesh", "KKD", 16.9891, 82.2475, "mid"),
    City("Kadapa", "Andhra Pradesh", "KDP", 14.4673, 78.8242, "small"),
    City("Anantapur", "Andhra Pradesh", "ATP", 14.6819, 77.6006, "small"),
    City("Eluru", "Andhra Pradesh", "ELR", 16.7107, 81.0952, "small"),
    City("Ongole", "Andhra Pradesh", "OGL", 15.5057, 80.0499, "small"),
    City("Vizianagaram", "Andhra Pradesh", "VZM", 18.1067, 83.3956, "small"),
    # --- Arunachal Pradesh
    City("Itanagar", "Arunachal Pradesh", "ITN", 27.0844, 93.6053, "small"),
    City("Naharlagun", "Arunachal Pradesh", "NHL", 27.1039, 93.6959, "small"),
    # --- Assam
    City("Guwahati", "Assam", "GHY", 26.1445, 91.7362, "large"),
    City("Silchar", "Assam", "SCL", 24.8333, 92.7789, "small"),
    City("Dibrugarh", "Assam", "DBR", 27.4728, 94.9120, "small"),
    City("Jorhat", "Assam", "JRH", 26.7509, 94.2037, "small"),
    City("Nagaon", "Assam", "NGN", 26.3464, 92.6840, "small"),
    # --- Bihar
    City("Patna", "Bihar", "PAT", 25.5941, 85.1376, "large"),
    City("Gaya", "Bihar", "GAY", 24.7914, 85.0002, "mid"),
    City("Bhagalpur", "Bihar", "BGP", 25.2425, 86.9842, "mid"),
    City("Muzaffarpur", "Bihar", "MFP", 26.1209, 85.3647, "mid"),
    City("Darbhanga", "Bihar", "DBG", 26.1542, 85.8918, "small"),
    City("Purnia", "Bihar", "PRN", 25.7771, 87.4753, "small"),
    City("Arrah", "Bihar", "ARA", 25.5541, 84.6600, "small"),
    City("Begusarai", "Bihar", "BGS", 25.4182, 86.1272, "small"),
    City("Katihar", "Bihar", "KTH", 25.5541, 87.5586, "small"),
    City("Munger", "Bihar", "MGR", 25.3708, 86.4734, "small"),
    City("Chapra", "Bihar", "CPR", 25.7815, 84.7470, "small"),
    City("Bihar Sharif", "Bihar", "BSF", 25.2000, 85.5200, "small"),
    # --- Chhattisgarh
    City("Raipur", "Chhattisgarh", "RPR", 21.2514, 81.6296, "large"),
    City("Bhilai", "Chhattisgarh", "BHL", 21.1938, 81.3509, "mid"),
    City("Bilaspur", "Chhattisgarh", "BSP", 22.0797, 82.1409, "mid"),
    City("Korba", "Chhattisgarh", "KRB", 22.3595, 82.7501, "small"),
    City("Durg", "Chhattisgarh", "DRG", 21.1904, 81.2849, "small"),
    # --- Goa
    City("Panaji", "Goa", "PNJ", 15.4909, 73.8278, "small"),
    City("Margao", "Goa", "MRG", 15.2832, 73.9862, "small"),
    # --- Gujarat
    City("Ahmedabad", "Gujarat", "AMD", 23.0225, 72.5714, "mega"),
    City("Surat", "Gujarat", "STV", 21.1702, 72.8311, "mega"),
    City("Vadodara", "Gujarat", "BRC", 22.3072, 73.1812, "large"),
    City("Rajkot", "Gujarat", "RJT", 22.3039, 70.8022, "large"),
    City("Bhavnagar", "Gujarat", "BVN", 21.7645, 72.1519, "mid"),
    City("Jamnagar", "Gujarat", "JAM", 22.4707, 70.0577, "mid"),
    City("Junagadh", "Gujarat", "JND", 21.5222, 70.4579, "small"),
    City("Gandhinagar", "Gujarat", "GNR", 23.2156, 72.6369, "small"),
    City("Anand", "Gujarat", "ANN", 22.5645, 72.9289, "small"),
    City("Nadiad", "Gujarat", "NAD", 22.6939, 72.8615, "small"),
    City("Navsari", "Gujarat", "NVS", 20.9467, 72.9520, "small"),
    City("Gandhidham", "Gujarat", "GIM", 23.0753, 70.1337, "small"),
    # --- Haryana
    City("Faridabad", "Haryana", "FBD", 28.4089, 77.3178, "large"),
    City("Gurugram", "Haryana", "GGN", 28.4595, 77.0266, "large"),
    City("Rohtak", "Haryana", "ROK", 28.8955, 76.6066, "small"),
    City("Panipat", "Haryana", "PNP", 29.3909, 76.9635, "mid"),
    City("Karnal", "Haryana", "KUN", 29.6857, 76.9905, "small"),
    City("Sonipat", "Haryana", "SNP", 28.9931, 77.0151, "small"),
    City("Yamunanagar", "Haryana", "YNR", 30.1290, 77.2674, "small"),
    City("Panchkula", "Haryana", "PKL", 30.6942, 76.8606, "small"),
    City("Bhiwani", "Haryana", "BNW", 28.7975, 76.1322, "small"),
    # --- Himachal Pradesh
    City("Shimla", "Himachal Pradesh", "SML", 31.1048, 77.1734, "small"),
    City("Solan", "Himachal Pradesh", "SLN", 30.9045, 77.0967, "small"),
    City("Dharamshala", "Himachal Pradesh", "DHM", 32.2190, 76.3234, "small"),
    # --- Jharkhand
    City("Ranchi", "Jharkhand", "RNC", 23.3441, 85.3096, "large"),
    City("Dhanbad", "Jharkhand", "DHN", 23.7957, 86.4304, "large"),
    City("Jamshedpur", "Jharkhand", "JSR", 22.8046, 86.2029, "mid"),
    City("Bokaro", "Jharkhand", "BKS", 23.6693, 86.1511, "small"),
    City("Deoghar", "Jharkhand", "DGR", 24.4823, 86.6968, "small"),
    # --- Karnataka
    City("Bengaluru", "Karnataka", "BLR", 12.9716, 77.5946, "mega"),
    City("Hubballi", "Karnataka", "HBL", 15.3647, 75.1240, "mid"),
    City("Mysuru", "Karnataka", "MYS", 12.2958, 76.6394, "mid"),
    City("Mangaluru", "Karnataka", "MNG", 12.9141, 74.8560, "mid"),
    City("Belagavi", "Karnataka", "BGM", 15.8497, 74.4977, "mid"),
    City("Kalaburagi", "Karnataka", "KLB", 17.3297, 76.8343, "mid"),
    City("Davanagere", "Karnataka", "DVG", 14.4644, 75.9218, "small"),
    City("Ballari", "Karnataka", "BAY", 15.1394, 76.9214, "small"),
    City("Vijayapura", "Karnataka", "VJP", 16.8302, 75.7100, "small"),
    City("Shivamogga", "Karnataka", "SMG", 13.9299, 75.5681, "small"),
    City("Tumakuru", "Karnataka", "TMK", 13.3392, 77.1140, "small"),
    City("Raichur", "Karnataka", "RCR", 16.2120, 77.3439, "small"),
    City("Bidar", "Karnataka", "BDR", 17.9106, 77.5199, "small"),
    City("Hosapete", "Karnataka", "HPT", 15.2689, 76.3909, "small"),
    # --- Kerala
    City("Thiruvananthapuram", "Kerala", "TVM", 8.5241, 76.9366, "large"),
    City("Kochi", "Kerala", "COK", 9.9312, 76.2673, "large"),
    City("Kozhikode", "Kerala", "CCJ", 11.2588, 75.7804, "mid"),
    City("Thrissur", "Kerala", "TCR", 10.5276, 76.2144, "mid"),
    City("Kollam", "Kerala", "QLN", 8.8932, 76.6141, "small"),
    City("Alappuzha", "Kerala", "ALP", 9.4981, 76.3388, "small"),
    City("Kannur", "Kerala", "CNN", 11.8745, 75.3704, "small"),
    City("Palakkad", "Kerala", "PGT", 10.7867, 76.6548, "small"),
    # --- Madhya Pradesh
    City("Indore", "Madhya Pradesh", "IDR", 22.7196, 75.8577, "large"),
    City("Bhopal", "Madhya Pradesh", "BHO", 23.2599, 77.4126, "large"),
    City("Jabalpur", "Madhya Pradesh", "JBP", 23.1815, 79.9864, "large"),
    City("Gwalior", "Madhya Pradesh", "GWL", 26.2183, 78.1828, "large"),
    City("Ujjain", "Madhya Pradesh", "UJN", 23.1765, 75.7885, "mid"),
    City("Sagar", "Madhya Pradesh", "SGR", 23.8388, 78.7378, "small"),
    City("Dewas", "Madhya Pradesh", "DWX", 22.9676, 76.0534, "small"),
    City("Satna", "Madhya Pradesh", "STN", 24.5854, 80.8322, "small"),
    City("Ratlam", "Madhya Pradesh", "RTM", 23.3315, 75.0367, "small"),
    City("Rewa", "Madhya Pradesh", "REW", 24.5362, 81.3037, "small"),
    City("Katni", "Madhya Pradesh", "KTE", 23.8315, 80.3943, "small"),
    City("Singrauli", "Madhya Pradesh", "SGL", 24.1997, 82.6753, "small"),
    City("Khandwa", "Madhya Pradesh", "KNW", 21.8257, 76.3522, "small"),
    City("Burhanpur", "Madhya Pradesh", "BAU", 21.3145, 76.2291, "small"),
    City("Morena", "Madhya Pradesh", "MRA", 26.4986, 78.0011, "small"),
    City("Bhind", "Madhya Pradesh", "BIX", 26.5647, 78.7873, "small"),
    # --- Maharashtra
    City("Mumbai", "Maharashtra", "BOM", 19.0760, 72.8777, "mega"),
    City("Pune", "Maharashtra", "PNQ", 18.5204, 73.8567, "mega"),
    City("Nagpur", "Maharashtra", "NAG", 21.1458, 79.0882, "large"),
    City("Thane", "Maharashtra", "TNA", 19.2183, 72.9781, "large"),
    City("Nashik", "Maharashtra", "ISK", 19.9975, 73.7898, "large"),
    City("Navi Mumbai", "Maharashtra", "NVM", 19.0330, 73.0297, "large"),
    City("Chhatrapati Sambhajinagar", "Maharashtra", "CSN", 19.8762, 75.3433, "large"),
    City("Solapur", "Maharashtra", "SUR", 17.6599, 75.9064, "mid"),
    City("Bhiwandi", "Maharashtra", "BIW", 19.2967, 73.0631, "mid"),
    City("Amravati", "Maharashtra", "AMI", 20.9374, 77.7796, "mid"),
    City("Nanded", "Maharashtra", "NED", 19.1383, 77.3210, "mid"),
    City("Kolhapur", "Maharashtra", "KOP", 16.7050, 74.2433, "mid"),
    City("Ulhasnagar", "Maharashtra", "ULN", 19.2215, 73.1645, "small"),
    City("Sangli", "Maharashtra", "SLI", 16.8524, 74.5815, "small"),
    City("Malegaon", "Maharashtra", "MMR", 20.5579, 74.5089, "small"),
    City("Akola", "Maharashtra", "AKD", 20.7002, 77.0082, "small"),
    City("Latur", "Maharashtra", "LTR", 18.4088, 76.5604, "small"),
    City("Dhule", "Maharashtra", "DHI", 20.9042, 74.7749, "small"),
    City("Ahmednagar", "Maharashtra", "ANG", 19.0948, 74.7480, "small"),
    City("Chandrapur", "Maharashtra", "CDP", 19.9615, 79.2961, "small"),
    City("Parbhani", "Maharashtra", "PBN", 19.2704, 76.7601, "small"),
    City("Jalna", "Maharashtra", "JLN", 19.8410, 75.8864, "small"),
    City("Ichalkaranji", "Maharashtra", "ICK", 16.6913, 74.4605, "small"),
    City("Ambernath", "Maharashtra", "ABH", 19.2094, 73.1875, "small"),
    City("Satara", "Maharashtra", "STR", 17.6805, 74.0183, "small"),
    # --- Manipur
    City("Imphal", "Manipur", "IMF", 24.8170, 93.9368, "small"),
    # --- Meghalaya
    City("Shillong", "Meghalaya", "SHL", 25.5788, 91.8933, "small"),
    # --- Mizoram
    City("Aizawl", "Mizoram", "AJL", 23.7271, 92.7176, "small"),
    # --- Nagaland
    City("Kohima", "Nagaland", "KHM", 25.6751, 94.1086, "small"),
    City("Dimapur", "Nagaland", "DMU", 25.9063, 93.7276, "small"),
    # --- Odisha
    City("Bhubaneswar", "Odisha", "BBI", 20.2961, 85.8245, "large"),
    City("Cuttack", "Odisha", "CTC", 20.4625, 85.8830, "mid"),
    City("Rourkela", "Odisha", "ROU", 22.2604, 84.8536, "mid"),
    City("Berhampur", "Odisha", "BAM", 19.3150, 84.7941, "small"),
    City("Sambalpur", "Odisha", "SBP", 21.4669, 83.9812, "small"),
    City("Puri", "Odisha", "PURI", 19.8135, 85.8312, "small"),
    # --- Punjab
    City("Ludhiana", "Punjab", "LDH", 30.9010, 75.8573, "large"),
    City("Amritsar", "Punjab", "ATQ", 31.6340, 74.8723, "large"),
    City("Jalandhar", "Punjab", "JUC", 31.3260, 75.5762, "mid"),
    City("Patiala", "Punjab", "PTA", 30.3398, 76.3869, "mid"),
    City("Bathinda", "Punjab", "BTI", 30.2110, 74.9455, "small"),
    City("Mohali", "Punjab", "MHL", 30.7046, 76.7179, "small"),
    # --- Rajasthan
    City("Jaipur", "Rajasthan", "Z", 26.9124, 75.7873, "mid"),
    City("Jodhpur", "Rajasthan", "JDH", 26.2389, 73.0243, "large"),
    City("Kota", "Rajasthan", "KTU", 25.2138, 75.8648, "large"),
    City("Bikaner", "Rajasthan", "BKN", 28.0229, 73.3119, "mid"),
    City("Udaipur", "Rajasthan", "UDR", 24.5854, 73.7125, "mid"),
    City("Ajmer", "Rajasthan", "AJM", 26.4499, 74.6399, "mid"),
    City("Bhilwara", "Rajasthan", "BHW", 25.3407, 74.6313, "small"),
    City("Alwar", "Rajasthan", "AWR", 27.5530, 76.6346, "small"),
    City("Sikar", "Rajasthan", "SIK", 27.6094, 75.1399, "small"),
    City("Pali", "Rajasthan", "PAL", 25.7711, 73.3234, "small"),
    City("Sri Ganganagar", "Rajasthan", "SGN", 29.9038, 73.8772, "small"),
    City("Bharatpur", "Rajasthan", "BTP", 27.2173, 77.4901, "small"),
    # --- Sikkim
    City("Gangtok", "Sikkim", "GTK", 27.3314, 88.6138, "small"),
    # --- Tamil Nadu
    City("Chennai", "Tamil Nadu", "MAA", 13.0827, 80.2707, "mega"),
    City("Coimbatore", "Tamil Nadu", "CJB", 11.0168, 76.9558, "large"),
    City("Madurai", "Tamil Nadu", "IXM", 9.9252, 78.1198, "large"),
    City("Tiruchirappalli", "Tamil Nadu", "TRZ", 10.7905, 78.7047, "mid"),
    City("Salem", "Tamil Nadu", "SXV", 11.6643, 78.1460, "mid"),
    City("Tirunelveli", "Tamil Nadu", "TEN", 8.7139, 77.7567, "mid"),
    City("Erode", "Tamil Nadu", "ED", 11.3410, 77.7172, "small"),
    City("Vellore", "Tamil Nadu", "VLR", 12.9165, 79.1325, "small"),
    City("Thoothukudi", "Tamil Nadu", "TUT", 8.7642, 78.1348, "small"),
    City("Thanjavur", "Tamil Nadu", "TJV", 10.7870, 79.1378, "small"),
    City("Dindigul", "Tamil Nadu", "DIG", 10.3673, 77.9803, "small"),
    City("Nagercoil", "Tamil Nadu", "NCJ", 8.1780, 77.4285, "small"),
    City("Avadi", "Tamil Nadu", "AVD", 13.1147, 80.1098, "small"),
    # --- Telangana
    City("Hyderabad", "Telangana", "HYD", 17.3850, 78.4867, "mega"),
    City("Warangal", "Telangana", "WGL", 17.9689, 79.5941, "mid"),
    City("Nizamabad", "Telangana", "NZB", 18.6725, 78.0941, "small"),
    City("Khammam", "Telangana", "KMM", 17.2473, 80.1514, "small"),
    City("Karimnagar", "Telangana", "KRM", 18.4386, 79.1288, "small"),
    City("Ramagundam", "Telangana", "RDM", 18.7600, 79.4740, "small"),
    # --- Tripura
    City("Agartala", "Tripura", "IXA", 23.8315, 91.2868, "small"),
    # --- Uttar Pradesh
    City("Lucknow", "Uttar Pradesh", "LKO", 26.8467, 80.9462, "mega"),
    City("Kanpur", "Uttar Pradesh", "KNU", 26.4499, 80.3319, "mega"),
    City("Ghaziabad", "Uttar Pradesh", "GZB", 28.6692, 77.4538, "large"),
    City("Agra", "Uttar Pradesh", "AGR", 27.1767, 78.0081, "large"),
    City("Varanasi", "Uttar Pradesh", "VNS", 25.3176, 82.9739, "large"),
    City("Meerut", "Uttar Pradesh", "MRT", 28.9845, 77.7064, "large"),
    City("Prayagraj", "Uttar Pradesh", "IXD", 25.4358, 81.8463, "large"),
    City("Noida", "Uttar Pradesh", "NOI", 28.5355, 77.3910, "large"),
    City("Bareilly", "Uttar Pradesh", "BEK", 28.3670, 79.4304, "mid"),
    City("Aligarh", "Uttar Pradesh", "ALG", 27.8974, 78.0880, "mid"),
    City("Moradabad", "Uttar Pradesh", "MBD", 28.8386, 78.7733, "mid"),
    City("Saharanpur", "Uttar Pradesh", "SRE", 29.9680, 77.5552, "mid"),
    City("Gorakhpur", "Uttar Pradesh", "GKP", 26.7606, 83.3732, "mid"),
    City("Firozabad", "Uttar Pradesh", "FZD", 27.1592, 78.3957, "small"),
    City("Jhansi", "Uttar Pradesh", "JHS", 25.4484, 78.5685, "small"),
    City("Mathura", "Uttar Pradesh", "MTJ", 27.4924, 77.6737, "small"),
    City("Muzaffarnagar", "Uttar Pradesh", "MZR", 29.4727, 77.7085, "small"),
    City("Shahjahanpur", "Uttar Pradesh", "SPN", 27.8815, 79.9098, "small"),
    City("Rampur", "Uttar Pradesh", "RMU", 28.8010, 79.0250, "small"),
    City("Mirzapur", "Uttar Pradesh", "MZP", 25.1337, 82.5644, "small"),
    City("Bulandshahr", "Uttar Pradesh", "BSC", 28.4070, 77.8498, "small"),
    City("Sambhal", "Uttar Pradesh", "SBL", 28.5850, 78.5718, "small"),
    City("Amroha", "Uttar Pradesh", "AMH", 28.9044, 78.4675, "small"),
    City("Hapur", "Uttar Pradesh", "HPU", 28.7306, 77.7759, "small"),
    City("Etawah", "Uttar Pradesh", "ETW", 26.7855, 79.0150, "small"),
    City("Farrukhabad", "Uttar Pradesh", "FBH", 27.3929, 79.5800, "small"),
    City("Mau", "Uttar Pradesh", "MAU", 25.9417, 83.5611, "small"),
    City("Loni", "Uttar Pradesh", "LNI", 28.7515, 77.2880, "small"),
    # --- Uttarakhand
    City("Dehradun", "Uttarakhand", "DED", 30.3165, 78.0322, "mid"),
    City("Haridwar", "Uttarakhand", "HDW", 29.9457, 78.1642, "small"),
    City("Haldwani", "Uttarakhand", "HLD", 29.2183, 79.5130, "small"),
    City("Rudrapur", "Uttarakhand", "RDP", 28.9845, 79.4304, "small"),
    # --- West Bengal
    City("Kolkata", "West Bengal", "CCU", 22.5726, 88.3639, "mega"),
    City("Howrah", "West Bengal", "HWH", 22.5958, 88.2636, "large"),
    City("Durgapur", "West Bengal", "DGP", 23.5204, 87.3119, "mid"),
    City("Asansol", "West Bengal", "ASN", 23.6739, 86.9524, "mid"),
    City("Siliguri", "West Bengal", "SGU", 26.7271, 88.3953, "mid"),
    City("Bardhaman", "West Bengal", "BWN", 23.2324, 87.8615, "small"),
    City("Malda", "West Bengal", "MLD", 25.0119, 88.1433, "small"),
    City("Kharagpur", "West Bengal", "KGP", 22.3460, 87.2320, "small"),
    City("Haldia", "West Bengal", "HAL", 22.0667, 88.0698, "small"),
    City("Barasat", "West Bengal", "BRT", 22.7248, 88.4800, "small"),
    City("Maheshtala", "West Bengal", "MHT", 22.4986, 88.2532, "small"),
    # --- Union territories
    City("Delhi", "Delhi", "DEL", 28.6139, 77.2090, "mega"),
    City("Chandigarh", "Chandigarh", "IXC", 30.7333, 76.7794, "mid"),
    City("Puducherry", "Puducherry", "PDY", 11.9416, 79.8083, "small"),
    City("Srinagar", "Jammu and Kashmir", "SXR", 34.0837, 74.7973, "large"),
    City("Jammu", "Jammu and Kashmir", "IXJ", 32.7266, 74.8570, "mid"),
    City("Leh", "Ladakh", "IXL", 34.1526, 77.5771, "small"),
    City("Port Blair", "Andaman and Nicobar Islands", "IXZ", 11.6234, 92.7265, "small"),
    City("Kavaratti", "Lakshadweep", "KVT", 10.5669, 72.6420, "small"),
    City("Daman", "Dadra and Nagar Haveli and Daman and Diu", "DMN", 20.3974, 72.8328, "small"),
    City("Silvassa", "Dadra and Nagar Haveli and Daman and Diu", "SLV", 20.2738, 73.0140, "small"),
)

BY_NAME = {c.name: c for c in CITIES}
BY_CODE = {c.code: c for c in CITIES}


def get(name: str) -> City:
    """Look a city up by exact name, with a useful error when it is not in the registry."""
    try:
        return BY_NAME[name]
    except KeyError:
        raise KeyError(
            f"{name!r} is not in the synthetic city registry. "
            f"Add it to CITIES in {__file__} with a unique code, or pick one of: "
            f"{', '.join(sorted(BY_NAME)[:8])}, ..."
        ) from None


def states() -> list[str]:
    return sorted({c.state for c in CITIES})
