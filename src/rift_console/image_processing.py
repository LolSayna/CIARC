import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import partial
# from typing import Optional

from loguru import logger
from PIL import Image

from rift_console.image_helper import (
    generate_spiral_walk,
    parse_image_name,
    find_image_names,
)
import shared.constants as con

##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level=con.RIFT_LOG_LEVEL, backtrace=True, diagnose=True)


def count_matching_pixels(
    offset: tuple[int, int], first_img: Image, second_img: Image, max_offset: int
) -> tuple[int, int]:
    """Counts how many pixels are equal between the two images for a given offset

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
            p2 = second_img.getpixel(
                (x_local + offset[0] + max_offset, y_local + offset[1] + max_offset)
            )

            # logger.error(f"{p1} {p2} {abs(p1[0] - p2[0])} {abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2])}")
            # only compare R G B and not Alpha. Since there is random noise a slight difference is allowed
            if (
                abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2])
                < con.IMAGE_NOISE_FORGIVENESS
            ):
                matches += 1

    return offset, matches


TMP_OFFSET = 2000
HALF_OFFSET = 1000


# Takes the folder location(including logs/melvonaut/images) and a list of image names
def stitch_images(
    image_path: str, image_name_list: list[str], panorama=None
) -> Image.Image:
    """Main stitching algorithm
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
        panorama = Image.new(
            "RGBA", (con.WORLD_X + TMP_OFFSET, con.WORLD_Y + TMP_OFFSET)
        )

    processed_images_counter = 0
    nudging_failed_counter = 0
    to_few_pixel_counter = 0
    max_offset_database = []

    # iterate images
    for image_name in image_name_list:
        with Image.open(image_path + image_name) as img:
            # extract image name
            lens_size, x, y = parse_image_name(image_name)

            img = img.convert("RGBA")

            # possible resize
            if lens_size != 600:
                img = img.resize((lens_size, lens_size), Image.Resampling.LANCZOS)

            logger.info(f"Parsing {image_name} {img.size} {img.mode}")

            # try position in a square arround the center
            # values 7x7 Grid: d = 3, n = 28   9x9 Grid: d = 4 n = 80   11x11 Grid, d = 5 n = 120
            spiral_coordinates = generate_spiral_walk(
                con.SEARCH_GRID_SIDE_LENGTH * con.SEARCH_GRID_SIDE_LENGTH
            )

            max_offset = int((con.SEARCH_GRID_SIDE_LENGTH - 1) / 2)
            existing_stitch = panorama.crop(
                (
                    x - max_offset + HALF_OFFSET,
                    y - max_offset + HALF_OFFSET,
                    x + lens_size + max_offset + HALF_OFFSET,
                    y + lens_size + max_offset + HALF_OFFSET,
                )
            )

            # check if existing_stich contains something
            total_pixel = existing_stitch.size[0] * existing_stitch.size[1]
            set_pixel = sum(
                1 for pixel in existing_stitch.getdata() if pixel != (0, 0, 0, 0)
            )
            empty_pixel = total_pixel - set_pixel

            logger.info(
                f"Existing stich ({existing_stitch.size[0]},{existing_stitch.size[1]}) w. {total_pixel}p "
                + f"set: {set_pixel} {set_pixel/total_pixel}% and transparent: {empty_pixel} {empty_pixel/total_pixel}%"
            )

            best_match_count = 0
            best_offset = (0, 0)
            skip = False

            # TODO next goal would to move in only one direction in which the matches get better
            if con.DO_IMAGE_NUDGING_SEARCH:
                # probiere nur zu match_count falls mehr als 20% aller pixel gefüllt
                if set_pixel / total_pixel == 0:
                    logger.warning("Emtpy panoarma, image still placed")

                elif set_pixel / total_pixel > 0.2:
                    # make a func with static params for this image
                    count_part = partial(
                        count_matching_pixels,
                        first_img=img,
                        second_img=existing_stitch,
                        max_offset=max_offset,
                    )

                    with ProcessPoolExecutor(
                        max_workers=con.NUMBER_OF_WORKER_THREADS
                    ) as executor:
                        # each Thread gets automatically assign a different coordinate from the pool
                        results = executor.map(count_part, spiral_coordinates)

                    for offset, matches in results:
                        if matches > best_match_count:
                            logger.info(
                                f"New best: matches {matches}p ({matches/total_pixel}%), with offset {best_offset}\n"
                            )
                            best_offset = offset
                            best_match_count = matches

                    # check if it worked
                    if best_match_count / (set_pixel) < 0.5:
                        logger.warning(
                            f"Nudging failed, image skipped, since best_match_count: {best_match_count}p ({best_match_count/total_pixel}%)"
                        )

                        skip = True
                        nudging_failed_counter += 1

                        logger.warning(
                            f"{max(abs(best_offset[0]), abs(best_offset[1]))} {best_offset[0]} {best_offset[1]}"
                        )
                        max_offset_database.append(
                            max(abs(best_offset[0]), abs(best_offset[1]))
                        )
                else:
                    logger.warning(
                        f"Too few pixel on panorama, image skipped, set_pixel%: {set_pixel/total_pixel}"
                    )
                    skip = True
                    to_few_pixel_counter += 1

                # need to check math for % here!
                logger.debug(
                    f"Placed Image best_match_count: {best_match_count}p ({best_match_count/total_pixel}%) with offset: {best_offset}\n"
                )

            if not skip:
                panorama.paste(
                    img,
                    (
                        x + best_offset[0] + HALF_OFFSET,
                        y + best_offset[1] + HALF_OFFSET,
                    ),
                )

            processed_images_counter += 1
            if processed_images_counter % con.SAVE_PANAORMA_STEP == 0:
                panorama.save(
                    con.PANORAMA_PATH + str(processed_images_counter) + ".png"
                )

        # if any(pixel < 255 for pixel in alpha.getdata()):
        #    return True

        if processed_images_counter >= con.STITCHING_COUNT_LIMIT:
            logger.warning(
                f"STITCHING_COUNT_LIMIT of {con.STITCHING_COUNT_LIMIT} reached!"
            )
            break

    logger.warning(
        f"\n\nDone stitching of {processed_images_counter} from {len(image_name_list)} given images, nudging_failed_counter: {nudging_failed_counter} , to_few_pixel_counter: {to_few_pixel_counter}\n"
    )

    for element, count in Counter(max_offset_database).items():
        logger.warning(f"Max_offset up to {element} occured {count} times")

    return panorama


