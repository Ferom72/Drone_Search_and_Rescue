# Wolf drone nodes
# TODO: (SlamMerge) topic
# TODO: Subscribes to (Command) topic
# TODO: Publish to (CommandResult) topic (may be removed as not critical)

# imports
import setup_path # If setup_path gives issue, comment out
import airsim
import rospy
import time
import json
import ast
import math
import math
from math import sqrt
# import constants
import Constants.configDrones as configDrones
import Constants.ros as ros
# import drone behavior
import DroneBehaviors.wolfSearchBehavior as wolfSearchBehavior;
from DroneBehaviors.lineBehavior import lineBehavior
# TODO: Investigate if we need to use a Lock while writing or reading global variables
from threading import Timer # Use for interval checks with minimal code
from threading import Thread # USe for important code running constantly
# TODO: Add custom message types
from std_msgs.msg import String
from std_srvs.srv import Trigger, TriggerResponse
from airsim_ros_pkgs.msg import droneData
from airsim_ros_pkgs.msg import droneData
from airsim_ros_pkgs.msg import requestLineBehavior
from airsim_ros_pkgs.msg import requestWolfSearchBehavior
from airsim_ros_pkgs.msg import requestConsensusDecisionBehavior
from airsim_ros_pkgs.srv import getDroneData
from airsim_ros_pkgs.srv import sendCommand
import ServiceRequestors.wolfGetWolfData as wolfService
import ServiceRequestors.instructWolf as instructWolf
import HelperFunctions.calcHelper as helper
import DroneBehaviors.collisionDetectionBehavior as collisionDetectionBehavior

# Environmental Variables
LOOP_NUMBER = configDrones.LOOP_NUMBER
MAX_TIME = configDrones.MAX_TIME
LOCAL_IP = configDrones.LOCAL_IP
COLLISION_MODE_TIME_LENGTH = configDrones.COLLISION_MODE_TIME_LENGTH
MAX_TURN_ANGLE = configDrones.MAX_TURN_ANGLE
# ros: topics
SLAM_MERGE_TOPIC = ros.SLAM_MERGE_TOPIC # TODO
WOLF_DATA_TOPIC = ros.WOLF_DATA_TOPIC
COMMAND_RESULT_TOPIC = ros.COMMAND_RESULT_TOPIC # TODO
COMMAND_TOPIC = ros.COMMAND_TOPIC # TODO
# ros: services: service calls should be in the ServiceRequesteros folder
PROXIMITY_WOLF_SERVICE = ros.PROXIMITY_WOLF_SERVICE
# dynamic services:
WOLF_DRONE_SERVICE = ros.WOLF_DRONE_SERVICE

# Internal Wolf Drone Memory Start -------------------------------------------
# Current pattern is ussing Global variable to allow access across threads (open to change)
# Global variables
DM_Drone_Name = None
DM_Wolfs_Cluster = [] # Drone will beassigned a group of drones to work with
WAYPOINT_COORDS = []
WAYPOINT_INDEX = 0
GROUP_0_SEARCH = 'Constants/Group0Spiral.txt'
GROUP_1_SEARCH = 'Constants/Group1Spiral.txt'
# Internal Wolf Drone Memory End -------------------------------------------
Line_Behavior = False
Cluster = ""
Task_Group = ""
Collision_Mode_Time = 0
# Memory for circle behavior
Wolf_Search_Behavior = False
Consensus_Decision_Behavior = False
Circle_Center_GPS = [] # gps cordinate
Circle_Radius_GPS = 0 # radius distance in gps
MIN_CIRCLE_RADIUS_GPS = 0.00008983152373552244 # 10 in x direction converted to gps
MIN_CIRCLE_RADIUS_METERS = 6.988048291572515 # 10 in x direction converted to Meters
Circle_Radius_Meters = 0 # radius distance in meters
Start_Time = 0 # time
Spread_Time = 0 #  time in seconds # time to get in position 
Search_Time = 0 #  time in seconds # time to search
End_Loop = False
NEARBY_DRONE_RADIUS = 0.0003
THRESHOLD = 16  # TODO: Needs to be scalable
COLLISION_DIRECTION_FACTOR = 10
# TODO: add tunning variables for behaviors (would be cool if we can train them)

