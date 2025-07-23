<H1>Changelog for ver 1.07.xx:</H1>

Core Functionality & UI Enhancements:

Profile Management:

Introduced the ability to create, save, load, and delete multiple user profiles, allowing for different vehicle or battery configurations.

Profiles are saved to and loaded from a BatteryUtils_Settings.json file.

Tabbed Interface:

The application was reorganized into a tabbed interface with "Battery Calculator," "Ride Log," and "About" sections for better navigation and organization.

Three-Column Layout:

The "Battery Calculator" tab was redesigned into a three-column layout: "Input," "Results," and "Breakdown" for a more structured and readable interface.

Battery Calculator Tab Improvements:

Dynamic Voltage Input:

The "Cells in Series (S)" input now dynamically appears only if the entered "Nominal Voltage (V)" cannot be automatically inferred (e.g., 48V implies 13S).

Flexible Current Battery State Input:

Added radio buttons to allow users to input their current battery state as either "Percentage (%)" or "Voltage (V)".

Enhanced Charging Options:

Preferred Low Battery Cutoff: Added an input for a preferred low battery cutoff percentage, with calculations for "Range to cutoff" and "Charge time from cutoff."

Charge Throttle Simulation: Introduced "Charge Throttle (%)" and "Throttled Rate (A)" inputs to simulate a reduced charging rate at higher battery percentages.

BMS Conditioning Time: Added an option to include "BMS Conditioning Time" (e.g., 15 min, 30 min, 1 hour) to the total charge time.

Charge Time Breakdown: The charge time calculation now provides a "Base Charge Time (to 100%)" and "Additional Time (due to options)" to show the impact of throttling and BMS conditioning.

Improved Efficiency Calculation & Display:

The "Miles/Wh" and "Miles/Ah" results were moved into the main "Range" group box for better visibility.

"Efficiency Source" Label: A label was added to clearly indicate whether the range calculations are using "Predicted" efficiency (based on driving style and wheel diameter) or "Logged" efficiency (from ride data).

"Reset Efficiency" Button: Reinstated this button within the "Range" group box to allow users to easily switch back to predicted efficiency.

New "Full Range to Cutoff" Metric:

A new result showing the estimated full range if the battery were only used down to the "Preferred Cutoff %" was added.

Ride Log Tab Features:

Comprehensive Ride Logging:

Expanded ride logging capabilities to include "Start Battery State" (percentage or voltage), "End Battery State" (percentage or voltage), "Wh Consumed," "Wh/mile," and "Riding Style" for each logged ride.

Ride Log Management:

Added functionality to delete selected ride entries from the log.

Efficiency Application from Log:

Introduced "Apply Last Ride Efficiency" and "Apply Average Efficiency" buttons to use historical ride data for range calculations on the "Battery Calculator" tab.

Data Import/Export:

Added "Export Ride Log" and "Import Ride Log" buttons to manage ride data as JSON files.

SuperCycle App Import: A dedicated "Import from SuperCycle App" button was added to parse JSON export files from the SuperCycle app, automatically populating relevant fields in the "Log New Ride" section.

Logged Rides Info Display:

A dedicated "Logged Rides Info" group box was added to the Breakdown column on the main "Battery Calculator" tab, displaying the last ride's efficiency and the overall average efficiency from all logged rides.

Charge Timer Enhancements:

Compact Display: The timer display was made more compact and visually appealing.

Estimated Battery State: Added a checkbox to show estimated battery percentage and voltage during the timer's operation, based on the initial charge state and calculated total charge time.

General Improvements:

Enhanced Error Handling: More robust error handling and informative message boxes for invalid inputs or calculation issues.

Improved UI Styling: Consistent styling for buttons and group boxes across the application.

Attribution and Links: The "About" tab was updated with Gobytego website and GitHub repository links, along with a section acknowledging and linking to the SuperCycle App
