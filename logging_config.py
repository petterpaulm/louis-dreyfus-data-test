import logging
import colorama

# Define log styles
class style:
    HEADER = lambda x: colorama.Fore.BLACK + colorama.Back.CYAN + str(x)
    COMPLEMENT = lambda x: colorama.Fore.RED + str(x)
    RESET = lambda x: colorama.Style.RESET_ALL + str(x)

class ColorFormatter(logging.Formatter):
    """Custom formatter to apply colors based on log level"""
    def format(self, record):
        level_colors = {
            logging.DEBUG: style.HEADER("[DEBUG]"),
            logging.INFO: style.HEADER("[INFO]"),
            logging.WARNING: style.COMPLEMENT("[WARNING]"),
            logging.ERROR: style.COMPLEMENT("[ERROR]"),
            logging.CRITICAL: style.COMPLEMENT("[CRITICAL]"),
        }
        log_color = level_colors.get(record.levelno, style.RESET("[LOG]"))
        log_msg = super().format(record)
        return f"{log_color} {log_msg} {style.RESET('')}"

# Setup logging
logging.basicConfig(
    filename="grib2_processing.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter("%(asctime)s - %(levelname)s - %(message)s"))

logging.getLogger().addHandler(console_handler)
