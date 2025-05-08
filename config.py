import os
# Import find_dotenv separately
from dotenv import load_dotenv, find_dotenv
import logging

# Configure logging
log = logging.getLogger(__name__) # Use module-specific logger

def load_api_key():
    """
    Loads the NVIDIA API key from the .env file or environment variables.
    Searches for .env file and specifically looks for NVIDIA_NIM_API_KEY.

    Returns:
        str: The NVIDIA API key, or None if not found.
    """
    log.info("Attempting to find .env file...")
    # 1. Find the .env file path
    dotenv_path = find_dotenv()

    if not dotenv_path:
        log.warning(".env file not found by find_dotenv(). Checking environment variables only.")
    elif not os.path.exists(dotenv_path):
        log.warning(f".env file path found ({dotenv_path}), but the file does not exist.")
        dotenv_path = None # Treat as not found if path exists but file doesn't
    elif not os.access(dotenv_path, os.R_OK):
        log.error(f".env file found at {dotenv_path}, but read permissions are denied.")
        dotenv_path = None # Treat as inaccessible
    else:
        log.info(f"Found .env file at: {dotenv_path}. Attempting to load.")
        # 2. Load the found .env file
        try:
            # verbose=True can help debugging .env parsing issues
            loaded_success = load_dotenv(dotenv_path=dotenv_path, override=True, verbose=True)
            if loaded_success:
                log.info(f"Successfully processed .env file: {dotenv_path}")
            else:
                log.warning(f"load_dotenv processed '{dotenv_path}' but reported no variables loaded (or file was empty). Check .env format.")
        except Exception as e:
            log.error(f"Error loading .env file ({dotenv_path}): {e}", exc_info=True)
            # Continue to check environment variables even if .env loading fails

    # 3. Get the API key from environment, specifically looking for NVIDIA_NIM_API_KEY
    # *** Use the variable name from the error message ***
    key_variable_name = "NVIDIA_NIM_API_KEY"
    log.info(f"Checking environment for {key_variable_name}...")
    api_key = os.getenv(key_variable_name)

    if not api_key:
        log.error(f"{key_variable_name} was NOT found in the environment after checking .env and system variables.")
        return None
    elif len(api_key.strip()) == 0:
         log.error(f"{key_variable_name} was found but is empty or contains only whitespace.")
         return None # Treat empty key as not found

    log.info(f"{key_variable_name} loaded successfully from environment.")
    return api_key

if __name__ == "__main__":
    # Example usage when running this script directly
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("--- Testing load_api_key() ---")
    key = load_api_key()
    if key:
        print("\nSUCCESS: API Key loaded.")
    else:
        print("\nFAILED: API Key could not be loaded.")
        print("Troubleshooting:")
        print("- Ensure a '.env' file exists in the project root directory or a parent directory.")
        # *** Update variable name in help text ***
        print("- Ensure the '.env' file contains: NVIDIA_NIM_API_KEY=\"YOUR_ACTUAL_KEY\"")
        print("- Check for typos in the variable name ('NVIDIA_NIM_API_KEY').")
        print("- Ensure there are no extra spaces around the key or '=' sign in the .env file.")
        print("- Check file permissions for the .env file.")
        print("- Check if the NVIDIA_NIM_API_KEY environment variable is set system-wide (if not using .env).")
    print("--- Test Finished ---")
