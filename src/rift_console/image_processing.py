from PIL import Image
import os
import re
import time

from shared.models import CameraAngle
import shared.constants as con
from loguru import logger
import datetime

def spiral_traverse(n):
    if n <= 0:
        return []

    # Initialize the grid with None
    grid = [[None] * n for _ in range(n)]
    
    result = []
 
    # Define the boundaries of the grid
    top, bottom = 0, n - 1
    left, right = 0, n - 1

    while top <= bottom and left <= right:
        # Traverse from left to right on the top row
        for i in range(left, right + 1):
            result.append((top, i))
        top += 1

        # Traverse from top to bottom on the right column
        for i in range(top, bottom + 1):
            result.append((i, right))
        right -= 1

        if top <= bottom:
            # Traverse from right to left on the bottom row
            for i in range(right, left - 1, -1):
                result.append((bottom, i))
            bottom -= 1

        if left <= right:
            # Traverse from bottom to top on the left column
            for i in range(bottom, top - 1, -1):
                result.append((i, left))
            left += 1

    return result

def tuple_abs_sum(t):
    return sum(abs(x) for x in t)


# Takes the folder location(including logs/melvonaut/images) and a list of image names
def stitch_images(image_path: str, image_list: list[str]) -> Image.Image:
    # Create a new empty image
    stitched_image = Image.new("RGBA", (con.WORLD_X, con.WORLD_Y))

    for image_name in image_list:
        with Image.open(image_path + image_name) as img:
            # read camera angle
            angle = image_name.split("_")[2]

            match angle:
                case CameraAngle.Narrow:
                    LENS_SIZE = 600
                case CameraAngle.Normal:
                    LENS_SIZE = 800
                case CameraAngle.Wide:
                    LENS_SIZE = 1000

            match = re.search(r"_x_(-?\d+)_y_(-?\d+)", image_name)

            if match:
                x = int(match.group(1))
                y = int(match.group(2))
            else:
                logger.error(f"!!!Coordinate reading failed for {image_name}")
                return stitched_image
            # x = int(image_name.split(zx_", 1)[1].split("_")[0]) - (int)(LENS_SIZE / 2)
            # y = int(image_name.split("y_", 1)[1].split("_")[0]) - (int)(LENS_SIZE / 2)

            if LENS_SIZE != 600:
                img = img.resize((LENS_SIZE, LENS_SIZE), Image.Resampling.LANCZOS)

            # try to find optimal position
            # also add progess bar
            """TODO
            matched_part_of_stiched_image = stitched_image.crop((x, y, x + LENS_SIZE + 5, y + LENS_SIZE + 5))


            stitched_image.show()
            img.show()
            matched_part_of_stiched_image.show()
            time.sleep(15)

            first = False
            if first:
                # Example: Traversing a 3x3 grid in a spiral pattern
                n = 5
                spiral_coordinates = sorted(spiral_traverse(n), key=tuple_abs_sum)
                for coord in spiral_coordinates:
                    matching = count_matching(img=img, existing_img=matched_part_of_stiched_image, LENS_SIZE=LENS_SIZE, offset=coord)
                    
                    logger.error(f"Matched pixels: {matching} for offset {coord}")
            first = True
            """
            stitched_image.paste(img, (x, y))

    return stitched_image

def count_matching(img: Image, existing_img: Image, LENS_SIZE: int, offset: tuple[int, int]) -> int:
    matching = 0
    for x_local in range(LENS_SIZE):
        for y_local in range(LENS_SIZE):
            #logger.error(f"offset: {offset} {x_local} {y_local} {offset[0]} {offset[1]}")
            p1 = img.getpixel((x_local, y_local))
            p2 = existing_img.getpixel((x_local + offset[0], y_local + offset[1]))

            if p2 != (0,0,0,0)  :
                logger.error(f"{p1} {p2} {p1==p2}")
            if p1 == p2:
                matching += 1

    return matching

# returns all images
def list_image_files(directory: str) -> list[str]:

    image_files = []
    for filename in os.listdir(directory):
        if filename.startswith("image"):
            image_files.append(filename)

    # pattern to find timestamp
    timestamp_pattern = r"_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})_"

    # Function to extract timestamp from a string
    def extract_timestamp(s):

        match = re.search(timestamp_pattern, s)
        if match:
            timestamp_str = match.group(1)
            # Parse timestamp string to a datetime object
            return datetime.datetime.fromisoformat(timestamp_str)
        else:
            return None

    # Sort the list of strings based on the extracted timestamp
    image_files = sorted(image_files, key=extract_timestamp)

    return image_files


def automated_processing(image_path: str, output_path: str) -> None:
    image_list = list_image_files(image_path)

    logger.warning(f"Starting stitching of {len(image_list)} image with path: {image_path}")

    panorama = stitch_images(image_path=image_path, image_list=image_list)
    preview = panorama.resize((1080, 540), Image.Resampling.LANCZOS)

    preview.save("src/rift_console/static/images/" + "preview.png")
    panorama.save(output_path + ".png")
    logger.warning("Created preview + panorma in Stitcher")


# for manual testing
def main() -> None:
    image_list = list_image_files(con.IMAGE_PATH)
    logger.warning(f"Starting Stiching of {len(image_list)} Images.")

    panorama = stitch_images(image_path=con.IMAGE_PATH, image_list=image_list)

    panorama.save("media/panorama.png")


# for now call this file directly TODO integrieren into console
if __name__ == "__main__":
    main()
