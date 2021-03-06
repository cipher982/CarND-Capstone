#!/usr/bin/env python

import rospy
import numpy as np
from geometry_msgs.msg import PoseStamped
from styx_msgs.msg     import Lane, Waypoint
from std_msgs.msg      import Int32
from scipy.spatial     import KDTree
from time              import sleep

import math

LOOKAHEAD_WPS = 200 # Number of waypoints we will publish. You can change this number
MAX_DECEL = .5


class WaypointUpdater(object):
    def __init__(self):
        rospy.init_node('waypoint_updater')

        # initialize
        self.pose            = None
        self.base_waypoints  = None
        self.waypoints_2d    = None
        self.waypoint_tree   = None
        self.base_lane       = None
        self.stopline_wp_idx = -1
        self.final_waypoints = Lane()

        self.closest_wp      = None

        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb, queue_size=1)
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)
        rospy.Subscriber('/traffic_waypoint', Int32, self.traffic_cb)

        self.final_waypoints_pub = rospy.Publisher('/final_waypoints', Lane, queue_size=1)
        #self.driving_mode_pub    = rospy.Publisher('/driving_mode', Int32, queue_size=1)
        self.car_waypoint_id_pub = rospy.Publisher('/car_waypoint_id', Int32, queue_size=1)

        self.loop()
        
    def loop(self):
        rate = rospy.Rate(50)
        while not rospy.is_shutdown():
            if self.pose and self.base_lane:
                self.publish_waypoints()
            rate.sleep()

    def get_closest_waypoint_idx(self):
        x = self.pose.pose.position.x
        y = self.pose.pose.position.y
        closest_idx = self.waypoint_tree.query([x, y], 1)[1]

        # check is closest_idx is front/behind of vehicle
        closest_coord = self.waypoints_2d[closest_idx]
        prev_coord    = self.waypoints_2d[closest_idx-1]

        # equation for hyperplane through closest_coord(s)
        cl_vect   = np.array(closest_coord)
        prev_vect = np.array(prev_coord)
        pos_vect  = np.array([x, y])

        val = np.dot(cl_vect - prev_vect, pos_vect - cl_vect)

        if val > 0:
            closest_idx = (closest_idx + 1) % len(self.waypoints_2d)

        self.closest_wp = closest_idx

        return closest_idx

    #def publish_waypoints(self, closest_idx):
    #    lane = Lane()
    #    lane.header    = self.base_waypoints.header
    #    lane.waypoints = self.base_waypoints.waypoints[closest_idx:closest_idx + LOOKAHEAD_WPS]
    #    self.final_waypoints_pub.publish(lane)

    def generate_lane(self):
        lane = Lane()

        closest_idx = None
        while closest_idx is None:
            try:
                closest_idx = self.get_closest_waypoint_idx()
            except AttributeError as error:
                pass

        farthest_idx   = closest_idx + LOOKAHEAD_WPS
        base_waypoints = self.base_lane.waypoints[closest_idx:farthest_idx]

        if self.stopline_wp_idx == -1 or (self.stopline_wp_idx >= farthest_idx):
            # clear, keep going
            #rospy.logwarn("using normal waypoints! stopline_wp_idx:{0}, farthest_idx:{1}".\
            #    format(self.stopline_wp_idx,farthest_idx))
            rospy.logwarn("Going. . .")
            lane.waypoints = base_waypoints
        else:
            # not clear, slow down
            #rospy.logwarn("applying decel waypoints! closest_idx:{0}".format(closest_idx))
            rospy.logwarn("Stopping. . .")
            lane.waypoints = self.decelerate_waypoints(base_waypoints, closest_idx)

        return lane

    def decelerate_waypoints(self, waypoints, closest_idx):
        temp = []
        for i, wp in enumerate(waypoints):
            p      = Waypoint()
            p.pose = wp.pose

            stop_idx = max(self.stopline_wp_idx - closest_idx - 2, 0) # 2 is arbt
            dist     = self.distance(waypoints, i, stop_idx)
            vel      = math.sqrt(2 * MAX_DECEL * dist)
            #vel      = dist * .85

            if vel < 1.0:
                vel = 0.0

            p.twist.twist.linear.x = min(vel, wp.twist.twist.linear.x)
            temp.append(p)

        return temp

    def pose_cb(self, msg):
        self.pose = msg

    def waypoints_cb(self, waypoints):
        self.base_lane = waypoints
        if not self.waypoints_2d:
            self.waypoints_2d = [[waypoint.pose.pose.position.x, waypoint.pose.pose.position.y] \
             for waypoint in waypoints.waypoints]
            self.waypoint_tree = KDTree(self.waypoints_2d)

    def traffic_cb(self, msg):
        self.stopline_wp_idx = msg.data
        rospy.logwarn("Traffic callback state:{0}".format(msg.data))

    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        pass

    def get_waypoint_velocity(self, waypoint):
        return waypoint.twist.twist.linear.x

    def set_waypoint_velocity(self, waypoints, waypoint, velocity):
        waypoints[waypoint].twist.twist.linear.x = velocity

    def distance(self, waypoints, wp1, wp2):
        dist = 0
        dl = lambda a, b: math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2  + (a.z-b.z)**2)
        for i in range(wp1, wp2+1):
            dist += dl(waypoints[wp1].pose.pose.position, waypoints[i].pose.pose.position)
            wp1   = i
        return dist

    def publish_waypoints(self):
        final_lane = self.generate_lane()
        self.final_waypoints_pub.publish(final_lane)

        if self.closest_wp is not None:
            self.car_waypoint_id_pub.publish(self.closest_wp)


if __name__ == '__main__':
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')











