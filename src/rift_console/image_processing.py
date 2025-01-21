import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import requests

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
        # add 1000 pixels on each side be used by nudging
        panorama = Image.new(
            "RGBA",
            (
                con.WORLD_X + con.STITCHING_BORDER * 2,
                con.WORLD_Y + con.STITCHING_BORDER * 2,
            ),
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
            try:
                img = img.convert("RGBA")
            except OSError as e:
                logger.warning(
                    f"Could not parse file {image_name}, skipped. Error: {e}"
                )

            # possible resize
            if lens_size != 600:
                img = img.resize((lens_size, lens_size), Image.Resampling.LANCZOS)

            logger.info(f"Parsing {image_name}")
            logger.debug(f"{img.size} {img.mode}")

            # try position in a square arround the center
            # values 7x7 Grid: d = 3, n = 28   9x9 Grid: d = 4 n = 80   11x11 Grid, d = 5 n = 120
            spiral_coordinates = generate_spiral_walk(
                con.SEARCH_GRID_SIDE_LENGTH * con.SEARCH_GRID_SIDE_LENGTH
            )

            max_offset = int((con.SEARCH_GRID_SIDE_LENGTH - 1) / 2)
            existing_stitch = panorama.crop(
                (
                    x - max_offset + con.STITCHING_BORDER,
                    y - max_offset + con.STITCHING_BORDER,
                    x + lens_size + max_offset + con.STITCHING_BORDER,
                    y + lens_size + max_offset + con.STITCHING_BORDER,
                )
            )

            # check if existing_stich contains something
            total_pixel = existing_stitch.size[0] * existing_stitch.size[1]
            set_pixel = sum(
                1 for pixel in existing_stitch.getdata() if pixel != (0, 0, 0, 0)
            )
            empty_pixel = total_pixel - set_pixel

            logger.debug(
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
                        x + best_offset[0] + con.STITCHING_BORDER,
                        y + best_offset[1] + con.STITCHING_BORDER,
                    ),
                )

            processed_images_counter += 1
            if processed_images_counter % con.SAVE_PANAORMA_STEP == 0:
                panorama.save(
                    con.PANORAMA_PATH + "step_" + str(processed_images_counter) + ".png"
                )

        # if any(pixel < 255 for pixel in alpha.getdata()):
        #    return True

        if processed_images_counter >= con.STITCHING_COUNT_LIMIT:
            logger.warning(
                f"STITCHING_COUNT_LIMIT of {con.STITCHING_COUNT_LIMIT} reached!"
            )
            break

    logger.warning(
        f"\n\nDone stitching of {processed_images_counter} from {len(image_name_list)} given images"
    )
    if con.DO_IMAGE_NUDGING_SEARCH:
        logger.warning(
            f"nudging_failed_counter: {nudging_failed_counter} , to_few_pixel_counter: {to_few_pixel_counter}\n"
        )

    for element, count in Counter(max_offset_database).items():
        logger.warning(f"Max_offset up to {element} occured {count} times")

    return panorama


def upload(id: int, path: str, folder: bool = False) -> None:
    """Uploads one objective image" """

    if folder:
        images = find_image_names(path)
        for img in images:
            logger.warning(img)
            upload(id, path + "/" + img, False)

            logger.warning(f"Uploaded folder of {len(images)}.")
        return

    logger.info(f"Uploading {id} with path {path}")
    params = {"objective_id": id}

    files = {"image": (path, open(path, "rb"), "image/png")}

    with requests.Session() as s:
        r = s.post(con.IMAGE_ENDPOINT, params=params, files=files)

        if r.status_code == 200:
            logger.warning(f"Uploaded: {r}")
            logger.warning(f"{r.text}{r.json()}")
        else:
            logger.error(f"Upload failed with code: {r.status_code}")
            logger.error(f"{r.text} {r.json()}")
    logger.info("Done with Uplaod!")


