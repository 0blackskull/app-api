"""
AstrologyAgent implementation using AutoGen with Swarm pattern.
"""
from email import message
from typing import Optional, List
import time
import openai
from datetime import datetime
import pytz
from sqlalchemy.orm import Session

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from app.agents.termination_conditions import MessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from app.agents.prompts import TARA_SYSTEM_PROMPT, TARA_GENZ_STYLE_APPENDIX
from app.agents.tools import get_transits, get_lagnas, get_yogas, get_divisional_chart, get_vimshottari_dasha, get_lat_long, get_timezone
from app.agents.astrology_utils import get_d1_chart_data_jhora, get_today_date_ist
from app.models import User
from app.utils.logger import get_logger
import time
import openai
from app.crud.message import get_last_thread_messages

logger = get_logger(__name__)

class AstrologyAgent:
    """
    AstrologyAgent class that creates and manages a single comprehensive astrology agent
    using AutoGen RoundRobinGroupChat for systematic 5-step astrological analysis.
    
    The agent follows a structured approach:
    1. Data Collection - Fetch all relevant charts, dashas, transits, yogas
    2. Data Analysis - Analyze D1 and relevant divisional charts 
    3. Dasha & Transit Analysis - Evaluate planetary periods and movements
    4. Yoga & Combination Analysis - Identify and interpret astrological combinations
    5. Synthesis & Conclusion - Provide comprehensive guidance and insights
    
    Each step is tracked with status indicators for transparency and completeness.
    
    **Enhanced Features:**
    - **D1 Chart Generation**: Automatically generates D1 charts for the main user and all additional users (friends/partners)
    - **Multi-User Analysis**: When friends are included in chat, provides comprehensive astrological data for all participants
    - **Compatibility Context**: Includes Ashtakoota scores and compatibility data when available
    - **Error Handling**: Gracefully handles missing birth data and chart generation failures
    """

    def __init__(self, user: User, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None, previous_context: str = None, thread_id: str = None, additional_users: List[User] | None = None, ashtakoota_raw: dict | None = None, db: Session = None):
        """
        Initialize the AstrologyAgent with the specified user and model.
        Automatically fetches D1 chart data and previous 3 question-answer pairs for context.
        
        Args:
            user: The User object to use for astrology readings
            model_name: The name of the OpenAI model to use
            api_key: Optional API key. If not provided, will use environment variable
            previous_context: Optional previous conversation context (deprecated, now fetched automatically)
            thread_id: Optional thread ID to fetch conversation context from
            additional_users: Optional list of extra users to include in the context for group questions
            ashtakoota_raw: Optional raw Ashtakoota scores to include in the system context when a participant is present
        """
        model_config = {
            "model": model_name, 
            "temperature": 0.5, 
            "max_tokens": 1000,
            "timeout": 60.0,  # 60 second timeout
            "max_retries": 3   # Built-in retry mechanism
        }

        if api_key:
            model_config["api_key"] = api_key
            
        self.model_client = OpenAIChatCompletionClient(**model_config)
        self.user = user
        self.thread_id = thread_id
        self.additional_users = additional_users or []
        self.ashtakoota_raw = ashtakoota_raw
        self.db = db
        
        # Fetch D1 chart data and previous conversation context
        d1_chart_data = self._get_d1_chart_data()
        previous_conversation = self._get_previous_conversation_context()
        
        # Format user info for the system prompt
        user_info = []
        if getattr(user, 'name', None):
            user_info.append(f"Name: {user.name}")
        if getattr(user, 'city_of_birth', None):
            user_info.append(f"City of Birth: {user.city_of_birth}")
        if getattr(user, 'current_residing_city', None):
            user_info.append(f"Current Residing City: {user.current_residing_city}")
        if getattr(user, 'time_of_birth', None):
            user_info.append(f"Time of Birth: {user.time_of_birth}")
        if getattr(user, 'pronouns', None):
            user_info.append(f"Pronouns: {user.pronouns}")
        user_info_str = "\n".join(user_info)
        
        logger.info(f"get_today_date_ist(): {get_today_date_ist()}")
        logger.info(f"TARA_SYSTEM_PROMPT: {TARA_SYSTEM_PROMPT}")
        logger.info(f"user_info_str: {user_info_str}")
        
        # Build the system message with all context
        base_prompt = TARA_SYSTEM_PROMPT
        if getattr(self.user, 'genz_style_enabled', False):
            base_prompt = f"{TARA_SYSTEM_PROMPT}\n{TARA_GENZ_STYLE_APPENDIX}"

        system_message = f"{base_prompt}\n\nUser Information:\n{user_info_str}"
        
        # Participants block
        if self.additional_users:
            participants_lines = ["\nParticipants (additional users included in this chat):"]
            for p in self.additional_users:
                line_parts = []
                if getattr(p, 'name', None):
                    line_parts.append(f"Name: {p.name}")
                if getattr(p, 'city_of_birth', None):
                    line_parts.append(f"City of Birth: {p.city_of_birth}")
                if getattr(p, 'time_of_birth', None):
                    line_parts.append(f"Time of Birth: {p.time_of_birth}")
                if getattr(p, 'gender', None):
                    line_parts.append(f"Gender: {p.gender}")
                if getattr(p, 'pronouns', None):
                    line_parts.append(f"Pronouns: {p.pronouns}")
                participants_lines.append(" - " + ", ".join(line_parts))
            
            # Add D1 chart data for additional users
            additional_users_d1_data = self._get_additional_users_d1_chart_data()
            if additional_users_d1_data:
                participants_lines.append(additional_users_d1_data)
                logger.info(f"Successfully generated D1 charts for {len(self.additional_users)} additional users")
            else:
                logger.info(f"No D1 charts generated for additional users - missing birth data or generation failed")
            
            participants_lines.append("When participants are present, compare/contrast their situations and provide group-aware recommendations.")
            participants_lines.append("If any participant's birth time or location is missing, state uncertainty and avoid precise timing for that participant.")
            system_message += "\n" + "\n".join(participants_lines)
        
        # Add Ashtakoota raw block if provided
        if isinstance(self.ashtakoota_raw, dict) and 'scores' in self.ashtakoota_raw:
            try:
                scores = self.ashtakoota_raw.get('scores', {})
                total = self.ashtakoota_raw.get('total', None)
                lines = ["\nRaw Ashtakoota Scores (for the participant)"]
                for k in ["Varna","Vashya","Tara","Yoni","Maitri","Gana","Bhakoot","Nadi"]:
                    if k in scores:
                        lines.append(f" - {k}: {scores[k]}")
                if total is not None:
                    lines.append(f"Total: {total} / 36")
                system_message += "\n" + "\n".join(lines)
            except Exception:
                pass
        
        # Add D1 chart data if available
        if d1_chart_data and not d1_chart_data.get('error'):
            d1_chart_str = self._format_d1_chart_data(d1_chart_data)
            system_message += f"\n\nD1 CHART DATA (For High Accuracy Analysis):\n{d1_chart_str}"
        
        # Add previous conversation context if available
        if previous_conversation and not previous_conversation.get('error'):
            context_text = previous_conversation.get('previous_conversation_pairs', '')
            if context_text and context_text != "No previous conversation found.":
                system_message += f"\n\nPrevious Conversation Context (Last 3 Q&A pairs):\n{context_text}"

        logger.info(f"System message: {system_message} {self.additional_users}")

        # Create the comprehensive astrology agent with step tracking
        self.astrology_agent = AssistantAgent(
            name="AstrologyAgent",
            model_client=self.model_client,
            system_message=system_message,
            model_client_stream=True,
            reflect_on_tool_use=False,  # Disabled to prevent streaming reflection errors
            tools=[
                get_transits,
                get_lagnas,
                get_yogas,
                get_divisional_chart,
                get_vimshottari_dasha,
            ],
            description="A comprehensive astrology agent that follows a 5-step analysis process: Data Collection → Analysis → Dasha/Transit → Yoga/Combinations → Synthesis.",
        )

        # Setup the team
        self.team = self._setup_team()

    def _get_d1_chart_data(self) -> dict:
        """Fetch D1 chart data for the user."""
        try:
            if not self.user.time_of_birth or not self.user.city_of_birth:
                logger.warning(f"User {self.user.id} missing birth time or city, cannot generate D1 chart")
                return {"error": "Missing birth time or city information"}
            
            # Parse birth time
            birth_time = self.user.time_of_birth
            year = birth_time.year
            month = birth_time.month
            day = birth_time.day
            hour = birth_time.hour
            minute = birth_time.minute
            second = birth_time.second
            
            # Get coordinates and timezone for birth city
            try:
                latitude, longitude = get_lat_long(self.user.city_of_birth)
                timezone_str = get_timezone(latitude, longitude)
                
                # Convert timezone string to offset hours
                tz = pytz.timezone(timezone_str)
                utc_offset = tz.utcoffset(datetime.now()).total_seconds() / 3600
                
                logger.info(f"Generated coordinates for {self.user.city_of_birth}: lat={latitude}, lon={longitude}, tz={timezone_str}, offset={utc_offset}")
            
            except Exception as e:
                logger.error(f"Error getting coordinates for {self.user.city_of_birth}: {e}")
                return {"error": f"Could not get coordinates for birth city: {self.user.city_of_birth}"}
            
            # Generate D1 chart
            d1_data = get_d1_chart_data_jhora(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=second,
                latitude=latitude,
                longitude=longitude,
                timezone_offset=utc_offset,
                ayanamsa_mode='LAHIRI',
                language='en'
            )
            
            logger.info(f"Successfully generated D1 chart for user {self.user.id}")
            return d1_data
            
        except Exception as e:
            logger.exception(f"Error generating D1 chart for user {self.user.id}: {e}")
            return {"error": str(e)}

    def _get_additional_users_d1_chart_data(self) -> str | None:
        """
        Generates D1 chart data for each additional user (friends/partners) and returns a formatted string.
        
        This method:
        1. Iterates through all additional users in the chat
        2. Validates birth time and city information for each user
        3. Generates D1 charts using JHora library for users with complete birth data
        4. Formats the chart data for inclusion in the system prompt
        5. Provides comprehensive logging for monitoring and debugging
        
        Returns:
            str | None: Formatted D1 chart data string for all valid users, or None if no charts could be generated
            
        Note:
            - Users missing birth time or city information are skipped with appropriate warnings
            - Chart generation failures are logged and included in the output for transparency
            - Only returns data if at least one chart was successfully generated
        """
        if not self.additional_users:
            logger.info("No additional users to generate D1 charts for")
            return None

        logger.info(f"Generating D1 charts for {len(self.additional_users)} additional users")
        d1_data_str = ""
        valid_charts_count = 0
        
        for p in self.additional_users:
            user_name = getattr(p, 'name', f'User_{p.id}')
            logger.info(f"Processing D1 chart for additional user: {user_name} (ID: {p.id})")
            if not p.time_of_birth or not p.city_of_birth:
                logger.warning(f"User {user_name} missing birth time or city, skipping D1 chart generation")
                d1_data_str += f"\n{user_name}: Missing birth time or city information - cannot generate D1 chart."
                continue

            try:
                birth_time = p.time_of_birth
                year = birth_time.year
                month = birth_time.month
                day = birth_time.day
                hour = birth_time.hour
                minute = birth_time.minute
                second = birth_time.second

                # Get coordinates and timezone for birth city
                latitude, longitude = get_lat_long(p.city_of_birth)
                timezone_str = get_timezone(latitude, longitude)
                utc_offset = pytz.timezone(timezone_str).utcoffset(datetime.now()).total_seconds() / 3600

                d1_data = get_d1_chart_data_jhora(
                    year=year,
                    month=month,
                    day=day,
                    hour=hour,
                    minute=minute,
                    second=second,
                    latitude=latitude,
                    longitude=longitude,
                    timezone_offset=utc_offset,
                    ayanamsa_mode='LAHIRI',
                    language='en'
                )
                
                if d1_data and not d1_data.get('error'):
                    logger.info(f"Successfully generated D1 chart for user {user_name}")
                    d1_data_str += f"\n\n{user_name}'s D1 Chart Data:"
                    d1_data_str += "\n" + self._format_d1_chart_data(d1_data)
                    valid_charts_count += 1
                else:
                    logger.error(f"Failed to generate D1 chart for user {user_name}: {d1_data.get('error', 'Unknown error')}")
                    d1_data_str += f"\n\n{user_name}: Error generating D1 chart - {d1_data.get('error', 'Unknown error')}"
                    
            except Exception as e:
                logger.exception(f"Exception while generating D1 chart for user {user_name}: {e}")
                d1_data_str += f"\n\n{user_name}: Error getting coordinates or generating D1 chart - {e}"

        # Only return if we have at least one valid chart
        logger.info(f"D1 chart generation complete: {valid_charts_count} successful out of {len(self.additional_users)} users")
        return d1_data_str if valid_charts_count > 0 else None

    def _get_previous_conversation_context(self) -> dict:
        """Get previous conversation context for context identification."""
        if not self.db or not self.thread_id:
            return {"error": "No database session or thread_id available"}
        
        try:
            messages = get_last_thread_messages(self.db, str(self.thread_id), n=3)  # Get 6 messages (3 Q&A pairs)
            
            if not messages:
                return {"context_text": "No previous conversation found."}
            
            # Format messages into Q&A pairs
            context_pairs = []
            for i in range(0, len(messages)):
                context_pairs.append(f"Q: {messages[i].query}\nA: {messages[i].content}")
            
            context_text = "\n\n".join(context_pairs)
            return {"previous_conversation_pairs": context_text}
            
        except Exception as e:
            logger.exception(f"Error fetching previous conversation context: {e}")
            return {"error": str(e)}

    def _format_d1_chart_data(self, d1_data: dict) -> str:
        """Format D1 chart data for inclusion in system prompt."""
        try:
            if 'error' in d1_data:
                return f"Error generating D1 chart: {d1_data['error']}"
            
            chart_info = d1_data.get('d1_chart_info', {})
            charts = d1_data.get('d1_charts', [])
            asc_house = d1_data.get('d1_ascendant_house', -1)
            
            formatted = []
            
            # Add chart information
            if chart_info:
                formatted.append("Chart Information:")
                for key, value in chart_info.items():
                    formatted.append(f"  {key}: {value}")
            
            # Add chart layout
            if charts:
                formatted.append("\nChart Layout:")
                for i, chart in enumerate(charts):
                    if chart and chart.strip():
                        formatted.append(f"  House {i+1}: {chart.strip()}")
            
            # Add ascendant house
            if asc_house != -1:
                formatted.append(f"\nAscendant House: {asc_house}")
            
            return "\n".join(formatted)
            
        except Exception as e:
            logger.exception(f"Error formatting D1 chart data: {e}")
            return f"Error formatting D1 chart data: {str(e)}"

    def _setup_team(self) -> RoundRobinGroupChat:
        """Set up the RoundRobinGroupChat with a single comprehensive astrology agent."""
        # Create termination condition combining text termination, final-answer close tag, and message limit
        text_termination = TextMentionTermination("TERMINATE")
        max_message_termination = MaxMessageTermination(max_messages=20)
        message_termination = MessageTermination()

        # Combine termination conditions
        combined_termination = (
            text_termination | max_message_termination | message_termination
        )

        # Set up the RoundRobinGroupChat with single agent
        return RoundRobinGroupChat(
            [
                self.astrology_agent,
            ],
            termination_condition=combined_termination,
            max_turns=30,
        )

    def _call_with_backoff(self, func, *args, **kwargs):
        """
        Call a function (e.g., OpenAI API call) with exponential backoff on various API errors.
        If the maximum number of retries is reached, gracefully handle the error by returning a user-friendly
        message or raising a custom exception, instead of raising the raw error.
        """
        max_attempts = 5
        delay = 2
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except (openai.RateLimitError, openai.APIError, openai.APITimeoutError) as e:
                if attempt < max_attempts - 1:
                    error_type = type(e).__name__
                    logger.warning(f"{error_type} hit, retrying in {delay} seconds (attempt {attempt+1}/{max_attempts})...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.exception(f"Max retries reached for {type(e).__name__} error.")
                    raise

    async def close(self):
        """Close the model client connection"""
        await self.model_client.close() 