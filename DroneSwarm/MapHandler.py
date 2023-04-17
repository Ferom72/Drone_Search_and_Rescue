import airsim
import numpy as np
import airsim
import math
from HelperFunctions import clusterHelper
import os
import cv2
from Constants import configDrones
import rospy
import time
import json
# import Constants
import Constants.ros as ros
from threading import Timer # Use for interval checks with minimal code
from threading import Thread # USe for important code running constantly
from std_msgs.msg import String
from std_srvs.srv import Trigger, TriggerResponse
from airsim_ros_pkgs.msg import droneData
from airsim_ros_pkgs.msg import updateMap
from airsim_ros_pkgs.srv import getDroneData, getDroneDataResponse
import threading
god = threading.Lock()

DETECTION_OUTPUT_SERIES = configDrones.DETECTION_OUTPUT_SERIES
GPS_GT = configDrones.GPS_GT
ZOOM_FACTOR = configDrones.ZOOM_FACTOR
MAX_PIX_COUNT = configDrones.MAX_PIX_COUNT
SPIRAL_LOCATION_1 = configDrones.SPIRAL_LOCATION_1

# Environmental Variables
# ros: topics
MAP_HANDLER_TOPIC = ros.MAP_HANDLER_TOPIC
FINAL_TARGET_POSITION = ros.FINAL_TARGET_POSITION
NEW_GPS_PREDICTION = ros.NEW_GPS_PREDICTION
UPDATE_DRONE_POSITION =  ros.UPDATE_DRONE_POSITION

PREVIOUS_GPS_POSITIONS = []
BATCH_DETECTIONS = []
BATCH_TIME = None
START_TIME = None
WOLF_COUNT = None

# Main Process Start ----------------------------------------------
def startMapHandler(wolfCount):
    print("Starting map handler")
    clearImg();
    global BATCH_TIME, START_TIME, WOLF_COUNT
    WOLF_COUNT = wolfCount
    BATCH_TIME = time.time()
    START_TIME = time.time()
    # Sets up empty arrays
    globalVarSetup(wolfCount)

    # Create Node for "ProximityOverseer" (Only one should exist)
    nodeName = "MapHandler"
    rospy.init_node(nodeName, anonymous = True)

    # Subscribe to map handler topic
    print("Subscribing to " + MAP_HANDLER_TOPIC)
    mapHandlerSub()

def globalVarSetup(droneCount):
    global PREVIOUS_GPS_POSITIONS
    PREVIOUS_GPS_POSITIONS = [None]*droneCount


# Connects subcriber listen to MapHandler
def mapHandlerSub():
    rospy.Subscriber(MAP_HANDLER_TOPIC, updateMap, updateResponseQ, ())
    # rospy.Subscriber(MAP_HANDLER_TOPIC, updateMap, updateMapHandler, ())
    rospy.spin()
# lat, lon
def clearImg():
    path = calcPath()
    if os.path.exists(path):
        os.remove(path)
    print("Remove image and recreate-------------------------------------------------------------------------------------------------------------------")
    image = np.zeros((MAX_PIX_COUNT, MAX_PIX_COUNT, 3))
    cv2.imwrite(path, image)
    time.sleep(3);

def updateResponseQ(data, args):
    with god:
        global BATCH_TIME, START_TIME, BATCH_DETECTIONS
        BATCH_DETECTIONS.append(data)
        timeDiff = time.time() - BATCH_TIME
        if (timeDiff > 5):
            path = calcPath()
            if os.path.exists(path):
                detectMap = cv2.imread(path)
            else:
                print("Start hadnling queue create new image++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++");
                detectionMap = np.zeros((pixCount, pixCount, 3))
                cv2.imwrite(path, detectionMap)
                detectMap = cv2.imread(path)

            # handle queue
            timeDiff = time.time() - START_TIME
            print("Start while ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++" + str(timeDiff));
            while (len(BATCH_DETECTIONS) > 0):
                dataStored = BATCH_DETECTIONS.pop(0)
                updateMapHandler(dataStored, detectMap)
            print("end while ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++");

            BATCH_TIME = time.time()
            cv2.imwrite(path, detectMap);
            print("imwrite complete");