# Main Process Start ----------------------------------------------
def wolfDroneController(droneName, droneCount):
    # set global vairable
    global DM_Drone_Name
    DM_Drone_Name = droneName
    global WAYPOINT_INDEX
    global End_Loop
    global Collision_Mode_Time

    # Sets global values for wolf cluster and coordinate
    wolfClusterCreation(droneName)
    droneBoundary = (int(droneCount) / 2)
    if (int(droneName) <= 2):
        readCoordFile(GROUP_0_SEARCH)
    else:
        readCoordFile(GROUP_1_SEARCH)

    # use this code to make print calls allowing you to know what process made the print statemnt
    debugPrint("Process started")

    # Create Node for wolf
    nodeName = "Wolf" + droneName
    rospy.init_node(nodeName, anonymous = True)
    debugPrint("Node initiated")

    # Start all threads here (if you have to make one somwhere else bring it up with the team)
    t = Thread(target = wolfServiceListeners, args=(droneName))
    t.start()
    t2 = Thread(target = endListener)
    t2.start()

    # Setup collision directory
    imgDir = collisionDetectionBehavior.setupCollisionDirectory(droneName)

    # Create topic publishers
    # (TODO: ADD IN SLAM MERGE AND COMMAND RESULT PUBLISHERS)
    wolfDataPublish = rospy.Publisher(WOLF_DATA_TOPIC, droneData, latch=True, queue_size=1)


    # Sets and connects to client and takes off drone
    client = takeOff(droneName)
    client.moveToZAsync(z=-3, velocity=8, vehicle_name = droneName).join()
    
    # start camera thread here
    t = Thread(target = wolfCameraDetection, args=(droneName))
    t.start()

    # Test Code startWolfSearch
    targetP = client.getMultirotorState(vehicle_name = "target")
    targetC = client.getMultirotorState(vehicle_name = "circle")
    # calc radius
    radiusC = abs(targetP.gps_location.longitude - targetC.gps_location.longitude);
    radiusM = helper.calcDistanceInMetersBetweenGPS(targetP.gps_location, targetC.gps_location);

    # test Wolf Search
    # startWolfSearch( circleCenterGPS=targetP.gps_location, circleRadiusGPS=radiusC*7, circleRadiusMeters=radiusM*7, spreadTimeS=40, searchTimeS=70 );
    # startLineBehavior(group0Waypoints = 'Constants/Group0Spiral.txt', group1Waypoints = 'Constants/Group1Spiral.txt')
    # startWolfSearch( circleCenterGPS=targetP.gps_location, circleRadiusGPS=radiusC*7, circleRadiusMeters=radiusM*7, spreadTimeS=40, searchTimeS=70 );
    # startLineBehavior(group0Waypoints = 'Constants/Group0Spiral.txt', group1Waypoints = 'Constants/Group1Spiral.txt')
    # test Consensus Decision
    # startConsensusDecision( circleCenterGPS=targetP.gps_location, circleRadiusGPS=MIN_CIRCLE_RADIUS_GPS*2, circleRadiusMeters=MIN_CIRCLE_RADIUS_METERS*2, searchTimeS=100 );
    # startConsensusDecision( circleCenterGPS=targetP.gps_location, circleRadiusGPS=MIN_CIRCLE_RADIUS_GPS*2, circleRadiusMeters=MIN_CIRCLE_RADIUS_METERS*2, searchTimeS=100 );

    # Wolf Drone search loop Start
    i = 1
    debugPrint("Starting Search and Rescue loop")
    timeSpent = 0;
    runtime = time.time()
    while (i < LOOP_NUMBER):
        # If we receive end command, end the loop
        if (End_Loop):
            debugPrint("Ending loop")
            return

        timeDiff = time.time() - runtime
        if (timeDiff > MAX_TIME):
            endLineBehavior()
            break;

        vector = [0, 0] # dont move if nothing to do
        yaw_mode = airsim.YawMode(is_rate=False, yaw_or_rate=(0)) # Set yaw to zero

        # test consensus behavior
        if(Consensus_Decision_Behavior):
            timeDiff = time.time() - Start_Time;
            stageLength = Search_Time / 5
            newP = None
            if (timeDiff < stageLength):
                newP = client.getMultirotorState(vehicle_name = "target")
                # if (droneName == "0"):
                    # print('target');
            elif (timeDiff < stageLength*2):
                newP = client.getMultirotorState(vehicle_name = "targetR")
                # if (droneName == "0"):
                    # print('targetR');
            elif (timeDiff < stageLength*3):
                newP = client.getMultirotorState(vehicle_name = "circle")
                # if (droneName == "0"):
                    # print('circle');
            elif (timeDiff < stageLength*4):
                newP = client.getMultirotorState(vehicle_name = "circle2")
                # if (droneName == "0"):
                    # print('circle2');
            elif (timeDiff < stageLength*5):
                newP = client.getMultirotorState(vehicle_name = "circle3")
                # if (droneName == "0"):
                    # print('circle3');
            else:
                newP = client.getMultirotorState(vehicle_name = "target")
                # if (droneName == "0"):
                    # print('circle3');
            if (newP != None):
                # if (droneName == "0"):
                    # print("Gps: " + str(newP.gps_location));
                updateConsensusDecisionCenter(circleCenterGPS=newP.gps_location);

        
        start=time.time() # gather time data

        # Publishes to (WolfData) topic
        wolfDataPublisher(wolfDataPublish, client, droneName)
        
        # TEST OUT WOLF SERVICE, wolfGetWolfData
        # wolfInfoArray = getWolfState()        # Get droneWolfState state array from service
        # print(wolfInfoArray[0])               # Example of printing wolf drone 3's information

        # Get Airsim Data and procesess it here
        # TODO: add Yolo person Detector (if runtime is to long Seprate into thread that runs on intervals)
            # getDataFromAirsim -> yolo detect -> update internal drone state or publish data to other drones
        # TODO: Publishes to (WolfData) topic
        # #####wolfDataPublisher(wolfDataPublish, client, droneName) # Publish drones state at each loop so other drones can cordiante behaviors
        # TODO: add Collision detecotr
            # getNeededAirSimData -> checkForCollision -> update collision behavior
        collisionAvoidance = False # set to true if need to do collision avoidance (open to better integration method)
        isChangeVelocity = True
        threshold = getDroneSpeed(client, droneName) * 2
        slightDeviation = getDroneSpeed(client, droneName) * 1.5

        # Check if threshold is under min
        if (threshold < 5):
            threshold = 5
            
        collisionAvoidance, closestObjectDistance,slightDeviationDistance = collisionDetectionBehavior.collisionAvoidanceCheck(client, droneName, threshold,slightDeviation)
        timeDiff = time.time() - Collision_Mode_Time
        if(collisionAvoidance):
            # debugPrint("Doing collision")
            Collision_Mode_Time = time.time()
            vector = collisionDetectionBehavior.collisionAlgo(client,imgDir,droneName,closestObjectDistance,slightDeviationDistance,COLLISION_DIRECTION_FACTOR)
            # client.moveByVelocityZAsync(vector[0], vector[1], -4, duration = COLLISION_DIRECTION_FACTOR, yaw_mode=yaw_mode, vehicle_name=droneName)

        elif (timeDiff < COLLISION_MODE_TIME_LENGTH):
            # debugPrint("Still doing collision, under time")
            isChangeVelocity = False

        # # TODO: Add in Drone behavior desion making
        elif (Consensus_Decision_Behavior): # Consensus Descion behavior
            currentDroneData = client.getMultirotorState(vehicle_name = droneName);
            
            vector = consensusDecisionBehaviorGetVector(currentDroneData);

            yawDegrees = wolfSearchBehavior.calcYaw(currentGPS=currentDroneData.gps_location, targetGPS=Circle_Center_GPS);
            yaw_mode  = airsim.YawMode(is_rate=False, yaw_or_rate=(yawDegrees));

            # check if time to end consensus Desension
            timeDiff = time.time() - Start_Time
            if (timeDiff > (Search_Time)):
                endConsensusDecision();

        elif (Wolf_Search_Behavior): # Wolf Search behavior
            currentDroneData = client.getMultirotorState(vehicle_name = droneName);

            vector = wolfSearchBehaviorGetVector(currentDroneData);

            yawDegrees = wolfSearchBehavior.calcYaw(currentGPS=currentDroneData.gps_location, targetGPS=Circle_Center_GPS);
            yaw_mode  = airsim.YawMode(is_rate=False, yaw_or_rate=(yawDegrees));

            timeDiff = time.time() - Start_Time;
            if (timeDiff > (Spread_Time + Search_Time)):
                endWolfSearch();

        elif (Line_Behavior): # Line_Behavior
            # Gets drones waypoint and vector movement
            newWaypoint = getNewWaypoint(droneName)
            vector = lineBehavior(client, int(droneName), DM_Wolfs_Cluster, newWaypoint)
            vectorTemp = 0

            vectorTemp = vector[0]
            vector[0] = vector[1]
            vector[1] = vectorTemp

            # Calculates camera direction based on velocity      
            if (vector[1] != 0):
                yaw = math.atan2(vector[1], vector[0])
                degrees = math.degrees(yaw)
                yaw_mode = airsim.YawMode(is_rate=False, yaw_or_rate=(degrees));
            else:
                degrees = 0
                yaw_mode = airsim.YawMode(is_rate=False, yaw_or_rate=(degrees));


        # TODO: Apply turning to desired action
        # TODO: Overide other behaviors if collisionAvoidance is needed

        # Grabs current drones velocity in x and y
        curDroneData = client.getGpsData(vehicle_name = droneName)
        curDroneVelocity = [curDroneData.gnss.velocity.x_val, curDroneData.gnss.velocity.y_val]

        # Calculates turning
        vector = helper.turningCalculation(curDroneVelocity, vector, MAX_TURN_ANGLE)

        if (isChangeVelocity):
            client.moveByVelocityZAsync(vector[0], vector[1], -4, duration = 0.5, yaw_mode=yaw_mode, vehicle_name=droneName)
        
        # Add in artifical loop delay (How fast the loop runs dictates the drones reaction speed)

        # time.sleep(0.18)
        end = time.time();
        timeSpent += end-start;

        # Checks if drones have made iot to the next waypoint
        allDronesAtWaypoint()

        i+=1
    # debugPrint("Ending Search and Rescue loop: ")
    debugPrint("Average Loop Time in seconds: " + str(timeSpent / i))
    # Wolf Drone search loop End

