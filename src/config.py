import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"
USER_SETTINGS_FILE = DATA_DIR / "user_settings.json"

#Mysql
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "root",
    "database": "mocap_db",
    "port": 3306,
    "raise_on_warnings": True,
    "use_pure": True
}

# Visualization defaults
DEFAULT_FRAME_RATE = 120.0
DEFAULT_CAMERA_DISTANCE = 10000
GRID_SIZE = 5000
GRID_SPACING = 400

# UI defaults
DEFAULT_WINDOW_WIDTH = 1250
DEFAULT_WINDOW_HEIGHT = 700
MIN_WINDOW_WIDTH = 1250
MIN_WINDOW_HEIGHT = 700

# File filters
C3D_FILE_FILTER = "C3D Files (*.c3d);;All Files (*)"

# Model output label keywords (for filtering)
MODEL_OUTPUT_KEYWORDS = (
    'angles', 'angle', 'power', 'force', 'moment', 
    'groundreaction', 'normalised', 'grf', 'centreofmass'
)
DEFAULT_VISIBLE_MARKERS = {
    'LFHD', 'RFHD', 'LBHD', 'RBHD', 'C7', 'T10', 'CLAV', 'STRN', 'RBAK',
    'LSHO', 'LUPA', 'LELB', 'LFRM', 'LWRA', 'LWRB', 'LFIN',
    'RSHO', 'RUPA', 'RELB', 'RFRM', 'RWRA', 'RWRB', 'RFIN',
    'LASI', 'RASI', 'LPSI', 'RPSI',
    'LTHI', 'LKNE', 'LTIB', 'LANK', 'LHEE', 'LTOE',
    'RTHI', 'RKNE', 'RTIB', 'RANK', 'RHEE', 'RTOE'
}