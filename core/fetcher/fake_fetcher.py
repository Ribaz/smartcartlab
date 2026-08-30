# core/fetcher/fake_fetcher.py
# Fake data fetcher for development and testing purposes.
# Generates realistic but completely fictional product data.
# No API keys or internet connection required.
#
# To use instead of KeepaFetcher, change one line in main.py:
#   from core.fetcher.fake_fetcher import FakeFetcher as Fetcher
 
import random
from typing import Dict, List

# --- Data pools for combinatorial generation ---
 
BRANDS = [
    "Samsung", "Sony", "Philips", "Bosch", "LG", "Xiaomi", "Apple", "Huawei",
    "Logitech", "Razer", "Corsair", "Kingston", "WD", "Seagate", "Asus", "Acer",
    "Dell", "HP", "Lenovo", "Microsoft", "Garmin", "Polar", "Fitbit", "Withings",
    "Oral-B", "Braun", "De'Longhi", "Tefal", "Rowenta", "Electrolux", "Whirlpool",
    "Dyson", "iRobot", "Neato", "Dremel", "Black+Decker", "Makita", "DeWalt",
    "Bose", "JBL", "Sennheiser", "Jabra", "Anker", "Belkin", "TP-Link", "Netgear",
    "Nintendo", "Lego", "Hasbro", "Mattel", "GoPro", "DJI", "Canon", "Nikon",
    "Fellowes", "Leitz", "Moleskine", "Targus", "Hama", "Trust", "Crucial",
    "Thermaltake", "Noctua", "be quiet!", "Seasonic", "EVGA", "MSI", "Gigabyte",
]
 
PRODUCT_TYPES = [
    # Informatica
    "Mouse Wireless", "Tastiera Meccanica", "SSD 1TB", "SSD 2TB", "RAM 16GB DDR5",
    "RAM 32GB DDR5", "Hard Disk 2TB", "Hard Disk 4TB", "Router Wi-Fi 6", "Switch 8 Porte",
    "Hub USB-C", "Monitor 27 pollici", "Monitor 32 pollici", "Webcam 4K", "Microfono USB",
    "Scheda Video RTX 4060", "Processore i7", "Dissipatore CPU", "Alimentatore 750W",
    "Case ATX", "Stampante Laser", "Stampante Inkjet", "Scanner A4", "UPS 1500VA",
    # Elettronica
    "Cuffie Wireless", "Cuffie In-Ear", "Soundbar", "Altoparlante Bluetooth",
    "Smartwatch", "Fitness Tracker", "Tablet 10 pollici", "E-Reader",
    "Videocamera d'azione", "Drone", "Fotocamera Mirrorless", "Obiettivo 50mm",
    "TV 55 pollici OLED", "TV 65 pollici QLED", "Proiettore Full HD",
    "Campanello Smart", "Telecamera Sicurezza", "Lampadine Smart Kit",
    "Assistente Vocale", "Caricatore Wireless", "Power Bank 20000mAh",
    # Casa e cucina
    "Friggitrice ad Aria", "Macchina Caffè Capsule", "Robot Aspirapolvere",
    "Bistecchiera Elettrica", "Multicooker", "Frullatore Immersione",
    "Macchina Pane", "Tostapane", "Bollitore Elettrico", "Lavastoviglie",
    "Lavatrice 8kg", "Asciugatrice", "Ferro da Stiro Verticale",
    "Purificatore Aria", "Deumidificatore", "Termoventilatore",
    # Sport e salute
    "Bilancia Smart", "Misuratore Pressione", "Spazzolino Elettrico",
    "Idropulsore Dentale", "Kettlebell 16kg", "Tappeto Yoga",
    "Fascia Cardio", "Pistola Massaggio", "Scarpe Running",
    # Fai da te
    "Trapano a Percussione", "Avvitatore 18V", "Smerigliatrice",
    "Levigatrice Orbitale", "Sega Circolare", "Multitool Oscillante",
    # Giochi e ufficio
    "Set Lego Technic", "Set Lego Icons", "Gioco da Tavolo",
    "Console Portatile", "Controller Wireless", "Distruggidocumenti",
    "Zaino Laptop 15 pollici", "Sedia Ergonomica", "Monitor Arm",
]
 
CATEGORIES = [
    "Informatica", "Informatica", "Informatica",       # peso maggiore
    "Elettronica", "Elettronica", "Elettronica",
    "Casa e cucina", "Casa e cucina",
    "Sport", "Salute", "Fai da te",
    "Giochi e giocattoli", "Ufficio",
]
 
NUM_PRODUCTS = 10000
 
 
class FakeFetcher:
 
    def fetch(self) -> List[Dict]:
        """
        Generate a list of fake products that mimics the output of KeepaFetcher.
        Returns 10000 fictional products with realistic price and review data.
        """
        products = [self._generate_product() for _ in range(NUM_PRODUCTS)]
        print(f"FakeFetcher: generated {len(products)} fake products.")
        return products
 
    def _generate_product(self) -> Dict:
        """Generate a single fake product with realistic price and review data."""
        brand = random.choice(BRANDS)
        product_type = random.choice(PRODUCT_TYPES)
        category = random.choice(CATEGORIES)
 
        # Generate realistic price history
        base_price  = round(random.uniform(10.0, 800.0), 2)
        avg_1y      = round(base_price * random.uniform(0.85, 1.5), 2)
        avg_90d     = round(avg_1y * random.uniform(0.80, 1.20), 2)
 
        # Current price: sometimes a real deal, sometimes not
        current_price = round(avg_90d * random.uniform(0.4, 1.10), 2)
 
        # Reviews: realistic distribution — most products have decent reviews
        review_score = round(random.choices(
            [random.uniform(1.0, 2.9),   # bad
             random.uniform(3.0, 3.9),   # mediocre
             random.uniform(4.0, 4.4),   # good
             random.uniform(4.5, 5.0)],  # excellent
            weights=[5, 15, 45, 35]
        )[0], 1)
        review_count = int(random.choices(
            [random.randint(1, 49),       # few reviews
             random.randint(50, 500),     # decent
             random.randint(501, 5000),   # popular
             random.randint(5001, 50000)],# bestseller
            weights=[20, 40, 30, 10]
        )[0])
 
        asin = f"B{random.randint(10000000, 99999999):08d}"
 
        return {
            "asin":          asin,
            "title":         f"{brand} {product_type}",
            "category":      category,
            "current_price": current_price,
            "avg_price_90d": avg_90d,
            "avg_price_1y":  avg_1y,
            "review_score":  review_score,
            "review_count":  review_count,
            "image_url":     None,
            "product_link":  f"https://www.amazon.it/dp/{asin}",
            "final_score":   None,
        }
 