# Main Process End ----------------------------------------------

# Theads Start ===========================================
def wolfServiceListeners(droneName):
    serviceName = WOLF_DRONE_SERVICE + droneName
    service = rospy.Service(serviceName, sendCommand, commandResponse)
    rospy.spin()

def endListener():
    rospy.Subscriber(ros.END_LOOP_TOPIC, String, handleEnd)
    rospy.spin()

def handleEnd(data):
    global End_Loop
    if (data.data == "End"):
        End_Loop = True

# checks drone camera with yolo detection
def wolfCameraDetection(droneName):
    threadClient = airsim.MultirotorClient(LOCAL_IP)
    debugPrint("Starting wolfCameraDetection loop")
    i = 0;
    timeSpent = 0;
    runtime = time.time()
    while (i < LOOP_NUMBER):
        timeDiff = time.time() - runtime
        if (timeDiff > MAX_TIME):
            break;
        start=time.time() # gather time data
        # todo: marry add camera checkl nad yolo detector

        # mock detection
        timeDiff = time.time() - runtime
        # if(not(Consensus_Decision_Behavior)):
        if(False):
            if(timeDiff > 18 and droneName == '1'):
                # targetP is estimated gps position
                targetP = threadClient.getMultirotorState(vehicle_name = "target")
                circleCenterGPS = targetP.gps_location
                circleRadiusGPS = MIN_CIRCLE_RADIUS_GPS*2
                circleRadiusMeters = MIN_CIRCLE_RADIUS_METERS*2
                searchTimeS = 100
                taskGroup = droneName + "Con"
                startConsensusDecision( circleCenterGPS=circleCenterGPS, circleRadiusGPS=circleRadiusGPS, circleRadiusMeters=circleRadiusMeters, searchTimeS=searchTimeS, taskGroup=taskGroup )
                # ToDO addd function call to return list of availalbe drones
                # THis is Hardcoded need to replace
                instructWolf.sendConsensusDecisionBehaviorRequest(WOLF_DRONE_SERVICE + '2', circleCenterGPS, circleRadiusGPS, circleRadiusMeters, searchTimeS, taskGroup)
                instructWolf.sendConsensusDecisionBehaviorRequest(WOLF_DRONE_SERVICE + '0', circleCenterGPS, circleRadiusGPS, circleRadiusMeters, searchTimeS, taskGroup)

        time.sleep(1);
        end = time.time();
        timeSpent += end-start;
        i+=1
    return;
