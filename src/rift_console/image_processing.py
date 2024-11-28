from PIL import Image
import os

from shared.models import CameraAngle
import shared.constants as con
from loguru import logger


def stitch_images(image_path: str, image_list: list[str]) -> Image.Image:
    # Create a new empty image
    stitched_image = Image.new("RGBA", (con.WORLD_X, con.WORLD_Y))

    for image_name in image_list:
        with Image.open(image_path + image_name) as img:
            # read camera angle
            angle = image_path.split("angle_", 1)[1].split("_")[0]

            match angle:
                case CameraAngle.Narrow:
                    LENS_SIZE = 600
                case CameraAngle.Normal:
                    LENS_SIZE = 800
                case CameraAngle.Wide:
                    LENS_SIZE = 1000

            x = int(image_path.split("x_", 1)[1].split("_")[0]) - (int)(LENS_SIZE / 2)
            y = int(image_path.split("y_", 1)[1].split("_")[0]) - (int)(LENS_SIZE / 2)

            if LENS_SIZE != 600:
                img = img.resize((LENS_SIZE, LENS_SIZE), Image.LANCZOS)

            stitched_image.paste(img, (x, y))

    return stitched_image


# returns all images
def list_image_files(directory: str) -> list[str]:
    image_files = []

    for filename in os.listdir(directory):
        if filename.startswith("image"):
            image_files.append(filename)

    return image_files


def automated_processing(image_path: str, output_path: str) -> None:
    image_list = list_image_files(image_path)

    logger.info(f"Starting Stiching of {len(image_list)} Images.")

    panorama = stitch_images(image_path=image_path, image_list=image_list)

    panorama.save(output_path + ".png")


# for manual testing
def main() -> None:
    image_list = list_image_files(con.IMAGE_PATH)
    logger.info(f"Starting Stiching of {len(image_list)} Images.")

    panorama = stitch_images(image_list)

    panorama.save("media/panorama.png")


# for now call this file directly TODO integrieren into console
if __name__ == "__main__":
    main()
