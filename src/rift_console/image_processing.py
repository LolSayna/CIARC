from PIL import Image
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import Optional

from rift_console.image_helper import generate_spiral_walk, parse_image_name
import shared.constants as con
from loguru import logger
import datetime
import re

##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level=con.RIFT_LOG_LEVEL, backtrace=True, diagnose=True)



def count_matching_pixels(offset: tuple[int, int], first_img: Image, second_img: Image, max_offset: int) -> tuple[int, int]:
    """ Counts how many pixels are equal between the two images for a given offset

    Args:
        offset (tuple[int, int]): shift of one image
        img (Image): first image
        existing_img (Image): second (larger to allow shift) image

    Returns:
        tuple[int, int]: used offset and number of matching pixels
    """

    matches = 0
    for x_local in range(first_img.size[0]):
        for y_local in range(first_img.size[1]):
            p1 = first_img.getpixel((x_local, y_local))
            p2 = second_img.getpixel((x_local + offset[0] + max_offset, y_local + offset[1] + max_offset))

            if p1 == p2:
                matches += 1

    return offset, matches


# Takes the folder location(including logs/melvonaut/images) and a list of image names
def stitch_images(image_path: str, images: list[str], panorama = None) -> Image.Image:
    """ Main stitching algorithm
    TODO add existing img

    Args:
        image_path (str): _description_
        images (list[str]): _description_
        panorama

    Returns:
        Image.Image: _description_
    """
    # create new panorama if it does not exist
    if panorama is None:
        panorama = Image.new("RGBA", (con.WORLD_X, con.WORLD_Y))

    stiched_image_counter = 0
    # iterate images
    for image_name in images:
        with Image.open(image_path + image_name) as img:

            logger.debug(f"Parsing {image_name} {img.size} {img.mode}")
            # extract image name
            lens_size, x, y = parse_image_name(image_name)

            img = img.convert("RGBA")

            # possible resize
            if lens_size != 600:
                img = img.resize((lens_size, lens_size), Image.Resampling.LANCZOS)


            # try position in a square arround the center
            # values 7x7 Grid: d = 3, n = 28   9x9 Grid: d = 4 n = 80   11x11 Grid, d = 5 n = 120
            spiral_coordinates = generate_spiral_walk(con.SEARCH_GRID_SIDE_LENGTH * con.SEARCH_GRID_SIDE_LENGTH)

            max_offset = int((con.SEARCH_GRID_SIDE_LENGTH - 1) / 2)
            existing_stitch = panorama.crop((x - max_offset, y - max_offset, x + lens_size + max_offset, y + lens_size + max_offset))


            # check if existing_stich contains something
            total_pixel = existing_stitch.size[0] * existing_stitch.size[1]
            set_pixel = sum(1 for pixel in existing_stitch.getdata() if pixel != (0, 0, 0, 0))
            empty_pixel = total_pixel - set_pixel

            logger.info(f"Existing stich ({existing_stitch.size[0]},{existing_stitch.size[1]}) w. {total_pixel}p " +
                        f"set: {set_pixel} {set_pixel/total_pixel}% and transparent: {empty_pixel} {empty_pixel/total_pixel}%")


            best_match_count = 0
            best_offset = (0, 0)

            # probiere nur zu match_count falls mehr als die Häflte der Pixel gefüllt
            if empty_pixel/total_pixel < 0.5:
                
                # make a func with static params for this image
                count_part = partial(count_matching_pixels, first_img=img, second_img=existing_stitch, max_offset=max_offset)

                with ProcessPoolExecutor(max_workers=con.NUMBER_OF_WORKER_THREADS) as executor:

                    # each Thread gets automatically assign a different coordinate from the pool
                    results = executor.map(count_part, spiral_coordinates)

                for offset, matches in results:
                    if matches > best_match_count:            
                        logger.debug(f"New best: matches {matches}p ({matches/total_pixel}%), with offset {best_offset}\n")
                        best_offset = offset
                        best_match_count = matches

                # check if it worked
                if best_match_count/(set_pixel) < 0.5:
                    logger.info(f"Reset offset to (0,0) since best_match_count: {best_match_count}p ({best_match_count/total_pixel}%)")
                    best_offset = (0, 0)
                    best_match_count = 0
            else:
                logger.info(f"Offset (0,0) since existing image set_pixel: {set_pixel} {set_pixel/total_pixel}")


            # need to check math for % here!
            logger.warning(f"Placed Image best_match_count: {best_match_count}p ({best_match_count/total_pixel}%) with offset: {best_offset}\n")

            panorama.paste(img, (x + best_offset[0], y + best_offset[1]))#

            stiched_image_counter += 1
            if stiched_image_counter % con.SAVE_PANAORMA_STEP == 0:
                panorama.save(con.PANORAMA_PATH + "step_pan/" + str(stiched_image_counter) + ".png")

    return panorama

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


# TODO add parameter to add new stiches onto an exisiting map
def automated_processing(image_path: str, output_path: str) -> None:
    image_list = list_image_files(image_path)

    logger.warning(f"Starting stitching of {len(image_list)} image with path: {image_path}")

    panorama = stitch_images(image_path=image_path, images=image_list)
    preview = panorama.resize((1080, 540), Image.Resampling.LANCZOS)

    preview.save("src/rift_console/static/images/" + "preview.png")
    panorama.save(output_path + ".png")
    logger.warning("Created preview + panorma in Stitcher")


# for manual testing
def main() -> None:
    image_path = con.IMAGE_PATH + "t" + "/"
    output_path = con.PANORAMA_PATH + "t"

    image_list = list_image_files(image_path)

    logger.warning(f"Starting stitching of {len(image_list)} image with path: {image_path}")

    panorama = stitch_images(image_path=image_path, images=image_list)
    preview = panorama.resize((1080, 540), Image.Resampling.LANCZOS)

    preview.save("src/rift_console/static/images/" + "preview.png")
    panorama.save(output_path + ".png")
    logger.warning("Created preview + panorma in Stitcher")


# for now call this file directly TODO integrieren into console
if __name__ == "__main__":
    main()
