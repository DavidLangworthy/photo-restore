import os
import time
import re
import argparse
from google import genai
from google.genai import types
from PIL import Image
from google.api_core import exceptions

# --- CONFIGURATION ---
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")

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
    client = genai.Client(api_key=API_KEY)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    return client

def extract_wait_time(error_message):
    """Finds 'retry in 38.39s' in the error message."""
    match = re.search(r"retry in (\d+(\.\d+)?)s", str(error_message))
    if match:
        return float(match.group(1))
    return 60.0 # Default to 60s if parse fails


def extract_inline_image_bytes(response):
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None)
            if data:
                return data
    return None


def process_images(input_folder, output_folder):
    client = setup(output_folder)
    
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
                image_part = types.Part.from_image(
                    image=img,
                    config=types.MediaResolution(level="ULTRA_HIGH"),
                )

                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[
                        types.Part.from_text(PROMPT),
                        image_part,
                    ],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    ),
                    request_options={"timeout": 30},
                )

                image_data = extract_inline_image_bytes(response)
                if image_data:
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
