import os
import logging
from typing import Optional

class Config:
    """Configuration class for the Telegram bot."""
    
    # Required environment variables
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    BFL_API_KEY: str = os.environ.get("BFL_API_KEY", "")
    
    # Optional environment variables
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "production")
    
    # BFL.ai API configuration
    BFL_API_URL: str = "https://api.bfl.ai/v1/flux-kontext-pro"
    BFL_TIMEOUT: int = int(os.environ.get("BFL_TIMEOUT", "120"))
    BFL_MAX_POLLS: int = int(os.environ.get("BFL_MAX_POLLS", "60"))
    BFL_POLL_INTERVAL: int = int(os.environ.get("BFL_POLL_INTERVAL", "2"))
    
    # Image processing configuration
    MAX_IMAGE_SIZE_MB: int = int(os.environ.get("MAX_IMAGE_SIZE_MB", "20"))
    DEFAULT_ASPECT_RATIO: str = os.environ.get("DEFAULT_ASPECT_RATIO", "1:1")
    OUTPUT_FORMAT: str = os.environ.get("OUTPUT_FORMAT", "jpeg")
    SAFETY_TOLERANCE: int = int(os.environ.get("SAFETY_TOLERANCE", "2"))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            logging.error("TELEGRAM_BOT_TOKEN environment variable is required")
            return False
        
        if not cls.BFL_API_KEY:
            logging.error("BFL_API_KEY environment variable is required")
            return False
        
        return True
    
    @classmethod
    def setup_logging(cls) -> None:
        """Setup logging configuration."""
        log_level = getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)
        
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=log_level,
            handlers=[
                logging.StreamHandler(),
            ]
        )
        
        # Reduce noise from external libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)


