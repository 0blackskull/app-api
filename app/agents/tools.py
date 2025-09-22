"""
Tools for the agent system.
"""
import os
from tavily import TavilyClient
from app.models import User
from app.models.partner import Partner
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from app.agents.astrology_utils import (
    get_transits_jhora as _get_transits,
    get_lagnas_jhora as _get_lagnas,
    get_yogas_jhora as _get_yogas,
    get_divisional_chart_jhora as _get_divisional_chart,
    get_d1_chart_data as _get_rasi_chart_with_dasha_and_significators_impl,
    get_arudha_lagna_jhora as _get_arudha_lagna,
    get_karakamsa_lagna_jhora as _get_karakamsa_lagna
)

from datetime import datetime

from app.utils.logger import get_logger

# Configure logging
logger = get_logger(__name__)


def create_person_data_tool(person: object, tool_name: str):
    """
    Returns basic birth data for a User or Partner for compatibility analysis.
    
    Args:
        person (User or Partner): The person object.
        tool_name (str): Unique name for the tool.
    Returns:
        function: A function returning a dict with id, name, city_of_birth, time_of_birth.
    Example Usage:
        # Create a tool to fetch user data
        tool = create_person_data_tool(user, "get_user_data")
        # tool() -> {'id': ..., 'name': ..., ...}
    """
    if not isinstance(person, (User, Partner)):
        raise TypeError(f"Expected User or Partner, got {type(person).__name__}")
    def fetch_person_data():
        return {
            "id": person.id,
            "name": person.name,
            "gender": getattr(person, "gender", None),
            "city_of_birth": person.city_of_birth,
            "current_residing_city": getattr(person, "current_residing_city", None),
            "time_of_birth": person.time_of_birth.isoformat() if person.time_of_birth else None,
        }
    fetch_person_data.__name__ = tool_name
    return fetch_person_data

def web_search(query: str) -> str:
    """
    Search the web for astrology-related information using Tavily.
    
    Args:
        query (str): The search query.
    Returns:
        str: Formatted search results or error message.
    Example Usage:
        # Search for current planetary positions
        web_search("current planetary positions")
        # Returns: summary and top results as string
    """
    try:
        # Initialize Tavily client
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            return "Error: TAVILY_API_KEY environment variable not set. Please configure your Tavily API key."
        
        tavily_client = TavilyClient(api_key=tavily_api_key)
        
        # Perform search with astrology context
        astrology_query = f"astrology {query}"
        response = tavily_client.search(
            query=astrology_query,
            search_depth="advanced",  # Get more comprehensive results
            max_results=10,  # Limit results for better performance
        )
        
        # Format the results
        results = []
        
        if response.get("results"):
            for result in response["results"][:3]:  # Limit to top 3 results
                title = result.get("title", "")
                content = result.get("content", "")
                url = result.get("url", "")
                
                if content:
                    result_text = f"**{title}**\n{content}"
                    if url:
                        result_text += f"\nSource: {url}"
                    results.append(result_text)
        
        # Get answer if available
        if response.get("answer"):
            results.insert(0, f"**Summary**: {response['answer']}")
        
        res = {'description': "Search the web for current astrology information, planetary positions, astrological events, and cosmic insights using web search"}
        if results:
            res["result"] = "\n\n".join(results)
            return res
        else:
            return f"No specific astrology information found for '{query}'. Try a more specific search."
            
    except Exception as e:
        return f"Error searching for astrology information: {str(e)}"

def get_panchanga(
    birth_date: str,
    birth_time: str,
    timezone: str,
    longitude: float,
    latitude: float,
    altitude: float = 0.0,
    ephe_path: str = "/app/ephe"
) -> dict:
    """
    Returns Moon's Rashi, Nakshatra, Pada, Tithi, Yoga, and Karana for Vedic compatibility.
    
    Args:
        birth_date (str): 'YYYY-MM-DD'
        birth_time (str): 'HH:MM'
        timezone (str): Timezone string
        longitude (float): East positive
        latitude (float): North positive
        altitude (float): Altitude in meters
        ephe_path (str): Path to ephemeris
    Returns:
        dict: Panchanga details
    Example Usage:
        # Get the panchanga for a specific birth
        get_panchanga('1990-03-15', '06:30', 'Asia/Kolkata', 80.27, 13.08)
        # Returns: dict with moon_rashi, nakshatra, etc.
    """
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../jhora')))
    import swisseph as swe
    from jhora.panchanga import drik
    from jhora.panchanga.drik import Place
    from jhora import utils

    # 1. Set up Swiss Ephemeris
    swe.set_ephe_path(ephe_path)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    swe.set_topo(lon=longitude, lat=latitude, alt=altitude)

    # 2. Prepare datetime in UTC
    dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    local_dt = pytz.timezone(timezone).localize(dt)
    utc = local_dt.astimezone(pytz.utc)
    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60.0)

    # 3. Place struct for drik
    # Place expects: name, latitude, longitude, timezone (in hours)
    # Get timezone offset in hours
    tz_offset = local_dt.utcoffset().total_seconds() / 3600.0
    place = Place("BirthPlace", latitude, longitude, tz_offset)

    # 4. Flags
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    # 5. Calculate Moon position and astrological metrics using JHora
    raasi_info = drik.raasi(jd, place)
    moon_rashi = raasi_info[0]  # 1–12

    nakshatra_info = drik.nakshatra(jd, place)
    nakshatra = nakshatra_info[0]  # 1–27
    pada = nakshatra_info[1]       # 1–4

    # 6. Tithi, Yoga, Karana using drik
    tithi_info = drik.tithi(jd, place)
    tithi_num = tithi_info[0]  # 1-30
    yoga_info = drik.yogam(jd, place)
    yoga_num = yoga_info[0]    # 1-27
    karana_info = drik.karana(jd, place)
    karana_num = karana_info[0]  # 1-60

    logger.info(f"Moon Rashi: {moon_rashi}, Nakshatra: {nakshatra}, Pada: {pada}, Tithi: {tithi_num}, Yoga: {yoga_num}, Karana: {karana_num}")
    return {
        "moon_rashi": moon_rashi,      # 1–12 (Aries–Pisces)
        "nakshatra": nakshatra,        # 1–27
        "pada": pada,                  # 1–4
        "tithi": tithi_num,            # 1–30
        "yoga": yoga_num,              # 1–27
        "karana": karana_num           # 1–60
    }

