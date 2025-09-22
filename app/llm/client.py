from typing import Dict, Any, Optional
import openai
from datetime import datetime, timedelta
import pytz
from app.config import settings
from app.llm.schemas import DailyFacts, CompatibilityAnalysis, LifeEvents, MultiDayFacts, RantAnalysis, WeeklyHoroscope, SuggestedQuestions
from app.llm.prompts import get_daily_facts_prompt, get_life_events_prompt, get_weekly_horoscope_prompt, get_suggested_questions_prompt
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.utils.logger import get_logger
from astral import LocationInfo
from astral.sun import sun

logger = get_logger(__name__)

class GooglePlayClient:
    """Client for Google Play Developer API."""
    
    def __init__(self):
        self.credentials = None
        self.service = None
        self._setup_credentials()
    
    def _setup_credentials(self):
        """Setup Google Play API credentials."""
        try:
            # Use explicit Google Play credentials path from settings
            service_account_path = settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON
            
            if not os.path.exists(service_account_path):
                logger.error(f"Google Play service account file not found: {service_account_path}")
                return
            
            # Create credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/androidpublisher']
            )
            
            # Build the service
            self.service = build('androidpublisher', 'v3', credentials=self.credentials)
            logger.info("Google Play API client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup Google Play API client: {e}")
    
    def get_subscription_info(self, package_name: str, purchase_token: str) -> Optional[Dict[str, Any]]:
        """Get subscription information from Google Play."""
        try:
            if not self.service:
                logger.error("Google Play API service not initialized")
                return None
            
            request = self.service.purchases().subscriptionsv2().get(  # type: ignore[attr-defined]
                packageName=package_name,
                token=purchase_token
            )
            response = request.execute()
            logger.info(f"Retrieved subscription info for token: {purchase_token}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get subscription info: {e}")
            return None
    
    def get_product_info(self, package_name: str, product_id: str, purchase_token: str) -> Optional[Dict[str, Any]]:
        """Get one-time product information from Google Play."""
        try:
            if not self.service:
                logger.error("Google Play API service not initialized")
                return None
            
            request = self.service.purchases().products().get(  # type: ignore[attr-defined]
                packageName=package_name,
                productId=product_id,
                token=purchase_token
            )
            response = request.execute()
            logger.info(f"Retrieved product info for token: {purchase_token}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get product info: {e}")
            return None
    
    def acknowledge_subscription(self, package_name: str, subscription_id: str, purchase_token: str) -> bool:
        """Acknowledge a subscription purchase."""
        try:
            if not self.service:
                logger.error("Google Play API service not initialized")
                return False
            
            request = self.service.purchases().subscriptions().acknowledge(  # type: ignore[attr-defined]
                packageName=package_name,
                subscriptionId=subscription_id,
                token=purchase_token,
                body={}
            )
            request.execute()
            logger.info(f"Acknowledged subscription for token: {purchase_token}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to acknowledge subscription: {e}")
            return False
    
    def acknowledge_product(self, package_name: str, product_id: str, purchase_token: str) -> bool:
        """Acknowledge a one-time product purchase."""
        try:
            if not self.service:
                logger.error("Google Play API service not initialized")
                return False
            
            request = self.service.purchases().products().acknowledge(  # type: ignore[attr-defined]
                packageName=package_name,
                productId=product_id,
                token=purchase_token,
                body={}
            )
            request.execute()
            logger.info(f"Acknowledged product for token: {purchase_token}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to acknowledge product: {e}")
            return False

    def cancel_subscription(self, package_name: str, subscription_id: str, purchase_token: str) -> bool:
        """Cancel a subscription (stop auto-renew). Access continues until period end."""
        try:
            if not self.service:
                logger.error("Google Play API service not initialized")
                return False

            request = self.service.purchases().subscriptions().cancel(  # type: ignore[attr-defined]
                packageName=package_name,
                subscriptionId=subscription_id,
                token=purchase_token
            )
            request.execute()
            logger.info(f"Cancelled subscription (auto-renew off) for token: {purchase_token}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}")
            return False

