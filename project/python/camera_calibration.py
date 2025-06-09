import os
import cv2
import json

def process_snapshots(snapshots_dir):
    squares_vertically = 12
    squares_horizontally = 8
    square_size = 0.02  # Length of a square side in meters
    marker_size = 0.015  # Length of a marker side in meters
    dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_1000)
    board = cv2.aruco.CharucoBoard((squares_vertically, squares_horizontally), square_size, marker_size, dict)
    board.setLegacyPattern(True)
    detectorParams = cv2.aruco.DetectorParameters()
    charucoParams = cv2.aruco.CharucoParameters()
    charucoDetector = cv2.aruco.CharucoDetector(board, charucoParams, detectorParams)

    snapshots = [f for f in os.listdir(snapshots_dir) if f.endswith('.jpg')]

    if not snapshots:
        print(f"No snapshots found in {snapshots_dir}.")
        return
    
    all_charuco_corners = []
    all_charuco_ids = []

    for snapshot in snapshots:
        image_path = os.path.join(snapshots_dir, snapshot)
        image = cv2.imread(image_path)
        # image_copy = image.copy()
        if image is None:
            print(f"Could not read image {image_path}. Skipping.")
            continue
        
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        charuco_corners, charuco_ids, marker_corners, marker_ids = charucoDetector.detectBoard(gray_image)
        # marker_corners, marker_ids, _ = cv2.aruco.detectMarkers(gray_image, dict, parameters=params)
        
        print(f"Processing {snapshot}: Detected {len(marker_ids)} markers.")

        if len(marker_ids) > 0:
            # cv2.aruco.drawDetectedMarkers(image_copy, marker_corners, marker_ids)
            # cv2.imshow('Detected Markers', image_copy)
            # cv2.waitKey(0)
            success, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(marker_corners, marker_ids, gray_image, board, charuco_corners, charuco_ids)
            if success and len(charuco_ids) > 4:
                print(f"Snapshot {snapshot}: Found {len(charuco_ids)} Charuco corners and {len(charuco_ids)} Charuco ids.")
                all_charuco_corners.append(charuco_corners)
                all_charuco_ids.append(charuco_ids)
    
    if not all_charuco_corners or not all_charuco_ids:
        print("No valid Charuco corners or IDs found in the snapshots.")
        return
    
    print(charuco_corners, marker_corners);

    img_w, img_h, _ = image.shape
    success, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(all_charuco_corners, all_charuco_ids, board, (img_w, img_h), None, None)

    if not success:
        print("Camera calibration failed. Please check your snapshots and try again.")
        return
    
    # Save calibration data
    data = {
        "camera_matrix": camera_matrix.tolist(),
        "dist_coeffs": dist_coeffs.tolist(),
        "rvecs": [rvec.tolist() for rvec in rvecs],
        "tvecs": [tvec.tolist() for tvec in tvecs]
    }
    with open(os.path.join(os.getcwd(), 'calibration_data.json'), 'w') as save_file:
        json.dump(data, save_file, indent=4)

    # Iterate through displaying all the images
    for snapshot in snapshots:
        image_path = os.path.join(snapshots_dir, snapshot)
        image = cv2.imread(image_path)
        # undistorted_image = image.copy()
        undistorted_image = cv2.undistort(image, camera_matrix, dist_coeffs)
        cv2.imshow('Undistorted Image', undistorted_image)
        cv2.waitKey(0)

if __name__ == "__main__":
    snapshots_dir = os.path.join(os.getcwd(), "calibration_snapshots");
    process_snapshots(snapshots_dir)