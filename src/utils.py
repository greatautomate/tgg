
import io
import logging
from typing import Tuple
from PIL import Image

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Image processing utilities."""
    
    SUPPORTED_RATIOS = {
        "1:1": (1, 1), "4:3": (4, 3), "3:4": (3, 4),
        "16:9": (16, 9), "9:16": (9, 16), "21:9": (21, 9),
        "9:21": (9, 21), "3:2": (3, 2), "2:3": (2, 3),
        "7:3": (7, 3), "3:7": (3, 7)
    }
    
    @staticmethod
    def gcd(a: int, b: int) -> int:
        """Calculate Greatest Common Divisor."""
        while b:
            a, b = b, a % b
        return a
    
    @classmethod
    def get_aspect_ratio(cls, image_bytes: bytes) -> str:
        """Calculate optimal aspect ratio from image bytes."""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size
            
            # Calculate GCD to get the simplest ratio
            ratio_gcd = cls.gcd(width, height)
            ratio_width = width // ratio_gcd
            ratio_height = height // ratio_gcd
            
            # Find closest supported ratio
            current_ratio = ratio_width / ratio_height
            closest_ratio = "1:1"
            min_diff = float('inf')
            
            for ratio_str, (r_w, r_h) in cls.SUPPORTED_RATIOS.items():
                target_ratio = r_w / r_h
                diff = abs(current_ratio - target_ratio)
                if diff < min_diff:
                    min_diff = diff
                    closest_ratio = ratio_str
            
            logger.info(
                f"Image processed: {width}x{height} -> "
                f"{ratio_width}:{ratio_height} -> {closest_ratio}"
            )
            return closest_ratio
            
        except Exception as e:
            logger.error(f"Error calculating aspect ratio: {e}")
            return "1:1"
    
    @staticmethod
    def validate_image_size(image_bytes: bytes, max_size_mb: int = 20) -> bool:
        """Validate image size constraints."""
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            logger.warning(f"Image size {size_mb:.2f}MB exceeds limit {max_size_mb}MB")
            return False
        return True

class MessageFormatter:
    """Message formatting utilities."""
    
    @staticmethod
    def format_welcome_message(username: str) -> str:
        """Format welcome message."""
        return f"""
🎨 **AI Image Editor Bot**

Hi {username}!

**Two ways to use:**

**Method 1** (Quick): Send photo with caption
📷➕📝 Attach your edit instruction as photo caption

**Method 2** (Step-by-step):
1. Send me an image
2. Send a text description of how you want to edit it

**Examples:**
• "Change the car color to red"
• "Add sunglasses to the person"  
• "Make the sky sunset colored"
• "Add text 'SALE' to the image"

The bot maintains your image's original aspect ratio!
        """
    
    @staticmethod
    def format_help_message() -> str:
        """Format help message."""
        return """
🔧 **Bot Commands & Usage**

**Commands:**
• `/start` - Start the bot
• `/help` - Show this help message
• `/clear` - Clear current image from memory
• `/status` - Show bot status

**How to edit images:**

**Method 1**: Photo with caption
📷 Send photo with editing instruction as caption

**Method 2**: Step-by-step
1. Send a photo to the bot
2. Send your editing instruction as text
3. Wait for the AI to process your request

**Tips:**
• Be specific in your descriptions
• The bot maintains original aspect ratios
• Processing may take 10-30 seconds
• You can send a new image anytime

**Supported edits:**
• Color changes
• Object modifications  
• Adding/removing elements
• Text overlay
• Style changes
        """