# Create global instance
google_play_client = GooglePlayClient()

class LLMClient:
    def __init__(self):
        """Initialize OpenAI client with API key from settings."""
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)



    async def get_daily_facts(self, user_data: Dict[str, Any], target_date: datetime = None) -> DailyFacts:
        """
        Get daily astrological facts for a user.
        Assumes sunrise and sunset times are already present in user_data if needed.
        
        Args:
            user_data: Dictionary containing user information
            target_date: Optional datetime for specific date (defaults to current date)
        """
        # Get target date and time in IST
        ist = pytz.timezone('Asia/Kolkata')
        if target_date is None:
            target_date = datetime.now(ist)
        else:
            # Ensure target_date is timezone aware
            if target_date.tzinfo is None:
                target_date = ist.localize(target_date)
        
        current_time = target_date.strftime('%Y-%m-%d %H:%M:%S %Z')

        # Get prompt from prompts module
        prompt = get_daily_facts_prompt(user_data, current_time)
        logger.info(f"Prompt: {prompt}")
        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a world-class Vedic astrology assistant with expertise in Panchanga, Muhūrta, transits, remedial astrology."},
                {"role": "user", "content": prompt}
            ],
            response_format=DailyFacts,
            temperature=1
        )

        # If the model refuses to respond, raise an error
        if completion.choices[0].message.refusal:
            raise ValueError(f"Model refused to respond: {completion.choices[0].message.refusal}")

        # Return the parsed DailyFacts object
        return completion.choices[0].message.parsed

    async def get_multi_day_facts(self, user_data: Dict[str, Any], location: Any, ist: Any) -> MultiDayFacts:
        """
        Get daily astrological facts for yesterday, today, and tomorrow.
        
        Args:
            user_data: Dictionary containing user information
            location: Geocoded location for sunrise/sunset calculations
            ist: IST timezone object
            
        Returns:
            MultiDayFacts object containing facts for all three days
        """
        today = datetime.now(ist)
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Generate facts for all three days with proper sunrise/sunset for each day
        yesterday_facts = await self.get_daily_facts_for_date(user_data, yesterday, location, ist)
        today_facts = await self.get_daily_facts_for_date(user_data, today, location, ist)
        tomorrow_facts = await self.get_daily_facts_for_date(user_data, tomorrow, location, ist)
        
        return MultiDayFacts(
            yesterday=yesterday_facts,
            today=today_facts,
            tomorrow=tomorrow_facts
        )

    async def get_daily_facts_for_date(self, user_data: Dict[str, Any], target_date: datetime, location: Any, ist: Any) -> DailyFacts:
        """
        Get daily astrological facts for a specific date with proper sunrise/sunset calculations.
        
        Args:
            user_data: Dictionary containing user information
            target_date: Target date for calculations
            location: Geocoded location for sunrise/sunset calculations
            ist: IST timezone object
            
        Returns:
            DailyFacts object for the specific date
        """
        # Create a copy of user data for this specific date
        date_user_data = user_data.copy()
        
        # Calculate sunrise/sunset for the specific date
        sunrise_str = None
        sunset_str = None
        if location:
            try:
                loc = LocationInfo("", "", "UTC", location.latitude, location.longitude)
                s = sun(loc.observer, date=target_date.date())
                sunrise_ist = s["sunrise"].astimezone(ist)
                sunset_ist = s["sunset"].astimezone(ist)
                sunrise_str = sunrise_ist.strftime('%Y-%m-%d %H:%M:%S %Z')
                sunset_str = sunset_ist.strftime('%Y-%m-%d %H:%M:%S %Z')
            except Exception as e:
                logger.error(f"Error calculating sunrise/sunset for {target_date.date()}: {e}")
        
        date_user_data["sunrise_time"] = sunrise_str
        date_user_data["sunset_time"] = sunset_str
        
        # Add the target date in IST
        date_user_data["today_ist"] = target_date.strftime('%Y-%m-%d')
        
        # Calculate moon and sun signs FIRST (before calling daily facts)
        pre_calculated_signs = None
        try:
            from app.agents.astrology_utils import calculate_moon_sun_signs_from_user_data
            
            # Calculate signs using our accurate function
            signs_data = calculate_moon_sun_signs_from_user_data(user_data)
            
            pre_calculated_signs = {
                "moon_sign": signs_data["birth_chart"]["moon_sign"],
                "sun_sign": signs_data["birth_chart"]["sun_sign"],
                "current_moon_transit": signs_data["current_transits"]["moon_sign"],
                "current_sun_transit": signs_data["current_transits"]["sun_sign"],
                "moon_longitude": signs_data["birth_chart"]["moon_longitude"],
                "sun_longitude": signs_data["birth_chart"]["sun_longitude"],
                "current_moon_longitude": signs_data["current_transits"]["moon_longitude"],
                "current_sun_longitude": signs_data["current_transits"]["sun_longitude"],
                "natal_ascendant": signs_data["birth_chart"]["ascendant"],
                "ascendant_lord": signs_data["birth_chart"]["ascendant_lord"],
                "ascendant_lord_transit": signs_data["current_transits"]["ascendant_lord_transit"]
            }
            
            logger.info(f"Pre-calculated signs for user: Moon={pre_calculated_signs['moon_sign']}, Sun={pre_calculated_signs['sun_sign']}")
            
        except Exception as e:
            logger.exception(f"Error calculating moon and sun signs: {e}")
            # Fallback to basic signs if calculation fails
            pre_calculated_signs = {
                "moon_sign": "Unknown",
                "sun_sign": "Unknown", 
                "current_moon_transit": "Unknown",
                "current_sun_transit": "Unknown",
                "moon_longitude": 0.0,
                "sun_longitude": 0.0,
                "current_moon_longitude": 0.0,
                "current_sun_longitude": 0.0
            }
        
        # Add pre-calculated signs to user data
        date_user_data["pre_calculated_signs"] = pre_calculated_signs
        
        # Add sidereal transits info for the specific date
        transits_info = None
        if location:
            try:
                from app.agents.astrology_utils import get_sidereal_transits_ist
                
                latitude = location.latitude
                longitude = location.longitude
                transits_info = get_sidereal_transits_ist(target_date, latitude, longitude)
            except Exception as e:
                logger.exception(f"Error in get_sidereal_transits_ist for {target_date.date()}:")
        date_user_data["transits_info"] = transits_info
        
        # Calculate Choghadiya periods for auspicious/inauspicious times
        from app.agents.astrology_utils import calculate_choghadiya, calculate_lucky_number, calculate_tithi_for_date
        
        choghadiya_data = calculate_choghadiya(target_date, location.latitude, location.longitude)
        
        # Calculate lucky number based on date of birth (not today's date)
        dob_str = user_data.get('time_of_birth')
        if dob_str:
            try:
                # Parse birth date from user data
                if isinstance(dob_str, str):
                    dob = datetime.fromisoformat(dob_str.replace('Z', '+00:00'))
                else:
                    dob = dob_str
                
                # Calculate Tithi for the target date (needed for lucky number calculation)
                tithi = calculate_tithi_for_date(target_date, location.latitude, location.longitude)
                
                # Calculate lucky number with Tithi
                lucky_number = calculate_lucky_number(dob, tithi=tithi)
            except Exception as e:
                logger.error(f"Error parsing birth date for lucky number: {e}")
                lucky_number = calculate_lucky_number(target_date, tithi=1)  # Fallback to today
        else:
            lucky_number = calculate_lucky_number(target_date, tithi=1)  # Fallback to today
        
        # Get daily facts for this specific date
        daily_facts = await self.get_daily_facts(date_user_data, target_date)
        
        # Override the auspicious/inauspicious times with Choghadiya calculations
        daily_facts.auspicious_time = choghadiya_data['auspicious_time']
        daily_facts.inauspicious_time = choghadiya_data['inauspicious_time']
        daily_facts.auspicious_time_reasoning = choghadiya_data['auspicious_time_reasoning']
        daily_facts.inauspicious_time_reasoning = choghadiya_data['inauspicious_time_reasoning']
        
        # Override the lucky number with calculated value
        daily_facts.lucky_number = lucky_number
        
        # Override moon_transit with our pre-calculated value
        if pre_calculated_signs and pre_calculated_signs.get('current_moon_transit') != 'Unknown':
            daily_facts.moon_transit = pre_calculated_signs['current_moon_transit']
            logger.info(f"Updated moon_transit to: {daily_facts.moon_transit}")
        
        return daily_facts

    async def generate_life_events(self, user_data: Dict[str, Any]) -> LifeEvents:
        """
        Generate last 5 years of significant life events based on astrological data.
        
        Args:
            user_data: Dictionary containing user information including birth data and D1 chart data
            
        Returns:
            LifeEvents object containing generated events and analysis
        """
        # Get current year for 5-year lookback
        current_year = datetime.now().year
        
        # Get prompt from prompts module with D1 chart data for high accuracy
        prompt = get_life_events_prompt(user_data, current_year)
        logger.info(f"Prompt for life events: {prompt}")
        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert Vedic astrologer with deep knowledge of planetary periods, astrological charts, lagnas, yogas, transits, dasha, and life event timing."},
                {"role": "user", "content": prompt}
            ],
            response_format=LifeEvents,
            temperature=0.5,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )

        # If the model refuses to respond, raise an error
        if completion.choices[0].message.refusal:
            raise ValueError(f"Model refused to respond: {completion.choices[0].message.refusal}")

        # Return the parsed LifeEvents object
        return completion.choices[0].message.parsed

    async def get_weekly_horoscope(
        self, 
        user_data: Dict[str, Any], 
        week_start_date: str, 
        week_end_date: str, 
        dasha_data: Dict[str, Any] = None, 
        transit_data: Dict[str, Any] = None,
        moon_movements: Dict[str, Any] = None
    ) -> WeeklyHoroscope:
        """
        Generate weekly horoscope predictions for a user.
        
        Args:
            user_data: Dictionary containing user information
            week_start_date: Start date of the week (YYYY-MM-DD)
            week_end_date: End date of the week (YYYY-MM-DD) 
            dasha_data: Current Dasha period information
            transit_data: Planetary transit information for the week
            moon_movements: Moon's nakshatra movements throughout the week
            
        Returns:
            WeeklyHoroscope object containing weekly predictions
        """
        # Get prompt from prompts module
        prompt = get_weekly_horoscope_prompt(
            user_data, week_start_date, week_end_date, dasha_data, transit_data, moon_movements
        )
        
        logger.info(f"Weekly horoscope prompt for {week_start_date} to {week_end_date}: {prompt}")
        
        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a master Vedic astrologer with deep expertise in Dasha periods, planetary transits, lunar movements, and precise weekly predictions."},
                {"role": "user", "content": prompt}
            ],
            response_format=WeeklyHoroscope,
            temperature=0.7,
        )

        # If the model refuses to respond, raise an error
        if completion.choices[0].message.refusal:
            raise ValueError(f"Model refused to respond: {completion.choices[0].message.refusal}")

        # Return the parsed WeeklyHoroscope object
        return completion.choices[0].message.parsed

    async def analyze_compatibility(self, analysis_data: Dict[str, Any], person1_name: str, person2_name: str, person1_details: Dict[str, Any], person2_details: Dict[str, Any], person1_gender: str = None, person2_gender: str = None, compatibility_type: str = "love") -> CompatibilityAnalysis:
        """
        Infers and structures compatibility analysis from pre-computed Ashtakoota data.
        
        Args:
            analysis_data: Dictionary containing the raw Ashtakoota compatibility scores and details.
            person1_name: Name of the first person.
            person2_name: Name of the second person.
            remedies_info: String containing information about astrological remedies from web search.
            person1_details: Vedic details for person 1 (nakshatra, pada, rashi).
            person2_details: Vedic details for person 2 (nakshatra, pada, rashi).
            person1_gender: Gender of the first person ('male', 'female', 'other', or None).
            person2_gender: Gender of the second person ('male', 'female', 'other', or None).
            compatibility_type: One of "love", "friendship", "homo-love".
            
        Returns:
            CompatibilityAnalysis object.
        """
        # Determine the traditional roles for compatibility analysis based on gender
        if person1_gender == 'male' and person2_gender == 'female':
            boy_name = person1_name
            girl_name = person2_name
            boy_details = person1_details
            girl_details = person2_details
        elif person1_gender == 'female' and person2_gender == 'male':
            boy_name = person2_name
            girl_name = person1_name
            boy_details = person2_details
            girl_details = person1_details
        else:
            # Same gender or gender not specified: use person1 as A, person2 as B
            boy_name = person1_name
            girl_name = person2_name
            boy_details = person1_details
            girl_details = person2_details
        
        use_neutral_labels = (compatibility_type != "love") or (person1_gender == person2_gender and person1_gender is not None)
        label_boy = "Person A" if use_neutral_labels else "Boy"
        label_girl = "Person B" if use_neutral_labels else "Girl"
        
        prompt = f"""
        Based on the following raw Ashtakoota compatibility data for {boy_name} ({label_boy}) and {girl_name} ({label_girl}), generate a complete and structured analysis.
        You must infer the overall summary and format the final output according to the `CompatibilityAnalysis` schema.

        Compatibility type: {compatibility_type}
        - If type is "friendship": emphasize companionship, emotional resonance, communication, and long-term support. De-emphasize purely romantic/sexual and future-generation aspects in the narrative.
        - If type is "friendship": treat the sexual aspect (Yoni) as not applicable; instead discuss emotional closeness using Bhakoot/Maitri language. Do not include sexual content.
        - If type is "homo-love": use inclusive, non-gendered language; do not assume traditional boy/girl roles.

        Gender Information:
        - {label_boy}: {boy_name} ({person1_gender if boy_name == person1_name else person2_gender})
        - {label_girl}: {girl_name} ({person2_gender if girl_name == person2_name else person1_gender})

        Follow the below instructions:
        - If any compatibility scores are low, suggest detailed remedies. 
        - Give an explanation for why the score is low.
        - Give a detailed explanation for both. 
        - Remedies should also include non-astrological remedies eg. "schedule a heart-to-heart conversation" 
        - Explanation should also be in non-astrological terms.
        
        Astrological Details:
        - {boy_name} ({label_boy}): {boy_details}
        - {girl_name} ({label_girl}): {girl_details}

        Raw Data for {boy_name} and {girl_name}:
        {analysis_data}
        """

        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """
                  You are an expert Vedic astrologer with specialisation in compatibility analysis. 
                  You will be given raw Ashtakoota compatibility data. 
                  Your task is to format this data into the required JSON schema and provide an insightful summary based on the scores. 
                  Incase score is low for some parameters, suggest remedies using astrological principles.
                 """},
                {"role": "user", "content": prompt}
            ],
            response_format=CompatibilityAnalysis
        )

        if completion.choices[0].message.refusal:
            raise ValueError(f"Model refused to respond: {completion.choices[0].message.refusal}")

        return completion.choices[0].message.parsed 

    async def generate_suggested_questions(self, previous_query: str, previous_answer: str, max_items: int = 5) -> SuggestedQuestions:
        """
        Generate suggested follow-up questions based on the previous query and the assistant's answer.
        """
        prompt = get_suggested_questions_prompt(previous_query, previous_answer, max_items)

        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful Vedic astrology assistant that suggests next questions to deepen the conversation, based on the previous query and the assistant's answer."},
                {"role": "user", "content": prompt}
            ],
            response_format=SuggestedQuestions,
            temperature=0.7,
        )

        if completion.choices[0].message.refusal:
            raise ValueError(f"Model refused to respond: {completion.choices[0].message.refusal}")

        return completion.choices[0].message.parsed

    async def analyze_rant(self, rant_content: str, user_name: str = "there") -> RantAnalysis:
        """
        Analyze rant content and provide therapeutic response.
        
        Args:
            rant_content: The user's rant or expression text
            user_name: The user's name for personalization (defaults to "there")
            
        Returns:
            RantAnalysis object with therapist response and validation
        """
        prompt = f"""
        Analyze the following user content and provide a therapeutic response.
        
        User: {user_name}
        User Content: "{rant_content}"
        
        Your task is to:
        1. Provide an empathetic, therapeutic response to console {user_name}
        2. Determine if this is a valid rant/gratitude expression or just random text
        3. Classify the type of content (gratitude, complaint, random, etc.)
        4. Analyze the emotional tone and intensity
        5. Explain your validation reasoning
        
        Guidelines:
        - Address {user_name} personally and warmly
        - Valid rants: Express genuine emotions, gratitude, complaints, or meaningful thoughts
        - Invalid content: Random text, gibberish, or content that doesn't express real feelings
        - Be empathetic and supportive in your response
        - Provide constructive advice when appropriate
        - Consider cultural and emotional context
        - Make the response feel personal and directed to {user_name}
        - In the end always mention, if you want a deeper conversation and understand why this is happening or how to come out of this loop, you can talk to me on chat page.
        - Keep it less than 100 words.
        """
        
        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a compassionate, empathetic therapist who helps people process their emotions and experiences. You provide supportive, therapeutic responses while being able to distinguish between genuine emotional expression and random text."},
                {"role": "user", "content": prompt}
            ],
            response_format=RantAnalysis,
            temperature=0.7,
        )
        
        if completion.choices[0].message.refusal:
            raise ValueError(f"Model refused to respond: {completion.choices[0].message.refusal}")
        
        return completion.choices[0].message.parsed 

    async def generate_trust_analysis(self, birth_data: dict) -> str:
        """
        Generate comprehensive trust and nature analysis based on advanced astrological data
        
        Args:
            birth_data: Dictionary containing user birth information with keys:
                - date: Birth date (YYYY-MM-DD)
                - time: Birth time (HH:MM)  
                - place: Birth place
                - latitude: Birth latitude
                - longitude: Birth longitude
                - timezone_offset: Timezone offset in hours
            
        Returns:
            String containing the enhanced trust and behavior analysis
        """
        try:
            # Import tools from agents
            from app.agents.tools import get_divisional_chart, get_vimshottari_dasha, get_ashtakavarga, get_shadbala, get_lat_long, get_timezone
            
            # Parse birth data
            birth_date = birth_data.get('date', 'N/A')
            birth_time = birth_data.get('time', 'N/A')
            birth_place = birth_data.get('place', 'N/A')
            
            # Extract date/time components for calculations
            if birth_date != 'N/A' and birth_time != 'N/A':
                try:
                    birth_dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
                    
                    # Get location data
                    latitude = birth_data.get('latitude')
                    longitude = birth_data.get('longitude')
                    timezone_offset = birth_data.get('timezone_offset', 5.5)  # Default to IST
                    
                    # Convert timezone to numeric if it's a string
                    if isinstance(timezone_offset, str):
                        # Handle timezone strings like "Asia/Kolkata" -> 5.5
                        if 'kolkata' in timezone_offset.lower() or 'india' in timezone_offset.lower():
                            timezone_offset = 5.5
                        elif 'utc' in timezone_offset.lower():
                            timezone_offset = 0.0
                        else:
                            # Try to extract numeric value from string like "+05:30"
                            try:
                                if '+' in timezone_offset or '-' in timezone_offset:
                                    # Parse "+05:30" format
                                    sign = 1 if timezone_offset.startswith('+') else -1
                                    time_part = timezone_offset[1:]
                                    if ':' in time_part:
                                        hours, minutes = time_part.split(':')
                                        timezone_offset = sign * (int(hours) + int(minutes) / 60.0)
                                    else:
                                        timezone_offset = sign * float(time_part)
                                else:
                                    timezone_offset = 5.5  # Default fallback
                            except:
                                timezone_offset = 5.5  # Default fallback
                    
                    # Ensure latitude and longitude are numeric
                    try:
                        latitude = float(latitude) if latitude is not None else None
                        longitude = float(longitude) if longitude is not None else None
                    except (ValueError, TypeError):
                        latitude = None
                        longitude = None
                    
                    if not latitude or not longitude:
                        # Try to get lat/long from place name
                        if birth_place != 'N/A':
                            lat, lon = get_lat_long(birth_place)
                            latitude = float(lat) if lat else 0.0
                            longitude = float(lon) if lon else 0.0
                            # Get timezone as numeric value
                            tz = get_timezone(latitude, longitude) if lat and lon else 5.5
                            if isinstance(tz, (int, float)):
                                timezone_offset = float(tz)
                            else:
                                timezone_offset = 5.5
                    
                    # Generate comprehensive astrological data for 90-95% accuracy
                    logger.info(f"Generating comprehensive astrological data for trust analysis...")
                    logger.info(f"Birth data parsed - Date: {birth_dt}, Lat: {latitude} ({type(latitude)}), Lon: {longitude} ({type(longitude)}), TZ: {timezone_offset} ({type(timezone_offset)})")
                    
                    # 1. Get D1, D9, D10 charts (Essential for personality)
                    d1_chart = get_divisional_chart('d1', birth_dt.year, birth_dt.month, birth_dt.day, 
                                                   birth_dt.hour, birth_dt.minute, 0, 
                                                   latitude, longitude, timezone_offset)
                    
                    d9_chart = get_divisional_chart('d9', birth_dt.year, birth_dt.month, birth_dt.day, 
                                                   birth_dt.hour, birth_dt.minute, 0, 
                                                   latitude, longitude, timezone_offset)
                    
                    d10_chart = get_divisional_chart('d10', birth_dt.year, birth_dt.month, birth_dt.day, 
                                                    birth_dt.hour, birth_dt.minute, 0, 
                                                    latitude, longitude, timezone_offset)
                    
                    # 2. Get Vimshottari Dasha (Current life period)
                    current_year = datetime.now().year
                    # Convert numeric timezone to string format for Vimshottari Dasha
                    if timezone_offset >= 0:
                        hours = int(timezone_offset)
                        minutes = int((timezone_offset - hours) * 60)
                        timezone_str = f"+{hours:02d}:{minutes:02d}"
                    else:
                        hours = int(abs(timezone_offset))
                        minutes = int((abs(timezone_offset) - hours) * 60)
                        timezone_str = f"-{hours:02d}:{minutes:02d}"
                    
                    vimshottari_dasha = get_vimshottari_dasha(birth_dt.year, birth_dt.month, birth_dt.day, 
                                                             birth_dt.hour, birth_dt.minute, 0, 
                                                             timezone_str, latitude, longitude,
                                                             start_year=current_year-2, end_year=current_year+5)
                    
                    # 3. Get Ashtakavarga (Planetary strengths)
                    ashtakavarga = get_ashtakavarga(birth_dt.year, birth_dt.month, birth_dt.day, 
                                                   birth_dt.hour, birth_dt.minute, 0, 
                                                   latitude, longitude, timezone_offset)
                    
                    # 4. Get Shadbala (6-fold planetary strength)
                    shadbala = get_shadbala(birth_dt.year, birth_dt.month, birth_dt.day, 
                                           birth_dt.hour, birth_dt.minute, 0, 
                                           latitude, longitude, timezone_offset)
                    
                    # Create comprehensive prompt with all astrological data
                    prompt = f"""
                    Based on comprehensive Vedic astrological analysis, generate a detailed personality and trust analysis:

                    **Birth Details:** {birth_date} at {birth_time} in {birth_place}
                    
                    **D1 Chart (Basic Nature & Personality):**
                    {d1_chart.get('charts', 'Data unavailable') if not d1_chart.get('error') else 'Chart calculation failed'}
                    
                    **D9 Chart (Marriage, Relationships & Deep Personality):**
                    {d9_chart.get('charts', 'Data unavailable') if not d9_chart.get('error') else 'Chart calculation failed'}
                    
                    **D10 Chart (Career & Professional Traits):**
                    {d10_chart.get('charts', 'Data unavailable') if not d10_chart.get('error') else 'Chart calculation failed'}
                    
                    **Current Dasha Period (Life Phase Influences):**
                    Current Dasha: {vimshottari_dasha.get('current_dasha', {}).get('dasa_lord', 'Unknown')}
                    Current Bhukti: {vimshottari_dasha.get('current_bhukti', {}).get('bhukti_lord', 'Unknown')}
                    
                    **Ashtakavarga Strengths (Planetary Power Analysis):**
                    {ashtakavarga.get('planetary_strengths', 'Data unavailable') if not ashtakavarga.get('error') else 'Strength analysis failed'}
                    
                    **Shadbala Analysis (6-fold Planetary Strength):**
                    Strongest Planet: {shadbala.get('strongest_planet', 'Unknown')}
                    Weakest Planet: {shadbala.get('weakest_planet', 'Unknown')}
                    
                    **Analysis Focus:**
                    - Natural behavioral tendencies and core personality traits
                    - Thought process and decision making patterns
                    - Habits
                    - Strengths and weaknesses
                    
                    **Output Requirements:**
                    - Proper Markdown formatting with headers and bullet points
                    - Bold and italic text for emphasis
                    - Personal, warm, and insightful tone
                    - Keep analysis concise but comprehensive (80-100 words)
                    - Make it actionable and self-awareness focused
                    - Don't include any astrological reasoning in the output.
                    
                    Provide a personality analysis that helps the person understand their authentic self through the lens of advanced Vedic astrology.
                    """
                    
                except Exception as e:
                    logger.error(f"Error parsing birth data for enhanced analysis: {e}")
                    # Fallback to basic analysis
                    prompt = f"""
                    Based on basic astrological data, generate a personality and trust analysis:

                    Birth Details: {birth_date} at {birth_time} in {birth_place}
                    
                    Focus on general personality traits, trust patterns, and behavioral tendencies.
                    Use Markdown formatting and keep it engaging and personal (80-100 words).
                    """
            else:
                # Fallback for incomplete birth data
                prompt = f"""
                Based on available birth information, provide a general personality analysis:
                
                Birth Details: {birth_data}
                
                Focus on general traits and provide guidance for better self-understanding.
                Use Markdown formatting and keep it warm and insightful (80-100 words).
                """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a master Vedic astrologer specializing in comprehensive personality analysis using advanced techniques like divisional charts, Ashtakavarga, Shadbala, and Dasha periods. You provide profound insights that help people understand their authentic nature and behavioral patterns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.exception("Error in enhanced generate_trust_analysis:", exc_info=e)
            # Fallback to basic analysis
            basic_prompt = f"""
            Based on birth information, provide a warm personality analysis:
            
            Birth Details: {birth_data.get('date', 'N/A')} at {birth_data.get('time', 'N/A')} in {birth_data.get('place', 'N/A')}
            
            Focus on personality traits, strengths, and areas for growth.
            Use Markdown formatting and keep it personal and engaging (80-100 words).
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert personality analyst providing insightful and warm personality assessments."},
                    {"role": "user", "content": basic_prompt}
                ],
                temperature=0.7,
                max_tokens=250
            )
            
            return response.choices[0].message.content 