# --- Ashtakoota Data Tables ---
RASHI_TO_VARNA = {
    1: 'Kshatriya', 2: 'Vaishya', 3: 'Shudra', 4: 'Brahmin', 5: 'Kshatriya', 6: 'Vaishya',
    7: 'Shudra', 8: 'Kshatriya', 9: 'Kshatriya', 10: 'Vaishya', 11: 'Shudra', 12: 'Brahmin'
}
VARNA_HIERARCHY = {'Brahmin': 4, 'Kshatriya': 3, 'Vaishya': 2, 'Shudra': 1}
RASHI_TO_VASHYA = {
    1: 'Chatushpada', 2: 'Chatushpada', 3: 'Dwipad', 4: 'Jalachar', 5: 'Chatushpada', 6: 'Dwipad',
    7: 'Dwipad', 8: 'Keeta', 9: 'Dwipad', 10: 'Jalachar', 11: 'Jalachar', 12: 'Jalachar'
}
VASHYA_COMPATIBLE = {
    'Chatushpada': ['Chatushpada'], 'Dwipad': ['Dwipad'], 'Jalachar': ['Jalachar'],
    'Vanachara': ['Vanachara'], 'Keeta': ['Keeta']
}
VASHYA_SPECIAL = {
    (1, 5): 2, (5, 1): 2, (2, 7): 2, (7, 2): 2, (3, 6): 2, (6, 3): 2,
    (4, 8): 1, (8, 4): 1, (9, 12): 2, (12, 9): 2, (10, 11): 1, (11, 10): 1
}
# --- FIXED YONI MAPPING ---
NAKSHATRA_TO_YONI = {
    1: 'Ashwa',      # Ashwini
    2: 'Gaja',       # Bharani
    3: 'Mesha',      # Krittika
    4: 'Sarpa',      # Rohini
    5: 'Sarpa',      # Mrigashira
    6: 'Shwan',      # Ardra
    7: 'Marjara',    # Punarvasu
    8: 'Mesha',      # Pushya
    9: 'Marjara',    # Ashlesha
    10: 'Mushaka',   # Magha
    11: 'Mushaka',   # Purva Phalguni
    12: 'Gau',       # Uttara Phalguni
    13: 'Mahisha',   # Hasta
    14: 'Vyaghra',   # Chitra
    15: 'Mahisha',   # Swati
    16: 'Vyaghra',   # Vishakha
    17: 'Mriga',     # Anuradha
    18: 'Mriga',     # Jyeshtha
    19: 'Shwan',     # Moola
    20: 'Vanara',    # Purva Ashadha
    21: 'Nakula',    # Uttara Ashadha
    22: 'Vanara',    # Shravana
    23: 'Simha',     # Dhanishta
    24: 'Ashwa',     # Shatabhisha
    25: 'Simha',     # Purva Bhadrapada
    26: 'Gau',       # Uttara Bhadrapada
    27: 'Gaja',      # Revati
}
YONI_TYPES = [
    'Ashva', 'Gaja', 'Mesha', 'Sarpa', 'Shvana', 'Marjara', 'Nakula', 'Mushaka', 'Gau', 'Mahisha', 'Vyaghra', 'Mriga', 'Vana', 'Simha', 'Matsya'
]
# 13 traditional yoni types (Ashva, Gaja, Mesha, Sarpa, Shvana, Marjara, Nakula, Mushaka, Gau, Mahisha, Vyaghra, Mriga, Vana, Simha, Matsya)
# But in Nakshatra mapping, only 13 are used, so we use those.

# Friendly, enemy, highly inimical pairs from Vedic sources
FRIENDLY_PAIRS = set([
    ('Ashva', 'Sarpa'), ('Ashva', 'Mriga'), ('Ashva', 'Vana'),
    ('Gaja', 'Mesha'), ('Gaja', 'Mahisha'), ('Gaja', 'Vana'),
    ('Mesha', 'Gau'), ('Mesha', 'Mahisha'),
    ('Sarpa', 'Gaja'), ('Sarpa', 'Ashva'),
    ('Shvana', 'Vana'),
    ('Marjara', 'Mriga'), ('Marjara', 'Simha'),
    ('Nakula', 'Matsya'),
    ('Mushaka', 'Marjara'),
    ('Gau', 'Mesha'), ('Gau', 'Vyaghra'),
    ('Mahisha', 'Gaja'), ('Mahisha', 'Mesha'),
    ('Vyaghra', 'Gau'),
    ('Mriga', 'Ashva'), ('Mriga', 'Marjara'),
    ('Vana', 'Ashva'), ('Vana', 'Gaja'), ('Vana', 'Shvana'),
    ('Simha', 'Marjara'),
    ('Matsya', 'Nakula'),
])
ENEMY_PAIRS = set([
    ('Ashva', 'Mahisha'), ('Gaja', 'Simha'), ('Mesha', 'Vana'), ('Sarpa', 'Nakula'),
    ('Shvana', 'Mriga'), ('Marjara', 'Mushaka'), ('Nakula', 'Sarpa'),
    ('Gau', 'Vyaghra'), ('Mahisha', 'Ashva'), ('Vyaghra', 'Gau'),
    ('Mriga', 'Shvana'), ('Vana', 'Mesha'), ('Simha', 'Gaja'), ('Mushaka', 'Marjara')
])
HIGHLY_INIMICAL_PAIRS = set([
    ('Ashva', 'Mahisha'), ('Mahisha', 'Ashva'),
    ('Gaja', 'Simha'), ('Simha', 'Gaja'),
    ('Mesha', 'Vana'), ('Vana', 'Mesha'),
    ('Nakula', 'Sarpa'), ('Sarpa', 'Nakula'),
    ('Mriga', 'Shvana'), ('Shvana', 'Mriga'),
    ('Marjara', 'Mushaka'), ('Mushaka', 'Marjara'),
    ('Gau', 'Vyaghra'), ('Vyaghra', 'Gau')
])

# Build the full YONI_COMPATIBILITY matrix
YONI_COMPATIBILITY = {}
for y1 in NAKSHATRA_TO_YONI.values():
    for y2 in NAKSHATRA_TO_YONI.values():
        pair = (y1, y2)
        if y1 == y2:
            YONI_COMPATIBILITY[pair] = 4
        elif pair in HIGHLY_INIMICAL_PAIRS:
            YONI_COMPATIBILITY[pair] = 0
        elif pair in FRIENDLY_PAIRS or (y2, y1) in FRIENDLY_PAIRS:
            YONI_COMPATIBILITY[pair] = 3
        elif pair in ENEMY_PAIRS or (y2, y1) in ENEMY_PAIRS:
            YONI_COMPATIBILITY[pair] = 1
        else:
            YONI_COMPATIBILITY[pair] = 2