# startConsensusDecision( circleCenterGPS=targetP.gps_location, circleRadiusGPS=MIN_CIRCLE_RADIUS_GPS*2, circleRadiusMeters=MIN_CIRCLE_RADIUS_METERS*2, searchTimeS=100 );
    debugPrint(" CameraDetection: Average Loop Time: " + str(timeSpent / i))


# Theads END ===========================================

# TODO: Functions need to Refatctor +++++++++++++++++++++++++++++++++++

# Creates drone groups based on wolf number
def wolfClusterCreation(droneName):
    droneNum = int(droneName)
    global DM_Wolfs_Cluster
    if (droneNum <= 2):
        DM_Wolfs_Cluster = [0, 1, 2]
    else:
        DM_Wolfs_Cluster = [3, 4, 5]

def commandResponse(request):
    global DM_Drone_Name
    global Task_Group
    messageType = request.messageType
    lineInfo = request.lineBehaviorStart
    wolfSearchInfo = request.wolfSearchBehaviorStart
    consensusDecisionInfo = request.consensusDecisionBehaviorStart

    print("Got a command")
    
    lineString = str(lineInfo)
    # Find datatype with info, execute command based on who has data
    if (messageType == "RequestLineBehavior"):
        startLineBehavior(lineInfo.cluster)
        # debugPrint("Do line behavior")
        return True

    elif (messageType == "RequestWolfSearch"):
        # debugPrint("Do wolf search")

        # Return false is wolf is already in a task group
        if (Task_Group != ""):
            debugPrint("Unable to complete wolf search request")
            return False

        # Check if we got message from overseer
        if (wolfSearchInfo.taskGroup == ""):
            # if so create task group with wolf name
            debugPrint("Got request wolf search from Overseer")
            taskGroup = "Task_Group_Search_" + DM_Drone_Name

            # Request nearby drones
            debugPrint("Requesting neaby wolfs")
            requestNearbyDrones(DM_Drone_Name, wolfSearchInfo.circleCenterGPS, wolfSearchInfo.circleRadiusGPS, wolfSearchInfo.circleRadiusMeters, wolfSearchInfo.spreadTimeS, wolfSearchInfo.searchTimeS,  taskGroup)

            # Start wolf search
            debugPrint("Doing search")
            startWolfSearch(wolfSearchInfo.circleCenterGPS, wolfSearchInfo.circleRadiusGPS, wolfSearchInfo.circleRadiusMeters, wolfSearchInfo.spreadTimeS, wolfSearchInfo.searchTimeS,  taskGroup)
            return True      
        # Got message from wolf, no need to request from nearby
        else:
            debugPrint("Got request for help at waypoint")
            startWolfSearch(wolfSearchInfo.circleCenterGPS, wolfSearchInfo.circleRadiusGPS, wolfSearchInfo.circleRadiusMeters, wolfSearchInfo.spreadTimeS, wolfSearchInfo.searchTimeS,  wolfSearchInfo.taskGroup)
            return True

        return False

    elif (messageType == "RequestConsensusDecision"):
        # debugPrint("Do consensus decision")
        circleCenterGPS = consensusDecisionInfo.circleCenterGPS
        circleRadiusGPS = consensusDecisionInfo.circleRadiusGPS
        circleRadiusMeters = consensusDecisionInfo.circleRadiusMeters
        searchTimeS = consensusDecisionInfo.searchTimeS
        taskGroup = consensusDecisionInfo.taskGroup
        startConsensusDecision( circleCenterGPS=circleCenterGPS, circleRadiusGPS=circleRadiusGPS, circleRadiusMeters=circleRadiusMeters, searchTimeS=searchTimeS, taskGroup=taskGroup );
        return True
    
    return False

