from pydantic import BaseModel, Field, conint, confloat

class LifeAspects(BaseModel):
    """Schema for daily life aspects ratings with detailed reasoning and remedies."""
    finances: conint(ge=1, le=5) = Field(..., description="Financial outlook for the day (1-5)")
    finances_remedy: str = Field("", description="For rating ≤4: Possible events (20-40 words), and 2-3 non-astrological practical remedies (40-60 words). For rating =5: Positive reasoning (30-40 words) with minimal astrology jargon.")
    physical_health: conint(ge=1, le=5) = Field(..., description="Physical health outlook for the day (1-5)")
    physical_health_remedy: str = Field("", description="For rating ≤4: Possible events (20-40 words), and 2-3 non-astrological practical remedies (40-60 words). For rating =5: Positive reasoning (30-40 words) with minimal astrology jargon.")
    mental_health: conint(ge=1, le=5) = Field(..., description="Mental health outlook for the day (1-5)")
    mental_health_remedy: str = Field("", description="For rating ≤4: Possible events (20-40 words), and 2-3 non-astrological practical remedies (40-60 words). For rating =5: Positive reasoning (30-40 words) with minimal astrology jargon.")
    relationship: conint(ge=1, le=5) = Field(..., description="Relationship outlook for the day (1-5)")
    relationship_remedy: str = Field("", description="For rating ≤4: Possible events (20-40 words), and 2-3 non-astrological practical remedies (40-60 words). For rating =5: Positive reasoning (30-40 words) with minimal astrology jargon.")
    career: conint(ge=1, le=5) = Field(..., description="Career outlook for the day (1-5)")
    career_remedy: str = Field("", description="For rating ≤4: Possible events (20-40 words), and 2-3 non-astrological practical remedies (40-60 words). For rating =5: Positive reasoning (30-40 words) with minimal astrology jargon.")

class WeeklyHoroscope(BaseModel):
    """Schema for weekly astrological horoscope."""
    # Week period information
    week_start_date: str = Field(..., description="Start date of the week (YYYY-MM-DD)")
    week_end_date: str = Field(..., description="End date of the week (YYYY-MM-DD)")
    
    # Weekly horoscope paragraph
    weekly_horoscope: str = Field(..., description="Comprehensive weekly horoscope paragraph describing the astrological influences and predictions for the week")

class DailyFacts(BaseModel):
    """Schema for daily astrological facts."""
    # Basic daily facts
    lucky_color: str = Field(..., description="Lucky color for the day")
    lucky_color_hex: str = Field(..., description="Hex color code for the lucky color")
    lucky_color_reasoning: str = Field(..., description="Reasoning for the lucky color")
    lucky_number: str = Field(..., description="Lucky number for the day")
    moon_transit: str = Field(..., description="Current moon transit (calculated by system)")
    ascendant_lord_transit: str = Field(..., description="Current ascendant sign lord transit (calculated by system)")
    auspicious_time: str = Field(..., description="Most Auspicious time period for the day(start - end time in IST)")
    inauspicious_time: str = Field(..., description="Most Inauspicious time period for the day(start - end time in IST)")
    auspicious_time_reasoning: str = Field(..., description="Reasoning for the auspicious time")
    inauspicious_time_reasoning: str = Field(..., description="Reasoning for the inauspicious time")
    
    # Day rating
    day_rating: conint(ge=1, le=5) = Field(..., description="Overall day rating (1-5, where 1 is very bad and 5 is best)")
    
    # Life aspects ratings
    life_aspects: LifeAspects = Field(..., description="Ratings for different life aspects")
    
    # Astrological signs (provided by system calculations)
    moon_sign: str = Field(..., description="Moon sign from birth chart (calculated by system)")
    ascendant_sign: str = Field(..., description="Current ascendant sign (calculated by system)")
    zodiac_sign: str = Field(..., description="Current zodiac sign (same as sun_sign)")
    sun_sign: str = Field(..., description="Sun sign from birth chart (calculated by system)")
    
    # Do's and Don'ts
    dos: list[str] = Field(..., description="List of dos for the day")
    donts: list[str] = Field(..., description="List of donts for the day")
    advice: str = Field(..., description="Advice for the day, atleast 60 words in markdown format")
    mystical_counsel: str = Field(..., description="Mystical counsel for the day, atmost 10 words in markdown format")

