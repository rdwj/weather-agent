"""Elicitation handling for ambiguous locations and missing information."""

import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import re

from ..models.weather_query import Location

logger = logging.getLogger(__name__)


@dataclass
class ElicitationRequest:
    """Request for additional information from user."""
    type: str  # "location", "clarification", "temporal"
    message: str
    options: Optional[List[Any]] = None
    context: Optional[Dict[str, Any]] = None


class LocationElicitor:
    """Handles location elicitation and disambiguation."""

    def __init__(self):
        """Initialize location elicitor."""
        self.common_ambiguous_cities = {
            "Springfield": [
                "Springfield, IL, USA",
                "Springfield, MA, USA",
                "Springfield, MO, USA",
                "Springfield, OH, USA"
            ],
            "Portland": [
                "Portland, OR, USA",
                "Portland, ME, USA"
            ],
            "Columbia": [
                "Columbia, SC, USA",
                "Columbia, MO, USA",
                "Columbia, MD, USA"
            ],
            "Arlington": [
                "Arlington, VA, USA",
                "Arlington, TX, USA"
            ]
        }

    def needs_location_elicitation(self, query: str, context_location: Optional[Location]) -> bool:
        """Check if location elicitation is needed.

        Args:
            query: User query
            context_location: Location from context if available

        Returns:
            True if location needs to be elicited
        """
        # Check if query contains location indicators
        location_patterns = [
            r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\bat\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'weather\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'temperature\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        ]

        query_has_location = False
        for pattern in location_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                query_has_location = True
                break

        # Check for contextual references
        context_references = ["there", "that place", "same location", "that city"]
        has_context_reference = any(ref in query.lower() for ref in context_references)

        # Elicitation needed if:
        # 1. No location in query and no context reference and no context location
        # 2. Query asks "where" questions
        if not query_has_location and not has_context_reference and not context_location:
            return True

        if "where" in query.lower() and "weather" in query.lower():
            return True

        return False

    def extract_location_from_query(self, query: str) -> Optional[str]:
        """Extract potential location from query.

        Args:
            query: User query

        Returns:
            Extracted location string or None
        """
        # Remove common weather terms to avoid false matches
        cleaned_query = query
        weather_terms = ["weather", "temperature", "forecast", "rain", "snow", "sunny", "cloudy"]
        for term in weather_terms:
            cleaned_query = cleaned_query.replace(term, "")

        # Try different patterns
        patterns = [
            r'\bin\s+([A-Za-z\s,]+?)(?:\?|$|\.|\s+weather|\s+today|\s+tomorrow)',
            r'\bat\s+([A-Za-z\s,]+?)(?:\?|$|\.|\s+weather|\s+today|\s+tomorrow)',
            r'\bfor\s+([A-Za-z\s,]+?)(?:\?|$|\.|\s+weather|\s+today|\s+tomorrow)',
            r'([A-Za-z]+(?:\s+[A-Za-z]+)*,\s*[A-Z]{2})',  # City, STATE format
            r'([A-Za-z]+(?:\s+[A-Za-z]+)*,\s*[A-Za-z]+)',  # City, Country format
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned_query, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Clean up the location string
                location = location.rstrip('.,!?')
                if len(location) > 2:  # Avoid single letters
                    return location

        return None

    def is_ambiguous_location(self, location_str: str) -> bool:
        """Check if a location string is ambiguous.

        Args:
            location_str: Location string to check

        Returns:
            True if location is ambiguous
        """
        # Check against known ambiguous cities
        city_name = location_str.split(',')[0].strip().title()
        if city_name in self.common_ambiguous_cities:
            return True

        # Check if it's just a city name without state/country
        if ',' not in location_str and not any(
            suffix in location_str.upper() for suffix in [' USA', ' US', ' UK', ' CA']
        ):
            # Single word locations are often ambiguous
            return True

        return False

    def get_disambiguation_options(self, location_str: str) -> List[str]:
        """Get disambiguation options for an ambiguous location.

        Args:
            location_str: Ambiguous location string

        Returns:
            List of possible location options
        """
        city_name = location_str.split(',')[0].strip().title()

        # Check known ambiguous cities
        if city_name in self.common_ambiguous_cities:
            return self.common_ambiguous_cities[city_name]

        # Generate generic options
        return [
            f"{location_str}, USA",
            f"{location_str}, UK",
            f"{location_str}, Canada",
            f"{location_str}, Australia"
        ]

    def create_elicitation_request(self,
                                  query: str,
                                  context: Optional[Dict[str, Any]] = None) -> ElicitationRequest:
        """Create an elicitation request for missing location.

        Args:
            query: User query
            context: Optional context information

        Returns:
            ElicitationRequest object
        """
        recent_locations = []
        if context and "recent_locations" in context:
            recent_locations = context["recent_locations"]

        if recent_locations:
            message = (
                "I need to know which location you'd like weather information for. "
                f"You recently asked about: {', '.join(recent_locations[:3])}. "
                "Or you can specify a new location."
            )
        else:
            message = (
                "I'd be happy to help with weather information! "
                "Please specify a location (city, state/country, or coordinates)."
            )

        return ElicitationRequest(
            type="location",
            message=message,
            options=recent_locations[:3] if recent_locations else None,
            context=context
        )

    def create_disambiguation_request(self,
                                     location_str: str,
                                     options: Optional[List[str]] = None) -> ElicitationRequest:
        """Create a disambiguation request for ambiguous location.

        Args:
            location_str: Ambiguous location string
            options: Optional list of disambiguation options

        Returns:
            ElicitationRequest object
        """
        if not options:
            options = self.get_disambiguation_options(location_str)

        options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(options)])

        message = (
            f'I found multiple locations matching "{location_str}". '
            f"Please specify which one:\n{options_text}\n\n"
            "Or provide more details like state or country."
        )

        return ElicitationRequest(
            type="clarification",
            message=message,
            options=options,
            context={"original_location": location_str}
        )