def getDroneSpeed(client, droneName):
    velocity = client.getGpsData(vehicle_name = droneName)

    velocityX = velocity.gnss.velocity.x_val
    velocityY = velocity.gnss.velocity.y_val

    speed = sqrt(velocityX**2 + velocityY**2)

    return speed

# Publishes wolf data to (WolfData) topic
def wolfDataPublisher(pub, client, droneName):
    position = client.getMultirotorState(vehicle_name = droneName)
    velocity = client.getGpsData(vehicle_name = droneName)

    # Creates droneMsg object and inserts values from AirSim apis
    droneMsg = droneData()
    droneMsg.droneName = droneName
    droneMsg.longitude = position.gps_location.longitude
    droneMsg.latitude = position.gps_location.latitude
    droneMsg.velocityX = velocity.gnss.velocity.x_val
    droneMsg.velocityY = velocity.gnss.velocity.y_val
    droneMsg.cluster = Cluster
    droneMsg.taskGroup = Task_Group

    # Publishes to topic
    pub.publish(droneMsg)

# Requests nearby drones to do search
def requestNearbyDrones(droneName, circleCenterGPS, circleRadiusGPS, circleRadiusMeters, spreadTimeS, searchTimeS,  taskGroup):
    # Get drone info array and sender info
    droneData = wolfService.getWolfState()
    senderDrone = droneData[int(droneName)]

    # Go through each drones and request to nearby drones in cluster
    for drone in droneData:
        # Gets distance between waypoint and drone
        distance = sqrt( (senderDrone.longitude - drone.longitude)**2 + (senderDrone.latitude - drone.latitude)**2 )

        # If a drone is within a certain radius of requestor 
        if ((distance < NEARBY_DRONE_RADIUS) and (drone.droneName != senderDrone.droneName) and (drone.cluster == senderDrone.cluster) and (drone.taskGroup == "")):
            serviceName = WOLF_DRONE_SERVICE + drone.droneName
            requestStatus = instructWolf.sendWolfSearchBehaviorRequest(serviceName, circleCenterGPS, circleRadiusGPS, circleRadiusMeters, spreadTimeS, searchTimeS,  taskGroup)
            print("Request bool:", requestStatus, "From drone", droneName)

