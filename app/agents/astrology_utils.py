from jhora.horoscope.transit import tajaka
from jhora.panchanga.drik import Date, Place
from jhora.horoscope.main import Horoscope
from jhora.horoscope.chart import yoga
from vedicastro.VedicAstro import VedicHoroscopeData
import polars as pl
from datetime import datetime, timedelta
import pytz
from app.schemas.user import ChartData
from app.utils.logger import get_logger
from typing import Dict, Any
import swisseph as swe
from datetime import timezone

logger = get_logger(__name__)

# Moon sign mapping from integer to name
MOON_SIGN_NAMES = [
    None,  # 0-index not used
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def get_moon_sign_name(moon_rashi: int) -> str | None:
    """
    Convert moon rashi integer to sign name.
    
    Args:
        moon_rashi (int): Moon rashi number (1-12)
    Returns:
        str | None: Sign name or None if invalid
    """
    if isinstance(moon_rashi, int) and 1 <= moon_rashi <= 12:
        return MOON_SIGN_NAMES[moon_rashi]
    return None

def get_d1_chart_data(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    utc: str,
    latitude: float,
    longitude: float,
    ayanamsa: str = 'LAHIRI',
    house_system: str = 'Placidus'
) -> dict:
    """
    Generates a comprehensive dictionary of astrological data for a given birth time and location.
    This data can be used as context for an AI Astrologer (LLM) to answer life questions.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        utc: str
        latitude: float
        longitude: float
        ayanamsa: str (default: 'LAHIRI')
        house_system: str (default: 'Placidus')
    """
    try:
        logger.info(f"Generating D1 chart data for year={year}, month={month}, day={day}, hour={hour}, minute={minute}, second={second}, utc={utc}, latitude={latitude}, longitude={longitude}, ayanamsa={ayanamsa}, house_system={house_system}")
        vhd = VedicHoroscopeData(
            year=year, month=month, day=day, hour=hour, minute=minute,
            second=second, utc=utc, latitude=latitude, longitude=longitude,
            ayanamsa=ayanamsa, house_system=house_system
        )
        chart = vhd.generate_chart()
        planets_data = vhd.get_planets_data_from_chart(chart)
        planets_df = pl.DataFrame(planets_data)
        planetary_positions = planets_df.to_dicts()
        houses_data = vhd.get_houses_data_from_chart(chart)
        houses_df = pl.DataFrame(houses_data)
        house_cusps = houses_df.to_dicts()
        planets_in_house = vhd.get_planet_in_house(houses_chart=chart, planets_chart=chart)
        planets_significators_table = vhd.get_planet_wise_significators(planets_data, houses_data)
        planet_wise_significators_df = pl.DataFrame(planets_significators_table)
        planet_wise_significators = planet_wise_significators_df.to_dicts()
        houses_significators_table = vhd.get_house_wise_significators(planets_data, houses_data)
        house_wise_significators_df = pl.DataFrame(houses_significators_table)
        house_wise_significators = house_wise_significators_df.to_dicts()
        dasa_data = vhd.compute_vimshottari_dasa(chart)
        vimshottari_dasa_formatted = []
        for dasa_lord, dasa_info in dasa_data.items():
            dasa_start = dasa_info.get('start')
            dasa_end = dasa_info.get('end')
            bhuktis_formatted = []
            if 'bhuktis' in dasa_info:
                for bhukti_lord, bhukti_info in dasa_info['bhuktis'].items():
                    bhukti_start = bhukti_info.get('start')
                    bhukti_end = bhukti_info.get('end')
                    bhuktis_formatted.append({
                        "bhukti_lord": bhukti_lord,
                        "start": str(bhukti_start),
                        "end": str(bhukti_end)
                    })
            vimshottari_dasa_formatted.append({
                "dasa_lord": dasa_lord,
                "start": str(dasa_start),
                "end": str(dasa_end),
                "bhuktis": bhuktis_formatted
            })
        astrology_context = {
            "birth_details": {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
                "utc": utc,
                "latitude": latitude,
                "longitude": longitude,
                "ayanamsa": ayanamsa,
                "house_system": house_system
            },
            "planetary_positions": planetary_positions,
            "house_cusps": house_cusps,
            "planets_in_houses": planets_in_house,
            "planet_wise_significators": planet_wise_significators,
            "house_wise_significators": house_wise_significators,
            "vimshottari_dasa": vimshottari_dasa_formatted
        }
        return astrology_context
    except Exception as e:
        logger.exception(f"An error occurred in get_d1_chart_data")
        return {"error": str(e)} 
    

def get_today_date_ist():
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    return now_ist.strftime('%d %B %Y')  # e.g., "25 June 2025"

def get_sidereal_transits_ist(ist_dt, lat_deg, lon_deg, ephe_path='/app/ephe'):
    import swisseph as swe
    import math
    from datetime import timedelta
    swe.set_ephe_path(ephe_path)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    # Convert IST → UTC → Julian Day
    ut = ist_dt - timedelta(hours=5, minutes=30)
    jd_ut = swe.utc_to_jd(ut.year, ut.month, ut.day,
                          ut.hour, ut.minute, ut.second, swe.GREG_CAL)[1]

    signs = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
             'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

    # Moon Sign (deg input, no ambiguity)
    moon_lon = swe.calc_ut(jd_ut, swe.MOON, flags)[0][0] % 360
    moon_sign = signs[int(moon_lon // 30)]

    # ✅ Use radians AND FLG_RADIANS in houses_ex()
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    cusps, _ = swe.houses_ex(jd_ut, lat_rad, lon_rad, b'P', flags | swe.FLG_RADIANS)
    asc_sign = signs[int(cusps[0] % 360 // 30)]

    # Ascendant‑lord and its transit (generic)
    lord_map = {
        'Aries':'Mars','Taurus':'Venus','Gemini':'Mercury','Cancer':'Moon',
        'Leo':'Sun','Virgo':'Mercury','Libra':'Venus','Scorpio':'Mars',
        'Sagittarius':'Jupiter','Capricorn':'Saturn','Aquarius':'Saturn','Pisces':'Jupiter'
    }
    asc_lord = lord_map[asc_sign]
    planet_id = getattr(swe, asc_lord.upper())
    lord_lon = swe.calc_ut(jd_ut, planet_id, flags)[0][0] % 360
    asc_lord_transit = signs[int(lord_lon // 30)]

    return {
       "moon_transit": moon_sign,
       "moon_longitude": moon_lon,
       "ascendant_sign": asc_sign,
       "ascendant_lord": asc_lord,
       "ascendant_lord_transit": asc_lord_transit
    }
    
def get_current_ist_datetime():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def get_weekly_moon_nakshatra_movements(
    week_start_year: int,
    week_start_month: int, 
    week_start_day: int,
    latitude: float,
    longitude: float,
    ephe_path: str = '/app/ephe'
) -> dict:
    """
    Calculate Moon's nakshatra movements throughout a specific week.
    
    Args:
        week_start_year: Year of the week start date
        week_start_month: Month of the week start date  
        week_start_day: Day of the week start date
        latitude: Latitude for calculations
        longitude: Longitude for calculations
        ephe_path: Path to ephemeris files
    
    Returns:
        Dictionary containing Moon's nakshatra movements for each day of the week
    """
    try:
        import swisseph as swe
        from datetime import date, timedelta
        
        swe.set_ephe_path(ephe_path)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        
        # Nakshatra names
        nakshatras = [
            'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
            'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
            'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
            'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha',
            'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
        ]
        
        week_start = date(week_start_year, week_start_month, week_start_day)
        moon_movements = {}
        
        # Calculate for each day of the week (7 days)
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_name = current_date.strftime('%A')
            
            # Convert to IST datetime (noon for consistency)
            ist_dt = datetime.combine(current_date, datetime.min.time().replace(hour=12))
            ist = pytz.timezone('Asia/Kolkata')
            ist_dt = ist.localize(ist_dt)
            
            # Convert IST to UTC for Swiss Ephemeris
            utc_dt = ist_dt - timedelta(hours=5, minutes=30)
            jd_ut = swe.utc_to_jd(utc_dt.year, utc_dt.month, utc_dt.day,
                                  utc_dt.hour, utc_dt.minute, utc_dt.second, swe.GREG_CAL)[1]
            
            # Calculate Moon's position
            moon_lon = swe.calc_ut(jd_ut, swe.MOON, flags)[0][0] % 360
            
            # Calculate nakshatra (each nakshatra = 13°20' = 13.333...)
            nakshatra_num = int(moon_lon / (360/27)) + 1
            if nakshatra_num > 27:
                nakshatra_num = 27
            
            nakshatra_name = nakshatras[nakshatra_num - 1]
            
            # Calculate pada (each nakshatra has 4 padas)
            nakshatra_progress = (moon_lon % (360/27)) / (360/27)
            pada = int(nakshatra_progress * 4) + 1
            
            moon_movements[day_name] = {
                'date': current_date.strftime('%Y-%m-%d'),
                'nakshatra_number': nakshatra_num,
                'nakshatra_name': nakshatra_name,
                'pada': pada,
                'moon_longitude': moon_lon,
                'nakshatra_progress_percent': round(nakshatra_progress * 100, 2)
            }
        
        # Identify nakshatra changes during the week
        nakshatra_changes = []
        prev_nakshatra = None
        for day_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            if day_name in moon_movements:
                current_nakshatra = moon_movements[day_name]['nakshatra_name']
                if prev_nakshatra and prev_nakshatra != current_nakshatra:
                    nakshatra_changes.append({
                        'day': day_name,
                        'date': moon_movements[day_name]['date'],
                        'from_nakshatra': prev_nakshatra,
                        'to_nakshatra': current_nakshatra
                    })
                prev_nakshatra = current_nakshatra
        
        return {
            'daily_positions': moon_movements,
            'nakshatra_changes': nakshatra_changes,
            'week_start_nakshatra': list(moon_movements.values())[0]['nakshatra_name'] if moon_movements else None,
            'week_end_nakshatra': list(moon_movements.values())[-1]['nakshatra_name'] if moon_movements else None
        }
        
    except Exception as e:
        logger.exception(f"Error calculating weekly Moon nakshatra movements for {week_start_year}-{week_start_month}-{week_start_day}")
        return {"error": str(e)}

def get_d2_chart_data(
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
    Generates the D2 (Hora) chart using the JHora library for a given birth time and location.
    Returns a dictionary with D2 chart data.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
    """
    try:

        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        # Instantiate Horoscope
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        # D2 chart: divisional_chart_factor=2
        d2_info, d2_charts, d2_asc_house = h.get_horoscope_information_for_chart(
            chart_index=None, chart_method=1, divisional_chart_factor=2
        )
        return {
            "d2_chart_info": d2_info,
            "d2_charts": d2_charts,
            "d2_ascendant_house": d2_asc_house
        }
    except Exception as e:
        print(f"An error occurred in get_d2_chart_data: {e}")
        return {"error": str(e)}

def get_d1_chart_data_jhora(
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
    Generates the D1 (Rasi) chart using the JHora library for a given birth time and location.
    Returns a dictionary with D1 chart data.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
    """
    try:
    
        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        # Instantiate Horoscope
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        # D1 chart: divisional_chart_factor=1
        d1_info, d1_charts, d1_asc_house = h.get_horoscope_information_for_chart(
            chart_index=None, chart_method=1, divisional_chart_factor=1
        )
        return {
            "d1_chart_info": d1_info,
            "d1_charts": d1_charts,
            "d1_ascendant_house": d1_asc_house
        }
    except Exception as e:
        print(f"An error occurred in get_d1_chart_data_jhora: {e}")
        return {"error": str(e)}

def get_divisional_chart_jhora(
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
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> ChartData:
    """
    Generates a specific divisional chart (e.g., D1, D2, D9, navamsa, etc.) using JHora for a given birth time and location.
    Returns the chart data as a ChartData Pydantic object.
    
    Args:
        chart: str
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
    """

    # Mapping of chart names/aliases to divisional_chart_factors
    chart_map = {
        'd1': 1, 'rasi': 1, 'rashi': 1,
        'd2': 2, 'hora': 2,
        'd3': 3, 'drekkana': 3, 'drekkana': 3,
        'd4': 4, 'chaturthamsa': 4,
        'd5': 5, 'panchamsa': 5,
        'd6': 6, 'shashthamsa': 6,
        'd7': 7, 'saptamsa': 7,
        'd8': 8, 'ashtamsa': 8,
        'd9': 9, 'navamsa': 9, 'navamsha': 9,
        'd10': 10, 'dasamsa': 10, 'dashamsa': 10,
        'd11': 11, 'rudramsa': 11,
        'd12': 12, 'dvadasamsa': 12, 'dwadasamsa': 12,
        'd16': 16, 'shodamsa': 16,
        'd20': 20, 'vimsamsa': 20,
        'd24': 24, 'chaturvimshamsa': 24,
        'd27': 27, 'nakshatramsa': 27,
        'd30': 30, 'trimsamsa': 30, 'trimsamsha': 30,
        'd40': 40, 'khavedamsa': 40,
        'd45': 45, 'akshavedamsa': 45,
        'd60': 60, 'shashtiamsa': 60, 'shashtiamsha': 60,
        'd81': 81,
        'd108': 108, 'ashtottaramsa': 108,
        'd144': 144
    }
    # Accept both Dn and name, case-insensitive
    chart_key = str(chart).strip().lower()
    if chart_key in chart_map:
        dcf = chart_map[chart_key]
    else:
        # Try if user gave just the number (e.g., '9')
        try:
            dcf = int(chart_key)
            if dcf not in chart_map.values():
                raise ValueError
        except Exception:
            logger.exception(f"Unknown chart name or factor: {chart}")
            return ChartData(error=f"Unknown chart name or factor: {chart}")
    try:
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        chart_info, charts, asc_house = h.get_horoscope_information_for_chart(
            chart_index=None, chart_method=1, divisional_chart_factor=dcf
        )
        return ChartData(
            chart_info=chart_info,
            charts=charts,
            ascendant_house=asc_house
        )
    except Exception as e:
        logger.exception(f"An error occurred in get_divisional_chart_jhora for chart {chart}, year {year}, month {month}, day {day}, hour {hour}, minute {minute}, second {second}, latitude {latitude}, longitude {longitude}, timezone_offset {timezone_offset}, ayanamsa_mode {ayanamsa_mode}, language {language}")
        return ChartData(error=str(e))

def get_yogas_jhora(
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
    Calculates all Yogas present in the divisional charts for a given birth date, time, and place using JHora.
    Returns a dictionary of found yogas and their details.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
    """
    try:
        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        # Compute Julian day using Horoscope utility
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        jd = h.julian_day  # Julian day for birth
        place = Place("BirthPlace", latitude, longitude, timezone_offset)
        yoga_results, found_count, total_possible = yoga.get_yoga_details_for_all_charts(
            jd, place, language=language
        )
        return {
            "yogas": yoga_results,
            "found_count": found_count,
            "total_possible": total_possible
        }
    except Exception as e:
        logger.exception(f"An error occurred in get_yogas_jhora for year {year}, month {month}, day {day}, hour {hour}, minute {minute}, second {second}, latitude {latitude}, longitude {longitude}, timezone_offset {timezone_offset}, ayanamsa_mode {ayanamsa_mode}, language {language}")
        return {"error": str(e)}

def get_lagnas_jhora(
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
    language: str = 'en',
    divisional_chart_factor: int = 1
) -> dict:
    """
    Calculates the main Lagna (ascendant) and special lagnas (Bhava, Hora, Ghati, Vighati, Pranapada, Indu, Kunda, Bhrigu Bindhu, Sree, Upapada) for a given birth date, time, and place using JHora.
    Returns a dictionary with all these lagnas' positions (constellation, longitude, etc).
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
        divisional_chart_factor: int (default: 1)
    """
    try:
        from jhora.panchanga.drik import Date, Place, ascendant, special_ascendant, pranapada_lagna, indu_lagna, kunda_lagna, bhrigu_bindhu_lagna, sree_lagna
        from jhora.horoscope.main import Horoscope
        from jhora.horoscope.chart import charts
        
        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        jd = h.julian_day
        place = Place("BirthPlace", latitude, longitude, timezone_offset)
        
        # Get planet positions for Upapada Lagna calculation
        planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=1)
        
        # Main Lagna
        lagna = ascendant(jd, place)
        
        # Special Lagnas
        bhava_lagna = special_ascendant(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor, lagna_rate_factor=1.0)
        hora_lagna = special_ascendant(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor, lagna_rate_factor=0.5)
        ghati_lagna = special_ascendant(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor, lagna_rate_factor=1.25)
        vighati_lagna = special_ascendant(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor, lagna_rate_factor=15.0)
        pranapada = pranapada_lagna(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor)
        indu = indu_lagna(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor)
        kunda = kunda_lagna(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor)
        bhrigu_bindhu = bhrigu_bindhu_lagna(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor)
        sree = sree_lagna(jd, place, ayanamsa_mode=ayanamsa_mode, divisional_chart_factor=divisional_chart_factor)
        
        # Calculate Upapada Lagna (12th house from Venus)
        # Venus is at index 5 in planet_positions (0=Lagna, 1=Sun, 2=Moon, 3=Mars, 4=Mercury, 5=Venus)
        if len(planet_positions) > 5:
            venus_house = planet_positions[5][1][0]  # Venus's house (0-indexed)
            upapada_house = (venus_house + 11) % 12  # 12th house from Venus (11 houses ahead)
            upapada_lagna = [upapada_house, 0]  # Start of the house
        else:
            upapada_lagna = [0, 0]  # Default if Venus not found
        
        # Get rashi names for better formatting
        rashi_names = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                      'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        
        # Format lagna data with enhanced information
        def format_lagna_data(lagna_data, lagna_name, description):
            if isinstance(lagna_data, list) and len(lagna_data) >= 2:
                constellation = lagna_data[0]
                longitude = lagna_data[1]
                rashi_name = rashi_names[constellation] if 0 <= constellation < 12 else "Unknown"
                degrees = f"{int(longitude)}°{int((longitude % 1) * 60)}'"
                
                return {
                    "constellation": constellation,
                    "longitude": longitude,
                    "rashi_name": rashi_name,
                    "degrees": degrees,
                    "description": description
                }
            else:
                return {
                    "constellation": None,
                    "longitude": None,
                    "rashi_name": "Unknown",
                    "degrees": "Unknown",
                    "description": description,
                    "error": "Invalid lagna data"
                }
        
        return {
            "lagna": format_lagna_data(lagna, "Main Lagna", "Primary ascendant for birth chart"),
            "bhava_lagna": format_lagna_data(bhava_lagna, "Bhava Lagna", "House-based lagna for timing"),
            "hora_lagna": format_lagna_data(hora_lagna, "Hora Lagna", "Wealth and financial rhythm lagna"),
            "ghati_lagna": format_lagna_data(ghati_lagna, "Ghati Lagna", "Power, authority, and social ascension lagna"),
            "vighati_lagna": format_lagna_data(vighati_lagna, "Vighati Lagna", "Fine timing lagna"),
            "pranapada_lagna": format_lagna_data(pranapada, "Pranapada Lagna", "Life force and vitality lagna"),
            "indu_lagna": format_lagna_data(indu, "Indu Lagna", "Wealth inflow and prosperity lagna"),
            "kunda_lagna": format_lagna_data(kunda, "Kunda Lagna", "Marriage and relationship lagna"),
            "bhrigu_bindhu_lagna": format_lagna_data(bhrigu_bindhu, "Bhrigu Bindhu Lagna", "Destiny and fate lagna"),
            "sree_lagna": format_lagna_data(sree, "Sree Lagna", "Overall prosperity and fortune lagna"),
            "upapada_lagna": format_lagna_data(upapada_lagna, "Upapada Lagna", "Marriage and spouse dynamics lagna")
        }
        
    except Exception as e:
        logger.exception(f"An error occurred in get_lagnas_jhora for year {year}, month {month}, day {day}, hour {hour}, minute {minute}, second {second}, latitude {latitude}, longitude {longitude}, timezone_offset {timezone_offset}, ayanamsa_mode {ayanamsa_mode}, language {language}")
        return {"error": str(e)}

def get_transits_jhora(
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
    language: str = 'en',
    divisional_chart_factor: int = 1,
    years_from_birth: int = 1,
    months: int = 1
) -> dict:
    """
    Calculates the annual (varsha pravesh) and monthly (maasa pravesh) transit charts for a given birth date, time, and place using JHora.
    'years_from_birth' is the number of years after birth for which the transit is sought.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
        divisional_chart_factor: int (default: 1)
        years_from_birth: int (default: 1)
        months: int (default: 1)
        
    """
    try:
        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        jd = h.julian_day
        place = Place("BirthPlace", latitude, longitude, timezone_offset)
        # Annual (Varsha Pravesh) chart
        annual_chart, annual_info = tajaka.varsha_pravesh(jd, place, divisional_chart_factor=divisional_chart_factor, years=years_from_birth)
        # Monthly (Maasa Pravesh) chart
        monthly_chart, monthly_info = tajaka.maasa_pravesh(jd, place, divisional_chart_factor=divisional_chart_factor, years=years_from_birth, months=months)
        return {
            "annual_transit_chart": {
                "chart": annual_chart,
                "date_info": annual_info
            },
            "monthly_transit_chart": {
                "chart": monthly_chart,
                "date_info": monthly_info
            }
        }
    except Exception as e:
        logger.exception(f"An error occurred in get_transits_jhora for year {year}, month {month}, day {day}, hour {hour}, minute {minute}, second {second}, latitude {latitude}, longitude {longitude}, timezone_offset {timezone_offset}, ayanamsa_mode {ayanamsa_mode}, language {language}, years_from_birth {years_from_birth}, months {months}")
        return {"error": str(e)}

def get_weekly_astrological_data(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    week_start_year: int,
    week_start_month: int,
    week_start_day: int,
    ayanamsa_mode: str = 'LAHIRI',
    language: str = 'en'
) -> dict:
    """
    Get comprehensive astrological data for weekly horoscope including current Dasha and transit information.
    
    Args:
        year: Birth year
        month: Birth month
        day: Birth day
        hour: Birth hour
        minute: Birth minute
        second: Birth second
        latitude: Birth latitude
        longitude: Birth longitude
        timezone_offset: Timezone offset
        week_start_year: Year of the week start date
        week_start_month: Month of the week start date
        week_start_day: Day of the week start date
        ayanamsa_mode: Ayanamsa mode (default 'LAHIRI')
        language: Language (default 'en')
    
    Returns:
        Dictionary containing Dasha and transit data for the week
    """
    try:
        # Calculate years from birth to the target week
        from datetime import date
        birth_date = date(year, month, day)
        week_start_date = date(week_start_year, week_start_month, week_start_day)
        years_from_birth = (week_start_date - birth_date).days // 365
        
        # Get transit data for the week
        transit_data = get_transits_jhora(
            year, month, day, hour, minute, second,
            latitude, longitude, timezone_offset,
            ayanamsa_mode, language,
            divisional_chart_factor=1,
            years_from_birth=max(1, years_from_birth),  # Ensure at least 1 year
            months=1
        )
        
        # Get current Dasha period (we'll use the existing D1 chart data function)
        d1_data = get_d1_chart_data(
            year, month, day, hour, minute, second,
            f"+{timezone_offset:05.2f}".replace('.', ':'),
            latitude, longitude
        )
        
        # Get Moon's nakshatra movements for the week
        moon_movements = get_weekly_moon_nakshatra_movements(
            week_start_year, week_start_month, week_start_day,
            latitude, longitude
        )
        
        # Extract Dasha information
        dasha_data = {}
        if 'vimshottari_dasa' in d1_data and d1_data['vimshottari_dasa']:
            vimshottari = d1_data['vimshottari_dasa']
            
            # Find current Dasha and Bhukti based on the week start date
            current_dasha = None
            current_bhukti = None
            
            def parse_dasha_date(date_str):
                """Parse Dasha date which comes in DD-MM-YYYY format"""
                try:
                    if isinstance(date_str, str):
                        # Handle DD-MM-YYYY format
                        if '-' in date_str and len(date_str.split('-')) == 3:
                            parts = date_str.split('-')
                            if len(parts[0]) == 2:  # DD-MM-YYYY format
                                day, month, year = parts
                                return datetime(int(year), int(month), int(day))
                            else:  # YYYY-MM-DD format
                                return datetime.fromisoformat(date_str)
                        else:
                            # Try direct ISO format parsing
                            return datetime.fromisoformat(date_str)
                    return None
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse Dasha date '{date_str}': {e}")
                    return None
            
            for dasha in vimshottari:
                dasha_start = parse_dasha_date(dasha['start'])
                dasha_end = parse_dasha_date(dasha['end'])
                week_start_dt = datetime(week_start_year, week_start_month, week_start_day)
                
                if dasha_start and dasha_end and dasha_start <= week_start_dt <= dasha_end:
                    current_dasha = {
                        'lord': dasha['dasa_lord'],
                        'start': dasha['start'],
                        'end': dasha['end']
                    }
                    
                    # Find current Bhukti
                    for bhukti in dasha.get('bhuktis', []):
                        bhukti_start = parse_dasha_date(bhukti['start'])
                        bhukti_end = parse_dasha_date(bhukti['end'])
                        
                        if bhukti_start and bhukti_end and bhukti_start <= week_start_dt <= bhukti_end:
                            current_bhukti = {
                                'lord': bhukti['bhukti_lord'],
                                'start': bhukti['start'],
                                'end': bhukti['end']
                            }
                            break
                    break
            
            dasha_data = {
                'current_dasha': current_dasha,
                'current_bhukti': current_bhukti,
                'full_timeline': vimshottari
            }
        
        return {
            'dasha_data': dasha_data,
            'transit_data': transit_data,
            'moon_nakshatra_movements': moon_movements,
            'birth_chart_summary': {
                'planetary_positions': d1_data.get('planetary_positions', []),
                'house_cusps': d1_data.get('house_cusps', [])
            }
        }
        
    except Exception as e:
        logger.exception(f"An error occurred in get_weekly_astrological_data for birth {year}-{month}-{day} and week {week_start_year}-{week_start_month}-{week_start_day}")
        return {"error": str(e)}

def get_comprehensive_weekly_data(user, start_date, end_date, get_lat_long_func, get_timezone_func):
    """
    Get comprehensive weekly astrological data for a user.
    
    Args:
        user: User object with birth data
        start_date: datetime object for week start
        end_date: datetime object for week end
        get_lat_long_func: Function to get latitude/longitude from city
        get_timezone_func: Function to get timezone from coordinates
    
    Returns:
        Dictionary containing dasha_data, transit_data, and moon_movements
    """
    try:
        if not user.time_of_birth or not user.city_of_birth:
            return {}
        
        # Extract birth components
        birth_time = user.time_of_birth
        year = birth_time.year
        month = birth_time.month
        day = birth_time.day
        hour = birth_time.hour
        minute = birth_time.minute
        second = birth_time.second
        
        # Get location data
        lat, lon = get_lat_long_func(user.city_of_birth)
        tz_str = get_timezone_func(lat, lon)
        
        # Convert timezone string to timezone object and calculate offset
        if isinstance(tz_str, str):
            import pytz
            try:
                tz_obj = pytz.timezone(tz_str)
                timezone_offset = tz_obj.utcoffset(datetime.now()).total_seconds() / 3600
            except Exception as tz_error:
                logger.warning(f"Could not parse timezone {tz_str}, using default offset: {tz_error}")
                timezone_offset = 5.5  # Default to IST
        else:
            # If it's already a timezone object
            timezone_offset = tz_str.utcoffset(datetime.now()).total_seconds() / 3600
        
        # Get weekly data
        weekly_data = get_weekly_astrological_data(
            year, month, day, hour, minute, second,
            lat, lon, timezone_offset,
            start_date.year, start_date.month, start_date.day
        )
        
        return {
            'dasha_data': weekly_data.get('dasha_data', {}),
            'transit_data': weekly_data.get('transit_data', {}),
            'moon_movements': weekly_data.get('moon_nakshatra_movements', {})
        }
        
    except Exception as e:
        logger.exception(f"Error getting comprehensive weekly data for user {user.id}")
        return {}

def get_arudha_lagna_jhora(
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
    Generates Arudha Lagna data using the JHora library for a given birth time and location.
    Returns a dictionary with Bhava Arudhas (A1-A12) and Graha Arudhas.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
    """
    try:
        from jhora.panchanga.drik import Date, Place
        from jhora.horoscope.main import Horoscope
        from jhora.horoscope.chart.arudhas import (
            bhava_arudhas_from_planet_positions,
            graha_arudhas_from_planet_positions
        )
        from jhora.horoscope.chart import charts
        
        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        
        # Instantiate Horoscope
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        
        # Create place object for calculations
        place = Place("BirthPlace", latitude, longitude, timezone_offset)
        
        # Get D1 chart planet positions
        d1_info, d1_charts, d1_asc_house = h.get_horoscope_information_for_chart(
            chart_index=None, chart_method=1, divisional_chart_factor=1
        )
        
        # Get planet positions for arudha calculations
        planet_positions = charts.divisional_chart(
            h.julian_day, place, divisional_chart_factor=1
        )
        
        # Calculate Bhava Arudhas (A1-A12) - based on Lagna
        bhava_arudhas = bhava_arudhas_from_planet_positions(planet_positions, arudha_base=0)
        
        # Calculate Graha Arudhas (for each planet)
        graha_arudhas = graha_arudhas_from_planet_positions(planet_positions)
        
        # Get rashi names (0-indexed: 0=Aries, 1=Taurus, etc.)
        rashi_names = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                      'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        
        # Format Bhava Arudhas (A1-A12)
        bhava_arudha_data = {}
        for i, rashi in enumerate(bhava_arudhas):
            house_num = i + 1
            rashi_name = rashi_names[rashi]
            bhava_arudha_data[f'A{house_num}'] = {
                'house': house_num,
                'rashi': rashi,
                'rashi_name': rashi_name,
                'description': f'Arudha Lagna for {house_num}{"st" if house_num == 1 else "nd" if house_num == 2 else "rd" if house_num == 3 else "th"} house'
            }
        
        # Format Graha Arudhas
        planet_names = ['Lagna', 'Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']
        graha_arudha_data = {}
        for i, rashi in enumerate(graha_arudhas):
            planet_name = planet_names[i]
            rashi_name = rashi_names[rashi]
            graha_arudha_data[planet_name] = {
                'planet': planet_name,
                'rashi': rashi,
                'rashi_name': rashi_name,
                'description': f'Arudha for {planet_name}'
            }
        
        # Note: d1_asc_house is 1-indexed (1-12), but we need to convert to 0-indexed for rashi lookup
        # Also handle the case where ascendant house might be 0-indexed
        asc_house = d1_asc_house
        if asc_house > 0:  # If it's 1-indexed, convert to 0-indexed for rashi lookup
            asc_rashi_index = asc_house - 1
        else:  # If it's already 0-indexed
            asc_rashi_index = asc_house
            
        asc_rashi_name = rashi_names[asc_rashi_index] if 0 <= asc_rashi_index < 12 else "Unknown"
        
        return {
            "bhava_arudhas": bhava_arudha_data,
            "graha_arudhas": graha_arudha_data,
            "chart_info": {
                "ascendant_house": asc_house,
                "ascendant_rashi": asc_rashi_name
            }
        }
        
    except Exception as e:
        logger.exception(f"An error occurred in get_arudha_lagna_jhora: {e}")
        return {"error": str(e)}

def get_karakamsa_lagna_jhora(
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
    Generates Karakamsa Lagna data using the JHora library for a given birth time and location.
    Karakamsa Lagna is the Navamsa (D9) sign of the Atmakaraka (most important planet).
    Returns a dictionary with Karakamsa Lagna position and related information.
    
    Args:
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        latitude: float
        longitude: float
        timezone_offset: float
        ayanamsa_mode: str (default: 'LAHIRI')
        language: str (default: 'en')
    """
    try:
        from jhora.panchanga.drik import Date, Place
        from jhora.horoscope.main import Horoscope
        from jhora.horoscope.chart import charts
        
        # Prepare date and time
        date_in = Date(year, month, day)
        birth_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        
        # Instantiate Horoscope
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_in,
            birth_time=birth_time,
            ayanamsa_mode=ayanamsa_mode,
            language=language
        )
        
        # Create place object for calculations
        place = Place("BirthPlace", latitude, longitude, timezone_offset)
        
        # Get D1 chart planet positions
        d1_planet_positions = charts.divisional_chart(
            h.julian_day, place, divisional_chart_factor=1
        )
        
        # Get D9 (Navamsa) chart planet positions
        d9_planet_positions = charts.divisional_chart(
            h.julian_day, place, divisional_chart_factor=9
        )
        
        # Find Atmakaraka (planet with highest longitude in D1 chart)
        atmakaraka_index = 0  # Default to Lagna
        max_longitude = 0
        
        for i, planet_data in enumerate(d1_planet_positions):
            if i > 0:  # Skip Lagna, start from Sun
                planet_longitude = planet_data[1][0] * 30 + planet_data[1][1]  # Convert to total degrees
                if planet_longitude > max_longitude:
                    max_longitude = planet_longitude
                    atmakaraka_index = i
        
        # Get Atmakaraka's position in D9 chart
        if atmakaraka_index < len(d9_planet_positions):
            atmakaraka_d9 = d9_planet_positions[atmakaraka_index]
            karakamsa_constellation = atmakaraka_d9[1][0]
            karakamsa_longitude = atmakaraka_d9[1][1]
        else:
            karakamsa_constellation = 0
            karakamsa_longitude = 0
        
        # Get rashi names
        rashi_names = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                      'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        
        # Planet names for Atmakaraka identification
        planet_names = ['Lagna', 'Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']
        
        return {
            "karakamsa_lagna": {
                "constellation": karakamsa_constellation,
                "longitude": karakamsa_longitude,
                "rashi_name": rashi_names[karakamsa_constellation] if 0 <= karakamsa_constellation < 12 else "Unknown",
                "degrees": f"{int(karakamsa_longitude)}°{int((karakamsa_longitude % 1) * 60)}'",
                "description": "Karakamsa Lagna - Navamsa sign of Atmakaraka for life purpose and dharma"
            },
            "atmakaraka": {
                "planet": planet_names[atmakaraka_index] if atmakaraka_index < len(planet_names) else "Unknown",
                "planet_index": atmakaraka_index,
                "d1_longitude": max_longitude,
                "description": "Most important planet (Atmakaraka) based on highest longitude"
            },
            "chart_info": {
                "d1_chart": "Rasi chart (D1) for Atmakaraka identification",
                "d9_chart": "Navamsa chart (D9) for Karakamsa Lagna calculation"
            }
        }
        
    except Exception as e:
        logger.exception(f"An error occurred in get_karakamsa_lagna_jhora: {e}")
        return {"error": str(e)}

def calculate_tithi_for_date(target_date: datetime, latitude: float, longitude: float) -> int:
    """
    Calculate proper Tithi for a given date and location using JHora library.
    
    Args:
        target_date: Target date for calculations
        latitude: Latitude for calculations
        longitude: Longitude for calculations
        
    Returns:
        Tithi number (1-30)
    """
    try:
        from jhora.panchanga import drik
        
        # Convert to IST if not already
        ist = pytz.timezone('Asia/Kolkata')
        if target_date.tzinfo is None:
            target_date_ist = ist.localize(target_date)
        else:
            target_date_ist = target_date.astimezone(ist)
        
        # Calculate timezone offset for the location
        timezone_offset = 5.5  # IST is UTC+5:30
        
        # Create Date and Place objects for JHora
        date_obj = Date(target_date_ist.year, target_date_ist.month, target_date_ist.day)
        place = Place("Location", latitude, longitude, timezone_offset)
        
        # Create Horoscope object to get Julian day
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_obj,
            birth_time=target_date_ist.strftime('%H:%M:%S'),
            ayanamsa_mode='LAHIRI',
            language='en'
        )
        
        # Calculate Tithi using JHora
        tithi_info = drik.tithi(h.julian_day, place)
        tithi_num = tithi_info[0]  # First element is the Tithi number (1-30)
        
        return tithi_num
        
    except Exception as e:
        logger.error(f"Error calculating Tithi for {target_date.date()}: {e}")
        return 1  # Default Tithi

def calculate_lucky_number(birth_date: datetime, tithi: int = None) -> str:
    """
    Calculate lucky number for a given birth date using numerology with Tithi.
    
    Args:
        birth_date: Birth date for calculations
        tithi: Tithi number (1-30) if available
        
    Returns:
        Lucky number as string
    """
    try:
        # Format date as DDMMYYYY
        date_str = birth_date.strftime('%d%m%Y')
        
        # Step 1: List individual digits [D1, D2, M1, M2, Y1, Y2, Y3, Y4]
        digits = [int(digit) for digit in date_str]
        
        # Step 2: Sum1 = sum(digits)
        sum1 = sum(digits)
        
        # Step 3: Reduce1 - iteratively sum digits until result is a single digit (1-9)
        reduce1 = sum1
        while reduce1 > 9:
            reduce1 = sum(int(digit) for digit in str(reduce1))
        
        # Step 4: Tithi_number (use provided tithi or skip this step for now)
        if tithi is not None:
            # Step 5: Sum2 = Reduce1 + Tithi_number
            sum2 = reduce1 + tithi
            # Step 6: Reduce2 - iteratively sum digits until result is a single digit (1-9)
            final_number = sum2
            while final_number > 9:
                final_number = sum(int(digit) for digit in str(final_number))
        else:
            # Skip Tithi addition for now, just use Reduce1
            final_number = reduce1
        
        return str(final_number)
        
    except Exception as e:
        logger.error(f"Error calculating lucky number for {birth_date.date()}: {e}")
        return "7"  # Default lucky number

def calculate_choghadiya(target_date: datetime, latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Calculate Choghadiya periods for a given date and location using JHora's calculations.
    
    Args:
        target_date: Target date for calculations
        latitude: Latitude for sunrise/sunset calculations
        longitude: Longitude for sunrise/sunset calculations
        
    Returns:
        Dictionary containing auspicious and inauspicious time periods
    """
    try:
        from jhora.panchanga import drik
        from jhora.panchanga.drik import Date, Place
        from jhora.horoscope.main import Horoscope
        
        # Get IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        if target_date.tzinfo is None:
            target_date = ist.localize(target_date)
        else:
            target_date = target_date.astimezone(ist)
        
        # Create JHora objects for accurate calculations
        timezone_offset = 5.5  # IST = UTC+5:30
        date_obj = Date(target_date.year, target_date.month, target_date.day)
        place = Place("Location", latitude, longitude, timezone_offset)
        
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_obj,
            birth_time="12:00:00",  # Noon for general calculations
            ayanamsa_mode='LAHIRI',
            language='en'
        )
        
        # Get JHora's sunrise/sunset times
        jhora_sunrise_data = drik.sunrise(h.julian_day, place)
        jhora_sunset_data = drik.sunset(h.julian_day, place)
        jhora_day_length = drik.day_length(h.julian_day, place)
        
        # Extract sunrise time (first element of sunrise data)
        sunrise_hours = jhora_sunrise_data[0] if isinstance(jhora_sunrise_data, list) else jhora_sunrise_data
        sunset_hours = jhora_sunset_data[0] if isinstance(jhora_sunset_data, list) else jhora_sunset_data
        
        # Convert JHora's decimal hours to datetime objects
        # Create a naive datetime for base calculations
        base_date = datetime(target_date.year, target_date.month, target_date.day)
        base_date_ist = ist.localize(base_date)
        
        sunrise_ist = base_date_ist + timedelta(hours=sunrise_hours)
        sunset_ist = base_date_ist + timedelta(hours=sunset_hours)
        
        # Calculate next sunrise for nighttime calculations
        next_day = base_date + timedelta(days=1)
        next_date_obj = Date(next_day.year, next_day.month, next_day.day)
        next_place = Place("Location", latitude, longitude, timezone_offset)
        next_h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=next_date_obj,
            birth_time="12:00:00",
            ayanamsa_mode='LAHIRI',
            language='en'
        )
        next_sunrise_data = drik.sunrise(next_h.julian_day, next_place)
        next_sunrise_hours = next_sunrise_data[0] if isinstance(next_sunrise_data, list) else next_sunrise_data
        next_sunrise_ist = base_date_ist + timedelta(days=1, hours=next_sunrise_hours)
        
        # Get weekday (0=Monday, 6=Sunday)
        weekday = target_date.weekday()
        
        # Define Choghadiya labels based on weekday
        weekday_labels = {
            0: "Amrita",  # Monday
            1: "Roga",    # Tuesday
            2: "Labha",   # Wednesday
            3: "Shubha",  # Thursday
            4: "Chara",   # Friday
            5: "Kala",    # Saturday
            6: "Udvega"   # Sunday
        }
        
        # Fixed 7-label cycle
        choghadiya_cycle = ["Chara", "Labha", "Amrita", "Kala", "Shubha", "Roga", "Udvega"]
        
        # Get starting label for this weekday
        first_label = weekday_labels[weekday]
        
        # Find the starting index in the cycle
        start_index = choghadiya_cycle.index(first_label)
        
        # Generate 16 labels (8 for day + 8 for night)
        labels = []
        for i in range(16):
            cycle_index = (start_index + i) % 7
            labels.append(choghadiya_cycle[cycle_index])
        
        # Calculate time periods
        day_duration = sunset_ist - sunrise_ist
        night_duration = next_sunrise_ist - sunset_ist
        
        day_slot_duration = day_duration / 8
        night_slot_duration = night_duration / 8
        
        # Generate time slots
        day_slots = []
        night_slots = []
        
        # Day slots (8 slots)
        for i in range(8):
            start_time = sunrise_ist + (i * day_slot_duration)
            end_time = sunrise_ist + ((i + 1) * day_slot_duration)
            day_slots.append({
                'start': start_time,
                'end': end_time,
                'label': labels[i],
                'type': 'day'
            })
        
        # Night slots (8 slots)
        for i in range(8):
            start_time = sunset_ist + (i * night_slot_duration)
            end_time = sunset_ist + ((i + 1) * night_slot_duration)
            night_slots.append({
                'start': start_time,
                'end': end_time,
                'label': labels[i + 8],
                'type': 'night'
            })
        
        # Get JHora's inauspicious periods
        rahu_kala = drik.raahu_kaalam(h.julian_day, place)
        yamaganda = drik.yamaganda_kaalam(h.julian_day, place)
        gulika = drik.gulikai_kaalam(h.julian_day, place)
        
        # Try to get Durmuhurtam if available
        try:
            durmuhurtam = drik.durmuhurtam(h.julian_day, place)
        except:
            durmuhurtam = None
        
        # Convert JHora times to datetime for comparison
        def jhora_time_to_datetime(jhora_time, base_date):
            """Convert JHora time format to datetime"""
            if isinstance(jhora_time, list) and len(jhora_time) >= 1:
                hours = jhora_time[0]
                return base_date + timedelta(hours=hours)
            return base_date
        
        rahu_start = jhora_time_to_datetime(rahu_kala[0], base_date_ist)
        rahu_end = jhora_time_to_datetime(rahu_kala[1], base_date_ist)
        yamaganda_start = jhora_time_to_datetime(yamaganda[0], base_date_ist)
        yamaganda_end = jhora_time_to_datetime(yamaganda[1], base_date_ist)
        gulika_start = jhora_time_to_datetime(gulika[0], base_date_ist)
        gulika_end = jhora_time_to_datetime(gulika[1], base_date_ist)
        
        # Enhanced scoring system considering multiple factors
        all_slots = day_slots + night_slots
        scored_slots = []
        
        for slot in all_slots:
            # Base score from Choghadiya label
            base_score = 0
            if slot['label'] == "Amrita":
                base_score = 3      # Most auspicious
            elif slot['label'] == "Shubha":
                base_score = 2      # Very auspicious
            elif slot['label'] == "Labha":
                base_score = 1      # Auspicious
            elif slot['label'] == "Chara":
                base_score = 0      # Neutral
            elif slot['label'] == "Roga":
                base_score = -1     # Inauspicious
            elif slot['label'] == "Udvega":
                base_score = -2     # Very inauspicious
            elif slot['label'] == "Kala":
                base_score = -3     # Most inauspicious
            
            # Penalty for overlapping with inauspicious periods
            penalty = 0
            
            # Check overlap with Rahu Kala
            if (slot['start'] < rahu_end and slot['end'] > rahu_start):
                penalty -= 2
            
            # Check overlap with Yamaganda
            if (slot['start'] < yamaganda_end and slot['end'] > yamaganda_start):
                penalty -= 1
            
            # Check overlap with Gulika
            if (slot['start'] < gulika_end and slot['end'] > gulika_start):
                penalty -= 1
            
            # Final score
            final_score = base_score + penalty
            
            scored_slots.append({
                **slot,
                'base_score': base_score,
                'penalty': penalty,
                'final_score': final_score
            })
        
        # Find best and worst slots
        best_slot = max(scored_slots, key=lambda x: x['final_score'])
        worst_slot = min(scored_slots, key=lambda x: x['final_score'])
        
        # Format times for output
        def format_time_range(start, end):
            start_str = start.strftime('%H:%M IST')
            end_str = end.strftime('%H:%M IST')
            return f"{start_str} - {end_str}"
        
        # Create detailed reasoning
        auspicious_reasoning = f"Most auspicious period: {best_slot['label']} Choghadiya"
        if best_slot['penalty'] < 0:
            auspicious_reasoning += f" (Note: Overlaps with inauspicious period, score reduced by {abs(best_slot['penalty'])})"
        
        inauspicious_reasoning = f"Most inauspicious period: {worst_slot['label']} Choghadiya"
        if worst_slot['penalty'] < 0:
            inauspicious_reasoning += f" (Further worsened by overlap with inauspicious period, additional penalty: {abs(worst_slot['penalty'])})"
        
        return {
            'auspicious_time': format_time_range(best_slot['start'], best_slot['end']),
            'inauspicious_time': format_time_range(worst_slot['start'], worst_slot['end']),
            'auspicious_time_reasoning': auspicious_reasoning,
            'inauspicious_time_reasoning': inauspicious_reasoning,
            'choghadiya_slots': all_slots,
            'inauspicious_periods': {
                'rahu_kala': format_time_range(rahu_start, rahu_end),
                'yamaganda': format_time_range(yamaganda_start, yamaganda_end),
                'gulika': format_time_range(gulika_start, gulika_end),
                'durmuhurtam': durmuhurtam
            },
            'scoring_details': {
                'best_slot_score': best_slot['final_score'],
                'worst_slot_score': worst_slot['final_score'],
                'best_slot_label': best_slot['label'],
                'worst_slot_label': worst_slot['label']
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating Choghadiya for {target_date.date()}: {e}")
        # Return default values if calculation fails
        return {
            'auspicious_time': "06:00 - 08:00 IST",
            'inauspicious_time': "18:00 - 20:00 IST",
            'auspicious_time_reasoning': "Default auspicious time (Choghadiya calculation failed)",
            'inauspicious_time_reasoning': "Default inauspicious time (Choghadiya calculation failed)",
            'choghadiya_slots': [],
            'inauspicious_periods': {},
            'scoring_details': {}
        }


def calculate_birth_chart_moon_sun_signs(
    birth_year: int,
    birth_month: int, 
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_second: int,
    birth_latitude: float,
    birth_longitude: float,
    birth_timezone: str,
    ephe_path: str = '/app/ephe'
) -> Dict[str, Any]:
    """
    Calculate moon and sun signs from birth chart data using Swiss Ephemeris.
    
    This function calculates:
    1. Birth chart moon sign (natal moon sign)
    2. Birth chart sun sign (natal sun sign) 
    3. Current transit moon sign (geocentric)
    4. Current transit sun sign (geocentric)
    
    Args:
        birth_year: Year of birth
        birth_month: Month of birth (1-12)
        birth_day: Day of birth (1-31)
        birth_hour: Hour of birth (0-23)
        birth_minute: Minute of birth (0-59)
        birth_second: Second of birth (0-59)
        birth_latitude: Latitude of birth place (positive for North, negative for South)
        birth_longitude: Longitude of birth place (positive for East, negative for West)
        birth_timezone: Timezone string of birth place (e.g., 'Asia/Kolkata', 'America/New_York')
        ephe_path: Path to ephemeris files
        
    Returns:
        Dictionary containing:
        {
            "birth_chart": {
                "moon_sign": "Cancer",
                "sun_sign": "Leo", 
                "moon_longitude": 95.5,
                "sun_longitude": 125.2,
                "moon_rashi": 4,
                "sun_rashi": 5
            },
            "current_transits": {
                "moon_sign": "Virgo",
                "sun_sign": "Capricorn",
                "moon_longitude": 165.3,
                "sun_longitude": 285.7
            },
            "calculation_details": {
                "birth_julian_day": 2450000.5,
                "current_julian_day": 2460000.5,
                "ayanamsa": "LAHIRI",
                "timezone_used": "Asia/Kolkata",
                "calculation_method": "Swiss Ephemeris with Lahiri Ayanamsa"
            }
        }
        
    Raises:
        ValueError: If birth date/time is invalid
        Exception: If ephemeris calculations fail
    """
    try:
        
        # Set up Swiss Ephemeris
        swe.set_ephe_path(ephe_path)
        swe.set_sid_mode(swe.SIDM_LAHIRI)  # Use Lahiri ayanamsa for Vedic astrology
        
        # Zodiac sign names (0-indexed for calculations)
        zodiac_signs = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]
        
        # 1. CALCULATE BIRTH CHART SIGNS
        
        # Create birth datetime object
        birth_dt = datetime(birth_year, birth_month, birth_day, 
                           birth_hour, birth_minute, birth_second)
        
        # Localize to birth timezone
        birth_tz = pytz.timezone(birth_timezone)
        birth_dt_localized = birth_tz.localize(birth_dt)
        
        # Convert to UTC for Swiss Ephemeris
        birth_dt_utc = birth_dt_localized.astimezone(timezone.utc)
        
        # Calculate Julian Day for birth time
        birth_jd = swe.utc_to_jd(
            birth_dt_utc.year, birth_dt_utc.month, birth_dt_utc.day,
            birth_dt_utc.hour, birth_dt_utc.minute, birth_dt_utc.second, 
            swe.GREG_CAL
        )[1]
        
        # Calculate birth chart planetary positions
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        
        # Moon position at birth
        birth_moon_data = swe.calc_ut(birth_jd, swe.MOON, flags)
        birth_moon_longitude = birth_moon_data[0][0] % 360
        birth_moon_sign_index = int(birth_moon_longitude // 30)
        birth_moon_sign = zodiac_signs[birth_moon_sign_index]
        birth_moon_rashi = birth_moon_sign_index + 1
        
        # Sun position at birth  
        birth_sun_data = swe.calc_ut(birth_jd, swe.SUN, flags)
        birth_sun_longitude = birth_sun_data[0][0] % 360
        birth_sun_sign_index = int(birth_sun_longitude // 30)
        birth_sun_sign = zodiac_signs[birth_sun_sign_index]
        birth_sun_rashi = birth_sun_sign_index + 1
        
        # Ascendant position at birth
        birth_cusps, _ = swe.houses_ex(birth_jd, birth_latitude, birth_longitude, b'P', flags)
        birth_asc_longitude = birth_cusps[0] % 360  # First element is ascendant
        birth_asc_sign_index = int(birth_asc_longitude // 30)
        birth_asc_sign = zodiac_signs[birth_asc_sign_index]
        
        # Ascendant lord mapping
        ascendant_lords = {
            'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury',
            'Cancer': 'Moon', 'Leo': 'Sun', 'Virgo': 'Mercury',
            'Libra': 'Venus', 'Scorpio': 'Mars', 'Sagittarius': 'Jupiter',
            'Capricorn': 'Saturn', 'Aquarius': 'Saturn', 'Pisces': 'Jupiter'
        }
        birth_asc_lord = ascendant_lords.get(birth_asc_sign, 'Unknown')
        
        # 2. CALCULATE CURRENT TRANSIT SIGNS (geocentric - no location needed)
        
        # Get current time in IST (for consistency with existing code)
        ist = pytz.timezone('Asia/Kolkata')
        current_ist = datetime.now(ist)
        
        # Convert IST to UTC for Swiss Ephemeris
        current_utc = current_ist - timedelta(hours=5, minutes=30)
        current_jd = swe.utc_to_jd(
            current_utc.year, current_utc.month, current_utc.day,
            current_utc.hour, current_utc.minute, current_utc.second,
            swe.GREG_CAL
        )[1]
        
        # Current planetary positions (geocentric - no lat/lon needed for basic positions)
        current_moon_data = swe.calc_ut(current_jd, swe.MOON, flags)
        current_moon_longitude = current_moon_data[0][0] % 360
        current_moon_sign_index = int(current_moon_longitude // 30)
        current_moon_sign = zodiac_signs[current_moon_sign_index]
        
        current_sun_data = swe.calc_ut(current_jd, swe.SUN, flags)
        current_sun_longitude = current_sun_data[0][0] % 360
        current_sun_sign_index = int(current_sun_longitude // 30)
        current_sun_sign = zodiac_signs[current_sun_sign_index]
        
        # Calculate current ascendant lord transit
        planet_ids = {
            'Mars': swe.MARS, 'Venus': swe.VENUS, 'Mercury': swe.MERCURY,
            'Moon': swe.MOON, 'Sun': swe.SUN, 'Jupiter': swe.JUPITER,
            'Saturn': swe.SATURN
        }
        
        current_asc_lord_id = planet_ids.get(birth_asc_lord)
        if current_asc_lord_id:
            current_asc_lord_data = swe.calc_ut(current_jd, current_asc_lord_id, flags)
            current_asc_lord_longitude = current_asc_lord_data[0][0] % 360
            current_asc_lord_sign_index = int(current_asc_lord_longitude // 30)
            current_asc_lord_transit = zodiac_signs[current_asc_lord_sign_index]
        else:
            current_asc_lord_transit = "Unknown"
            current_asc_lord_longitude = 0.0
        
        # 3. COMPILE RESULTS
        
        result = {
            "birth_chart": {
                "moon_sign": birth_moon_sign,
                "sun_sign": birth_sun_sign,
                "moon_longitude": round(birth_moon_longitude, 2),
                "sun_longitude": round(birth_sun_longitude, 2),
                "moon_rashi": birth_moon_rashi,
                "sun_rashi": birth_sun_rashi,
                "ascendant": birth_asc_sign,
                "ascendant_lord": birth_asc_lord
            },
            "current_transits": {
                "moon_sign": current_moon_sign,
                "sun_sign": current_sun_sign,
                "moon_longitude": round(current_moon_longitude, 2),
                "sun_longitude": round(current_sun_longitude, 2),
                "ascendant_lord_transit": current_asc_lord_transit,
                "ascendant_lord_longitude": round(current_asc_lord_longitude, 2)
            },
            "calculation_details": {
                "birth_julian_day": round(birth_jd, 6),
                "current_julian_day": round(current_jd, 6),
                "ayanamsa": "LAHIRI",
                "timezone_used": birth_timezone,
                "calculation_method": "Swiss Ephemeris with Lahiri Ayanamsa"
            }
        }
        
        logger.info(f"Successfully calculated moon and sun signs for birth: {birth_year}-{birth_month}-{birth_day} {birth_hour}:{birth_minute}:{birth_second}")
        return result
        
    except Exception as e:
        logger.exception(f"Error calculating moon and sun signs: {str(e)}")
        raise Exception(f"Failed to calculate astrological signs: {str(e)}")





def calculate_moon_sun_signs_from_user_data(
    user_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to calculate moon and sun signs from user data structure.
    
    Args:
        user_data: Dictionary containing user birth information
        
    Returns:
        Same structure as calculate_birth_chart_moon_sun_signs()
    """
    try:
        # Extract birth details from user data
        time_of_birth = user_data.get('time_of_birth')
        city_of_birth = user_data.get('city_of_birth')
        
        if not time_of_birth:
            raise ValueError("time_of_birth is required in user_data")
        
        # Parse birth datetime
        if isinstance(time_of_birth, str):
            # Handle ISO format string
            birth_dt = datetime.fromisoformat(time_of_birth.replace('Z', '+00:00'))
        else:
            birth_dt = time_of_birth
        
        # Extract coordinates from city_of_birth or use defaults
        birth_lat = user_data.get('birth_latitude', 0.0)
        birth_lon = user_data.get('birth_longitude', 0.0)
        birth_tz = user_data.get('birth_timezone', 'Asia/Kolkata')

        return calculate_birth_chart_moon_sun_signs(
            birth_year=birth_dt.year,
            birth_month=birth_dt.month,
            birth_day=birth_dt.day,
            birth_hour=birth_dt.hour,
            birth_minute=birth_dt.minute,
            birth_second=birth_dt.second,
            birth_latitude=birth_lat,
            birth_longitude=birth_lon,
            birth_timezone=birth_tz
        )
        
    except Exception as e:
        logger.exception(f"Error calculating moon and sun signs from user data: {str(e)}")
        raise Exception(f"Failed to calculate moon and sun signs from user data: {str(e)}")