def cut(source: str, target: str) -> None:
    """Cut a small portion from a bigger Panorama.

    Args:
        source: Filelocation of the given Panoram.
        target: Location where to save the Cut.
    """
    # Hallo element
    #
    image_path = con.PANORAMA_PATH + source + ".png"
    output_path = con.PANORAMA_PATH + target + ".png"

    remove_offset = (1000, 1000, con.WORLD_X + 1000, con.WORLD_Y + 1000)
    coordinates = (7914, 5304, 8514, 5904)

    Image.MAX_IMAGE_PIXELS = 500000000

    logger.warning(image_path)
    # remove offset
    with Image.open(image_path) as img:
        cut_img = img.crop(remove_offset)
        logger.warning("Removed offset")

    cropped = cut_img.crop(coordinates)
    cropped.show()

    cropped.save(output_path)


# TODO add parameter to add new stiches onto an exisiting map
def automated_processing(image_path: str) -> None:
    """Stitches images from the given subfolder onto one big image, which is stored under the same name

    Args:
        image_path (str): folder location in con.PANORAMA_PATH and name of final panorama
    """

    output_path = con.PANORAMA_PATH + image_path
    image_path = con.IMAGE_PATH + image_path + "/"

    image_name_list = find_image_names(image_path)

    logger.warning(
        f"Starting stitching of {len(image_name_list)} image with path: {image_path}"
    )

    panorama = stitch_images(image_path=image_path, image_name_list=image_name_list)

    # preview
    # TODO change path later
    # preview = panorama.resize((1080, 540), Image.Resampling.LANCZOS)
    # preview.save("src/rift_console/static/images/" + "preview.png")

    panorama.save(output_path + ".png")

    logger.warning(f"Saved panorama in {output_path}")


# For CLI testing
if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: python3 image_processing.py IMAGE_PATH\nAbgebrochen!")
        sys.exit(1)
    if sys.argv[1] == "cut":
        cut
        if len(sys.argv) == 3:
            cut(sys.argv[1], sys.argv[2])
            sys.exit(0)
        sys.exit(1)

    automated_processing(sys.argv[1])
