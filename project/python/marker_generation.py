import cv2
from cv2 import aruco
import numpy as np
import os
import re
import time
from enum import IntEnum, StrEnum

# CONSTANTS
# Directory to save generated markers to
SAVE_DIR = "markers"
# Full path to the save directory
SAVE_PATH = os.path.join(os.getcwd(), SAVE_DIR)
# Dictionary of existing ArUco dictionaries with their attributes dimension and capacity
ARUCO_DICTIONARIES = {
    aruco.DICT_4X4_50: [4, 50],
    aruco.DICT_4X4_100: [4, 100],
    aruco.DICT_4X4_250: [4, 250],
    aruco.DICT_4X4_1000: [4, 1000],
    aruco.DICT_5X5_50: [5, 50],
    aruco.DICT_5X5_100: [5, 100],
    aruco.DICT_5X5_250: [5, 250],
    aruco.DICT_5X5_1000: [5, 1000],
    aruco.DICT_6X6_50: [6, 50],
    aruco.DICT_6X6_100: [6, 100],
    aruco.DICT_6X6_250: [6, 250],
    aruco.DICT_6X6_1000: [6, 1000],
    aruco.DICT_7X7_50: [7, 50],
    aruco.DICT_7X7_100: [7, 100],
    aruco.DICT_7X7_250: [7, 250],
    aruco.DICT_7X7_1000: [7, 1000],
    aruco.DICT_ARUCO_ORIGINAL: [4, 1024],
    aruco.DICT_APRILTAG_16H5: [4, 16],
    aruco.DICT_APRILTAG_25H9: [4, 25],
    aruco.DICT_APRILTAG_36H10: [4, 36],
    aruco.DICT_APRILTAG_36H11: [4, 36],
}
# filename: 'marker{marker_id}[_INV][_n].jpg'
FILENAME_BASE = "marker"
INVERTED_TAG = "_INV"
FILE_EXTENSION = ".jpg"
# Regular expressions to match marker filenames
REGEX = rf"{FILENAME_BASE}(\d+)(_\d+)?{FILE_EXTENSION}"
REGEX_INVERT = rf"{FILENAME_BASE}(\d+){INVERTED_TAG}(_\d+)?{FILE_EXTENSION}"

class FileAction(IntEnum):
    """Actions that can be performed when generating markers.

    - CREATE: Generate a new marker image and save it.
    - OVERWRITE: Overwrite an existing marker image.
    - SKIP: Skip generating the current marker image.
    - KEEP_BOTH: Generate a new marker image and save it as a new version of the original.
    - DECIDE_PER_MARKER: Allow the user to decide for each marker whether to overwrite, skip, or keep both versions.
    """
    
    CREATE = 0
    OVERWRITE = 1
    SKIP = 2
    KEEP_BOTH = 3
    DECIDE_PER_MARKER = 4

class Operation(StrEnum):
    """Operations that can be performed when generating markers in case of file conflicts.

    - OVERWRITE: Overwrite an existing marker image.
    - SKIP: Skip generating the current marker image.
    - KEEP_BOTH: Generate a new marker image and save it as a new version of the original.
    - DECIDE_PER_MARKER: Allow the user to decide for each marker whether to overwrite, skip, or keep both versions.
    """
    NO_OP = ""
    OVERWRITE = "o"
    SKIP = "s"
    KEEP_BOTH = "k"
    DECIDE_PER_MARKER = "d"

def generate_marker_single(dict: int, marker_id: int, marker_size_px: int = 420, inverted: bool = False, border_thickness: int = 0):
    """Generates a single ArUco marker image and saves it to the specified directory.

    If the marker image already exists, the user is prompted to decide whether to overwrite it, skip it, or keep both versions.

    :param dict: The ArUco dictionary to use for marker generation.
    :param marker_id: The ID of the marker to generate.
    :param marker_size_px: The size of the marker image in pixels. This should be a multiple of the marker's dimension. Default is 420.
    :param inverted: If True, the marker image will be inverted (black on white + white border). Default is False.
    :param border_thickness: The thickness of the border to add to the marker image. Default is 0 (no border).
    :raises ValueError: If the marker ID is out of range for the specified dictionary.
    :raises OSError: If the save directory cannot be created or is not a directory.
    """

    # Get the marker's dimension and the dictionary capacity
    dict_attribs = get_dict_attribs(dict)
    marker_dimension, dict_cap = dict_attribs if dict_attribs is not None else (0, 0)

    # Run preliminary checks
    can_run = prelim_check(dict_cap, marker_dimension, 1, marker_size_px)
    if not can_run:
        print("[FAILED] Generation aborted: Preliminary checks failed.")
        return
    print("[SUCCESS] Preliminary checks passed.")

    # Check if the marker ID is within the valid range for the dictionary
    if not (0 <= marker_id <= dict_cap):
        print(f": [Error] Marker ID must be in the range 0 to {dict_cap}.")
        print("[FAILED] Generation aborted: Marker ID out of range.")
        return

    # Get the ArUCo Dictionary object for the specified dictionary ID
    aruco_dict = aruco.getPredefinedDictionary(dict)
    # Generate the marker image
    action = process_single_marker(aruco_dict, marker_id, marker_size_px, inverted, border_thickness)
    # Inform the user about the action taken
    match action:
        case FileAction.CREATE:
            print(f"[DONE] Marker {marker_id} generated and saved to directory '{SAVE_DIR}'.")
        case FileAction.OVERWRITE:
            print(f"[DONE] Marker {marker_id} overwritten.")
        case FileAction.SKIP:
            print("[DONE] File skipped. No image generated.")
        case FileAction.KEEP_BOTH:
            print(f"[DONE] Marker {marker_id} saved as a new file.")

