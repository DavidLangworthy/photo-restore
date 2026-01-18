import os
import time
import re
import argparse
import google.generativeai as genai
from PIL import Image
from google.api_core import exceptions  # <--- REQUIRED for catching 429 errors
# Make sure you have this import at the top!
from google.api_core import exceptions

# --- CONFIGURATION ---
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY not found. Please run: export API_KEY='Your_Key'")

MODEL_NAME = "gemini-3-pro-image-preview"
PROMPT = """
Rerender this image in a high-fidelity, cinematic lighting style, keeping the original composition. 
Try and make all the objects sharp and clear but otherwise the same. Remember that the final image 
should be in color. Attempt to correct any obvious lighting errors and focus blur, but again due not 
change the details of the photo.  In particular keep facial details the same, same gaze and same expression.  
It is a family album. Some of the photos may have a white boarder. Crop this out and do not include 
it in the rendered image.
"""

VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
# ---------------------

def setup(output_folder):
    genai.configure(api_key=API_KEY)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

def extract_wait_time(error_message):
    """Finds 'retry in 38.39s' in the error message."""
    match = re.search(r"retry in (\d+(\.\d+)?)s", str(error_message))
    if match:
        return float(match.group(1))
    return 60.0 # Default to 60s if parse fails


def process_images(input_folder, output_folder):
    setup(output_folder)
    model = genai.GenerativeModel(MODEL_NAME)
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return

    # Sort files to ensure order
    files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith(VALID_EXTENSIONS)])
    total = len(files)
    
    print(f"--- Starting Batch Process using {MODEL_NAME} ---")
    print(f"Found {total} images.")

    for index, filename in enumerate(files):
        input_path = os.path.join(input_folder, filename)
        output_filename = f"c_{filename}"
        output_path = os.path.join(output_folder, output_filename)

        if os.path.exists(output_path):
            continue

        print(f"[{index+1}/{total}] Processing {filename}...")

        # RETRY LOOP
        retry_count = 0
        max_retries = 2  # Don't try forever on a bad image

        while retry_count < max_retries:
            try:
                img = Image.open(input_path)
                
                # --- THE FIX IS HERE ---
                # We force a 120-second timeout. If it takes longer, we kill it and retry.
                response = model.generate_content(
                    [PROMPT, img],
                    request_options={'timeout': 30} 
                )
                
                if response.parts:
                    image_data = response.parts[0].inline_data.data
                    with open(output_path, 'wb') as f:
                        f.write(image_data)
                    print(f"   -> Saved.")
                    break # Success, leave while loop
                else:
                    print(f"   -> Warning: No image data returned. Retrying...")
                    retry_count += 1
            
            except exceptions.ResourceExhausted as e:
                # HIT RATE LIMIT (429) - Wait and continue
                wait_time = extract_wait_time(e) + 1.0
                print(f"   -> Hit Rate Limit (429). Sleeping {wait_time:.1f}s...")
                time.sleep(wait_time)
            
            except (exceptions.DeadlineExceeded, exceptions.ServiceUnavailable) as e:
                # TIMEOUT or SERVER ERROR - Wait briefly and retry
                print(f"   -> Network Timeout/Glitch ({type(e).__name__}). Retrying in 5s...")
                time.sleep(5)
                retry_count += 1

            except Exception as e:
                # FATAL ERROR (Corrupt file, etc)
                print(f"   -> FATAL ERROR on {filename}: {e}")
                with open("error_log.txt", "a") as log:
                    log.write(f"{filename}: {e}\n")
                break # Give up on this specific image
        
        if retry_count >= max_retries:
             print(f"   -> Failed after {max_retries} attempts. Skipping.")

        # Brief pause between images to be nice to the API
        time.sleep(2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    process_images(args.input, args.output)