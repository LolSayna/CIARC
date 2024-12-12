from PIL import Image
import os
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import Optional

from rift_console.image_helper import generate_spiral_walk, parse_image_name
import shared.constants as con
from loguru import logger
import datetime
import re


def count_matching_pixels(offset: tuple[int, int], first_img: Image, second_img: Image, max_offset: int) -> tuple[int, int]:
    """ Counts how many pixels are equal between the two images for a given offset

    Args:
        offset (tuple[int, int]): shift of one image
        img (Image): first image
        existing_img (Image): second (larger to allow shift) image

    Returns:
        tuple[int, int]: used offset and number of matching pixels
    """

    matching = 0
    for x_local in range(first_img.size[0]):
        for y_local in range(second_img.size[1]):
            p1 = first_img.getpixel((x_local, y_local))
            p2 = second_img.getpixel((x_local + offset[0] + max_offset, y_local + offset[1] + max_offset))

            #logger.error(f"offset: {offset} {x_local} {y_local} {offset[0]} {offset[1]} {p1} {p2}")
            if p1 == p2:
                matching += 1

    return offset, matching


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

    # iterate images
    for image_name in images:
        with Image.open(image_path + image_name) as img:

            logger.info(f"Parsing {image_name} {img.size} {img.mode}")

            img = img.convert("RGBA")

            # extract image name
            lens_size, x, y = parse_image_name(image_name)

            # possible resize
            if lens_size != 600:
                img = img.resize((lens_size, lens_size), Image.Resampling.LANCZOS)

            # try position in a square arround the center
            # values 7x7 Grid: d = 3, n = 28   9x9 Grid: d = 4 n = 80   11x11 Grid, d = 5 n = 120
            search_grid_side_length = 11
            spiral_coordinates = generate_spiral_walk(search_grid_side_length * search_grid_side_length)

            max_offset = int((search_grid_side_length - 1) / 2)

            existing_stitch = panorama.crop((x - max_offset, y - max_offset, x + lens_size + max_offset, y + lens_size + max_offset))

            # convert to greyscale
            #img_grey = img.convert(mode="L")
            #existing_stitch_grey = existing_stitch.convert(mode="L")

            #img.show()
            #existing_stitch.show()
            #time.sleep(100)

            pixels = img.getdata()
            
            # warum klapt das net?
            empty_pixels = sum(1 for pixel in pixels if pixel == (0, 0, 0, 0)) 
            full_pixels = len(pixels) - empty_pixels

            best_coord = (0, 0)
            matches = 0
            num_workers = 10 # 1 for single core

            logger.warning(f"Stitching: {image_name}\n#Pixels: {len(pixels)}\t\tFull: {full_pixels}\t\tEmtpy: {empty_pixels}")
                        
            """
            logger.error(f"img: {img.size}")
            img.show()
            img_grey.show()
            matched_part_of_stiched_image.show()
            time.sleep(10)
"""
            if empty_pixels/len(pixels) < 0.5:  # probiere nur zu matches falls mehr als die Häflte der Pixel gefüllt

                count_part = partial(count_matching_pixels, first_img=img, second_img=existing_stitch, max_offset=max_offset)

                with ProcessPoolExecutor(max_workers=num_workers) as executor:

                    # Map the tasks (coordinates) to the executor
                    results = executor.map(count_part, spiral_coordinates)

                for offset, matching in results:
                    if matching > matches:
                        logger.debug(f"New best: offset: {offset}\t\t#Matched {matching} with %: {matches/(full_pixels+1)}")
                        best_coord = offset
                        matches = matching

                # check if it worked
                if matches/(full_pixels+1) < 0.5:
                    logger.info(f"Reset offset to (0,0) since no good match was found")
                    best_coord = (0, 0)
                    matches = 0


            logger.warning(f"Best was {best_coord}\t\twith %: {matches/(full_pixels+1)}\n\n")

            panorama.paste(img, (x + best_coord[0], y + best_coord[1]))
            
            #img.show()
            #matched_part_of_stiched_image.show()
            #stitched_image.show()
            #time.sleep(15)

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
    image_path = con.IMAGE_PATH + "/t" + "/"
    output_path = con.PANORAMA_PATH + "/t"

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