class TemporalElicitor:
    """Handles temporal context elicitation."""

    @staticmethod
    def extract_temporal_context(query: str) -> Optional[str]:
        """Extract temporal context from query.

        Args:
            query: User query

        Returns:
            Temporal context string or None
        """
        query_lower = query.lower()

        # Temporal patterns with priority
        temporal_patterns = [
            ("right now", "now"),
            ("currently", "now"),
            ("today", "today"),
            ("tonight", "tonight"),
            ("tomorrow", "tomorrow"),
            ("day after tomorrow", "day_after_tomorrow"),
            ("this week", "this_week"),
            ("next week", "next_week"),
            ("this weekend", "weekend"),
            ("next weekend", "next_weekend"),
            ("next (\d+) days", "next_n_days"),
            ("(\d+) day forecast", "n_day_forecast"),
            ("hourly", "hourly"),
            ("weekly", "weekly")
        ]

        for pattern, temporal_type in temporal_patterns:
            if isinstance(pattern, str) and pattern in query_lower:
                return temporal_type
            elif re.search(pattern, query_lower):
                match = re.search(pattern, query_lower)
                if "n_days" in temporal_type or "n_day" in temporal_type:
                    days = match.group(1)
                    return f"{temporal_type}:{days}"
                return temporal_type

        return None

    @staticmethod
    def needs_temporal_clarification(query: str) -> bool:
        """Check if temporal clarification is needed.

        Args:
            query: User query

        Returns:
            True if temporal context needs clarification
        """
        # Ambiguous temporal references
        ambiguous_terms = [
            "later", "soon", "eventually",
            "sometime", "weather forecast"  # Generic forecast without timeframe
        ]

        query_lower = query.lower()
        has_ambiguous = any(term in query_lower for term in ambiguous_terms)

        # Check if asking for forecast without specific timeframe
        if "forecast" in query_lower and not any(
            term in query_lower for term in ["day", "week", "tomorrow", "hourly"]
        ):
            return True

        return has_ambiguous

    @staticmethod
    def create_temporal_elicitation() -> ElicitationRequest:
        """Create elicitation request for temporal context.

        Returns:
            ElicitationRequest object
        """
        message = (
            "What time period would you like to know about?\n"
            "  • Current conditions\n"
            "  • Today's forecast\n"
            "  • Tomorrow's weather\n"
            "  • 5-day forecast\n"
            "  • This week's forecast"
        )

        return ElicitationRequest(
            type="temporal",
            message=message,
            options=["now", "today", "tomorrow", "5-day", "week"]
        )


class ElicitationManager:
    """Manages all types of elicitation."""

    def __init__(self):
        """Initialize elicitation manager."""
        self.location_elicitor = LocationElicitor()
        self.temporal_elicitor = TemporalElicitor()

    def analyze_query_for_elicitation(self,
                                     query: str,
                                     context: Optional[Dict[str, Any]] = None) -> Optional[ElicitationRequest]:
        """Analyze query to determine if elicitation is needed.

        Args:
            query: User query
            context: Optional context information

        Returns:
            ElicitationRequest if needed, None otherwise
        """
        # Check for location elicitation
        context_location = context.get("location") if context else None
        if self.location_elicitor.needs_location_elicitation(query, context_location):
            return self.location_elicitor.create_elicitation_request(query, context)

        # Check for location disambiguation
        location_str = self.location_elicitor.extract_location_from_query(query)
        if location_str and self.location_elicitor.is_ambiguous_location(location_str):
            return self.location_elicitor.create_disambiguation_request(location_str)

        # Check for temporal clarification
        if self.temporal_elicitor.needs_temporal_clarification(query):
            return self.temporal_elicitor.create_temporal_elicitation()

        return None

    def handle_elicitation_response(self,
                                   response: str,
                                   elicitation: ElicitationRequest) -> Tuple[bool, Dict[str, Any]]:
        """Handle user's response to elicitation.

        Args:
            response: User's response
            elicitation: Original elicitation request

        Returns:
            Tuple of (success, extracted_info)
        """
        result = {"type": elicitation.type}

        if elicitation.type == "location":
            # Extract location from response
            location = self.location_elicitor.extract_location_from_query(response)
            if location:
                result["location"] = location
                return True, result
            else:
                # Check if user selected from options
                if elicitation.options:
                    try:
                        # Check for numeric selection
                        selection = int(response.strip())
                        if 1 <= selection <= len(elicitation.options):
                            result["location"] = elicitation.options[selection - 1]
                            return True, result
                    except ValueError:
                        pass

                    # Check for text match
                    response_lower = response.lower()
                    for option in elicitation.options:
                        if option.lower() in response_lower:
                            result["location"] = option
                            return True, result

        elif elicitation.type == "clarification":
            # Handle disambiguation response
            if elicitation.options:
                try:
                    selection = int(response.strip())
                    if 1 <= selection <= len(elicitation.options):
                        result["location"] = elicitation.options[selection - 1]
                        return True, result
                except ValueError:
                    pass

                # Check for text match or additional details
                location = self.location_elicitor.extract_location_from_query(response)
                if location:
                    result["location"] = location
                    return True, result

        elif elicitation.type == "temporal":
            # Extract temporal context from response
            temporal = self.temporal_elicitor.extract_temporal_context(response)
            if temporal:
                result["temporal"] = temporal
                return True, result

        return False, result