# Function get drones subwaypoint based on index
def getNewWaypoint(droneName):
    # Created global waypoints
    global WAYPOINT_INDEX
    # print("DroneName: ", droneName, "Current waypoint index", WAYPOINT_INDEX)
    currentWaypoint = WAYPOINT_COORDS[WAYPOINT_INDEX]
    newWaypoint = currentWaypoint

    if (WAYPOINT_INDEX >= 1):
        # Radius in charge of distance between drones
        radius = 0.0001
        previousWaypoint = WAYPOINT_COORDS[WAYPOINT_INDEX-1]

        # Finds vector between waypoints
        waypointDiffX = float(currentWaypoint[0]) - float(previousWaypoint[0])
        waypointDiffY = float(currentWaypoint[1]) - float(previousWaypoint[1])

        # Gets normalized difference vector
        vectorVal = sqrt(waypointDiffX**2 + waypointDiffY**2)
        xDirection = (waypointDiffX/vectorVal) * radius
        yDirection = (waypointDiffY/vectorVal) * radius

        # Creates lanes for 3 group clusters
        if (len(DM_Wolfs_Cluster) == 3):
            # Moves first drone left of the waypoint
            if ((int(droneName) % 3) == 0):
                newWaypointX = float(currentWaypoint[0]) - yDirection + xDirection
                newWaypointY = float(currentWaypoint[1]) + xDirection + yDirection
                newWaypoint = [float(newWaypointX), float(newWaypointY)]
            # Moves second drone directly to waypoint
            elif((int(droneName) % 3) == 1):
                newWaypoint = currentWaypoint
            # Moves third drone right of the waypoint
            elif((int(droneName) % 3) == 2):
                newWaypointX = float(currentWaypoint[0]) + yDirection - xDirection
                newWaypointY = float(currentWaypoint[1]) - xDirection - yDirection
                newWaypoint = [float(newWaypointX), float(newWaypointY)]

        # Creates lanes for 4 group clusters
        if (len(DM_Wolfs_Cluster) == 4):
            # Moves first drone left of the waypoint
            if ((int(droneName) % 4) == 0):
                newWaypointX = float(currentWaypoint[0]) - (yDirection * 1.5)
                newWaypointY = float(currentWaypoint[1]) + (xDirection * 1.5)
                newWaypoint = [float(newWaypointX), float(newWaypointY)]
                # print("Drone", droneName, "Int dronename", (int(droneName)), "Moving to ", newWaypoint)
            # Moves second drone directly to waypoint
            elif((int(droneName) % 4) == 1):
                newWaypointX = float(currentWaypoint[0]) - (yDirection * 0.5)
                newWaypointY = float(currentWaypoint[1]) + (xDirection * 0.5)
                newWaypoint = [float(newWaypointX), float(newWaypointY)]
            elif ((int(droneName) % 4) == 2):
                newWaypointX = float(currentWaypoint[0]) + (yDirection * 0.5)
                newWaypointY = float(currentWaypoint[1]) - (xDirection * 0.5)
                newWaypoint = [float(newWaypointX), float(newWaypointY)]
                # print("Drone", droneName, "Moving to ", newWaypoint)
            # Moves third drone right of the waypoint
            elif((int(droneName) % 4) == 3):
                newWaypointX = float(currentWaypoint[0]) + (yDirection * 1.5)
                newWaypointY = float(currentWaypoint[1]) - (xDirection * 1.5)
                newWaypoint = [float(newWaypointX), float(newWaypointY)]
                # print("Drone", droneName, "Int dronename", (int(droneName)), "Moving to ", newWaypoint)


    return newWaypoint


# Reads values in SpiralSearch.txt and sets it to global variable
def readCoordFile(filename):
    file = open(filename, 'r')
    f = file.readlines()
    i = 0

    # Creates an array for the coordinates and strips the newlines
    newList = []
    for line in f:
        newLine = line.strip()
        newLine = newLine.split(' ')
        newList.append(newLine)

    global WAYPOINT_COORDS
    WAYPOINT_COORDS = newList