RASHI_LORDS = {
    1: 'Mars', 2: 'Venus', 3: 'Mercury', 4: 'Moon', 5: 'Sun', 6: 'Mercury', 7: 'Venus', 8: 'Mars', 9: 'Jupiter', 10: 'Saturn', 11: 'Saturn', 12: 'Jupiter'
}
PLANET_RELATIONSHIPS = {
    'Sun': {'friends': ['Moon', 'Mars', 'Jupiter'], 'enemies': ['Venus', 'Saturn'], 'neutral': ['Mercury']},
    'Moon': {'friends': ['Sun', 'Mercury'], 'enemies': [], 'neutral': ['Mars', 'Jupiter', 'Venus', 'Saturn']},
    'Mars': {'friends': ['Sun', 'Moon', 'Jupiter'], 'enemies': ['Mercury'], 'neutral': ['Venus', 'Saturn']},
    'Mercury': {'friends': ['Sun', 'Venus'], 'enemies': ['Moon'], 'neutral': ['Mars', 'Jupiter', 'Saturn']},
    'Jupiter': {'friends': ['Sun', 'Moon', 'Mars'], 'enemies': ['Mercury', 'Venus'], 'neutral': ['Saturn']},
    'Venus': {'friends': ['Mercury', 'Saturn'], 'enemies': ['Sun', 'Moon'], 'neutral': ['Mars', 'Jupiter']},
    'Saturn': {'friends': ['Mercury', 'Venus'], 'enemies': ['Sun', 'Moon', 'Mars'], 'neutral': ['Jupiter']}
}
NAKSHATRA_TO_GANA = {
    1: 'Deva', 2: 'Manushya', 3: 'Rakshasa', 4: 'Manushya', 5: 'Deva', 6: 'Manushya', 7: 'Deva', 8: 'Deva', 9: 'Rakshasa', 10: 'Rakshasa', 11: 'Manushya', 12: 'Manushya', 13: 'Deva', 14: 'Rakshasa', 15: 'Deva', 16: 'Rakshasa', 17: 'Deva', 18: 'Rakshasa', 19: 'Rakshasa', 20: 'Manushya', 21: 'Manushya', 22: 'Deva', 23: 'Rakshasa', 24: 'Rakshasa', 25: 'Manushya', 26: 'Manushya', 27: 'Deva'
}
BHAKOOT_MATRIX = {
    (1, 1): 7, (1, 2): 0, (1, 3): 7, (1, 4): 7, (1, 5): 0, (1, 6): 0, (1, 7): 7, (1, 8): 0, (1, 9): 0, (1, 10): 7, (1, 11): 7, (1, 12): 0,
    (2, 1): 0, (2, 2): 7, (2, 3): 0, (2, 4): 7, (2, 5): 7, (2, 6): 0, (2, 7): 0, (2, 8): 7, (2, 9): 0, (2, 10): 0, (2, 11): 7, (2, 12): 7,
    (3, 1): 7, (3, 2): 0, (3, 3): 7, (3, 4): 0, (3, 5): 7, (3, 6): 7, (3, 7): 0, (3, 8): 0, (3, 9): 7, (3, 10): 0, (3, 11): 0, (3, 12): 7,
    (4, 1): 7, (4, 2): 7, (4, 3): 0, (4, 4): 7, (4, 5): 0, (4, 6): 7, (4, 7): 7, (4, 8): 0, (4, 9): 0, (4, 10): 7, (4, 11): 0, (4, 12): 0,
    (5, 1): 0, (5, 2): 7, (5, 3): 7, (5, 4): 0, (5, 5): 7, (5, 6): 0, (5, 7): 7, (5, 8): 7, (5, 9): 0, (5, 10): 0, (5, 11): 7, (5, 12): 0,
    (6, 1): 0, (6, 2): 0, (6, 3): 7, (6, 4): 7, (6, 5): 0, (6, 6): 7, (6, 7): 0, (6, 8): 7, (6, 9): 7, (6, 10): 0, (6, 11): 0, (6, 12): 7,
    (7, 1): 7, (7, 2): 0, (7, 3): 0, (7, 4): 7, (7, 5): 7, (7, 6): 0, (7, 7): 7, (7, 8): 0, (7, 9): 7, (7, 10): 7, (7, 11): 0, (7, 12): 0,
    (8, 1): 0, (8, 2): 7, (8, 3): 0, (8, 4): 0, (8, 5): 7, (8, 6): 7, (8, 7): 0, (8, 8): 7, (8, 9): 0, (8, 10): 7, (8, 11): 7, (8, 12): 0,
    (9, 1): 0, (9, 2): 0, (9, 3): 7, (9, 4): 0, (9, 5): 0, (9, 6): 7, (9, 7): 7, (9, 8): 0, (9, 9): 7, (9, 10): 0, (9, 11): 7, (9, 12): 7,
    (10, 1): 7, (10, 2): 0, (10, 3): 0, (10, 4): 7, (10, 5): 0, (10, 6): 0, (10, 7): 7, (10, 8): 7, (10, 9): 0, (10, 10): 7, (10, 11): 0, (10, 12): 7,
    (11, 1): 7, (11, 2): 7, (11, 3): 0, (11, 4): 0, (11, 5): 7, (11, 6): 0, (11, 7): 0, (11, 8): 7, (11, 9): 7, (11, 10): 0, (11, 11): 7, (11, 12): 0,
    (12, 1): 0, (12, 2): 7, (12, 3): 7, (12, 4): 0, (12, 5): 0, (12, 6): 7, (12, 7): 0, (12, 8): 0, (12, 9): 7, (12, 10): 7, (12, 11): 0, (12, 12): 7
}
NAKSHATRA_TO_NADI = {
    1: 'Adi', 2: 'Madhya', 3: 'Antya', 4: 'Adi', 5: 'Madhya', 6: 'Antya', 7: 'Adi', 8: 'Madhya', 9: 'Antya', 10: 'Adi', 11: 'Madhya', 12: 'Antya', 13: 'Adi', 14: 'Madhya', 15: 'Antya', 16: 'Adi', 17: 'Madhya', 18: 'Antya', 19: 'Adi', 20: 'Madhya', 21: 'Antya', 22: 'Adi', 23: 'Madhya', 24: 'Antya', 25: 'Adi', 26: 'Madhya', 27: 'Antya'
}

def compatibility_ashtakoota(
    boy_rashi: int,
    boy_nakshatra: int,
    boy_pada: int,
    girl_rashi: int,
    girl_nakshatra: int,
    girl_pada: int
) -> dict:
    """
    Calculate 36-guna (Ashtakoota) compatibility between two people using Moon Rashi, Nakshatra, and Pada.
    
    Args:
        boy_rashi (int): Boy's Moon Rashi (1-12)
        boy_nakshatra (int): Boy's Nakshatra (1-27)
        boy_pada (int): Boy's Nakshatra Pada (1-4)
        girl_rashi (int): Girl's Moon Rashi (1-12)
        girl_nakshatra (int): Girl's Nakshatra (1-27)
        girl_pada (int): Girl's Nakshatra Pada (1-4)
    Returns:
        dict: Guna scores, total, explanations, dosha cancellation info
    Example Usage:
        # Check compatibility between two people
        compatibility_ashtakoota(1, 5, 2, 3, 7, 1)
        # Returns: dict with scores and explanations
    """
    # 1. Varna
    def varna_score(r1, r2):
        v1 = RASHI_TO_VARNA[r1]
        v2 = RASHI_TO_VARNA[r2]
        if v1 == v2 or VARNA_HIERARCHY[v1] >= VARNA_HIERARCHY[v2]:
            return 1
        return 0
    # 2. Vashya
    def vashya_score(r1, r2):
        if (r1, r2) in VASHYA_SPECIAL:
            return VASHYA_SPECIAL[(r1, r2)]
        v1 = RASHI_TO_VASHYA[r1]
        v2 = RASHI_TO_VASHYA[r2]
        if v1 == v2 or v2 in VASHYA_COMPATIBLE.get(v1, []):
            return 2
        return 1
    # 3. Tara
    def tara_score(boy_nakshatra, girl_nakshatra):
        # Tara Koota with fractional scores (see: https://www.jyotishgher.in/kundli-milan/tara-dosha.php)
        # Count from girl to boy (inclusive)
        d1 = (boy_nakshatra - girl_nakshatra) % 27
        if d1 == 0:
            d1 = 27
        rem1 = d1 % 9
        if rem1 == 0:
            rem1 = 9
        # Count from boy to girl (inclusive)
        d2 = (girl_nakshatra - boy_nakshatra) % 27
        if d2 == 0:
            d2 = 27
        rem2 = d2 % 9
        if rem2 == 0:
            rem2 = 9
        favorable = {2, 4, 6, 8, 9}
        even1 = rem1 in favorable
        even2 = rem2 in favorable
        if even1 and even2:
            return 3
        elif even1 or even2:
            return 1.5
        else:
            return 0
    # 4. Yoni
    def yoni_score(n1, n2):
        y1 = NAKSHATRA_TO_YONI[n1]
        y2 = NAKSHATRA_TO_YONI[n2]
        if (y1, y2) in YONI_COMPATIBILITY:
            return YONI_COMPATIBILITY[(y1, y2)]
        elif (y2, y1) in YONI_COMPATIBILITY:
            return YONI_COMPATIBILITY[(y2, y1)]
        return 2
    # 5. Maitri (Graha Maitri)
    def maitri_score(r1, r2):
        lord1 = RASHI_LORDS[r1]
        lord2 = RASHI_LORDS[r2]
        if lord1 == lord2:
            return 5
        elif lord2 in PLANET_RELATIONSHIPS[lord1]['friends']:
            return 4
        elif lord2 in PLANET_RELATIONSHIPS[lord1]['neutral']:
            return 3
        elif lord2 in PLANET_RELATIONSHIPS[lord1]['enemies']:
            return 1
        return 0
    # 6. Gana
    def gana_score(girl_nakshatra, boy_nakshatra):
        # Standard Gana Koota scoring table (see: https://www.anytimeastro.com/blog/astrology/gana-koota-in-kundli-matching/, https://www.astroyogi.com/blog/gana-koota-in-kundli-matching.aspx, https://www.ganeshaspeaks.com/astrology/nakshatras-constellations/gana-in-astrology/)
        g1 = NAKSHATRA_TO_GANA[girl_nakshatra]
        g2 = NAKSHATRA_TO_GANA[boy_nakshatra]
        logger.info(f"Gana: {g1}, {g2}")
        scoring_table = {
            ('Deva', 'Deva'): 6,
            ('Deva', 'Manushya'): 6,
            ('Deva', 'Rakshasa'): 0,
            ('Manushya', 'Deva'): 5,
            ('Manushya', 'Manushya'): 6,
            ('Manushya', 'Rakshasa'): 1,
            ('Rakshasa', 'Deva'): 1,
            ('Rakshasa', 'Manushya'): 0,
            ('Rakshasa', 'Rakshasa'): 6,
        }
        return scoring_table.get((g1, g2), 0)
    # 7. Bhakoot
    def bhakoot_score(r1, r2):
        return BHAKOOT_MATRIX.get((r1, r2), 0)
    # 8. Nadi
    def nadi_score(n1, n2):
        nadi1 = NAKSHATRA_TO_NADI[n1]
        nadi2 = NAKSHATRA_TO_NADI[n2]
        return 8 if nadi1 != nadi2 else 0
    # Dosha Cancellations
    def nadi_dosha_cancel(r1, n1, r2, n2):
        return (r1 == r2 and n1 != n2) or (n1 == n2 and r1 != r2) or (n1 == n2 and r1 == r2)
    def bhakoot_dosha_cancel(r1, r2):
        return r1 == r2
    # Compute all
    scores = {
        'Varna': varna_score(boy_rashi, girl_rashi),
        'Vashya': vashya_score(boy_rashi, girl_rashi),
        'Tara': tara_score(boy_nakshatra, girl_nakshatra),
        'Yoni': yoni_score(boy_nakshatra, girl_nakshatra),
        'Maitri': maitri_score(boy_rashi, girl_rashi),
        'Gana': gana_score(girl_nakshatra, boy_nakshatra),
        'Bhakoot': bhakoot_score(boy_rashi, girl_rashi),
        'Nadi': nadi_score(boy_nakshatra, girl_nakshatra),
    }

    total = sum(scores.values())
    # Dosha cancellation info
    nadi_cancel = nadi_dosha_cancel(boy_rashi, boy_nakshatra, girl_rashi, girl_nakshatra)
    bhakoot_cancel = bhakoot_dosha_cancel(boy_rashi, girl_rashi)
    return {
        'scores': scores,
        'total': total,
        'explanation': {
            'Varna': 'Varna (Personality): Based on Moon sign caste classification.',
            'Vashya': 'Vashya (Dominance/Mutual Influence): Based on Rashi mutual influence.',
            'Tara': 'Tara (Health): Based on Nakshatra distance.',
            'Yoni': 'Yoni (Sexual): Based on Nakshatra yoni animal compatibility.',
            'Maitri': 'Maitri (Friendship): Based on Moon lord friendship.',
            'Gana': 'Gana (Temperament): Based on Nakshatra gana type.',
            'Bhakoot': 'Bhakoot (Emotional): Based on Moon sign distance matrix.',
            'Nadi': 'Nadi (Future Generation): Based on Nakshatra nadi type.'
        },
        'dosha_cancellation': {
            'Nadi': nadi_cancel,
            'Bhakoot': bhakoot_cancel
        }
    }

