#!/usr/bin/env python3
"""
Enhanced Rahu Kala Test with JHora's Sunrise/Sunset Calculations
This ensures we use the exact same sunrise/sunset times that JHora uses internally
"""

import sys
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Tuple

def test_jhora_sunrise_sunset(target_date: datetime, latitude: float, longitude: float) -> Dict[str, any]:
    """
    Test JHora's sunrise/sunset calculations vs other methods
    """
    
    print(f"🌅 Testing Sunrise/Sunset Calculations")
    print(f"📅 Date: {target_date.strftime('%A, %B %d, %Y')}")
    print(f"📍 Location: {latitude:.4f}°N, {longitude:.4f}°W")
    print("=" * 60)
    
    results = {}
    
    # Method 1: JHora's calculation
    try:
        from jhora.panchanga import drik
        from jhora.panchanga.drik import Date, Place
        from jhora.horoscope.main import Horoscope
        
        # Create JHora objects
        timezone_offset = 5.5  # IST = UTC+5:30
        date_obj = Date(target_date.year, target_date.month, target_date.day)
        place = Place("TestLocation", latitude, longitude, timezone_offset)
        
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_obj,
            birth_time="12:00:00",
            ayanamsa_mode='LAHIRI',
            language='en'
        )
        
        # Get JHora's sunrise/sunset
        jhora_sunrise = drik.sunrise(h.julian_day, place)
        jhora_sunset = drik.sunset(h.julian_day, place)
        jhora_day_length = drik.day_length(h.julian_day, place)
        
        print("✅ JHora Calculations:")
        print(f"   Sunrise: {jhora_sunrise}")
        print(f"   Sunset: {jhora_sunset}")
        print(f"   Day Length: {jhora_day_length:.4f} hours ({jhora_day_length*60:.1f} minutes)")
        
        # Convert to readable time
        def jhora_time_to_readable(time_data):
            if isinstance(time_data, list) and len(time_data) >= 1:
                # JHora returns [time_in_hours, ...]
                hours = time_data[0]
                hour_int = int(hours)
                minute_int = int((hours - hour_int) * 60)
                return f"{hour_int:02d}:{minute_int:02d}"
            return str(time_data)
        
        sunrise_readable = jhora_time_to_readable(jhora_sunrise)
        sunset_readable = jhora_time_to_readable(jhora_sunset)
        
        print(f"   Sunrise (readable): {sunrise_readable} IST")
        print(f"   Sunset (readable): {sunset_readable} IST")
        
        results['jhora'] = {
            'sunrise_raw': jhora_sunrise,
            'sunset_raw': jhora_sunset,
            'sunrise_readable': sunrise_readable,
            'sunset_readable': sunset_readable,
            'day_length': jhora_day_length,
            'julian_day': h.julian_day
        }
        
    except Exception as e:
        print(f"❌ JHora calculation failed: {e}")
        results['jhora'] = {'error': str(e)}
    
    # Method 2: Astral library (what we currently use)
    try:
        from astral import LocationInfo
        from astral.sun import sun
        
        loc = LocationInfo("", "", "UTC", latitude, longitude)
        s = sun(loc.observer, date=target_date.date())
        
        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        astral_sunrise = s["sunrise"].astimezone(ist)
        astral_sunset = s["sunset"].astimezone(ist)
        astral_day_length = (astral_sunset - astral_sunrise).total_seconds() / 3600
        
        print(f"\n✅ Astral Library Calculations:")
        print(f"   Sunrise: {astral_sunrise.strftime('%H:%M:%S IST')}")
        print(f"   Sunset: {astral_sunset.strftime('%H:%M:%S IST')}")
        print(f"   Day Length: {astral_day_length:.4f} hours ({astral_day_length*60:.1f} minutes)")
        
        results['astral'] = {
            'sunrise': astral_sunrise,
            'sunset': astral_sunset,
            'day_length': astral_day_length
        }
        
    except Exception as e:
        print(f"❌ Astral calculation failed: {e}")
        results['astral'] = {'error': str(e)}
    
    # Method 3: Compare differences
    if 'jhora' in results and 'astral' in results and 'error' not in results['jhora'] and 'error' not in results['astral']:
        print(f"\n📊 Comparison:")
        
        # Try to extract actual time from JHora format
        try:
            jhora_sunrise_hours = results['jhora']['sunrise_raw'][0] if isinstance(results['jhora']['sunrise_raw'], list) else results['jhora']['sunrise_raw']
            jhora_sunset_hours = results['jhora']['sunset_raw'][0] if isinstance(results['jhora']['sunset_raw'], list) else results['jhora']['sunset_raw']
            
            # Convert to datetime for comparison
            base_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            ist = pytz.timezone('Asia/Kolkata')
            base_date_ist = ist.localize(base_date)
            
            jhora_sunrise_dt = base_date_ist + timedelta(hours=jhora_sunrise_hours)
            jhora_sunset_dt = base_date_ist + timedelta(hours=jhora_sunset_hours)
            
            # Calculate differences
            sunrise_diff = (results['astral']['sunrise'] - jhora_sunrise_dt).total_seconds() / 60  # minutes
            sunset_diff = (results['astral']['sunset'] - jhora_sunset_dt).total_seconds() / 60    # minutes
            day_length_diff = results['astral']['day_length'] - results['jhora']['day_length']    # hours
            
            print(f"   Sunrise difference: {sunrise_diff:.1f} minutes (Astral - JHora)")
            print(f"   Sunset difference: {sunset_diff:.1f} minutes (Astral - JHora)")
            print(f"   Day length difference: {day_length_diff*60:.1f} minutes")
            
            results['comparison'] = {
                'sunrise_diff_minutes': sunrise_diff,
                'sunset_diff_minutes': sunset_diff,
                'day_length_diff_hours': day_length_diff,
                'jhora_sunrise_dt': jhora_sunrise_dt,
                'jhora_sunset_dt': jhora_sunset_dt
            }
            
        except Exception as e:
            print(f"   ⚠️  Could not compare times: {e}")
    
    return results

