BatteryUtils: Your Comprehensive E-Bike/E-Scooter Battery & Ride Management Tool
=================================================================================
1.09.02 
Updated 02/07/2026
<br>BatteryUtils is a desktop application designed to help e-bike/e-scooter enthusiasts manage their battery health, predict range, and log their rides efficiently. It combines essential calculations with ride tracking, all within a user-friendly interface.</br>

* * *
<img align="center" width="900" src="https://github.com/Gobytego/BatteryUtils/blob/main/screenshot01.png">

<img align="center" width="900" src="https://github.com/Gobytego/BatteryUtils/blob/main/screenshot002.png">

Key Features:
-------------

### 1\. Multi-Profile Management: 

*   **Create, Save, Load, and Delete Profiles:** Easily set up and switch between different e-bike or battery configurations. Perfect for users with multiple bikes, different battery packs, or who want to track changes over time.
*   **Persistent Settings:** All your profile data, including logged rides, is automatically saved and loaded, so you never lose your information.

### 2\. Battery Calculator & Range Prediction:

*   **Detailed Battery Input:** Enter your battery's nominal voltage, capacity (in Wh or Ah), and charger rate. The app intelligently infers the number of cells in series (S) and displays the min/max voltage range.
*   **Dynamic Range Estimation:** Get an estimated full range based on your battery's capacity and your riding style.
*   **Real-time Remaining Range:** Input your current battery percentage or voltage, and the app calculates your estimated remaining range.
*   **Preferred Cutoff Range:** Define a "preferred low battery cutoff" percentage, and the app will tell you the estimated range you have until you reach that cutoff, both from your current state and from a full charge.
*   **Efficiency Metrics:** See your bike's estimated Miles/Wh and Miles/Ah for better understanding of efficiency.
*   **Driving Style & Wheel Diameter Adjustment:** The range calculation adapts based on your selected driving style (Aggressive, Casual, Eco) and your wheel diameter, providing more accurate predictions tailored to your setup.
*   **Efficiency Source Indicator:** Clearly shows whether your range calculations are based on "Predicted" efficiency (from your inputs) or "Logged" efficiency (from your ride history).

### 3\. Advanced Charging Calculations:

*   **Time to Full Charge:** Calculates the estimated time required to fully charge your battery from its current state.
*   **Charge Throttle Simulation:** Account for charger throttling (e.g., charging at a lower rate for the last 10% of charge) to get a more realistic total charge time.
*   **BMS Conditioning Time:** Factor in additional time for Battery Management System (BMS) balancing/conditioning at the end of the charge cycle.
*   **Percentage After Duration:** Predict what percentage your battery will reach after a specified charging duration.

### 4\. Ride Log & Efficiency Tracking:

*   **Comprehensive Ride Logging:** Record details for each ride, including date, distance, start/end battery state (percentage or voltage), and riding style.
*   **Automatic Efficiency Calculation:** For each logged ride, the app automatically calculates the "Wh Consumed" and "Wh/mile" (efficiency).
*   **Average Efficiency:** Get an overall average Wh/mile and Miles/Wh across all your logged rides for the current profile.
*   **Apply Logged Efficiency:** Directly apply the efficiency from your last ride or your overall average to the main calculator for more personalized range predictions.
*   **Data Management:** Easily delete selected ride entries from your log.
*   **Import/Export Ride Logs:** Export your ride log to a JSON file for backup or analysis, and import existing logs.
*   **SuperCycle App Integration:** Conveniently import ride data directly from JSON files exported by the SuperCycle App, pre-populating distance and date for quick logging.

### 5\. Interactive Charge Timer:

*   **Countdown/Count-up Timer:** Set a specific charge time or let it count up to track charging duration.
*   **Real-time Battery State Estimation (NEW!):** While the timer runs, the app provides real-time estimates of your battery's current percentage and voltage, along with estimated remaining range and range to cutoff, based on your configured battery and charging parameters. This helps you monitor progress without needing external tools.

### 6\. Detailed Breakdown & Export:

*   **Vehicle Breakdown Section:** A dedicated panel provides a clear summary of all your entered and derived battery, motor, and charging parameters.
*   **Export Breakdown:** Export a detailed text file of your current vehicle configuration and calculated results for easy sharing or record-keeping.

BatteryUtils is a versatile tool designed to give e-bike owners greater insight and control over their battery's performance and longevity.



to run the batteryutils.py in python you will need the following installed:
 - pyqt6

so far this has only been tested on Linux if anyone wants to test on Mac or Windows be my guest.  