def generate_marker_multi(dict: int, marker_count: int, marker_size_px: int = 420, inverted: bool = False, border_thickness: int = 0):
    """Generates ArUco marker images in bulk and saves them to the specified directory.
    
    If the marker images already exist, the user is prompted to decide whether to overwrite all, skip all, keep both versions or decide per marker.
    
    :param dict: The ArUco dictionary to use for marker generation.
    :param marker_count: The number of markers to generate.
    :param marker_size_px: The size of the marker image in pixels. This should be a multiple of the marker's dimension. Default is 420.
    :param inverted: If True, the marker image will be inverted (black on white + white border). Default is False.
    :param border_thickness: The thickness of the border to add to the marker image. Default is 0 (no border).
    """

    # Get the marker's dimension and the dictionary capacity
    dict_attribs = get_dict_attribs(dict)
    marker_dimension, dict_cap = dict_attribs if dict_attribs is not None else (0, 0)

    # Run preliminary checks
    can_run = prelim_check(dict_cap, marker_dimension, marker_count, marker_size_px)
    if not can_run:
        print("[FAILED] Generation aborted: Preliminary checks failed.")
        return
    print("[SUCCESS] Preliminary checks passed.")

    # Ask for confirmation before proceeding
    print(f"[Summary] Will generate {marker_count} markers with")
    print(f"--image-size: {marker_size_px}px --inverted: {inverted} --border: {border_thickness if border_thickness > 0 else 'False'}")
    confirm = input(f">> Continue? (y/n): ").lower()
    if confirm == 'n':
        print("[EXITED] User cancelled generation.")
        return
    print(f"[STARTED] Generating {marker_count} markers...")

    # Create a set to store existing marker IDs
    existing_markers_ids = set()
    # Prelim check ensures the directory exists
    dir_contents = os.listdir(SAVE_PATH)
    pattern = REGEX_INVERT if inverted else REGEX
    # Check for existing markers in the directory
    for dir in dir_contents:
        match = re.match(pattern, dir)
        if match is not None:
            existing_markers_ids.add(int(match.group(1)))
    
    # Limit the marker count to the dictionary capacity
    marker_count = min(dict_cap, marker_count)
    # Spread the chosen markers evenly across the dictionary
    step = int((dict_cap - 1) / (marker_count - 1))
    # Check if any of the existing markers conflict with the new markers
    conflicting_markers = [i for i in range(0, dict_cap, step) if i in existing_markers_ids]

    operation = Operation.NO_OP
    options = [Operation.OVERWRITE, Operation.SKIP, Operation.KEEP_BOTH, Operation.DECIDE_PER_MARKER]
    # If there are any existing markers that conflict with the new markers, prompt the user
    if len(conflicting_markers) > 0:
        print(f": [Alert] The following markers already exist and may be overwritten: {conflicting_markers}. What would you like to do?")
        opInput = input(f">> (o)verwrite all / (s)kip all / (k)eep both for all / (d)ecide per marker: ").lower()
        while opInput not in options:
            print(f": [Error] Command '{opInput}' is not a valid option.")
            opInput = input(f">> (o)verwrite all / (s)kip all / (k)eep both for all / (d)ecide per marker: ").lower()
        operation = Operation[opInput]

    # Get the ArUco Dictionary object for the specified dictionary ID
    aruco_dict = aruco.getPredefinedDictionary(dict)
    iteration, generated, skipped, overwritten = 0, 0, 0, 0
    for i in range(0, dict_cap, step):
        # Generate the marker image
        action = process_single_marker(aruco_dict, i, marker_size_px, inverted, border_thickness, operation)
        iteration += 1
        match action:
            case FileAction.CREATE:
                generated += 1
                print(f": [{iteration}/{marker_count}] Marker {i} generated.")
            case FileAction.OVERWRITE:
                overwritten += 1
                generated += 1
                print(f": [{iteration}/{marker_count}] Marker {i} overwritten.")
            case FileAction.SKIP:
                skipped += 1
                print(f": [{iteration}/{marker_count}] File skipped.")
            case FileAction.KEEP_BOTH:
                generated += 1
                print(f": [{iteration}/{marker_count}] Marker {i} saved as a new file.")
        time.sleep(0.2)
    
    print(f"[DONE] {generated if generated > 0 else "No"} marker{"" if generated == 1 else "s"} generated. {skipped if skipped > 0 else "No"} marker{"" if skipped == 1 else "s"} skipped. {overwritten if overwritten > 0 else "No"} marker{"" if overwritten == 1 else "s"} overwritten.")

