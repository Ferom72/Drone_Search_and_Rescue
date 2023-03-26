LOOP_NUMBER = 100000
MAX_TIME = 500
LOCAL_IP = "172.22.224.1"
MIN_CIRCLE_RADIUS_GPS = 0.00008983152373552244 # 10 in x direction converted to gps
MIN_CIRCLE_RADIUS_METERS = 6.988048291572515 # 10 in x direction converted to Meters
DISTANCE_LEAD_OVERSEER_GPS = MIN_CIRCLE_RADIUS_GPS * 2
MIN_DIFFRENCE_IN_RADIUS = MIN_CIRCLE_RADIUS_GPS * 0.2
REQUIRED_SEPERATION_PERCENT = 0.8
WOLF_SEARCH_REQUEST_HELP_DISTANCE_MULTIPLE = 1.5
CONSENSUS_DECISION_REQUEST_HELP_DISTANCE_MULTIPLE = 3
MAX_CONSENSUS_ITERATION_NUMBER = 7
CIRCLE_SPACING = MIN_CIRCLE_RADIUS_GPS * 0.2
MIN_CIRCLE_PADDING_FOR_SEARCH_HISTORY = MIN_CIRCLE_RADIUS_GPS * 1.1
MAX_WAYPOINT_SAVE_TIME = 100    # measured in seconds
CONSENSUS_THRESHOLD = 0.1
YOLO_CONFIDENCE = 0.1