# --- Utilities for geocoding and timezone ---
def get_lat_long(city_name: str):
    """
    Return (latitude, longitude) for a city name using geopy.
    
    Args:
        city_name (str): Name of the city
    Returns:
        tuple: (latitude, longitude)
    Example Usage:
        # Get coordinates for Chennai
        get_lat_long("Chennai")
        # Returns: (13.08, 80.27)
    """
    geolocator = Nominatim(user_agent="astro_app")
    location = geolocator.geocode(city_name, timeout=30)
    if location:
        return location.latitude, location.longitude
    else:
        raise ValueError(f"Could not geocode city: {city_name}")

def get_timezone(lat: float, lon: float):
    """
    Return timezone string for given latitude and longitude using timezonefinder.
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
    Returns:
        str: Timezone string
    Example Usage:
        # Get timezone for Chennai
        get_timezone(13.08, 80.27)
        # Returns: 'Asia/Kolkata'
    """
    tf = TimezoneFinder()
    tz = tf.timezone_at(lng=lon, lat=lat)
    if tz:
        return tz
    else:
        raise ValueError(f"Could not find timezone for lat={lat}, lon={lon}")

def get_transits(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    language: str = 'en',
    divisional_chart_factor: int = 1,
    years_from_birth: int = 1,
    months: int = 1
) -> dict:
    """
    Calculate annual and monthly transit charts for a given birth date, time, and place using JHora.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset from UTC in hours
        language (str): Output language (default 'en')
        divisional_chart_factor (int): Chart division factor (default 1)
        years_from_birth (int): Years after birth for annual transit (default 1)
        months (int): Months after specified years for monthly transit (default 1)
    
    Returns:
        dict: Transit chart data with the following structure:
        {
            "annual_transit_chart": {
                "chart": [[planet_id, (house, longitude)], ...],  # List of [planet, (house, degrees)]
                "date_info": [(year, month, day), (hour, minute, second)]  # Transit date and time
            },
            "monthly_transit_chart": {
                "chart": [[planet_id, (house, longitude)], ...],  # List of [planet, (house, degrees)]
                "date_info": [(year, month, day), (hour, minute, second)]  # Transit date and time
            }
        }
        
        Note: planet_id values: 0=Sun, 1=Moon, 2=Mars, 3=Mercury, 4=Jupiter, 5=Venus, 6=Saturn, 7=Rahu, 8=Ketu
        house values: 0-11 (Aries=0, Taurus=1, ..., Pisces=11)
        longitude values: degrees within the sign (0-30)
        
        Error case: {"error": "error message"}
    
    Example Usage:
        # Get annual/monthly transits for a birth
        get_transits(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with transit chart info
    """
    logger.info(f"get_transits called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, language={language}, divisional_chart_factor={divisional_chart_factor}, years_from_birth={years_from_birth}, months={months}")
    return _get_transits(
        year, month, day, hour, minute, second, latitude, longitude, timezone_offset,
        "LAHIRI", language, divisional_chart_factor, years_from_birth, months
    )


def get_lagnas(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    language: str = 'en',
    divisional_chart_factor: int = 1
) -> dict:
    """
    Calculate main and special lagnas for a given birth date, time, and place using JHora.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset from UTC in hours
        language (str): Output language (default 'en')
        divisional_chart_factor (int): Chart division factor (default 1)
    
    Returns:
        dict: All lagnas with zodiac positions and degrees:
        {
            "lagna": [constellation, longitude, nakshatra_number, pada_number],
            "bhava_lagna": [constellation, longitude],
            "hora_lagna": [constellation, longitude],
            "ghati_lagna": [constellation, longitude],
            "vighati_lagna": [constellation, longitude],
            "pranapada_lagna": [constellation, longitude],
            "indu_lagna": [constellation, longitude],
            "kunda_lagna": [constellation, longitude],
            "bhrigu_bindhu_lagna": [constellation, longitude],
            "sree_lagna": [constellation, longitude]
        }
        
        Where:
        - constellation: 0-11 (Aries=0, Taurus=1, ..., Pisces=11)
        - longitude: degrees within the sign (0-30)
        - nakshatra_number: 0-26 (Ashwini=0, Bharani=1, ..., Revati=26)
        - pada_number: 1-4 (quarter of nakshatra)
        
        Error case: {"error": "error message"}
    
    Example Usage:
        # Get all lagnas for a birth
        get_lagnas(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with lagna data
    """
    logger.info(f"get_lagnas called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, language={language}, divisional_chart_factor={divisional_chart_factor}")
    return _get_lagnas(
        year, month, day, hour, minute, second, latitude, longitude, timezone_offset,
        "LAHIRI", language, divisional_chart_factor
    )


