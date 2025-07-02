import asyncio
import base64
import io
import logging
import time
from typing import Optional

import requests
from telegram import Update, ForceReply
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)

from config import Config
from utils import ImageProcessor, MessageFormatter

# Setup configuration and logging
Config.setup_logging()
logger = logging.getLogger(__name__)

# Validate configuration
if not Config.validate():
    exit(1)

class BFLImageEditor:
    """BFL.ai API client for image editing."""
    
    def __init__(self):
        self.api_url = Config.BFL_API_URL
        self.api_key = Config.BFL_API_KEY
        self.timeout = Config.BFL_TIMEOUT
        self.max_polls = Config.BFL_MAX_POLLS
        self.poll_interval = Config.BFL_POLL_INTERVAL
    
    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "accept": "application/json",
            "x-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def edit_image(self, image_base64: str, prompt: str, aspect_ratio: str) -> Optional[bytes]:
        """Edit image using BFL.ai API."""
        try:
            # Create editing request
            payload = {
                "prompt": prompt,
                "input_image": image_base64,
                "aspect_ratio": aspect_ratio,
                "output_format": Config.OUTPUT_FORMAT,
                "safety_tolerance": Config.SAFETY_TOLERANCE
            }
            
            logger.info(f"Starting image edit request with prompt: {prompt[:50]}...")
            
            response = requests.post(
                self.api_url, 
                headers=self._get_headers(), 
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            response_data = response.json()
            polling_url = response_data.get("polling_url")
            request_id = response_data.get("id")
            
            if not polling_url:
                logger.error(f"No polling URL received: {response_data}")
                return None
            
            logger.info(f"Request {request_id} created, polling for result...")
            
            # Poll for result
            return await self._poll_for_result(polling_url, request_id)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in edit_image: {e}")
            return None
    
    async def _poll_for_result(self, polling_url: str, request_id: str) -> Optional[bytes]:
        """Poll for editing result."""
        for poll_count in range(1, self.max_polls + 1):
            try:
                await asyncio.sleep(self.poll_interval)
                
                result_response = requests.get(
                    polling_url, 
                    headers=self._get_headers(),
                    timeout=30
                )
                result_response.raise_for_status()
                result_data = result_response.json()
                
                status = result_data.get("status")
                logger.debug(f"Poll #{poll_count} for {request_id}: {status}")
                
                if status == "Ready":
                    edited_image_url = result_data.get("result", {}).get("sample")
                    if edited_image_url:
                        # Download the edited image
                        image_response = requests.get(edited_image_url, timeout=30)
                        image_response.raise_for_status()
                        logger.info(f"Successfully retrieved edited image for {request_id}")
                        return image_response.content
                    else:
                        logger.error(f"No image URL in ready response for {request_id}")
                        return None
                        
                elif status in ["Error", "Failed"]:
                    error_msg = result_data.get("failure_reason", "Unknown error")
                    logger.error(f"Request {request_id} failed: {error_msg}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Polling error for {request_id}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected polling error for {request_id}: {e}")
                continue
        
        logger.error(f"Request {request_id} timed out after {self.max_polls} polls")
        return None

class TelegramBot:
    """Main Telegram bot class."""
    
    def __init__(self):
        self.bfl_editor = BFLImageEditor()
        self.image_processor = ImageProcessor()
        self.formatter = MessageFormatter()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        welcome_msg = self.formatter.format_welcome_message(user.mention_html())
        
        await update.message.reply_html(
            welcome_msg,
            reply_markup=ForceReply(selective=True)
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_msg = self.formatter.format_help_message()
        await update.message.reply_text(help_msg)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        status_msg = f"""
🤖 **Bot Status**

✅ Bot is running
🔧 Environment: {Config.ENVIRONMENT}
📊 Max image size: {Config.MAX_IMAGE_SIZE_MB}MB
⏱️ API timeout: {Config.BFL_TIMEOUT}s
🎯 Default aspect ratio: {Config.DEFAULT_ASPECT_RATIO}
        """
        await update.message.reply_text(status_msg)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command."""
        if "photo" in context.user_data:
            context.user_data.clear()
            await update.message.reply_text("✅ Image cleared! Send a new image to start editing.")
        else:
            await update.message.reply_text("No image to clear. Send an image first!")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages."""
        try:
            if not update.message.photo:
                await update.message.reply_text("❌ Please send a photo.")
                return
            
            # Get caption if present
            caption = update.message.caption
            
            processing_msg = await update.message.reply_text("📥 Processing your image...")
            
            # Download photo
            photo_file = await update.message.photo[-1].get_file()
            photo_bytes = await photo_file.download_as_bytes()
            
            # Validate image size
            if not self.image_processor.validate_image_size(photo_bytes, Config.MAX_IMAGE_SIZE_MB):
                await processing_msg.edit_text(
                    f"❌ Image too large. Maximum size is {Config.MAX_IMAGE_SIZE_MB}MB."
                )
                return
            
            # Calculate aspect ratio
            aspect_ratio = self.image_processor.get_aspect_ratio(photo_bytes)
            
            # Store photo data
            context.user_data["photo"] = base64.b64encode(photo_bytes).decode("utf-8")
            context.user_data["aspect_ratio"] = aspect_ratio
            
            if caption and caption.strip():
                # Process immediately with caption
                await processing_msg.edit_text(
                    f"✅ Image received with caption!\n"
                    f"📐 Aspect ratio: {aspect_ratio}\n"
                    f"📝 Prompt: \"{caption}\"\n\n"
                    f"🎨 Starting edit..."
                )
                await self._process_edit(update, context, caption.strip(), processing_msg)
            else:
                # Wait for text prompt
                await processing_msg.edit_text(
                    f"✅ Image received!\n"
                    f"📐 Detected aspect ratio: {aspect_ratio}\n\n"
                    f"💬 Now send me your editing instructions!"
                )
                
        except Exception as e:
            logger.error(f"Error handling photo: {e}")
            await update.message.reply_text("❌ Error processing image. Please try again.")
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        if "photo" not in context.user_data:
            await update.message.reply_text(
                "📷 Please send a photo first!\nUse /start to see how to use the bot."
            )
            return
        
        prompt = update.message.text
        processing_msg = await update.message.reply_text("🎨 Processing your edit request...")
        
        await self._process_edit(update, context, prompt, processing_msg)
    
    async def _process_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          prompt: str, processing_msg) -> None:
        """Process image editing request."""
        try:
            image_base64 = context.user_data["photo"]
            aspect_ratio = context.user_data.get("aspect_ratio", Config.DEFAULT_ASPECT_RATIO)
            
            # Update processing message
            await processing_msg.edit_text(
                f"🎨 Editing your image...\n"
                f"📝 Prompt: {prompt}\n"
                f"📐 Aspect ratio: {aspect_ratio}\n\n"
                f"⏳ This may take 10-30 seconds..."
            )
            
            # Edit image
            edited_image_bytes = await self.bfl_editor.edit_image(
                image_base64, prompt, aspect_ratio
            )
            
            if edited_image_bytes:
                # Send edited image
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=io.BytesIO(edited_image_bytes),
                    caption=f"✨ **Edited Image**\n📝 Prompt: {prompt}"
                )
                await processing_msg.delete()
                
                await update.message.reply_text(
                    "🔄 You can send another editing instruction for this image, "
                    "or send a new image to start over!"
                )
            else:
                await processing_msg.edit_text(
                    "❌ Failed to edit image. Please try again with a different prompt."
                )
                
        except Exception as e:
            logger.error(f"Error processing edit: {e}")
            await processing_msg.edit_text("❌ An error occurred. Please try again.")

def main() -> None:
    """Main function to run the bot."""
    logger.info("Starting Telegram BFL.ai Image Editor Bot...")
    
    # Create bot instance
    bot = TelegramBot()
    
    # Create application
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("clear", bot.clear_command))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    
    # Start bot
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

