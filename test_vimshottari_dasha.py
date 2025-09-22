#!/usr/bin/env python3
"""
Simple script to test get_vimshottari_dasha function and output results to a file.
"""

import sys
import os
from datetime import datetime

from app.agents.tools import get_vimshottari_dasha

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))


def test_vimshottari_dasha():
    """Test the get_vimshottari_dasha function with sample data."""
    
    # Sample birth data (you can modify these values)
    birth_year = 1998
    birth_month = 10
    birth_day = 25
    birth_hour = 8
    birth_minute = 30
    birth_second = 0
    utc_offset = "+05:30"  # IST
    latitude = 9.9312  # Chennai
    longitude = 76.2673
    
    # Test parameters
    start_year = 2024
    end_year = 2030
    
    print(f"Testing get_vimshottari_dasha function...")
    print(f"Birth: {birth_year}-{birth_month:02d}-{birth_day:02d} {birth_hour:02d}:{birth_minute:02d}:{birth_second:02d}")
    print(f"Location: {latitude}, {longitude}")
    print(f"Period: {start_year} - {end_year}")
    print("-" * 50)
    
    try:
        # Call the function
        result = get_vimshottari_dasha(
            year=birth_year,
            month=birth_month,
            day=birth_day,
            hour=birth_hour,
            minute=birth_minute,
            second=birth_second,
            utc=utc_offset,
            latitude=latitude,
            longitude=longitude,
            start_year=start_year,
            end_year=end_year
        )
        
        # Check for errors
        if "error" in result:
            print(f"Error: {result['error']}")
            return result
        
        # Print summary to console
        print(f"✅ Successfully calculated vimshottari dasha!")
        print(f"Total dasha periods: {result['period_info']['total_dasha_periods']}")
        print(f"Total bhukti periods: {result['period_info']['total_bhukti_periods']}")
        
        if result['current_dasha']:
            print(f"Current dasha: {result['current_dasha']['dasa_lord']}")
        if result['current_bhukti']:
            print(f"Current bhukti: {result['current_bhukti']['bhukti_lord']}")
        
        return result
        
    except Exception as e:
        error_msg = f"Exception occurred: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}

def save_result_to_file(result, filename="vimshottari_dasha_result.txt"):
    """Save the result to a text file."""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("VIMSHOTTARI DASHA CALCULATION RESULT\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated on: {timestamp}\n\n")
        
        if "error" in result:
            f.write(f"ERROR: {result['error']}\n")
            return
        
        # Write period info
        period_info = result.get('period_info', {})
        f.write("PERIOD INFORMATION:\n")
        f.write(f"Requested start year: {period_info.get('requested_start_year', 'N/A')}\n")
        f.write(f"Requested end year: {period_info.get('requested_end_year', 'N/A')}\n")
        f.write(f"Total dasha periods: {period_info.get('total_dasha_periods', 'N/A')}\n")
        f.write(f"Total bhukti periods: {period_info.get('total_bhukti_periods', 'N/A')}\n\n")
        
        # Write current dasha info
        if result.get('current_dasha'):
            current_dasha = result['current_dasha']
            f.write("CURRENT DASHA:\n")
            f.write(f"Lord: {current_dasha.get('dasa_lord', 'N/A')}\n")
            f.write(f"Start: {current_dasha.get('start', 'N/A')}\n")
            f.write(f"End: {current_dasha.get('end', 'N/A')}\n\n")
        
        # Write current bhukti info
        if result.get('current_bhukti'):
            current_bhukti = result['current_bhukti']
            f.write("CURRENT BHUKTI:\n")
            f.write(f"Lord: {current_bhukti.get('bhukti_lord', 'N/A')}\n")
            f.write(f"Start: {current_bhukti.get('start', 'N/A')}\n")
            f.write(f"End: {current_bhukti.get('end', 'N/A')}\n\n")
        
        # Write all dasha periods
        f.write("ALL DASHA PERIODS:\n")
        f.write("-" * 30 + "\n")
        
        for i, dasha in enumerate(result.get('vimshottari_dasa', []), 1):
            f.write(f"\nDASHA {i}:\n")
            f.write(f"  Lord: {dasha.get('dasa_lord', 'N/A')}\n")
            f.write(f"  Start: {dasha.get('start', 'N/A')}\n")
            f.write(f"  End: {dasha.get('end', 'N/A')}\n")
            
            # Write bhuktis
            bhuktis = dasha.get('bhuktis', [])
            if bhuktis:
                f.write(f"  Bhuktis ({len(bhuktis)}):\n")
                for j, bhukti in enumerate(bhuktis, 1):
                    f.write(f"    {j}. {bhukti.get('bhukti_lord', 'N/A')}: {bhukti.get('start', 'N/A')} to {bhukti.get('end', 'N/A')}\n")
            else:
                f.write("  Bhuktis: None\n")
        
        print(f"✅ Result saved to: {filename}")

def main():
    """Main function to run the test and save results."""
    
    print("🚀 Starting Vimshottari Dasha Test Script\n")
    
    # Test the function
    result = test_vimshottari_dasha()
    
    if result and "error" not in result:
        # Save results to file
        save_result_to_file(result)
        
        # Also save as JSON for easier parsing
        import json
        json_filename = "vimshottari_dasha_result.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"✅ JSON result saved to: {json_filename}")
    
    print("\n🏁 Test script completed!")

if __name__ == "__main__":
    main() 