def prelim_check(dict_capacity: int, marker_dimension: int, marker_count: int, marker_size_px: int) -> bool:
    """Performs preliminary checks before generating markers.
    
    Checks if the dictionary exists, if the marker count is valid, and if the marker size is a multiple of the marker dimension.
    
    :param dict_capacity: The capacity of the dictionary (number of markers).
    :param marker_dimension: The dimension of the markers in the dictionary.
    :param marker_count: The number of markers to generate.
    :param marker_size_px: The size of the marker image in pixels.
    :return: True if all checks pass, False otherwise.
    
    """

    print(f"[STARTED] Running preliminary checks for marker generation...")

    if dict_capacity is None or marker_dimension is None:
        print(": [Error] Dictionary not found.")
        return False

    if dict_capacity == 0:
        print(": [Error] Dictionary does not contain any markers to generate.")
        return False
    
    # Create the directory if it doesn't exist
    if not os.path.exists(SAVE_PATH):
        try:
            os.makedirs(SAVE_PATH)
        except OSError as err:
            print(f": [Error] Could not create directory {SAVE_DIR}: {err}")
            return False
    # Check if the save path is a directory
    elif not os.path.isdir(SAVE_DIR):
        print(f": [Error] '{SAVE_DIR}' is not a directory.")
        return False

    if marker_count < 1:
        print(": [Alert] marker_count must be greater than 0 in order to generate markers.")
    elif marker_count > dict_capacity:
        print(f": [Alert] Attempting to generate more markers than available ({dict_capacity}). Marker count will be updated.")
        print(": [Info] If you need more markers, pick a larger dictionary.")

    # Check if the marker size is a multiple of the marker dimension and update it if necessary
    if (marker_size_px % marker_dimension) != 0:
        og_marker_size_px = marker_size_px
        marker_size_px = marker_dimension * np.ceil(marker_size_px / marker_dimension)
        print(f": [Alert] Bad image size: {og_marker_size_px}. Must be a multiple of marker dimension. Resized to {marker_size_px}.")
        print(": [Info] To prevent resizing, make sure the image size is a multiple of the marker dimension.")
    
    return True

def process_single_marker(dict: aruco.Dictionary, marker_id: int, marker_size_px: int, inverted: bool, border_thickness: int, operation: Operation = Operation.NO_OP) -> int:
    """Processes a single marker image generation request.
    
    :param dict: The ArUco dictionary to use for marker generation.
    :param marker_id: The ID of the marker to generate.
    :param marker_size_px: The size of the marker image in pixels.
    :param inverted: Whether the marker image should be inverted (black on white w/ white border).
    :param border_thickness: The thickness of the border to add to the marker image.
    :param operation: The operation to perform if the marker image already exists. If not set, the user will be prompted for an action.
    :return: One of [FileAction.CREATE, FileAction.OVERWRITE, FileAction.SKIP, FileAction.KEEP_BOTH] representing the action taken.
    """
    
    # Construct the filename based on the marker ID and whether it is inverted
    filename = f"{FILENAME_BASE}{marker_id}{INVERTED_TAG if inverted else ""}{FILE_EXTENSION}"
    filepath = os.path.join(SAVE_PATH, filename)
    
    # If there are no conflicts with existing files, simply write the image
    if not os.path.exists(filepath):
        writeImage(dict, marker_id, marker_size_px, inverted, border_thickness, filepath)
        return FileAction.CREATE
    
    # If no operation is specified, or if the operation should be 
    # decided per marker, prompt the user for an action
    # This needs to be done first, so we can then process the chosen operation as if it was already set
    if operation == Operation.NO_OP or operation == Operation.DECIDE_PER_MARKER:
        options = [Operation.OVERWRITE, Operation.SKIP, Operation.KEEP_BOTH]
        print(f": [Alert] Marker {marker_id} already has an associated image in directory '{SAVE_DIR}'. What would you like to do?")
        opInput = input(f">> (o)verwrite / (s)kip / (k)eep both: ").lower()
        while opInput not in options:
            print(f": [Error] Command '{opInput}' is not a valid option.")
            opInput = input(f">> (o)verwrite / (s)kip / (k)eep both: ").lower()
        operation = Operation[opInput]
    
    # If we need to keep both versions, we need to add a version number to the filename
    if operation == Operation.KEEP_BOTH:
        # Start with version 1 and increment until a unique filename is found
        version = 1
        while os.path.exists(os.path.join(SAVE_PATH, filename)):
            filename = f"{FILENAME_BASE}{marker_id}{INVERTED_TAG if inverted else ""}_{version}{FILE_EXTENSION}"
            version += 1
        filepath = os.path.join(SAVE_PATH, filename)
        writeImage(dict, marker_id, marker_size_px, inverted, border_thickness, filepath)
        return FileAction.KEEP_BOTH
    
    # If we need to overwrite the existing file, simply write the image
    if operation == Operation.OVERWRITE:
        writeImage(dict, marker_id, marker_size_px, inverted, border_thickness, filepath)
        return FileAction.OVERWRITE
    
    # If we need to skip the existing file, do nothing
    return FileAction.SKIP