def get_yogas(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    language: str = 'en'
) -> dict:
    """
    Calculate all Yogas present in the divisional charts for a given birth date, time, and place using JHora.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset from UTC in hours
        language (str): Output language (default 'en')
    
    Returns:
        dict: Yoga names found in all divisional charts:
        {
            "yogas": ["yoga_name1", "yoga_name2", ...],
            "found_count": 15,  # Number of yogas found
            "total_possible": 120  # Total possible yogas across all charts
        }
        
        Error case: {"error": "error message"}
    
    Example Usage:
        # Get all yogas for a birth
        get_yogas(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with yoga names only
    """
    logger.info(f"get_yogas called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, language={language}")
    result = _get_yogas(
        year, month, day, hour, minute, second, latitude, longitude, timezone_offset,
        "LAHIRI", language
    )
    
    # If there's an error, return it as is
    if "error" in result:
        return result
    
    # Extract only yoga names from the yogas dictionary
    yoga_names = list(result.get("yogas", {}).keys())
    
    return {
        "yogas": yoga_names,
        "found_count": result.get("found_count", 0),
        "total_possible": result.get("total_possible", 0)
    }


def get_divisional_chart(
    chart: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    language: str = 'en'
) -> dict:
    """
    Generate divisional charts (Varga charts) for advanced Vedic astrology analysis using JHora.
    
    Args:
        chart (str): Chart name or alias (e.g., 'd1', 'd9', 'navamsa')
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset from UTC in hours
        language (str): Output language (default 'en')
    
    Returns:
        dict: ChartData object with the following structure:
        {
            "chart_info": {
                "planet_name": "♉︎Taurus 15° 30' 45\"",  # Planet position in readable format
                "planet_name2": "♊︎Gemini 22° 15' 30\"",
                ...
            },
            "charts": [
                "House 1: Sun☉, Moon☾",  # House 1 contents
                "House 2: Mars♂",         # House 2 contents
                "House 3: Empty",         # House 3 contents
                ...                       # All 12 houses
            ],
            "ascendant_house": 2,  # House number (0-11) where ascendant falls
            "error": null          # Error message if any
        }
        
        Chart names supported:
        - D1/D2/D3/D4/D5/D6/D7/D8/D9/D10/D11/D12/D16/D20/D24/D27/D30/D40/D45/D60/D81/D108/D144

        Error case: {"error": "error message"}
    
    Example Usage:
        # Get D9 (Navamsa) chart for a birth
        get_divisional_chart('d9', 1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with divisional chart info
    """
    logger.info(f"get_divisional_chart called with: chart={chart}, year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, language={language}")
    chart_data = _get_divisional_chart(
        chart, year, month, day, hour, minute, second, latitude, longitude, timezone_offset,
        "LAHIRI", language
    )
    # Convert ChartData object to dictionary format as documented
    return chart_data.model_dump()

def get_rasi_chart_with_dasha_and_significators(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    utc: str,
    latitude: float,
    longitude: float,
    ayanamsa: str = 'Lahiri',
    house_system: str = 'Placidus'
) -> dict:
    """
    Generate the D1 (Rasi) chart, vimshottari dasha, bhukti, house cusps, and significators for a given birth time and location.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        utc (str): UTC offset string (e.g., '+05:30')
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        ayanamsa (str): Ayanamsa correction system (default 'Lahiri')
        house_system (str): House system (default 'Placidus')
    Returns:
        dict: D1 chart, vimshottari dasha, bhukti, house cusps, significators, planetary positions
    Example Usage:
        # Get D1 chart and dasha for a birth
        get_rasi_chart_with_dasha_and_significators(1990, 3, 15, 6, 30, 0, '+05:30', 13.08, 80.27)
        # Returns: dict with chart and dasha info
    """
    logger.info(f"get_rasi_chart_with_dasha_and_significators called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, utc={utc}, latitude={latitude}, longitude={longitude}, ayanamsa={ayanamsa}, house_system={house_system}")
    return _get_rasi_chart_with_dasha_and_significators_impl(
        year, month, day, hour, minute, second, utc, latitude, longitude, ayanamsa, house_system
    )