def calculate_rahu_kala_with_jhora_times(target_date: datetime, latitude: float, longitude: float) -> Dict[str, any]:
    """
    Calculate Rahu Kala using JHora's exact sunrise/sunset times
    """
    
    print(f"\n🎯 Calculating Rahu Kala with JHora's Sunrise/Sunset")
    print("=" * 60)
    
    try:
        from jhora.panchanga import drik
        from jhora.panchanga.drik import Date, Place
        from jhora.horoscope.main import Horoscope
        
        # Create JHora objects
        timezone_offset = 5.5
        date_obj = Date(target_date.year, target_date.month, target_date.day)
        place = Place("TestLocation", latitude, longitude, timezone_offset)
        
        h = Horoscope(
            latitude=latitude,
            longitude=longitude,
            timezone_offset=timezone_offset,
            date_in=date_obj,
            birth_time="12:00:00",
            ayanamsa_mode='LAHIRI',
            language='en'
        )
        
        print("✅ Using JHora's internal calculations:")
        
        # Method 1: Direct JHora trikalam
        rahu_kala_direct = drik.trikalam(h.julian_day, place, 'raahu kaalam')
        yamaganda_direct = drik.trikalam(h.julian_day, place, 'yamagandam')
        gulika_direct = drik.trikalam(h.julian_day, place, 'gulikai')
        
        print(f"   Rahu Kala (direct): {rahu_kala_direct}")
        print(f"   Yamaganda (direct): {yamaganda_direct}")
        print(f"   Gulika (direct): {gulika_direct}")
        
        # Method 2: Using lambda functions
        rahu_kala_lambda = drik.raahu_kaalam(h.julian_day, place)
        yamaganda_lambda = drik.yamaganda_kaalam(h.julian_day, place)
        gulika_lambda = drik.gulikai_kaalam(h.julian_day, place)
        
        print(f"\n   Rahu Kala (lambda): {rahu_kala_lambda}")
        print(f"   Yamaganda (lambda): {yamaganda_lambda}")
        print(f"   Gulika (lambda): {gulika_lambda}")
        
        # Method 3: Manual calculation using JHora's sunrise/sunset
        sunrise_data = drik.sunrise(h.julian_day, place)
        sunset_data = drik.sunset(h.julian_day, place)
        day_length = drik.day_length(h.julian_day, place)
        weekday = drik.vaara(h.julian_day)
        
        print(f"\n🔧 Manual calculation using JHora's times:")
        print(f"   Sunrise data: {sunrise_data}")
        print(f"   Sunset data: {sunset_data}")
        print(f"   Day length: {day_length:.4f} hours")
        print(f"   Weekday: {weekday} ({['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][weekday]})")
        
        # Extract sunrise time (first element of sunrise data)
        sunrise_hours = sunrise_data[0] if isinstance(sunrise_data, list) else sunrise_data
        
        # JHora's offsets
        rahu_offsets = [0.875, 0.125, 0.75, 0.5, 0.625, 0.375, 0.25]
        yamaganda_offsets = [0.5, 0.375, 0.25, 0.125, 0.0, 0.75, 0.625]
        gulika_offsets = [0.75, 0.625, 0.5, 0.375, 0.25, 0.125, 0.0]
        
        # Calculate manual times
        rahu_start = sunrise_hours + day_length * rahu_offsets[weekday]
        rahu_end = rahu_start + 0.125 * day_length
        
        yamaganda_start = sunrise_hours + day_length * yamaganda_offsets[weekday]
        yamaganda_end = yamaganda_start + 0.125 * day_length
        
        gulika_start = sunrise_hours + day_length * gulika_offsets[weekday]
        gulika_end = gulika_start + 0.125 * day_length
        
        def hours_to_time_string(hours):
            hour_int = int(hours)
            minute_int = int((hours - hour_int) * 60)
            second_int = int(((hours - hour_int) * 60 - minute_int) * 60)
            return f"{hour_int:02d}:{minute_int:02d}:{second_int:02d}"
        
        print(f"\n   Manual Rahu Kala: {hours_to_time_string(rahu_start)} - {hours_to_time_string(rahu_end)}")
        print(f"   Manual Yamaganda: {hours_to_time_string(yamaganda_start)} - {hours_to_time_string(yamaganda_end)}")
        print(f"   Manual Gulika: {hours_to_time_string(gulika_start)} - {hours_to_time_string(gulika_end)}")
        
        # Try Durmuhurtam
        try:
            durmuhurtam = drik.durmuhurtam(h.julian_day, place)
            print(f"\n   Durmuhurtam: {durmuhurtam}")
        except Exception as e:
            print(f"\n   Durmuhurtam failed: {e}")
        
        # Try Gauri Choghadiya
        try:
            gauri_choghadiya = drik.gauri_chogadiya(h.julian_day, place)
            print(f"\n   Gauri Choghadiya: {gauri_choghadiya}")
        except Exception as e:
            print(f"\n   Gauri Choghadiya failed: {e}")
        
        return {
            'success': True,
            'rahu_kala_direct': rahu_kala_direct,
            'yamaganda_direct': yamaganda_direct,
            'gulika_direct': gulika_direct,
            'sunrise_data': sunrise_data,
            'sunset_data': sunset_data,
            'day_length': day_length,
            'weekday': weekday,
            'julian_day': h.julian_day
        }
        
    except Exception as e:
        print(f"❌ JHora calculation failed: {e}")
        return {'success': False, 'error': str(e)}