def writeImage(dict, marker_id, marker_size_px, inverted, border_thickness, filepath):
    marker = generate_marker_image(dict, marker_id, marker_size_px, inverted)
    # Add border in inverted colour, if specified
    if border_thickness > 0:
        # Add additional border to the marker image
        # If the marker is inverted, the border bits will be white => additional border should be black
        # If the marker is not inverted, the border bits will be black => additional border should be white
        border_colour = (0, 0, 0) if inverted else (255, 255, 255)
        marker = cv2.copyMakeBorder(marker, border_thickness, border_thickness, border_thickness, border_thickness, cv2.BORDER_CONSTANT, value=border_colour)
    cv2.imwrite(filepath, marker)

def generate_marker_image(dict: aruco.Dictionary, marker_id: int, marker_size_px: int, inverted: bool):
    # Memalloc marker image
    marker_image = np.zeros((marker_size_px, marker_size_px, 1), dtype=np.uint8)
    # Generate the marker image
    marker_image = aruco.generateImageMarker(dict, marker_id, marker_size_px, marker_image, 1)
    # Invert the marker image if needed
    if inverted:
        marker_image = cv2.bitwise_not(marker_image)
    return marker_image

def get_dict_attribs(dict: int) -> list[int] | None:
    dict_attribs = ARUCO_DICTIONARIES.get(dict)
    return dict_attribs

def main():
    dict = aruco.DICT_5X5_50
    
    print("Welcome to the ArUco marker generator!")
    print("=========================================================")
    print(f"Markers will be saved in the directory '{SAVE_PATH}'")
    print("You can generate a single marker or multiple markers at once.")
    print("=========================================================")
    count, marker_size_px, inverted, border_thickness = None, None, None, None
    while count is None:
        try:
            count = int(input(">> How many markers would you like to generate? (0 to exit): "))
            if count < 0:
                count = None
            elif count == 0:
                print("[EXITED] User cancelled generation.")
                exit(0)
        except ValueError:
            print(": [Error] Marker count must be a positive integer.")
    while marker_size_px is None:
        try:
            marker_size_px = int(input(">> Set the marker image size (in pixels) or press Enter to use the default (420): ") or 420)
            if marker_size_px <= 0:
                marker_size_px = None
        except ValueError:
            print(": [Error] Marker size must be a positive integer. If you want to use the default size, press Enter without typing anything.")
    while inverted is None:
        inverted_input = input(">> Invert the marker image? (y/n, default: n): ").lower()
        if inverted_input in ['y', 'yes']:
            inverted = True
        elif inverted_input in ['n', 'no', '']:
            inverted = False
        else:
            print(": [Error] Invalid input. Please enter 'y' or 'n'.")
    while border_thickness is None:
        try:
            border_thickness = int(input(">> Set the border thickness (in pixels) or press Enter to generate without border: ") or 0)
            if border_thickness < 0:
                border_thickness = None
        except ValueError:
            print(": [Error] Border thickness must be a non-negative integer. If you want to use the default size, press Enter without typing anything.")

    # Generate markers
    generate_marker_multi(dict, count, marker_size_px=marker_size_px, inverted=inverted, border_thickness=border_thickness)

if __name__ == "__main__":
    main()