def cut(panorama_path: str, X1: int, Y1: int, X2: int, Y2: int) -> None:
    """Cut a small portion from a bigger Panorama.

    Args:
        panorama_path (str): Name of the file (should include con.PANORAMA_PATH)
        coordinates: Section that should be cut and saved
    """
    coordinates = (int(X1), int(Y1), int(X2), int(Y2))
    with Image.open(panorama_path) as panorama:
        cut_img = panorama.crop(coordinates)

    cut_img.show()
    cut_img.save(panorama_path.replace(".png", "") + "_cut.png")

    logger.warning("Saved cut to media/*_cut.png")


def create_thumbnail(panorama_path: str) -> None:
    """Creates a scaled down panorama and a greyscale one from a given panorama and saves it to `src/rift_console/static/images/thumb.png` from where it can be used by html.

    Args:
        panorama_path (str): Name of the file (should include con.PANORAMA_PATH)
    """
    with Image.open(panorama_path) as panorama:
        thumb = panorama.resize(
            (con.SCALED_WORLD_X, con.SCALED_WORLD_Y), Image.Resampling.LANCZOS
        )
        thumb.save("src/rift_console/static/images/" + "thumb.png")
        thumb = thumb.convert("L")
        thumb.save("src/rift_console/static/images/" + "thumb_grey.png")
    logger.warning(
        "Saved Thumbnail to src/rift_console/static/images/thumb.png and thumb_grey.png"
    )


# TODO add parameter to add new stiches onto an exisiting map
def automated_stitching(local_path: str) -> None:
    """Stitches images from the given path into one big image, which is stored under the same name in con.PANORAMA_PATH.

    Args:
        local_path (str): Path of a folder with images that should be stitched.
    """

    image_path = local_path + "/"
    output_path = con.PANORAMA_PATH + "stitched"

    image_name_list = find_image_names(image_path)

    logger.warning(
        f"Starting stitching of {len(image_name_list)} image with path: {image_path}"
    )

    panorama = stitch_images(image_path=image_path, image_name_list=image_name_list)

    remove_offset = (
        con.STITCHING_BORDER,
        con.STITCHING_BORDER,
        con.WORLD_X + con.STITCHING_BORDER,
        con.WORLD_Y + con.STITCHING_BORDER,
    )
    panorama = panorama.crop(remove_offset)
    panorama.save(output_path + ".png")

    logger.warning(f"Saved panorama in {output_path}.png")


# For CLI testing
if __name__ == "__main__":
    print("GO")

    if len(sys.argv) < 2:
        print("Usage: python3 src/rift_console/image_processing.py stitch PATH")
        print("Usage: python3 src/rift_console/image_processing.py thumb PATH")
        print(
            "Usage: python3 src/rift_console/image_processing.py cut PATH X1 Y1 X2 Y2"
        )
        print("Exiting, wrong number of params!")
        sys.exit(1)

    # Stiching
    if sys.argv[1] == "stitch":
        if len(sys.argv) == 3:
            automated_stitching(local_path=sys.argv[2])
            sys.exit(0)
        print("Usage: python3 src/rift_console/image_processing.py stitch PATH")
        sys.exit(1)
    # Create Thumbnail
    elif sys.argv[1] == "thumb":
        if len(sys.argv) == 3:
            create_thumbnail(panorama_path=sys.argv[2])
            sys.exit(0)
        print("Usage: python3 src/rift_console/image_processing.py thumb PATH")
        sys.exit(1)
    # Cut
    elif sys.argv[1] == "cut":
        if len(sys.argv) == 7:
            cut(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
            sys.exit(0)
        print(
            "Usage: python3 src/rift_console/image_processing.py cut PATH X1 Y1 X2 Y2)"
        )
        sys.exit(1)
    # Upload objective
    elif sys.argv[1] == "upload":
        if len(sys.argv) == 5:
            upload(id=sys.argv[2], path=sys.argv[3], folder=eval(sys.argv[4]))
            sys.exit(0)
        print(
            "Usage: python3 src/rift_console/image_processing.py upload ID PATH IS_FOLDER"
        )
        sys.exit(1)