def get_vimshottari_dasha(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    utc: str,
    latitude: float,
    longitude: float,
    ayanamsa: str = 'Lahiri',
    house_system: str = 'Placidus',
    start_year: int = None,
    end_year: int = None
) -> dict:
    """
    Calculate vimshottari dasha (planetary periods) for a given birth time and location within a specific period.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        utc (str): UTC offset string (e.g., '+05:30')
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        ayanamsa (str): Ayanamsa correction system (default 'Lahiri')
        house_system (str): House system (default 'Placidus')
        start_year (int): Start year for dasha timeline (default: birth year)
        end_year (int): End year for dasha timeline (default: birth year + 120)
    
    Returns:
        dict: Vimshottari dasha periods with the following structure:
        {
            "vimshottari_dasa": [
                {
                    "dasa_lord": "Sun",           # Planet ruling the major period
                    "start": "15-03-1990",        # Start date in DD-MM-YYYY format
                    "end": "15-03-1996",          # End date in DD-MM-YYYY format
                    "bhuktis": [                  # Sub-periods within the major period
                        {
                            "bhukti_lord": "Sun",     # Planet ruling the sub-period
                            "start": "15-03-1990",    # Sub-period start date
                            "end": "15-03-1991"       # Sub-period end date
                        },
                        {
                            "bhukti_lord": "Moon",
                            "start": "15-03-1991",
                            "end": "15-03-1992"
                        }
                        # ... more bhuktis
                    ]
                },
                {
                    "dasa_lord": "Moon",
                    "start": "15-03-1996",
                    "end": "15-03-2006",
                    "bhuktis": [...]
                }
                # ... more dasha periods
            ],
            "current_dasha": {                    # Current major period (if within requested range)
                "dasa_lord": "Jupiter",
                "start": "15-03-2020",
                "end": "15-03-2036",
                "bhuktis": [...]
            },
            "current_bhukti": {                   # Current sub-period (if within requested range)
                "bhukti_lord": "Venus",
                "start": "15-03-2024",
                "end": "15-03-2026"
            },
            "period_info": {
                "requested_start_year": 2024,     # Requested start year
                "requested_end_year": 2030,       # Requested end year
                "total_dasha_periods": 3,         # Number of dasha periods in range
                "total_bhukti_periods": 15        # Total number of bhukti periods
            }
        }
        
        **Planet Names in dasha_lord and bhukti_lord:**
        - "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
        
        **Date Format:**
        - All dates are in DD-MM-YYYY format (e.g., "15-03-1990")
        - Times are included in the original data but may be truncated in output
        
        **Dasha Periods:**
        - Sun: 6 years, Moon: 10 years, Mars: 7 years, Mercury: 17 years
        - Jupiter: 16 years, Venus: 20 years, Saturn: 19 years, Rahu: 18 years, Ketu: 7 years
        - Total cycle: 120 years
        
        **Bhukti (Sub-period) Calculation:**
        - Each bhukti duration = (dasha_lord_period × bhukti_lord_period) / 120
        - Example: Jupiter dasha + Venus bhukti = (16 × 20) / 120 = 2.67 years
        
        **Error Cases:**
        - {"error": "error message"} - if calculation fails
        - {"error": "No vimshottari dasa data available"} - if no dasha data found
        
        **Filtering:**
        - Only returns dasha periods that overlap with the requested year range
        - If no range specified, returns full 120-year cycle
        - Current dasha/bhukti only populated if within requested range
    
    Example Usage:
        # Calculate vimshottari dasha for 2024-2030 for a birth
        get_vimshottari_dasha(1990, 3, 15, 6, 30, 0, '+05:30', 13.08, 80.27, start_year=2024, end_year=2030)
        # Returns: dict with dasha periods for the specified range
        
        # Get full vimshottari cycle
        get_vimshottari_dasha(1990, 3, 15, 6, 30, 0, '+05:30', 13.08, 80.27)
        # Returns: dict with complete 120-year dasha cycle
    """
    logger.info(f"get_vimshottari_dasha called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, utc={utc}, latitude={latitude}, longitude={longitude}, ayanamsa={ayanamsa}, house_system={house_system}, start_year={start_year}, end_year={end_year}")
    
    try:
        # Set default period if not specified
        if start_year is None:
            start_year = year
        if end_year is None:
            end_year = year + 120  # Full vimshottari cycle
        
        logger.info(f"Using period: start_year={start_year}, end_year={end_year}")
        
        # Get the full chart data which includes vimshottari dasha
        logger.info("Calling _get_rasi_chart_with_dasha_and_significators_impl...")
        chart_data = _get_rasi_chart_with_dasha_and_significators_impl(
            year, month, day, hour, minute, second, utc, latitude, longitude, ayanamsa, house_system
        )
        
        logger.info(f"Chart data keys: {list(chart_data.keys()) if isinstance(chart_data, dict) else 'Not a dict'}")
        
        if chart_data.get('error'):
            logger.error(f"Error in chart data: {chart_data['error']}")
            return {"error": chart_data['error']}
        
        full_vimshottari_dasa = chart_data.get('vimshottari_dasa', [])
        logger.info(f"Full vimshottari dasa count: {len(full_vimshottari_dasa)}")
        
        if not full_vimshottari_dasa:
            logger.warning("No vimshottari dasa data found in chart_data")
            return {
                "vimshottari_dasa": [],
                "current_dasha": None,
                "current_bhukti": None,
                "period_info": {
                    "requested_start_year": start_year,
                    "requested_end_year": end_year,
                    "total_dasha_periods": 0,
                    "total_bhukti_periods": 0
                },
                "error": "No vimshottari dasa data available"
            }
        
        # Filter dasha periods by the specified year range
        filtered_dasha = []
        for i, dasha in enumerate(full_vimshottari_dasa):
            logger.info(f"Processing dasha {i+1}: {dasha.get('dasa_lord', 'Unknown')}")
            
            start_date = dasha.get('start', '')
            end_date = dasha.get('end', '')
            
            logger.info(f"Dasha {i+1} dates: start={start_date}, end={end_date}")
            
            if start_date and end_date:
                try:
                    # Parse dates - they come in DD-MM-YYYY format
                    if '-' in start_date and len(start_date.split('-')) == 3:
                        # Check if it's DD-MM-YYYY format
                        parts = start_date.split('-')
                        if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                            # Convert DD-MM-YYYY to YYYY-MM-DD
                            dasha_start_year = int(parts[2])  # Year is the third part
                            dasha_end_year = int(end_date.split('-')[2])  # Same for end date
                        else:
                            # Assume YYYY-MM-DD format
                            dasha_start_year = int(parts[0])
                            dasha_end_year = int(end_date.split('-')[0])
                    else:
                        logger.warning(f"Unexpected date format for dasha {i+1}: {start_date}")
                        continue
                    
                    logger.info(f"Dasha {i+1} years: start_year={dasha_start_year}, end_year={dasha_end_year}")
                    
                    # Check if dasha period overlaps with requested range
                    if (dasha_start_year <= end_year and dasha_end_year >= start_year):
                        logger.info(f"Dasha {i+1} overlaps with requested period")
                        
                        # Filter bhuktis within the requested range
                        filtered_bhuktis = []
                        bhuktis = dasha.get('bhuktis', [])
                        logger.info(f"Dasha {i+1} has {len(bhuktis)} bhuktis")
                        
                        for j, bhukti in enumerate(bhuktis):
                            bhukti_start = bhukti.get('start', '')
                            bhukti_end = bhukti.get('end', '')
                            
                            logger.info(f"Bhukti {j+1} dates: start={bhukti_start}, end={bhukti_end}")
                            
                            if bhukti_start and bhukti_end:
                                try:
                                    # Parse bhukti dates - same logic as dasha dates
                                    if '-' in bhukti_start and len(bhukti_start.split('-')) == 3:
                                        parts = bhukti_start.split('-')
                                        if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                                            # Convert DD-MM-YYYY to YYYY-MM-DD
                                            bhukti_start_year = int(parts[2])
                                            bhukti_end_year = int(bhukti_end.split('-')[2])
                                        else:
                                            # Assume YYYY-MM-DD format
                                            bhukti_start_year = int(parts[0])
                                            bhukti_end_year = int(bhukti_end.split('-')[0])
                                    else:
                                        logger.warning(f"Unexpected bhukti date format: {bhukti_start}")
                                        continue
                                    
                                    logger.info(f"Bhukti {j+1} years: start_year={bhukti_start_year}, end_year={bhukti_end_year}")
                                    
                                    # Check if bhukti period overlaps with requested range
                                    if (bhukti_start_year <= end_year and bhukti_end_year >= start_year):
                                        logger.info(f"Bhukti {j+1} overlaps with requested period")
                                        filtered_bhuktis.append(bhukti)
                                    else:
                                        logger.info(f"Bhukti {j+1} does not overlap with requested period")
                                except Exception as e:
                                    logger.warning(f"Error parsing bhukti dates: {e}")
                                    # If we can't parse the bhukti dates, include it
                                    filtered_bhuktis.append(bhukti)
                        
                        # Create filtered dasha entry
                        filtered_dasha.append({
                            "dasa_lord": dasha.get('dasa_lord'),
                            "start": start_date,
                            "end": end_date,
                            "bhuktis": filtered_bhuktis
                        })
                        logger.info(f"Added filtered dasha {i+1} with {len(filtered_bhuktis)} bhuktis")
                    else:
                        logger.info(f"Dasha {i+1} does not overlap with requested period")
                        
                except Exception as e:
                    logger.warning(f"Error parsing dasha dates: {e}")
                    # If we can't parse the dasha dates, include it
                    filtered_dasha.append(dasha)
        
        logger.info(f"Filtered dasha count: {len(filtered_dasha)}")
        
        # Find current dasha and bhukti
        current_date = datetime.now()
        current_dasha = None
        current_bhukti = None
        
        logger.info(f"Current date: {current_date}")
        
        for i, dasha in enumerate(filtered_dasha):
            start_date = dasha.get('start', '')
            end_date = dasha.get('end', '')
            if start_date and end_date:
                try:
                    # Parse dates for current dasha detection
                    if '-' in start_date and len(start_date.split('-')) == 3:
                        parts = start_date.split('-')
                        if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                            # Convert DD-MM-YYYY to datetime
                            start_dt = datetime.strptime(f"{parts[2]}-{parts[1]}-{parts[0]}", '%Y-%m-%d')
                            end_dt = datetime.strptime(f"{end_date.split('-')[2]}-{end_date.split('-')[1]}-{end_date.split('-')[0]}", '%Y-%m-%d')
                        else:
                            # Assume YYYY-MM-DD format
                            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    else:
                        continue
                    
                    logger.info(f"Checking dasha {i+1} period: {start_dt} to {end_dt}")
                    
                    if start_dt <= current_date <= end_dt:
                        current_dasha = dasha
                        logger.info(f"Found current dasha: {dasha.get('dasa_lord')}")
                        
                        # Find current bhukti within this dasha
                        bhuktis = dasha.get('bhuktis', [])
                        for j, bhukti in enumerate(bhuktis):
                            bhukti_start = bhukti.get('start', '')
                            bhukti_end = bhukti.get('end', '')
                            if bhukti_start and bhukti_end:
                                try:
                                    # Parse bhukti dates
                                    if '-' in bhukti_start and len(bhukti_start.split('-')) == 3:
                                        parts = bhukti_start.split('-')
                                        if len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
                                            # Convert DD-MM-YYYY to datetime
                                            bhukti_start_dt = datetime.strptime(f"{parts[2]}-{parts[1]}-{parts[0]}", '%Y-%m-%d')
                                            bhukti_end_dt = datetime.strptime(f"{bhukti_end.split('-')[2]}-{bhukti_end.split('-')[1]}-{bhukti_end.split('-')[0]}", '%Y-%m-%d')
                                        else:
                                            # Assume YYYY-MM-DD format
                                            bhukti_start_dt = datetime.strptime(bhukti_start, '%Y-%m-%d')
                                            bhukti_end_dt = datetime.strptime(bhukti_end, '%Y-%m-%d')
                                    else:
                                        continue
                                    
                                    logger.info(f"Checking bhukti {j+1} period: {bhukti_start_dt} to {bhukti_end_dt}")
                                    
                                    if bhukti_start_dt <= current_date <= bhukti_end_dt:
                                        current_bhukti = bhukti
                                        logger.info(f"Found current bhukti: {bhukti.get('bhukti_lord')}")
                                        break
                                except Exception as e:
                                    logger.warning(f"Error parsing bhukti dates for current detection: {e}")
                                    continue
                        break
                except Exception as e:
                    logger.warning(f"Error parsing dasha dates for current detection: {e}")
                    continue
        
        total_bhukti_periods = sum(len(d.get('bhuktis', [])) for d in filtered_dasha)
        
        result = {
            "vimshottari_dasa": filtered_dasha,
            "current_dasha": current_dasha,
            "current_bhukti": current_bhukti,
            "period_info": {
                "requested_start_year": start_year,
                "requested_end_year": end_year,
                "total_dasha_periods": len(filtered_dasha),
                "total_bhukti_periods": total_bhukti_periods
            }
        }
        
        logger.info(f"Final result: {len(filtered_dasha)} dasha periods, {total_bhukti_periods} bhukti periods")
        return result
        
    except Exception as e:
        logger.exception(f"Error in get_vimshottari_dasha:")
        return {"error": f"Failed to calculate vimshottari dasha: {str(e)}"}

