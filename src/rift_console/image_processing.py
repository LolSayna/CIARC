from PIL import Image
import os

import shared.constants as con

# world map
world_x = 21600
world_y = 10800


def stitch_images(image_paths: list[str]) -> Image.Image:
    # Open images
    images = [Image.open(con.IMAGE_PATH + image_path) for image_path in image_paths]

    # Create a new empty image
    stitched_image = Image.new("RGBA", (world_x, world_y))

    # Place each image side by side
    for image, filename in zip(images, image_paths):
        x = int(filename.split("x_", 1)[1].split("_")[0]) - 300
        y = int(filename.split("y_", 1)[1].split("_")[0]) - 300

        print("pasting " + str(x) + " " + str(y))
        stitched_image.paste(image, (x, y))

    return stitched_image


def list_image_files(directory: str) -> list[str]:
    # List to store files starting with 'image'
    image_files = []

    # Iterate over all files in the specified directory
    for filename in os.listdir(directory):
        # Check if the filename starts with 'image'
        if filename.startswith("image"):
            # Add to the list of image files
            image_files.append(filename)

    return image_files


def main() -> None:
    # Image file paths
    image_paths = list_image_files(con.IMAGE_PATH)
    print(image_paths)
    # Stitch images
    panorama = stitch_images(image_paths)

    # Save and show the result
    panorama.save("media/panorama.png")
    # panorama.show()


# for now call this file directly TODO integrieren into console
if __name__ == "__main__":
    main()
