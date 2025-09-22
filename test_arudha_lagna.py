#!/usr/bin/env python3
"""
Test script for the Arudha Lagna tool
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.agents.astrology_utils import get_arudha_lagna_jhora

def test_arudha_lagna():
    """Test the arudha lagna function with sample data"""
    
    # Test data for Chennai, India (13.0878°N, 80.2785°E)
    # Date: March 15, 1990, Time: 6:30 AM IST (+5:30)
    test_data = {
        'year': 1990,
        'month': 3,
        'day': 15,
        'hour': 6,
        'minute': 30,
        'second': 0,
        'latitude': 13.0878,
        'longitude': 80.2785,
        'timezone_offset': 5.5,
        'ayanamsa_mode': 'LAHIRI',
        'language': 'en'
    }
    
    print("Testing Arudha Lagna Tool...")
    print(f"Test data: {test_data['year']}-{test_data['month']:02d}-{test_data['day']:02d} "
          f"{test_data['hour']:02d}:{test_data['minute']:02d}:{test_data['second']:02d}")
    print(f"Location: {test_data['latitude']}°N, {test_data['longitude']}°E")
    print(f"Timezone: +{test_data['timezone_offset']} hours")
    print("-" * 50)
    
    try:
        # Call the arudha lagna function
        result = get_arudha_lagna_jhora(**test_data)
        
        if 'error' in result:
            print(f"Error: {result['error']}")
            return False
        
        print("✅ Arudha Lagna calculation successful!")
        print()
        
        # Display Bhava Arudhas (A1-A12)
        print("Bhava Arudhas (A1-A12):")
        print("-" * 30)
        for house_key, house_data in result['bhava_arudhas'].items():
            print(f"{house_key:>3}: {house_data['rashi_name']:>12} (Rashi {house_data['rashi']})")
        print()
        
        # Display Graha Arudhas
        print("Graha Arudhas:")
        print("-" * 30)
        for planet_name, planet_data in result['graha_arudhas'].items():
            print(f"{planet_name:>8}: {planet_data['rashi_name']:>12} (Rashi {planet_data['rashi']})")
        print()
        
        # Display chart info
        print("Chart Information:")
        print("-" * 30)
        chart_info = result['chart_info']
        print(f"Ascendant House: {chart_info['ascendant_house']}")
        print(f"Ascendant Rashi: {chart_info['ascendant_rashi']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_arudha_lagna()
    if success:
        print("\n🎉 Arudha Lagna tool test completed successfully!")
    else:
        print("\n💥 Arudha Lagna tool test failed!")
        sys.exit(1) 