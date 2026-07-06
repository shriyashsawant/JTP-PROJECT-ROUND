BRAND_CONFIGS = {
    # ── Indian Premium / Designer ──
    "bellavita": {
        "name": "Bella Vita",
        "website": "https://bellavitaorganic.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
        "collections": ["perfume", "luxury-perfume", "attar"],
    },
    "bellavitaluxury": {
        "name": "Bella Vita Luxury",
        "website": "https://shop.bellavitaluxury.co.in",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
        "note": "Separate luxury store with richer product descriptions",
    },
    "skinn": {
        "name": "Skinn by Titan",
        "website": "https://skinn.in",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "ajmal": {
        "name": "Ajmal Perfumes",
        "website": "https://in.ajmal.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "engage": {
        "name": "Engage",
        "website": "https://www.itcstore.in",
        "platform": "Shopify",
        "scrape_method": "html",
        "collections": ["engage"],
        "note": "Sold via ITC store; requires special handling",
    },
    "fogg": {
        "name": "Fogg",
        "website": "https://www.viniinternational.com",
        "platform": "Custom",
        "scrape_method": "html",
        "note": "Brand page on Vini Cosmetics site",
    },
    "villain": {
        "name": "Villain",
        "website": "https://www.villain.in",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "themancompany": {
        "name": "The Man Company",
        "website": "https://www.themancompany.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "ustraa": {
        "name": "Ustraa",
        "website": "https://www.ustraa.com",
        "platform": "Shopify",
        "scrape_method": "html",
        "collections": ["all"],
    },
    "denver": {
        "name": "Denver",
        "website": "https://denverformen.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "wildstone": {
        "name": "Wild Stone",
        "website": "https://wildstone.in",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "parkavenue": {
        "name": "Park Avenue",
        "website": "https://parkavenue.in",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "beardo": {
        "name": "Beardo",
        "website": "https://beardo.in",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "lattafa": {
        "name": "Lattafa",
        "website": "https://lattafa.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "maisonalhambra": {
        "name": "Maison Alhambra",
        "website": "https://lattafa.com",
        "platform": "Custom",
        "scrape_method": "html",
        "note": "Lattafa sub-brand; products on same domain",
    },
    "armaf": {
        "name": "Armaf",
        "website": "https://armafperfume.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "rasasi": {
        "name": "Rasasi",
        "website": "https://rasasi.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "afnan": {
        "name": "Afnan",
        "website": "https://afnan.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "pariscorner": {
        "name": "Paris Corner",
        "website": "https://pariscornerperfumes.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "fragranceworld": {
        "name": "Fragrance World",
        "website": "https://fragranceworld.ae",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "swissarabian": {
        "name": "Swiss Arabian",
        "website": "https://swissarabian.com",
        "platform": "Magento",
        "scrape_method": "html",
    },
    "alharamain": {
        "name": "Al Haramain",
        "website": "https://alharamainperfumes.in",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "ahmedalmaghribi": {
        "name": "Ahmed Al Maghribi",
        "website": "https://ahmedalmaghribi.com",
        "platform": "Custom",
        "scrape_method": "html",
    },

    # ── Niche / Artisanal Indian ──
    "bombayperfumery": {
        "name": "Bombay Perfumery",
        "website": "https://bombayperfumery.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "allgoodscent": {
        "name": "All Good Scents",
        "website": "https://allgoodscents.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "nasoprofumi": {
        "name": "Naso Profumi",
        "website": "https://nasoprofumi.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "houseofem5": {
        "name": "House of EM5",
        "website": "https://www.houseofem5.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "perfumeryco": {
        "name": "Perfumery.co.in",
        "website": "https://perfumery.co.in",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "scentedelic": {
        "name": "Scentedelic",
        "website": "https://scentedelic.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "muznafragrances": {
        "name": "Muzna Fragrances",
        "website": "https://muznafragrances.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "hasanoud": {
        "name": "Hasan Oud",
        "website": "https://hasanoud.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "fraganote": {
        "name": "Fraganote",
        "website": "https://fraganote.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "aeronot": {
        "name": "Aeronot",
        "website": "https://aeronot.in",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "scentari": {
        "name": "Scentari",
        "website": "https://scentari.in",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "almaham": {
        "name": "Al Maham Fragrances",
        "website": "https://almahamfragrances.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "aafiyaperfumes": {
        "name": "Aafiya Perfumes",
        "website": "https://aafiyaperfumes.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "isakfragrances": {
        "name": "ISAK Fragrances",
        "website": "https://isakfragrances.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "exoticscentsindia": {
        "name": "Exotic Scents India",
        "website": "https://exoticscentsindia.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "olfactorymusicfest": {
        "name": "Olfactory Music Fest",
        "website": "https://olfactorymusicfest.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "houseofkanzan": {
        "name": "House of Kanzan",
        "website": "https://houseofkanzan.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },

    # ── Mass Market ──
    "layerrshot": {
        "name": "Layer'r Shot",
        "website": "https://layerrshot.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "secrettemptation": {
        "name": "Secret Temptation",
        "website": "https://secrettemptation.in",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "setwet": {
        "name": "Set Wet",
        "website": "https://setwet.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "envyfragrances": {
        "name": "Envy",
        "website": "https://envyfragrances.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "yardleyindia": {
        "name": "Yardley London India",
        "website": "https://yardleylondon.co.in",
        "platform": "Custom",
        "scrape_method": "html",
    },

    # ── Attar / Traditional ──
    "sugandhco": {
        "name": "Sugandhco",
        "website": "https://sugandhco.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "mlramnarain": {
        "name": "ML Ramnarain",
        "website": "https://mlramnarain.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "gulabsinghjohrimal": {
        "name": "Gulabsingh Johrimal",
        "website": "https://gulabsinghjohrimal.com",
        "platform": "Shopify",
        "scrape_method": "products_json",
        "products_json": "/products.json?limit=250",
    },
    "kannaujattar": {
        "name": "Kannauj Attars",
        "website": "https://kannaujattar.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "roohkhus": {
        "name": "Ruh Khus",
        "website": "https://ruhkhus.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
    "arochem": {
        "name": "Arochem",
        "website": "https://www.arochem.com",
        "platform": "Custom",
        "scrape_method": "html",
    },
}

ECOMMERCE_SITES = {
    "amazon": {
        "url": "https://www.amazon.in",
        "search_url": "https://www.amazon.in/s?k={query}+perfume&rh=n%3A1374304031",
    },
    "nykaa": {
        "url": "https://www.nykaa.com",
        "search_url": "https://www.nykaa.com/search?q={query}&root=search",
    },
    "myntra": {
        "url": "https://www.myntra.com",
        "search_url": "https://www.myntra.com/{query}",
    },
    "flipkart": {
        "url": "https://www.flipkart.com",
        "search_url": "https://www.flipkart.com/search?q={query}+perfume",
    },
}

REVIEW_SOURCES = {
    "fragrantica": {
        "url": "https://www.fragrantica.com",
        "search_url": "https://www.fragrantica.com/search/?q={query}",
    },
    "parfumo": {
        "url": "https://www.parfumo.net",
        "search_url": "https://www.parfumo.net/search?q={query}",
    },
    "reddit": {
        "url": "https://www.reddit.com",
        "search_url": "https://www.reddit.com/r/DesiFragranceAddicts/search/?q={query}&sort=relevance&t=all",
    },
    "youtube": {
        "url": "https://www.youtube.com",
        "search_url": "https://www.youtube.com/results?search_query={query}+perfume+review+india",
    },
}

SHOPIFY_BRANDS = [
    k for k, v in BRAND_CONFIGS.items()
    if v.get("platform") == "Shopify" and v.get("scrape_method") == "products_json"
]

CUSTOM_BRANDS = [
    k for k, v in BRAND_CONFIGS.items()
    if v.get("platform") != "Shopify" or v.get("scrape_method") != "products_json"
]