def updateMapHandler(data, detectMap):
    print("In map handler")
    global PREVIOUS_GPS_POSITIONS
    # Gets the update type from the data
    updateMapType = data.updateType
    
    # Get the tuples
    wolfPositionTuple = GPSToTuple(data.wolfPosition)
    targetPositionTuple = GPSToTuple(data.targetPosition)

    # Add true target position
    if (updateMapType == FINAL_TARGET_POSITION):
        print("GOT FINAL TARGET")
        targetPositionTuple = GPSToTuple(data.targetPosition)
        handleTargetPosition(finalTargetPosition=targetPositionTuple, detectMap=detectMap)

    # Add gps prediction
    elif (updateMapType == NEW_GPS_PREDICTION):
        print("NEW GPS PREDICTION")
        # Gets necessary variables
        wolfPositionTuple = GPSToTuple(data.wolfPosition)
        predictedPosition = GPSToTuple(data.targetPosition)
        imageNumber = data.imageNumber
        vehicleName = data.wolfNumber
        previousGPSPostion = PREVIOUS_GPS_POSITIONS[vehicleName]

        # Calls drone and gps update functions
        handleDronePosition(lastWolfPos=previousGPSPostion, wolfPos=wolfPositionTuple, detectMap=detectMap, vehicleName=vehicleName)
        handleGPSPrediction(wolfPos=wolfPositionTuple, predPos=predictedPosition, imageNumber=imageNumber, vehicleName=vehicleName, detectMap=detectMap)

        # Updates previous gps into array
        PREVIOUS_GPS_POSITIONS[vehicleName] = wolfPositionTuple

    # Add drone position
    elif (updateMapType == UPDATE_DRONE_POSITION):
        print("UPDATING DRONE POSITION")
        # Gets necessary variables
        wolfPositionTuple = GPSToTuple(data.wolfPosition)
        vehicleName = data.wolfNumber
        previousGPSPostion = PREVIOUS_GPS_POSITIONS[vehicleName]

        # Calls drone and gps update functions
        handleDronePosition(lastWolfPos=previousGPSPostion, wolfPos=wolfPositionTuple, detectMap=detectMap, vehicleName=vehicleName)

        # Updates previous gps into array
        PREVIOUS_GPS_POSITIONS[vehicleName] = wolfPositionTuple

# Converts tuples
def GPSToTuple(GPS):
    return [GPS.latitude, GPS.longitude]

