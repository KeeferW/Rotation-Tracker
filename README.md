
# Rotation Tracker

This program is made specifically for tracking rotating objects in circular motions. It saves data such as the angle from the center of rotation and the number of revolutions the object has made in a given time frame. 

This program uses OpenCV (cv2) for edge detection, motion tracking, visuals, background subtraction, and data displays; Tkinter for GUI components; and NumPy for math operations.

It is written in Python 3.11.7 using the Conda interpreter, and converted into an executable using cx_Freeze 3.1. No additional packages need to be installed, however, the .exe is dependant on its lib folder and .dll files to run.
## Algorithms

This program uses several methods to determine the area to motion track.

The program uses edge detection to outline moving pixels using intensity gradients. In this case we use the lower and upper bounds 5 and 300, resulting a large range of edges that are visible. Due to the low contrast nature of the high-speed video, this is a necessary limitation.

To combat the excessive noise the large range of intensity gradients can produce, we implement the Gaussian Mixture-based Background/Foreground Segmentation Algorithm (MOG Background Subtraction). This algorithm helps differentiate moving objects from static backgrounds and the strength of this algorithm can be controlled using a threshold variable set by the user.

However, this algorithm has a tendency to over compensate, removing pixels from moving objects and causing the motion tracker to fail and skip frames. This is where we apply an outlier filter to completely ignore all pixels outside of the motion tracked area, this is a variable the user can set as well.

To calculate which pixel the motion tracker should be positioned at, we use centroid calculations to find the average position of all the filtered edge detected pixels.

The program also makes use of the exponential smoothing algorithm to control the speed of the motion tracker. Varying rotation speeds
and framerates can cause the motion tracker to either be slower or jumpier than necessary. The user can set the alpha value for this algorithm which controls the rate at which the motion tracker changes position.

Lastly, we use the atan2 function of the python math library to calculate the angle from the motion tracked pixel to the center of rotation (chosen by the user). Every time the angle returns to its initial value (or comes within a threshold of 3 degrees), one rotation is counted. The angle will be outputted starting from 180 to -180 rotating counterclockwise. East: 180, North: 90, West: -180, South: -90.

Further OpenCV documentation can be found here:

Canny Edge Detection: https://docs.opencv.org/4.x/da/d22/tutorial_py_canny.html

Background Subtraction: https://docs.opencv.org/3.4/d8/d38/tutorial_bgsegm_bg_subtraction.html

CV2: https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html
## Usage and Functionality

When opened, the user is prompted to choose a .mp4 file from their file selector. Once chosen, the user will be prompted to input several values from 0 to 100.

Background Subtraction Strength: Threshold for ignoring background noise.
Lower = Weaker background cancellation, skips less frames
Higher = Stronger background cancellation, skips more frames

Motion Tracking Speed: Controls the speed of the motion tracking algorithm.
Lower = Slower, smoother
Higher = Faster, jumpier

Maximum Outlier Distance: Determines how far a pixel has to be to be considered an outlier. Outliers are ignored in centroid calculation.
Lower = More accurate, loses track of the moving object more often
Higher = Less accurate, can readjust itself with more leeway

Next, the user will be shown the first frame of the video and will be prompted to input the pixel coordinates of the center of rotation. When the user hovers over the frame window, the pixel coordinates of the crosshair's center will be displayed in a separate window. The user should input coordinates in X, Y format.

The original video and edge detection window will begin to play with the frame #, seconds elapsed, current angle to center, and rotations on the left side of the original video. The motion tracked pixel and the center of rotation will be shown as well with a line connecting them. The color of the motion tracked pixel, connecting line, and rotation counter will switch colors (red - yellow - green - cyan - purple) when a full rotation is counted.

The user can pause with spacebar, or quit early with q. 

Once the video ends or is quit early, the CSV file with all the data can be saved. It will be automatically named speed_data - {original video} to the video's directory, but can be renamed and moved before saving. 

The CSV is formatted as following: Frame, X, Y, Angle, Rotations, Seconds Elapsed. 