def allDronesAtWaypoint():
    global WAYPOINT_INDEX
    wolfInfoArray = wolfService.getWolfState()

    currentWaypoint = WAYPOINT_COORDS[WAYPOINT_INDEX]
    newWaypoint = currentWaypoint

    if (WAYPOINT_INDEX >= 1):
        radius = 0.0001
        previousWaypoint = WAYPOINT_COORDS[WAYPOINT_INDEX-1]

        # Finds vector between waypoints
        waypointDiffX = float(currentWaypoint[0]) - float(previousWaypoint[0])
        waypointDiffY = float(currentWaypoint[1]) - float(previousWaypoint[1])

        # Gets normalized difference vector
        vectorVal = sqrt(waypointDiffX**2 + waypointDiffY**2)
        xDirection = (waypointDiffX/vectorVal) * radius
        yDirection = (waypointDiffY/vectorVal) * radius

        if (len(DM_Wolfs_Cluster) == 3):
            for droneNum in DM_Wolfs_Cluster:
                # Calculates first drone based of lane
                if ((int(droneNum) % 3) == 0):
                    newWaypointX = float(currentWaypoint[0]) - yDirection + xDirection
                    newWaypointY = float(currentWaypoint[1]) + xDirection + yDirection
                    newWaypoint = [float(newWaypointX), float(newWaypointY)]
                # Calculates second drone based of lane
                elif((int(droneNum) % 3) == 1):
                    newWaypoint = currentWaypoint

                # Calculates third drone based of lane
                elif((int(droneNum) % 3) == 2):
                    newWaypointX = float(currentWaypoint[0]) + yDirection - xDirection
                    newWaypointY = float(currentWaypoint[1]) - xDirection - yDirection
                    newWaypoint = [float(newWaypointX), float(newWaypointY)]                  

                # Get difference between waypoint and drones actual location
                xDifference = wolfInfoArray[droneNum].longitude - newWaypointX
                yDifference = wolfInfoArray[droneNum].latitude - newWaypointY

                # If any of the drones are out of bounds, return false
                if ((abs(xDifference) > 0.00015) or (abs(yDifference) > 0.00015)):
                    return 0

        # TODO: IMPLEMENT GROUP OF FOUR MATH IF NECESSARY

    else:
        for droneNum in DM_Wolfs_Cluster:
            xDifference = wolfInfoArray[droneNum].longitude - float(WAYPOINT_COORDS[WAYPOINT_INDEX][0])
            yDifference = wolfInfoArray[droneNum].latitude - float(WAYPOINT_COORDS[WAYPOINT_INDEX][1])

            # If any of the drones are out of bounds, return false
            if ((abs(xDifference) > 0.0002) or (abs(yDifference) > 0.0002)):
                return 0

    WAYPOINT_INDEX = WAYPOINT_INDEX + 1
    # print("Drones:", DM_Wolfs_Cluster, "Made it to waypoint:", WAYPOINT_INDEX)
    # print("Drones:", DM_Wolfs_Cluster, "Made it to waypoint:", WAYPOINT_INDEX)
    return 1


# Enables api control, takes off drone, returns the client
def takeOff(droneName):
    client = airsim.MultirotorClient(LOCAL_IP)
    debugPrint("Checking if connected to MulirotorClient")
    client.confirmConnection()
    debugPrint("Connected to MulirotorClient")
    client.enableApiControl(True, droneName)
    client.armDisarm(True, droneName)
    client.takeoffAsync(vehicle_name=droneName).join()
    # client.moveByAngleRatesZAsync(roll_rate=0, pitch_rate=0, yaw_rate=2, z=-3, duration=1, vehicle_name=droneName).join()

    return client

def startLineBehavior(clusterName):
    global Cluster
    global Line_Behavior
    Cluster = clusterName
    Line_Behavior = True

def endLineBehavior():
    global Cluster
    global Line_Behavior
    Cluster = ""
    Line_Behavior = False

def startWolfSearch( circleCenterGPS, circleRadiusGPS, circleRadiusMeters, spreadTimeS, searchTimeS, taskGroup):
    global Wolf_Search_Behavior;
    global Circle_Center_GPS;
    global Circle_Radius_GPS, Circle_Radius_Meters;
    global Start_Time, Spread_Time, Search_Time;
    global Task_Group;

    Circle_Center_GPS = circleCenterGPS;
    Circle_Radius_GPS, Circle_Radius_Meters = circleRadiusGPS, circleRadiusMeters;
    Search_Time = searchTimeS;
    Spread_Time = spreadTimeS;
    Start_Time = time.time();
    Task_Group = taskGroup;
    Wolf_Search_Behavior = True;