def compare_with_drik_panchang_exact(results: Dict) -> None:
    """
    Compare with Drik Panchang values for Nov 28, 2025
    """
    
    print(f"\n📊 Comparison with Drik Panchang (Nov 28, 2025):")
    print("=" * 60)
    
    # Expected values from https://www.drikpanchang.com/muhurat/choghadiya.html?date=28/11/2025
    expected = {
        'sunrise': '06:56 AM',
        'sunset': '04:26 PM', 
        'rahu_kala': ('10:30 AM', '11:41 AM'),
        'yamaganda': ('12:52 PM', '02:03 PM'),
        'gulika': ('08:07 AM', '09:18 AM')
    }
    
    print("🎯 Expected from Drik Panchang:")
    print(f"   Sunrise: {expected['sunrise']}")
    print(f"   Sunset: {expected['sunset']}")
    print(f"   Rahu Kala: {expected['rahu_kala'][0]} - {expected['rahu_kala'][1]}")
    print(f"   Yamaganda: {expected['yamaganda'][0]} - {expected['yamaganda'][1]}")
    print(f"   Gulika: {expected['gulika'][0]} - {expected['gulika'][1]}")
    
    if results.get('success'):
        print(f"\n🔍 JHora Results:")
        print(f"   Rahu Kala: {results['rahu_kala_direct']}")
        print(f"   Yamaganda: {results['yamaganda_direct']}")
        print(f"   Gulika: {results['gulika_direct']}")
        
        # Try to parse and compare
        def parse_jhora_time(time_str):
            """Parse JHora's time format to comparable format"""
            if isinstance(time_str, list) and len(time_str) >= 1:
                return str(time_str[0])
            return str(time_str)
        
        rahu_start = parse_jhora_time(results['rahu_kala_direct'][0])
        rahu_end = parse_jhora_time(results['rahu_kala_direct'][1])
        
        print(f"\n📝 Parsed Times:")
        print(f"   Rahu Kala: {rahu_start} - {rahu_end}")

if __name__ == "__main__":
    print("🚀 Enhanced JHora Sunrise/Sunset Test")
    print("Testing accuracy of sunrise/sunset calculations")
    print("=" * 60)
    
    # Test with Drik Panchang example: Nov 28, 2025, Fairfield, CT
    test_date = datetime(2025, 11, 28)
    latitude = 41.1792   # Fairfield, CT
    longitude = -73.2634
    
    # Test sunrise/sunset accuracy
    time_results = test_jhora_sunrise_sunset(test_date, latitude, longitude)
    
    # Calculate Rahu Kala with JHora's times
    rahu_results = calculate_rahu_kala_with_jhora_times(test_date, latitude, longitude)
    
    # Compare with Drik Panchang
    compare_with_drik_panchang_exact(rahu_results)
    
    print("\n" + "=" * 60)
    print("🎯 Key Insights:")
    print("   1. JHora uses its own sunrise/sunset calculations")
    print("   2. These may differ slightly from Astral library")
    print("   3. For accuracy, we should use JHora's times consistently")
    print("   4. JHora's trikalam() gives us exact Rahu Kala periods")
    print("=" * 60)
    
    print("\n📝 Recommendation:")
    print("   ✅ Use JHora's trikalam() function directly")
    print("   ✅ This ensures consistent sunrise/sunset calculations")
    print("   ✅ No need to manually calculate - JHora handles everything")
    print("   ✅ Results should match Drik Panchang more closely")