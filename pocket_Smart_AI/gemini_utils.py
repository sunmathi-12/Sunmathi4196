import os, json
from urllib.parse import quote_plus

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SHOPS = {"amazon": "https://www.amazon.in/s?k=", "flipkart": "https://www.flipkart.com/search?q=",
         "ikea": "https://www.ikea.com/in/en/search/?q=", "swiggy": "https://www.swiggy.com/search?query=",
         "zomato": "https://www.zomato.com/search?q=", "oyo": "https://www.oyorooms.com/search?location="}
PLATFORMS = {"home": ["Amazon", "Flipkart", "IKEA"], "party": ["Swiggy", "Zomato", "OYO", "Amazon"],
             "jewelry": ["Amazon", "Flipkart"]}
HINT = {"home": "Cover every room and the requested quantities of lights, fans and dining tables; balance function, style and price.",
        "party": "Split the budget across catering, decoration, entertainment and venue/stay for the event type and guest count; give cost per guest for catering.",
        "jewelry": "Match the occasion and style. If an outfit image is attached, coordinate colours with it."}
WEIGHTS = {"home": {"Furniture": .45, "Lighting": .25, "Decor": .2, "Ceiling fans": .1},
           "party": {"Catering": .5, "Decoration": .2, "Entertainment": .15, "Venue or stay": .15},
           "jewelry": {"Necklace": .45, "Earrings": .25, "Bracelet": .15, "Ring": .15}}


def _prompt(kind, budget, inputs):
    ctx = "; ".join(f"{k}={v}" for k, v in inputs.items() if k != "budget" and v)
    return (f"You are PocketSmart AI, a budget planner for shoppers in India. Category: {kind}. "
            f"Total budget: INR {budget:.0f}. Details: {ctx or 'none'}. "
            f"Use only these platforms: {', '.join(PLATFORMS[kind])}. {HINT[kind]} "
            "Total of all picks must not exceed the budget. Prices are estimates in INR. Do not invent URLs. "
            'Reply with JSON only: {"summary": "2 sentences", "picks": '
            '[{"category": "", "name": "", "platform": "", "price": 0, "why": "one sentence"}]}')


def _pick(kind, category, name, platform, price, why):
    key = platform.lower() if platform.lower() in SHOPS else PLATFORMS[kind][0].lower()
    return {"category": category, "name": name, "platform": platform if key == platform.lower() else PLATFORMS[kind][0],
            "price": price, "why": why, "url": SHOPS[key] + quote_plus(name)}


def _clean(data, kind, budget):
    picks = []
    for p in data.get("picks", [])[:12]:
        try:
            price, name = float(p["price"]), str(p["name"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if name and price > 0:
            picks.append(_pick(kind, str(p.get("category", kind)).strip(), name, str(p.get("platform", "")).strip(),
                               price, str(p.get("why", "")).strip()))
    if not picks:
        raise ValueError("no usable picks")
    total = sum(p["price"] for p in picks)
    return {"summary": str(data.get("summary", "")), "picks": picks, "total": total,
            "over_budget": total > budget * 1.05, "fallback": False}


def fallback(kind, budget):
    """Default suggestions (used when Gemini fails or no API key is set)."""
    picks = [_pick(kind, cat, f"{cat.lower()} {kind} essentials", PLATFORMS[kind][i % len(PLATFORMS[kind])],
                   round(budget * w), f"About {int(w * 100)}% of your budget.")
             for i, (cat, w) in enumerate(WEIGHTS[kind].items())]
    return {"summary": "Default budget split. Add a valid GEMINI_API_KEY for personalised picks.", "picks": picks,
            "total": sum(p["price"] for p in picks), "over_budget": False, "fallback": True}


def recommend(kind, budget, inputs, image=None):
    try:
        from google import genai
        from google.genai import types
        parts = [_prompt(kind, budget, inputs)]
        if image:
            parts.append(types.Part.from_bytes(data=image[0], mime_type=image[1]))
        r = genai.Client(api_key=os.environ["GEMINI_API_KEY"]).models.generate_content(
            model=MODEL, contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4))
        text = r.text.strip().removeprefix("```json").removesuffix("```").strip()
        return _clean(json.loads(text), kind, budget)
    except Exception as e:
        print("Gemini unavailable, using fallback:", e)
        return fallback(kind, budget)
