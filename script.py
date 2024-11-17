import cv2
import os
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
import time


def find_most_recent_screenshot(screenshots_folder):
    list_of_files = glob(os.path.join(screenshots_folder, "*.png"))
    if not list_of_files:
        raise FileNotFoundError("No screenshots found in the folder.")
    return max(list_of_files, key=os.path.getctime)


def mark_image_with_box(image, position, box_size, color, thickness=2):
    top_left = position
    bottom_right = (top_left[0] + box_size[0], top_left[1] + box_size[1])
    cv2.rectangle(image, top_left, bottom_right, color, thickness)


def load_templates(prints_folder):
    template_files = glob(os.path.join(prints_folder, "print_*.png"))
    templates = {int(os.path.basename(f).split('_')[1].split('.')[0]): cv2.imread(f, cv2.IMREAD_GRAYSCALE) 
                 for f in template_files if os.path.exists(f)}
    return templates


def match_template(screenshot_gray, template, threshold=0.7):
    result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(result >= threshold)
    return list(zip(*loc[::-1]))


def find_and_mark_prints(screenshot, templates):
    screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    found_positions = {}

    with ThreadPoolExecutor(max_workers=len(templates)) as executor:
        futures = {executor.submit(match_template, screenshot_gray, template): print_id
                   for print_id, template in templates.items()}
        for future in as_completed(futures):
            print_id = futures[future]
            positions = future.result()
            if positions:
                found_positions[print_id] = positions
                for pos in positions:
                    mark_image_with_box(screenshot, pos, box_size=(387, 514), color=(0, 0, 255), thickness=2)
    return screenshot, found_positions


def process_subimages(print_id, positions, screenshot_gray, subimage_files):
    matches = []
    for subimage_file in subimage_files:
        subimage = cv2.imread(subimage_file, cv2.IMREAD_GRAYSCALE)
        if subimage is not None:
            result = cv2.matchTemplate(screenshot_gray, subimage, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            matches.append((max_val, max_loc))
    return matches


def find_and_mark_subimages(screenshot, prints_folder, found_positions):
    screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    all_matches = []

    subimage_files = {print_id: glob(os.path.join(prints_folder, str(print_id), "*.png"))
                      for print_id in found_positions.keys()}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_subimages, print_id, positions, screenshot_gray, subimage_files.get(print_id, []))
            for print_id, positions in found_positions.items()
        ]
        for future in as_completed(futures):
            all_matches.extend(future.result())

    sorted_matches = sorted(all_matches, key=lambda x: x[0], reverse=True)[:4]
    for confidence, (x, y) in sorted_matches:
        mark_image_with_box(screenshot, (x, y), box_size=(124, 124), color=(255, 0, 0), thickness=2)
        print(f"Marked Subimage, Confidence: {confidence:.2f}, Position: ({x}, {y})")
    return screenshot


def main():
    start_time = time.time()

    screenshots_folder = 'screenshots'
    prints_folder = '.'

    try:
        screenshot_path = find_most_recent_screenshot(screenshots_folder)
        print(f"Found screenshot: {screenshot_path}")

        screenshot = cv2.imread(screenshot_path)
        templates = load_templates(prints_folder)

        marked_screenshot, found_positions = find_and_mark_prints(screenshot, templates)

        final_screenshot = find_and_mark_subimages(marked_screenshot, prints_folder, found_positions)

        final_image_pil = Image.fromarray(cv2.cvtColor(final_screenshot, cv2.COLOR_BGR2RGB))
        final_image_pil.show()

    except FileNotFoundError as e:
        print(str(e))

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Time taken for the entire program: {elapsed_time:.2f} seconds")


if __name__ == '__main__':
    main()
