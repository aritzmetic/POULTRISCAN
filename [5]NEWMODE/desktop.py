# desktop.py

import os
import stat
import sys

# --- Configuration ---
USER_HOME = "/home/pi"
PROJECT_NAME = "poultriscan-env"

# --- Configuration for [1]APP ---
APP_FOLDER = "[1]APP" 
APP_NAME = "PoultriScan App" 
DESKTOP_FILENAME = "PoultriScan_App.desktop"
# --- End Configuration ---

# --- Generated Paths ---
# The directory where the [1]APP/app.py script is located
PROJECT_DIR = os.path.join(USER_HOME, PROJECT_NAME, APP_FOLDER)

# Path to the python executable in your virtual environment
VENV_PYTHON = os.path.join(USER_HOME, PROJECT_NAME, "bin", "python")

# Path to the specific app.py you want to run
APP_SCRIPT = os.path.join(PROJECT_DIR, "app.py")

# --- !! CORRECTED ICON PATH !! ---
# Now points to the logo inside the [1]APP folder
ICON_PATH = os.path.join(PROJECT_DIR, "logo.png")

# Path for the new desktop icon
DESKTOP_FILE_PATH = os.path.join(USER_HOME, "Desktop", DESKTOP_FILENAME)
# --- End Generated Paths ---

def create_desktop_icon():
    """
    Creates a .desktop file on the user's desktop to launch the
    main PoultriScan application.
    """
    
    print(f"Starting creation for: {APP_NAME}...")

    # 1. Check that all required paths exist
    print("Checking paths...")
    paths_to_check = {
        "Virtual Env Python": VENV_PYTHON,
        "Application Script": APP_SCRIPT,
        "Application Directory": PROJECT_DIR,
        "Icon File": ICON_PATH  # Added check for the icon
    }
    
    for name, path in paths_to_check.items():
        if not os.path.exists(path):
            print(f"--- ERROR ---")
            print(f"{name} not found at expected path:")
            print(f"{path}")
            print("\nPlease check the Configuration variables or your file locations.")
            return
    
    print("All required paths seem valid.")

    # 2. Define the command to run the app
    exec_command = f'sh -c "cd {PROJECT_DIR} && export QT_IM_MODULE=none && {VENV_PYTHON} {APP_SCRIPT}"'

    # 3. Define the content for the .desktop file
    desktop_content = f"""[Desktop Entry]
Version=1.0
Name={APP_NAME}
Comment=Run the main PoultriScan application
Exec={exec_command}
Icon={ICON_PATH}
Terminal=false
Type=Application
Categories=Application;Science;Utility;
"""

    # 4. Write the file and make it executable
    try:
        desktop_dir = os.path.dirname(DESKTOP_FILE_PATH)
        if not os.path.exists(desktop_dir):
            os.makedirs(desktop_dir)
            print(f"Created directory: {desktop_dir}")

        # Overwrite any existing file
        with open(DESKTOP_FILE_PATH, "w") as f:
            f.write(desktop_content)
        
        print(f"\nSuccessfully created file: {DESKTOP_FILE_PATH}")

        # 5. Make the file executable
        current_permissions = os.stat(DESKTOP_FILE_PATH).st_mode
        os.chmod(DESKTOP_FILE_PATH, current_permissions | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        
        print("Made the desktop file executable.")

        # 6. Mark the file as 'trusted' by the desktop
        # This command prevents the "Untrusted application launcher" pop-up
        os.system(f'gio set "{DESKTOP_FILE_PATH}" metadata::trusted true')
        print("Marked file as 'trusted' to avoid pop-up.")

        print("\n--- SUCCESS ---")
        print(f"Desktop icon '{APP_NAME}' has been created/updated.")
        print("You can now double-click it to run.")

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred while writing the file: {e}")

if __name__ == "__main__":
    create_desktop_icon()