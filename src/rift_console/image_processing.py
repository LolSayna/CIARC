from PIL import Image
import os
import re
import time

from shared.models import CameraAngle
import shared.constants as con
from loguru import logger
import datetime


### HELPER FUNCTIONS

# generate spiral pattern (0,0), (0,1), (1,0), (1,1), ...
def spiral_traverse(n):
    # The possible directions we can move: right, up, left, down
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    
    # Start at the origin
    x, y = 0, 0
    # The initial direction is to the right
    direction_index = 0
    
    # This will hold the path of the spiral
    spiral = [(x, y)]
    
    # Number of steps we take before changing direction
    steps = 1
    
    while len(spiral) < n:
        for _ in range(2):
            for _ in range(steps):
                if len(spiral) < n:
                    # Move in the current direction
                    dx, dy = directions[direction_index]
                    x += dx
                    y += dy
                    # Add the new position to the spiral
                    spiral.append((x, y))
                else:
                    break
            # Change direction clockwise
            direction_index = (direction_index + 1) % 4
        # After moving two directions, we increase the number of steps
        steps += 1
    
    return spiral


# abs of multiple values
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

            n = 80
            d = 4

            spiral_coordinates = sorted(spiral_traverse(n), key=tuple_abs_sum)

            matched_part_of_stiched_image = stitched_image.crop((x - d, y - d, x + LENS_SIZE + d, y + LENS_SIZE + d))

            img_grey = img.convert(mode="L")
            stiched_grey = matched_part_of_stiched_image.convert(mode="L")


            pixels = stiched_grey.getdata()

            empty_pixels = sum(1 for pixel in pixels if pixel == (0)) 

            best_coord = (0, 0)
            matches = 0
            
            if empty_pixels/len(pixels) < 0.5:  # probiere nur zu matches falls mehr als die Häflte der Pixel gefüllt

                logger.error(f"{image_name} with emtpy pixels percantage: {empty_pixels/len(pixels)}")

                for coord in spiral_coordinates:
                    matching = count_matching(img=img_grey, existing_img=stiched_grey, LENS_SIZE=LENS_SIZE, offset=coord)
                    if matching > matches:
                        best_coord = coord
                        matches = matching

                logger.error(f"Best was {best_coord} with matches: {matches} and percantage: {matches/len(pixels)}")
            # Example: Traversing a 3x3 grid in a spiral pattern

            #for coord in spiral_coordinates:

            # TODO add check to filter low matches out
            stitched_image.paste(img, (x + best_coord[0], y + best_coord[1]))
            
            #img.show()
            #matched_part_of_stiched_image.show()
            #stitched_image.show()
            #time.sleep(15)

    return stitched_image

def count_matching(img: Image, existing_img: Image, LENS_SIZE: int, offset: tuple[int, int]) -> int:
    matching = 0
    for x_local in range(LENS_SIZE):
        for y_local in range(LENS_SIZE):
            p1 = img.getpixel((x_local, y_local))
            p2 = existing_img.getpixel((x_local + offset[0], y_local + offset[1]))

            #logger.error(f"offset: {offset} {x_local} {y_local} {offset[0]} {offset[1]} {p1} {p2}")
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
    image_path = con.IMAGE_PATH + "/t" + "/"
    output_path = con.PANORAMA_PATH + "/t"

    image_list = list_image_files(image_path)

    logger.warning(f"Starting stitching of {len(image_list)} image with path: {image_path}")

    panorama = stitch_images(image_path=image_path, image_list=image_list)
    preview = panorama.resize((1080, 540), Image.Resampling.LANCZOS)

    preview.save("src/rift_console/static/images/" + "preview.png")
    panorama.save(output_path + ".png")
    logger.warning("Created preview + panorma in Stitcher")


# for now call this file directly TODO integrieren into console
if __name__ == "__main__":
    main()