def handleTargetPosition(finalTargetPosition, detectMap):
    # path = calcPath()
    positionMapCenter = SPIRAL_LOCATION_1
    pixCount = MAX_PIX_COUNT
    FUDGE_FACTOR = ZOOM_FACTOR

    # calculate lat and lon offset
    LAT_OFFSET = (pixCount/2) - positionMapCenter[0]*FUDGE_FACTOR
    LON_OFFSET = (pixCount/2) - positionMapCenter[1]*FUDGE_FACTOR  

    # if os.path.exists(path):
    #     detectMap = cv2.imread(path)
    # else:
    #     print("Remove image handleTargetPosition-------------------------------------------------------------------------------------------------------------------");
    #     detectionMap = np.zeros((pixCount, pixCount, 3))
    #     cv2.imwrite(path, detectionMap)
    #     detectMap = cv2.imread(path)    

    cv2.circle(detectMap, (int(finalTargetPosition[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(finalTargetPosition[1]*FUDGE_FACTOR + LON_OFFSET))), 5, (0, 255, 0), 2) # draw ground truth postion
    # cv2.imwrite(path, detectMap)


def handleGPSPrediction(wolfPos, predPos, imageNumber, vehicleName, detectMap):
    # path = calcPath()
    positionMapCenter = SPIRAL_LOCATION_1
    pixCount = MAX_PIX_COUNT
    FUDGE_FACTOR = ZOOM_FACTOR
    targetPosition = configDrones.GPS_GT

    # calculate lat and lon offset
    LAT_OFFSET = (pixCount/2) - positionMapCenter[0]*FUDGE_FACTOR
    LON_OFFSET = (pixCount/2) - positionMapCenter[1]*FUDGE_FACTOR  

    # if os.path.exists(path):
    #     print("Path exists, doing read")
    #     detectMap = cv2.imread(path)
    # else:
    #     print("Remove image handleGPSPrediction-------------------------------------------------------------------------------------------------------------------");
    #     detectionMap = np.zeros((pixCount, pixCount, 3))
    #     cv2.imwrite(path, detectionMap)
    #     detectMap = cv2.imread(path)    

    cv2.line(detectMap, (int(wolfPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(wolfPos[1]*FUDGE_FACTOR + LON_OFFSET))), (int(predPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(predPos[1]*FUDGE_FACTOR + LON_OFFSET))), (255, 255, 0), 2) # draw line between wolf and prediction
    cv2.circle(detectMap, (int(wolfPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(wolfPos[1]*FUDGE_FACTOR + LON_OFFSET))), 2, (0, 0, 255), 2) # draw vehicle postion
    cv2.circle(detectMap, (int(predPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(predPos[1]*FUDGE_FACTOR + LON_OFFSET))), 2, (255, 0, 0), 2) # draw predicted gps postion for wolf
    cv2.circle(detectMap, (int(targetPosition[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(targetPosition[1]*FUDGE_FACTOR + LON_OFFSET))), 5, (0, 255, 0), 2) # draw ground truth postion
    cv2.putText(detectMap, str(imageNumber) + '_v' + str(vehicleName), (int(wolfPos[0]*FUDGE_FACTOR + LAT_OFFSET) + 1, abs(int(wolfPos[1]*FUDGE_FACTOR + LON_OFFSET)) + 1), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 1)
    # cv2.imwrite(path, detectMap)

def handleDronePosition(lastWolfPos, wolfPos, detectMap, vehicleName):
    # path = calcPath()
    positionMapCenter = SPIRAL_LOCATION_1
    pixCount = MAX_PIX_COUNT
    FUDGE_FACTOR = ZOOM_FACTOR
    targetPosition = configDrones.GPS_GT
    global WOLF_COUNT

    # calculate lat and lon offset
    LAT_OFFSET = (pixCount/2) - positionMapCenter[0]*FUDGE_FACTOR
    LON_OFFSET = (pixCount/2) - positionMapCenter[1]*FUDGE_FACTOR 

    # if os.path.exists(path):
    #     detectMap = cv2.imread(path)
    # else:
    #     detectionMap = np.zeros((pixCount, pixCount, 3))
    #     cv2.imwrite(path, detectionMap)
    #     detectMap = cv2.imread(path) 

    # if type(detectMap) == None or detectMap.size == 0:
    #     print("READ ERRORRRRRRRRRRRRRRR")
    #     return

    wolfColor = (255*( 1 - vehicleName/WOLF_COUNT), 140, 255*(vehicleName/WOLF_COUNT))

    if (lastWolfPos != None): 
        detectMap = cv2.line(detectMap, (int(wolfPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(wolfPos[1]*FUDGE_FACTOR + LON_OFFSET))), (int(lastWolfPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(lastWolfPos[1]*FUDGE_FACTOR + LON_OFFSET))), wolfColor, 1) # draw line between wolf and prediction
    detectMap = cv2.circle(detectMap, (int(wolfPos[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(wolfPos[1]*FUDGE_FACTOR + LON_OFFSET))), 1, wolfColor, 1) # draw vehicle postion
    detectMap = cv2.circle(detectMap, (int(targetPosition[0]*FUDGE_FACTOR + LAT_OFFSET), abs(int(targetPosition[1]*FUDGE_FACTOR + LON_OFFSET))), 5, (0, 255, 0), 2) # draw ground truth postion
    # detectMap=cv2.imwrite(path, detectMap)

def calcPath():
    return '/home/testuser/AirSim/PythonClient/multirotor/Drone-Search-and-Rescue-SD/DroneSwarm/detectionMaps' + '/' + 'detections' + '_' + DETECTION_OUTPUT_SERIES + '_' + '.jpeg' 