def get_arudha_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Arudha Lagna data for a given birth time and location using JHora library.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Arudha Lagna data with the following structure:
        {
            "bhava_arudhas": {
                "A1": {"house": 1, "rashi": 0, "rashi_name": "Aries", "description": "Arudha Lagna for 1st house"},
                "A2": {"house": 2, "rashi": 1, "rashi_name": "Taurus", "description": "Arudha Lagna for 2nd house"},
                # ... A3 to A12
            },
            "graha_arudhas": {
                "Lagna": {"planet": "Lagna", "rashi": 0, "rashi_name": "Aries", "description": "Arudha for Lagna"},
                "Sun": {"planet": "Sun", "rashi": 1, "rashi_name": "Taurus", "description": "Arudha for Sun"},
                # ... other planets
            },
            "chart_info": {
                "ascendant_house": 1,
                "ascendant_rashi": "Aries"
            }
        }
    
    Example Usage:
        # Get Arudha Lagna for a birth
        get_arudha_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with Arudha Lagna data
    """
    logger.info(f"get_arudha_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Convert timezone offset to the format expected by JHora
    # JHora expects timezone offset in hours (e.g., 5.5 for IST)
    return _get_arudha_lagna(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )

def get_previous_conversation_context(user_id: str, n_pairs: int = 3, thread_id: str = None) -> dict:
    """
    Get previous conversation context for a user.
    
    Args:
        user_id: The user ID
        n_pairs: Number of message pairs to retrieve
        thread_id: Optional thread ID to limit context to specific thread
        
    Returns:
        Dictionary with conversation context
    """
    # This is a placeholder implementation
    # In a real implementation, you would query the database for previous messages
    return {
        "user_id": user_id,
        "thread_id": thread_id,
        "message_pairs": [],
        "context_summary": "No previous context available"
    }

def get_upapada_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Upapada Lagna data for marriage and spouse dynamics analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Upapada Lagna data for marriage analysis
    
    Example Usage:
        # Get Upapada Lagna for marriage analysis
        get_upapada_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
    """
    logger.info(f"get_upapada_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Use the enhanced get_lagnas function which now includes Upapada Lagna
    lagnas_data = _get_lagnas(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )
    
    if 'error' in lagnas_data:
        return lagnas_data
    
    # Extract and return only Upapada Lagna data
    return {
        "upapada_lagna": lagnas_data.get("upapada_lagna", {}),
        "chart_info": {
            "description": "Upapada Lagna (UL) - Essential for marriage and spouse dynamics analysis",
            "significance": "12th house from Venus, indicates marriage timing, spouse characteristics, and relationship dynamics"
        }
    }

def get_hora_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Hora Lagna data for wealth and financial rhythm analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Hora Lagna data for wealth analysis
    
    Example Usage:
        # Get Hora Lagna for wealth analysis
        get_hora_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
    """
    logger.info(f"get_hora_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Use the enhanced get_lagnas function which includes Hora Lagna
    lagnas_data = _get_lagnas(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )
    
    if 'error' in lagnas_data:
        return lagnas_data
    
    # Extract and return only Hora Lagna data
    return {
        "hora_lagna": lagnas_data.get("hora_lagna", {}),
        "chart_info": {
            "description": "Hora Lagna (HL) - Wealth and financial rhythm analysis",
            "significance": "Indicates wealth accumulation patterns, financial prosperity, and material gains timing"
        }
    }

def get_ghatika_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Ghatika Lagna data for power, authority, and social ascension analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Ghatika Lagna data for power and authority analysis
    
    Example Usage:
        # Get Ghatika Lagna for power analysis
        get_ghatika_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
    """
    logger.info(f"get_ghatika_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Use the enhanced get_lagnas function which includes Ghatika Lagna
    lagnas_data = _get_lagnas(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )
    
    if 'error' in lagnas_data:
        return lagnas_data
    
    # Extract and return only Ghatika Lagna data
    return {
        "ghatika_lagna": lagnas_data.get("ghatika_lagna", {}),
        "chart_info": {
            "description": "Ghatika Lagna (GL) - Power, authority, and social ascension analysis",
            "significance": "Indicates power dynamics, authority positions, and social climbing opportunities"
        }
    }

def get_sree_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Sree Lagna data for overall prosperity and fortune analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Sree Lagna data for prosperity analysis
    
    Example Usage:
        # Get Sree Lagna for prosperity analysis
        get_sree_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
    """
    logger.info(f"get_sree_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Use the enhanced get_lagnas function which includes Sree Lagna
    lagnas_data = _get_lagnas(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )
    
    if 'error' in lagnas_data:
        return lagnas_data
    
    # Extract and return only Sree Lagna data
    return {
        "sree_lagna": lagnas_data.get("sree_lagna", {}),
        "chart_info": {
            "description": "Sree Lagna - Overall prosperity and fortune analysis",
            "significance": "Indicates general prosperity, fortune, and success in life endeavors"
        }
    }

def get_indu_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Indu Lagna data for wealth inflow and prosperity analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Indu Lagna data for wealth inflow analysis
    
    Example Usage:
        # Get Indu Lagna for wealth inflow analysis
        get_indu_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
    """
    logger.info(f"get_indu_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Use the enhanced get_lagnas function which includes Indu Lagna
    lagnas_data = _get_lagnas(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )
    
    if 'error' in lagnas_data:
        return lagnas_data
    
    # Extract and return only Indu Lagna data
    return {
        "indu_lagna": lagnas_data.get("indu_lagna", {}),
        "chart_info": {
            "description": "Indu Lagna - Wealth inflow and prosperity analysis",
            "significance": "Indicates wealth accumulation patterns, financial inflow, and prosperity timing"
        }
    }

def get_karakamsa_lagna(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Generate Karakamsa Lagna data for psychological and dharmic life analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset in hours (e.g., 5.5 for IST)
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Language for output (default 'en')
    
    Returns:
        dict: Karakamsa Lagna data for life purpose analysis
    
    Example Usage:
        # Get Karakamsa Lagna for life purpose analysis
        get_karakamsa_lagna(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
    """
    logger.info(f"get_karakamsa_lagna called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    # Use the specialized Karakamsa Lagna function
    return _get_karakamsa_lagna(
        year, month, day, hour, minute, second,
        latitude, longitude, timezone_offset,
        ayanamsa_mode, language
    )

def get_ashtakavarga(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Calculate Ashtakavarga (8-fold strength analysis) for personality and behavioral traits.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset from UTC in hours
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Output language (default 'en')
    
    Returns:
        dict: Ashtakavarga analysis with the following structure:
        {
            "binna_ashtaka_varga": [[...], [...], ...],  # 8x12 matrix for each planet
            "samudhaya_ashtaka_varga": [...],             # Combined strength for each house
            "prastara_ashtaka_varga": [[[...]], ...],     # Detailed breakdown
            "planetary_strengths": {
                "Sun": 25, "Moon": 30, "Mars": 22, ...   # Strength scores
            },
            "house_strengths": [28, 25, 30, ...],         # Strength for each house
            "error": null
        }
        
        Error case: {"error": "error message"}
    
    Example Usage:
        # Get Ashtakavarga for personality analysis
        get_ashtakavarga(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with Ashtakavarga strength analysis
    """
    logger.info(f"get_ashtakavarga called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    try:
        # Import required jhora modules
        from jhora.panchanga import drik
        from jhora import utils
        
        # Calculate planetary positions directly using jhora
        jd = utils.julian_day_number(drik.Date(year, month, day), (hour, minute, second))
        place = drik.Place('', latitude, longitude, timezone_offset)
        
        # Get planetary positions for D1 chart
        planet_positions = drik.planetary_positions(jd, place)
        ascendant_info = drik.ascendant(jd, place)
        
        # Create house_to_planet_list format expected by jhora
        # Initialize with empty houses
        house_to_planet_list = ['' for _ in range(12)]
        
        # Add planetary positions to houses
        for planet_data in planet_positions:
            planet_id = planet_data[0]  # Planet index (0=Sun, 1=Moon, etc.)
            house_num = planet_data[2]  # House/constellation number (0-11)
            
            if house_to_planet_list[house_num]:
                house_to_planet_list[house_num] += f'/{planet_id}'
            else:
                house_to_planet_list[house_num] = str(planet_id)
        
        # Add ascendant (Lagna) to its house
        asc_house = ascendant_info[0]  # Ascendant house (0-11)
        if house_to_planet_list[asc_house]:
            house_to_planet_list[asc_house] += '/L'
        else:
            house_to_planet_list[asc_house] = 'L'
        
        try:
            # Import and use jhora's ashtakavarga function
            from jhora.horoscope.chart.ashtakavarga import get_ashtaka_varga
            
            binna_ashtaka_varga, samudhaya_ashtaka_varga, prastara_ashtaka_varga = get_ashtaka_varga(house_to_planet_list)
            
            # Calculate planetary strengths (sum across all houses for each planet)
            planetary_strengths = {}
            planet_names = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Lagna']
            for i, planet in enumerate(planet_names):
                if i < len(binna_ashtaka_varga):
                    planetary_strengths[planet] = sum(binna_ashtaka_varga[i])
            
            return {
                "binna_ashtaka_varga": binna_ashtaka_varga,
                "samudhaya_ashtaka_varga": samudhaya_ashtaka_varga,
                "prastara_ashtaka_varga": prastara_ashtaka_varga,
                "planetary_strengths": planetary_strengths,
                "house_strengths": samudhaya_ashtaka_varga,
                "error": None
            }
        except Exception as e:
            logger.exception(f"Error in Ashtakavarga calculation:")
            return {"error": f"Ashtakavarga calculation failed: {str(e)}"}
        
    except Exception as e:
        logger.exception(f"Error in get_ashtakavarga:")
        return {"error": f"Failed to calculate Ashtakavarga: {str(e)}"}

def get_shadbala(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Calculate Shadbala (6-fold planetary strength) for personality and behavioral analysis.
    
    Args:
        year (int): Birth year
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        second (int): Birth second (0-59)
        latitude (float): Latitude of birth place
        longitude (float): Longitude of birth place
        timezone_offset (float): Timezone offset from UTC in hours
        ayanamsa_mode (str): Ayanamsa correction system (default 'LAHIRI')
        language (str): Output language (default 'en')
    
    Returns:
        dict: Shadbala analysis with the following structure:
        {
            "sthana_bala": [...],      # Positional strength
            "kaala_bala": [...],       # Temporal strength  
            "dig_bala": [...],         # Directional strength
            "cheshta_bala": [...],     # Motional strength
            "naisargika_bala": [...],  # Natural strength
            "drik_bala": [...],        # Aspectual strength
            "total_shadbala": [...],   # Total strength in vimsopaka
            "shadbala_rupas": [...],   # Strength in rupas
            "strength_ratios": [...],  # Strength ratios vs required
            "strongest_planet": "Jupiter",  # Planet with highest strength
            "weakest_planet": "Saturn",     # Planet with lowest strength
            "error": null
        }
        
        Error case: {"error": "error message"}
    
    Example Usage:
        # Get Shadbala for personality analysis
        get_shadbala(1990, 3, 15, 6, 30, 0, 13.08, 80.27, 5.5)
        # Returns: dict with Shadbala strength analysis
    """
    logger.info(f"get_shadbala called with: year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, latitude={latitude}, longitude={longitude}, timezone_offset={timezone_offset}, ayanamsa_mode={ayanamsa_mode}, language={language}")
    
    try:
        # Import required jhora modules
        from jhora.horoscope.chart.strength import shad_bala
        from jhora import utils
        from jhora.panchanga import drik
        
        # Convert to Julian day and place format for jhora
        jd = utils.julian_day_number(drik.Date(year, month, day), (hour, minute, second))
        # Create place using drik.Place namedtuple
        place = drik.Place('', latitude, longitude, timezone_offset)
        
        # Calculate Shadbala using jhora
        try:
            shadbala_result = shad_bala(jd, place, ayanamsa_mode)
        except Exception as e:
            logger.exception(f"Error calling jhora shad_bala:")
            return {"error": f"Shadbala calculation failed: {str(e)}"}
        
        if not shadbala_result or len(shadbala_result) < 9:
            return {"error": "Invalid Shadbala calculation result"}
        
        # Extract components: [sthana, kaala, dig, cheshta, naisargika, drik, total, rupas, ratios]
        sthana_bala, kaala_bala, dig_bala, cheshta_bala, naisargika_bala, drik_bala, total_shadbala, shadbala_rupas, strength_ratios = shadbala_result
        
        # Planet names for mapping
        planet_names = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn']
        
        # Find strongest and weakest planets
        strongest_planet = planet_names[shadbala_rupas.index(max(shadbala_rupas))] if shadbala_rupas else "Unknown"
        weakest_planet = planet_names[shadbala_rupas.index(min(shadbala_rupas))] if shadbala_rupas else "Unknown"
        
        # Create detailed strength mapping
        planetary_strengths = {}
        for i, planet in enumerate(planet_names):
            if i < len(shadbala_rupas):
                planetary_strengths[planet] = {
                    "sthana_bala": sthana_bala[i] if i < len(sthana_bala) else 0,
                    "kaala_bala": kaala_bala[i] if i < len(kaala_bala) else 0,
                    "dig_bala": dig_bala[i] if i < len(dig_bala) else 0,
                    "cheshta_bala": cheshta_bala[i] if i < len(cheshta_bala) else 0,
                    "naisargika_bala": naisargika_bala[i] if i < len(naisargika_bala) else 0,
                    "drik_bala": drik_bala[i] if i < len(drik_bala) else 0,
                    "total_vimsopaka": total_shadbala[i] if i < len(total_shadbala) else 0,
                    "total_rupas": shadbala_rupas[i] if i < len(shadbala_rupas) else 0,
                    "strength_ratio": strength_ratios[i] if i < len(strength_ratios) else 0
                }
        
        return {
            "sthana_bala": sthana_bala,
            "kaala_bala": kaala_bala,
            "dig_bala": dig_bala,
            "cheshta_bala": cheshta_bala,
            "naisargika_bala": naisargika_bala,
            "drik_bala": drik_bala,
            "total_shadbala": total_shadbala,
            "shadbala_rupas": shadbala_rupas,
            "strength_ratios": strength_ratios,
            "planetary_strengths": planetary_strengths,
            "strongest_planet": strongest_planet,
            "weakest_planet": weakest_planet,
            "error": None
        }
        
    except Exception as e:
        logger.exception(f"Error in get_shadbala:")
        return {"error": f"Failed to calculate Shadbala: {str(e)}"}