class CompatibilityAspect(BaseModel):
    """Schema for individual compatibility aspects."""
    score: confloat(ge=0, le=8) = Field(..., description="Score for this aspect (can be integer or .5)")
    max_score: int = Field(..., description="Maximum possible score for this aspect")
    comment: str = Field(..., description="Detailed comment about this aspect of compatibility")

class CompatibilityAnalysis(BaseModel):
    """Schema for astrological compatibility analysis between two users."""
    total_score: conint(ge=0, le=36) = Field(..., description="Total compatibility score out of 36")
    max_score: int = Field(36, description="Maximum possible compatibility score (36)")
    overall_match_percentage: confloat(ge=0, le=100) = Field(..., description="Overall compatibility percentage (total_score/36 * 100)")
    is_decent_match: bool = Field(..., description="Whether the match is decent (>=50%)")
    
    # Individual aspects
    personality_match: CompatibilityAspect = Field(..., description="Varna (Personality) compatibility (max 1)")
    attraction_match: CompatibilityAspect = Field(..., description="Vashya (Attraction) compatibility (max 2)")
    health_match: CompatibilityAspect = Field(..., description="Tara (Health) compatibility (max 3)")
    sexual_match: CompatibilityAspect = Field(..., description="Yoni (Sexual) compatibility (max 4)")
    friendship_match: CompatibilityAspect = Field(..., description="Maitri (Friendship) compatibility (max 5)")
    temperament_match: CompatibilityAspect = Field(..., description="Gan (Temperament) compatibility (max 6)")
    emotional_match: CompatibilityAspect = Field(..., description="Bhakut (Emotional) compatibility (max 7)")
    future_generation_match: CompatibilityAspect = Field(..., description="Nadi (Future Generation) compatibility (max 8)")
    
    # Summary
    summary: str = Field(..., description="Overall summary of the compatibility analysis")

class LifeEventDomain(BaseModel):
    """Schema for a single life event domain."""
    domain_name: str = Field(..., description="Name of the life domain (e.g., 'Career & Finance', 'Love & Relationship', 'Health', 'Family', 'Travel')")
    events: str = Field(..., description="Significant life changing events for this domain from the past 5 years")
    astrological_reasoning: str = Field(..., description="Brief astrological reasoning for why this domain was activated")

class LifeEvents(BaseModel):
    """Schema for life events analysis for the past 5 years with adaptive domain discovery."""
    domains: list[LifeEventDomain] = Field(..., description="List of life event domains that were most significantly activated based on astrological analysis")
    analysis_summary: str = Field(..., description="Overall summary of the astrological analysis and why these specific domains were chosen") 

class MultiDayFacts(BaseModel):
    """Schema for daily astrological facts for multiple days."""
    yesterday: DailyFacts = Field(..., description="Yesterday's daily facts")
    today: DailyFacts = Field(..., description="Today's daily facts")
    tomorrow: DailyFacts = Field(..., description="Tomorrow's daily facts")


class RantAnalysis(BaseModel):
    """Schema for rant analysis and therapeutic response."""
    therapist_response: str = Field(..., description="Empathetic, therapeutic response to console the person")
    is_valid_rant: bool = Field(..., description="Whether this is a valid rant/gratitude expression or just random text")
    rant_type: str = Field(..., description="Classification of the content: gratitude, complaint, random, etc.")
    emotional_tone: str = Field(..., description="Analysis of the emotional tone and intensity")
    validation_reasoning: str = Field(..., description="Brief explanation of why the content was classified as valid or invalid") 


class SuggestedQuestions(BaseModel):
    """Schema for suggested follow-up questions based on prior Q/A context."""
    suggested_questions: list[str] = Field(..., description="3 concise, diverse, safe follow-up questions for the user")
