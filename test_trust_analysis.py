#!/usr/bin/env python3
"""
Simple test script to verify trust analysis implementation
"""

import asyncio
from app.llm.client import LLMClient

async def test_trust_analysis():
    """Test the trust analysis generation"""
    try:
        # Initialize LLM client
        llm_client = LLMClient()
        
        # Test data
        birth_data = {
            "date": "1990-05-15",
            "time": "14:30",
            "place": "Mumbai, India"
        }
        
        print("Testing trust analysis generation...")
        print(f"Birth data: {birth_data}")
        
        # Generate analysis
        analysis = await llm_client.generate_trust_analysis(birth_data)
        
        print("\nGenerated Analysis:")
        print("=" * 50)
        print(analysis)
        print("=" * 50)
        
        print("\n✅ Trust analysis generation successful!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_trust_analysis())
