"""QuBot Constants Module.

This module contains all global constants used throughout the QuBot Discord bot.
These constants include timezone information, color codes, and other configuration
values that need to be consistent across different bot components.

The constants are organized by category and follow Python naming conventions
for module-level constants (UPPER_CASE with underscores).

Example:
    Import and use constants in other modules:

        from utils.constants import ZONE_INFO, COLOR_BLUE

        # Use timezone for datetime operations
        current_time = datetime.now(ZONE_INFO)

        # Use color for Discord embeds
        embed = discord.Embed(color=COLOR_BLUE)

Note:
    - All timezone operations should use ZONE_INFO for consistency
    - Color constants use hexadecimal format compatible with discord.py
    - Add new constants to appropriate sections with proper documentation
"""

from zoneinfo import ZoneInfo

# =============================================================================
# TIMEZONE CONFIGURATION
# =============================================================================

ZONE_INFO: ZoneInfo = ZoneInfo("Europe/Rome")
"""ZoneInfo: Primary timezone for the bot (Europe/Rome).

This constant should be used for all datetime operations that require timezone
awareness, ensuring consistent time handling across all bot features.

Note:
    - Automatically handles daylight saving time transitions
    - Compatible with Python 3.9+ zoneinfo module
    - Replaces deprecated pytz usage
"""

# =============================================================================
# COLOR CONSTANTS
# =============================================================================

COLOR_BLUE: int = 0x4285F4
"""int: Primary blue color used in Discord embeds and UI elements.

This is Google Blue (#4285F4) in hexadecimal format, compatible with
discord.py's color system. Use this for consistent branding across
all bot messages and embeds.

Example:
    embed = discord.Embed(
        title="Information",
        description="Bot response",
        color=COLOR_BLUE
    )
    
Note:
    - Color value is in hexadecimal format (0x prefix)
    - Compatible with discord.py Embed color parameter
    - Maintains consistent visual branding
"""
