from tkinter import Tk, filedialog, simpledialog, Label, Entry, Button, messagebox
import cv2
import numpy as np
import os
import time
import math

# Edge detection - outlines moving pixels
def canny_edge_detection(image):
    edges = cv2.Canny(image, 5, 300) # lower and upper bounds for detecting what's an edge or not
    return edges

# Controls the speed/jumpiness of the motion tracking algorithm
def exponential_moving_average(current, previous, alpha):
    if previous is None:
        return current
    else:
        return alpha * current + (1 - alpha) * previous

# Ignores outlying points not caught by background subtracking since motion tracking is based off centroids
def filter_outliers(points, current_point, max_distance):
    filtered_points = []
    for point in points:
        distance = np.linalg.norm(np.array(current_point) - np.array(point))

        # If the distance to a detected point is not an outlier, consider it in the centroid calculation
        if distance <= max_distance:
            filtered_points.append(point)

    return filtered_points

# Displays pixel coordinates in a separate widow when the user hovers over the first frame window
def hover_effect(event, x, y, flags, param):
    global coord_window
    if event == cv2.EVENT_MOUSEMOVE:
        coord_window = np.zeros((100, 300, 3), np.uint8)  # Clear the window
        cv2.putText(coord_window, f"x: {x}, y: {y}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.imshow("Coordinates", coord_window)

# Export and save data to a CSV in the video's directory with user-defined name
def save_csv(speed_data, video_filename):
    directory = os.path.dirname(video_filename)
    default_csv_filename = f"speed_data - {os.path.basename(video_filename)}.csv"
    csv_filename = filedialog.asksaveasfilename(initialdir=directory, initialfile=default_csv_filename, title="Save CSV", filetypes=[("CSV files", "*.csv")])
    if not csv_filename:
        print("CSV save canceled.")
        return

    with open(csv_filename, 'w') as f:
        f.write("Frame #, x, y, Angle to Center, Rotations, Seconds elapsed\n") # Headers
        for data in speed_data:
            #          Frames          X               Y               Angle      Rotations  Seconds Elapsed
            f.write(f"{int(data[0])}, {int(data[1])}, {int(data[2])}, {data[3]}, {data[4]}, {data[5]}\n")


# Get user inputs for background subtraction, alpha value, and outlier distance with a GUI window
def get_input_values():
    values = {}
    root = Tk()
    root.title("Input (0 - 100)")
    
    # Function to validate input values
    def validate_input(value):
        try:
            float_val = float(value)
            if 0 <= float_val <= 100:
                return True
            else:
                return False
        except ValueError:
            return False

    # Threshold for ignoring background noise. Lower = Less accurate but skips less frames | Higher = more accurate but skips frames more often
    Label(root, text="Background Subtraction Strength").grid(row=0, column=0)
    values['threshold'] = Entry(root)
    values['threshold'].grid(row=0, column=1)
    
    # Controls the speed of the motion tracking algorithm. Lower = slower but smoother | Higher = faster but jumpier
    Label(root, text="Motion Tracking Speed").grid(row=1, column=0)
    values['alpha'] = Entry(root)
    values['alpha'].grid(row=1, column=1)
    
    # Determines how far a pixel has to be to be considered an outlier. Outliers are ignored in centroid calculation
    Label(root, text="Maximum Outlier Distance").grid(row=2, column=0)
    values['max_distance'] = Entry(root)
    values['max_distance'].grid(row=2, column=1)

    def submit_input(event=None):
        input_values = {key: entry.get() for key, entry in values.items()}
        if '' in input_values.values():
            messagebox.showerror("Error", "Please fill all the input fields.")
        else:
            if all(validate_input(entry.get()) for entry in values.values()):
                root.quit()
            else:
                messagebox.showerror("Error", "Please enter valid values between 0 and 100.")

    # Bind the Enter key to submit the input values
    root.bind('<Return>', submit_input)

    Button(root, text="Submit", command=submit_input).grid(row=3, columnspan=2)
    Button(root, text="Cancel", command=root.quit).grid(row=4, columnspan=2)

    root.mainloop()

    if not all(values.values()):
        return None
    
    input_values = {key: float(entry.get()) for key, entry in values.items()} # {Background subtraction, alpha, outlier distance}
    root.destroy()
    return input_values

def main():
    # Check if a file is not selected
    video_path = filedialog.askopenfilename(title="Select MP4 video file", filetypes=[("MP4 files", "*.mp4")])
    if not video_path:
        print("No file selected.")
        return

    # Check if inputs are empty
    input_values = get_input_values()
    if input_values is None:
        print("Input canceled. Exiting...")
        return
    
    # Check if video cannot be opened
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Unable to open video file.")
        return

    # Check if frames can be read
    ret, frame = cap.read()
    if not ret:
        print("Error: Unable to read video frame.")
        return

    video_filename = os.path.splitext(os.path.basename(video_path))[0]

    # User inputs (1st window)
    # 30 20 20 for sample 3-3
    user_threshold = input_values['threshold'] * 2
    alpha_value = input_values['alpha'] / 100.00
    max_distance = input_values['max_distance']

    frame_rate = cap.get(cv2.CAP_PROP_FPS) # Get framerate from cv2
    frame_delay = int(1000 / frame_rate)  # Calculate delay based on original frame rate
    frame_count = 1  # Initialize frame count
    prev_rotated_frame = 0  # Frame count when last rotation occurred
    prev_frame_time = None 
    paused = False  # Flag to track if video is paused


    motion_detected = False  # Flag to track motion detection
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=user_threshold, detectShadows=False) # CV2 function to subtract background noise

    center_point = None # X, Y coordinate of the center reference point
    angle_to_center = None  # Angle from the center point to the tracked point
    smoothed_loc = None # Smoothed position of the motion tracked point
    rotations = 0  # Initialize rotation count
    speed_data = [] # All final calcs

    # Paused first frame window to help choose the center of rotation
    paused_frame_window = "Paused First Frame"
    cv2.namedWindow(paused_frame_window)
    cv2.moveWindow(paused_frame_window, 500, 30)
    cv2.imshow(paused_frame_window, frame)
    
    # Coord window to display cursor coordinates
    global coord_window
    coord_window = np.zeros((100, 300, 3), np.uint8)
    cv2.imshow("Coordinates", coord_window)
    cv2.setMouseCallback(paused_frame_window, hover_effect)

    # Display the paused first frame window, coordinate input window, and coordinate display window
    while True:
        start_frame_time = time.time()

        ret, frame = cap.read()
        if not ret:
            break

        # Display paused first frame and input box window
        cv2.imshow(paused_frame_window, frame)
        cv2.setMouseCallback(paused_frame_window, hover_effect)

        # Wait for user input in input box
        center_input_text = simpledialog.askstring("Input Pixel Coordinates", "Enter pixel coordinates of the center of rotation (x, y):")

        # If canceled, force quit
        if center_input_text is None:  
            break
        
        # If valid coordinates, read input and set center coordinates
        if center_input_text:
            try:
                cx, cy = map(int, center_input_text.split(','))
                center_point = (cx, cy)
                cv2.destroyAllWindows()  # Close windows when coordinates are submitted
                break
            except ValueError:
                messagebox.showerror("Error", "Invalid input format. Please enter coordinates separated by comma.")

        if cv2.waitKey(frame_delay) & 0xFF == ord('q'):
            break

    # After inputs are successfully submitted
    # Iterate every frame of the video
    while True:
        start_frame_time = time.time()

        # If video is not paused, process the frame
        if not paused:  
            ret, frame = cap.read()
            if not ret:
                break

            # Apply background subtraction to edge detection window
            fg_mask = bg_subtractor.apply(frame)
            edges = canny_edge_detection(fg_mask)
            cv2.imshow("Edge Detection", edges)

            # Calculate centroid of white pixels
            white_pixels = np.where(edges == 255)
            if len(white_pixels[0]) > 0:
                motion_detected = True  # Motion detected in this frame
                centroid_x = int(np.mean(white_pixels[1]))
                centroid_y = int(np.mean(white_pixels[0]))
                current_loc = (centroid_x, centroid_y)
            
            # When there are no edges to detect
            else:
                motion_detected = False
                cv2.imshow(video_filename, frame)  # Show original frame without drawing
                continue

            # Don't crash if center point is not detected somehow
            if center_point is None:
                center_point = current_loc
                cv2.circle(frame, center_point, 5, (0, 255, 0), -1)
                cv2.imshow(video_filename, frame)
                if cv2.waitKey(frame_delay) & 0xFF == ord('q'):
                    break
                continue
            
            # Further motion tracking smoothing
            if smoothed_loc is not None:
                white_pixels_filtered = filter_outliers(zip(white_pixels[1], white_pixels[0]), smoothed_loc, max_distance)
                if white_pixels_filtered:  # Check if the filtered list is not empty
                    white_pixels_filtered = np.array(white_pixels_filtered).T
                    centroid_x = int(np.mean(white_pixels_filtered[0]))
                    centroid_y = int(np.mean(white_pixels_filtered[1]))
                    current_loc = (centroid_x, centroid_y)
                else:
                    # No valid points found after filtering, use the previous smoothed_loc
                    current_loc = smoothed_loc

            smoothed_loc = exponential_moving_average(np.array(current_loc), smoothed_loc, alpha_value) # Update current position based on user inputted alpha value

            # Calculate actual seconds elapsed
            current_frame_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            elapsed_seconds = current_frame_time

            # Capture the angle from the center to the tracked point in the first frame to be used as a reference for counting rotations
            if angle_to_center is None:
                first_angle = math.degrees(math.atan2(cy - smoothed_loc[1], cx - smoothed_loc[0]))

            angle_to_center = math.degrees(math.atan2(cy - smoothed_loc[1], cx - smoothed_loc[0])) # Update angle every frame
            if smoothed_loc is not None:
                if prev_frame_time is not None and current_frame_time != prev_frame_time:
                    # Check for if the current angle is almost the same as the reference angle
                    if abs(angle_to_center - first_angle) < 3 and prev_rotated_frame > 31: # Wait 30 frames before starting the rotation check to avoid double counting
                        rotations += 1
                        prev_rotated_frame = 0 # Reset frame count since last rotation

                # Add all relevant calculations to a single array to be passed to the CSV 
                #                  Frame count                       x                y                angle                      rotations  seconds elapsed
                speed_data.append([cap.get(cv2.CAP_PROP_POS_FRAMES), smoothed_loc[0], smoothed_loc[1], round(angle_to_center, 2), rotations, round(elapsed_seconds, 2)])
                prev_frame_time = current_frame_time

            # Visualize coordinate positions and change color every rotation
            cv2.circle(frame, (cx, cy), 2, (255, 255, 255), -1) # Center point
            def color_switch(arg):
                # Reset color order every 5 rotations
                if arg >= 5:
                    arg = arg % 5
                switch = {
                    0: (0, 0, 255),     #red
                    1: (0, 255, 255),   #yellow
                    2: (0, 255, 0),     #green
                    3: (255, 200, 0),   #cyan
                    4: (255, 50, 150)   #purple
                }
                return switch.get(arg, (0, 0, 0))
            cv2.circle(frame, (int(smoothed_loc[0]), int(smoothed_loc[1])), 2, color_switch(rotations), -1)  # Motion tracked point
            cv2.line(frame, (cx, cy), (int(smoothed_loc[0]), int(smoothed_loc[1])), color_switch(rotations), 1) # Line from center to tracked point
        
            # Display current frame, seconds, angle, and rotations on the video playback
            cv2.putText(frame, f"Frame: {frame_count}", (0, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Seconds: {round(elapsed_seconds, 2)}", (0, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Angle: {int(angle_to_center)}", (0, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Rotation: {rotations}", (0, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_switch(rotations), 1)

            cv2.imshow(video_filename, frame) # Start the video playback

            # Calculate delay to maintain original frame rate
            end_frame_time = time.time()
            processing_time = end_frame_time - start_frame_time
            actual_delay = max(1, frame_delay - int(processing_time * 1000))

            if not motion_detected:
                time.sleep(0.01)  # Sleep for a short period if no motion detected

            # Update frame count after the frame is processed
            frame_count += 1
            prev_rotated_frame += 1 

        # Key inputs while the video is playing
        key = cv2.waitKey(actual_delay)
        if key == ord(' '): # Space to pause and unpause
            paused = not paused 
        if key == ord('q'): # q to quit
            break
    
    # End playback and close windows when video ends or is quit
    cap.release()
    cv2.destroyAllWindows()

    save_csv(speed_data, video_filename)

if __name__ == "__main__":
    main()