def wolfSearchBehaviorGetVector(currentDroneData):
    radius = Circle_Radius_GPS
    radiusM = Circle_Radius_Meters

    timeDiff = time.time() - Start_Time;
    if (timeDiff > Spread_Time):
        timeDiv = (Search_Time - (timeDiff - Spread_Time)) / Search_Time
        radius = (radius - MIN_CIRCLE_RADIUS_GPS)*timeDiv + MIN_CIRCLE_RADIUS_GPS;
        radiusM = (radiusM - MIN_CIRCLE_RADIUS_METERS)*timeDiv + MIN_CIRCLE_RADIUS_METERS;
    
    wolfDataArray = wolfService.getWolfDataOfTaskGroup(DM_Drone_Name, Task_Group);
    # calcSpeedVector function variables
    averageAlignmentSpeed = 12;
    bonusAlignmentSpeed = 0;
    maxCohSepSpeed = 4;
    maxSpeed = 13;

    vector = wolfSearchBehavior.calcSpeedVector(currentDroneData=currentDroneData, targetGPS=Circle_Center_GPS, \
                radius=radius, radiusM=radiusM, wolfData=wolfDataArray, \
                averageAlignmentSpeed=averageAlignmentSpeed, bonusAlignmentSpeed=bonusAlignmentSpeed, \
                maxCohSepSpeed=maxCohSepSpeed, maxSpeed=maxSpeed);
    
    return vector;


def endWolfSearch():
    global Wolf_Search_Behavior;
    global Circle_Center_GPS;
    global Circle_Radius_GPS, Circle_Radius_Meters;
    global Start_Time, Spread_Time, Search_Time;
    global Task_Group;

    Circle_Center_GPS = None;
    Circle_Radius_GPS, Circle_Radius_Meters = None, None;
    Start_Time, Spread_Time, Search_Time = None, None, None;
    Task_Group = "";
    Wolf_Search_Behavior = False;

def startConsensusDecision( circleCenterGPS, circleRadiusGPS, circleRadiusMeters, searchTimeS, taskGroup):
    global Consensus_Decision_Behavior;
    global Circle_Center_GPS;
    global Circle_Radius_GPS, Circle_Radius_Meters;
    global Start_Time, Spread_Time, Search_Time;
    global Task_Group;

    Circle_Center_GPS = circleCenterGPS;
    Circle_Radius_GPS, Circle_Radius_Meters = circleRadiusGPS, circleRadiusMeters;
    Search_Time = searchTimeS;
    Start_Time = time.time();
    Task_Group = taskGroup;
    Consensus_Decision_Behavior = True;
    Wolf_Search_Behavior = False; 

def consensusDecisionBehaviorGetVector(currentDroneData):
    radius = Circle_Radius_GPS
    radiusM = Circle_Radius_Meters
    targetGPS = Circle_Center_GPS
    wolfDataArray = wolfService.getWolfDataOfTaskGroup(DM_Drone_Name, Task_Group);
    averageAlignmentSpeed = 12;
    bonusAlignmentSpeed = 0;
    maxCohSepSpeed = 4;
    maxSpeed = 13
    
    vector = wolfSearchBehavior.calcSpeedVector(currentDroneData=currentDroneData, targetGPS=targetGPS, \
                radius=radius, radiusM=radiusM, wolfData=wolfDataArray, \
                averageAlignmentSpeed=averageAlignmentSpeed, bonusAlignmentSpeed=bonusAlignmentSpeed, \
                maxCohSepSpeed=maxCohSepSpeed, maxSpeed=maxSpeed);

    return vector;

def updateConsensusDecisionCenter(circleCenterGPS):
    global Circle_Center_GPS;

    Circle_Center_GPS = circleCenterGPS

def endConsensusDecision():
    global Consensus_Decision_Behavior;
    global Circle_Center_GPS;
    global Circle_Radius_GPS, Circle_Radius_Meters;
    global Start_Time, Spread_Time, Search_Time;
    global Task_Group;

    Circle_Center_GPS = None;
    Circle_Radius_GPS, Circle_Radius_Meters = None, None;
    Start_Time, Search_Time = None, None;
    Task_Group = "";
    Consensus_Decision_Behavior = False;
    


def debugPrint( debugMessage):
    global DM_Drone_Name
    print("Wolf: ", DM_Drone_Name, " : " ,  debugMessage)