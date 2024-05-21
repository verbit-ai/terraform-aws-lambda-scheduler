import boto3

import sys
import os
import json
import logging
import datetime
import time
import pytz

logger = logging.getLogger()
logger.setLevel(logging.INFO)

aws_region = None

rds_scheduling_enabled = os.getenv('RDS_SCHEDULING_ENABLED', 'True')
rds_scheduling_enabled = rds_scheduling_enabled.capitalize()
logger.info("rds_schedule is %s." % rds_scheduling_enabled)

rds_schedule = os.getenv('RDS_SCHEDULE', '''{\
"mon": {"start": 5, "stop": 19},\
"tue": {"start": 5, "stop": 19},\
"wed": {"start": 5, "stop": 19},\
"thu": {"start": 5, "stop": 19},\
"fri": {"start": 5, "stop": 19}\
}''')

ec2_scheduling_enabled = os.getenv('EC2_SCHEDULING_ENABlED', 'True')
ec2_scheduling_enabled = ec2_scheduling_enabled.capitalize()
logger.info("ec2_schedule is %s." % ec2_scheduling_enabled)

ec2_schedule = os.getenv('EC2_SCHEDULE', '''{\
"mon": {"start": 6, "stop": 19},\
"tue": {"start": 6, "stop": 19},\
"wed": {"start": 6, "stop": 19},\
"thu": {"start": 6, "stop": 19},\
"fri": {"start": 6, "stop": 19}\
}''')


debugmode = os.getenv('DEBUGMODE', 'False') == 'True'


def init():
    # Setup AWS connection
    aws_region = os.getenv('AWS_REGION', 'us-east-1')

    global ec2
    logger.info("-----> Connecting to region \"%s\"", aws_region)
    ec2 = boto3.resource('ec2', region_name=aws_region)
    logger.info("-----> Connected to region \"%s\"", aws_region)


def debugout(module, data):
    if debugmode:
        logger.info("DEBUG %s : %s" % (module, data))


def checkdate(data, state, day, hh):
    debugout('checkdate', "DEBUG checkdate state (%s) day (%s) hh (%s) data (%s)" % (state, day, hh, data))

    try:
        schedule = {}
        if data == '':
            debugout('checkdate', "data is empty")
            return False
        elif len(data) > 1 and data[0] == '{':
            # JSON-Format
            debugout('checkdate', 'JSON format found. (%s)' % data)
            schedule = json.loads(data)
        else:
            # RDS-Format
            try:

                debugout('checkdate', "RDS format found")
                # remove ' ' at atart and end, replace multiple ' ' with ' '
                t = dict(x.split('=') for x in ' '.join(data.split()).split(' '))
                for d in t.keys():
                    dday, datastate = d.split('_')
                    val = [int(i) for i in t[d].split('/')]
                    debugout('checkdate', "RDS data: dday (%s) datastate (%s) val (%s)" % (dday, datastate, val))
                    dstate = {}
                    dstate[datastate] = val
                    if dday in schedule:
                        schedule[dday].update(dstate)
                    else:
                        schedule[dday] = dstate

            except Exception as e:
                logger.error("Error checkdate : %s" % (e))

        if debugout:
            for d in schedule.keys():
                for s in schedule[d].keys():
                    debugout('checkdate', 'keys: day (%s) state (%s)' % (d, s))

    except:
        logger.error("Error checkdate invalid data : %s : %s" % (data, e))

    try:
        schedule_data = []

        if day in schedule.keys() and state in schedule[day]:
            if type(schedule[day][state]) is list:
                schedule_data = schedule[day][state]
            else:
                schedule_data = [schedule[day][state]]
            debugout('checkdate', 'day schedule_data %s' % ', '.join(str(s) for s in schedule_data))

        if 'daily' in schedule.keys() and state in schedule['daily']:
            if type(schedule['daily'][state]) is list:
                schedule_data.extend(schedule['daily'][state])
            else:
                schedule_data.extend([int(schedule['daily'][state])])
            debugout('checkdate', 'daily schedule_data %s' % ', '.join(str(s) for s in schedule_data))

        workdays = ['mon', 'tue', 'wed', 'thu', 'fri']
        if day in workdays and 'workday' in schedule.keys() and state in schedule['workday']:
            debugout('checkdate', 'workday found')
            if type(schedule['workday'][state]) is list:
                schedule_data.extend(schedule['workday'][state])
            else:
                schedule_data.extend([schedule['workday'][state]])
            debugout('checkdate', 'workday schedule_data %s' % ', '.join(str(s) for s in schedule_data))

        debugout('checkdate', 'len %i schedule_data %s' % (len(schedule_data), ','.join(str(s) for s in schedule_data)))

        if int(hh) in schedule_data:
            logger.info("checkdate %s time matches hh (%i)" % (state, int(hh)))
            return True

        return False
    except Exception as e:
        logger.error("Error checkdate %s time : %s" % (state, e))

#
# Loop EC2 instances and check if a 'schedule' tag has been set. Next, evaluate value and start/stop instance if needed.
#


def check():
    # Get all reservations.
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name',
                                               'Values': ['pending', 'running', 'stopping', 'stopped']}])

    # Get current day + hour (using gmt by default if time parameter not set to local)
    time_zone = os.getenv('TIME', 'gmt')
    if time_zone == 'local':
        hh = int(time.strftime("%H", time.localtime()))
        day = time.strftime("%a", time.localtime()).lower()
        logger.info("-----> Checking for EC2 instances to start or stop for 'day' " + day + " 'local time' hour " + str(hh))
    elif time_zone == 'gmt':
        hh = int(time.strftime("%H", time.gmtime()))
        day = time.strftime("%a", time.gmtime()).lower()
        logger.info("-----> Checking for EC2 instances to start or stop for 'day' " + day + " 'gmt' hour " + str(hh))
    else:
        if time_zone in pytz.all_timezones:
            d = datetime.datetime.now()
            d = pytz.utc.localize(d)
            req_timezone = pytz.timezone(time_zone)
            d_req_timezone = d.astimezone(req_timezone)
            hh = int(d_req_timezone.strftime("%H"))
            day = d_req_timezone.strftime("%a").lower()
            logger.info("-----> Checking for EC2 instances to start or stop for 'day' " +
                        day + " '" + time_zone + "' hour " + str(hh))
        else:
            logger.error('Invalid time timezone string value \"%s\", please check!' % (time_zone))
            raise ValueError('Invalid time timezone string value')

    started = []
    stopped = []

    if not instances:
        logger.error('Unable to find any EC2 Instances, please check configuration')

    for instance in instances:
        logger.info("-----> Evaluating EC2 instance \"%s\" state %s" % (instance.id, instance.state["Name"]))

        try:
            # ignore tags on EC2
            data = ec2_schedule

            try:
                if checkdate(data, 'start', day, hh) and instance.state["Name"] != 'running':

                    logger.info("Starting EC2 instance \"%s\"." % (instance.id))
                    started.append(instance.id)
                    ec2.instances.filter(InstanceIds=[instance.id]).start()
            except Exception as e:
                logger.error("Error checking start time : %s" % e)
                pass

            try:
                if checkdate(data, 'stop', day, hh) and instance.state["Name"] == 'running':

                    logger.info("Stopping EC2 instance \"%s\"." % (instance.id))
                    stopped.append(instance.id)
                    ec2.instances.filter(InstanceIds=[instance.id]).stop()
            except Exception as e:
                logger.error("Error checking stop time : %s" % e)

        except ValueError as e:
            # invalid JSON
            logger.error('Invalid value for tag \"schedule\" on EC2 instance \"%s\", please check!' % (instance.id))


def rds_init():
    # Setup AWS connection
    aws_region = os.getenv('AWS_REGION', 'us-east-1')

    logger.info("-----> Connecting rds to region \"%s\"", aws_region)
    global rds
    rds = boto3.client('rds', region_name=aws_region)
    logger.info("-----> Connected rds to region \"%s\"", aws_region)


def flattenjson(b, delim):
    val = {}
    for i in b.keys():
        if isinstance(b[i], dict):
            get = flattenjson(b[i], delim)
            for j in get.keys():
                val[i + delim + j] = get[j]
        else:
            val[i] = b[i]

    return val


def dict_to_string(d):
    val = ""
    for k, v in d.items():
        if type(v) is list:
            vs = '/'.join(str(s) for s in v)
        else:
            vs = v
        if len(val) == 0:
            val = k+"="+str(vs)
        else:
            val = val+" "+k+"="+str(vs)

    return val


#
# Loop RDS instances and check if a 'schedule' tag has been set. Next, evaluate value and start/stop instance if needed.
#
def rds_check():
    # Get all reservations.
    instances = rds.describe_db_instances()
    clusters = rds.describe_db_clusters()

    # Get current day + hour (using gmt by default if time parameter not set to local)
    time_zone = os.getenv('TIME', 'gmt')
    if time_zone == 'local':
        hh = int(time.strftime("%H", time.localtime()))
        day = time.strftime("%a", time.localtime()).lower()
        logger.info("-----> Checking RDS instances to start or stop for 'day' " + day + " 'local time' hour " + str(hh))
    elif time_zone == 'gmt':
        hh = int(time.strftime("%H", time.gmtime()))
        day = time.strftime("%a", time.gmtime()).lower()
        logger.info("-----> Checking RDS instances to start or stop for 'day' " + day + " 'gmt' hour " + str(hh))
    else:
        if time_zone in pytz.all_timezones:
            d = datetime.datetime.now()
            d = pytz.utc.localize(d)
            req_timezone = pytz.timezone(time_zone)
            d_req_timezone = d.astimezone(req_timezone)
            hh = int(d_req_timezone.strftime("%H"))
            day = d_req_timezone.strftime("%a").lower()
            logger.info("-----> Checking RDS instances to start or stop for 'day' " +
                        day + " '" + time_zone + "' hour " + str(hh))
        else:
            logger.error('Invalid time timezone string value \"%s\", please check!' % (time_zone))
            raise ValueError('Invalid time timezone string value')

    if not instances:
        logger.error('Unable to find any RDS Instances, please check configuration')
    hh = str(hh)
    rds_loop(instances, hh, day, 'Instance')
    rds_loop(clusters, hh, day, 'Cluster')


#
# Checks the schedule tags for instances or clusters, and stop/starts accordingly
#
def rds_loop(rds_objects, hh, day, object_type):
    started = []
    stopped = []

    for instance in rds_objects['DB'+object_type+'s']:
        if 'DBInstanceStatus' not in instance:
            instance['DBInstanceStatus'] = ''
        if 'Status' not in instance:
            instance['Status'] = ''
        # instance = json.loads(db_instance)
        logger.info("-----> Evaluating RDS instance \"%s\" state: %s" %
                    (instance['DB'+object_type+'Identifier'], instance['DBInstanceStatus']))
        response = rds.list_tags_for_resource(ResourceName=instance['DB'+object_type+'Arn'])
        taglist = response['TagList']
        try:
            # ignore tags on RDS
            data = rds_schedule

            try:
                # Convert the start/stop hour into a list, in case of multiple values
                if checkdate(data, 'start', day, hh) and (instance['DBInstanceStatus'] == 'stopped' or instance['Status'] == 'stopped'):

                    logger.info("-----> Starting RDS instance \"%s\"." % (instance['DB'+object_type+'Identifier']))
                    started.append(instance['DB'+object_type+'Identifier'])
                    if object_type == 'Instance':
                        rds.start_db_instance(DBInstanceIdentifier=instance['DB'+object_type+'Identifier'])
                    if object_type == 'Cluster':
                        rds.start_db_cluster(DBClusterIdentifier=instance['DB'+object_type+'Identifier'])

                elif checkdate(data, 'stop', day, hh) and (instance['DBInstanceStatus'] == 'available' or instance['Status'] == 'available'):
                    logger.info("-----> Stopping RDS instance \"%s\"." % (instance['DB'+object_type+'Identifier']))
                    stopped.append(instance['DB'+object_type+'Identifier'])
                    if object_type == 'Instance':
                        rds.stop_db_instance(DBInstanceIdentifier=instance['DB'+object_type+'Identifier'])
                    if object_type == 'Cluster':
                        rds.stop_db_cluster(DBClusterIdentifier=instance['DB'+object_type+'Identifier'])
            except Exception as e:
                logger.info("ERROR rds_loop \"%s\" " % (e))
                pass  # catch exception if 'stop' is not in schedule.

        except ValueError as e:
            # invalid JSON
            logger.error(e)
            logger.error('Invalid value for tag \"schedule\" on RDS instance \"%s\", please check!' %
                         (instance['DB'+object_type+'Identifier']))


# Main function. Entrypoint for Lambda
def handler(event, context):

    if (ec2_scheduling_enabled == 'True'):
        init()
        check()

    if (rds_scheduling_enabled == 'True'):
        rds_init()
        rds_check()


# Manual invocation of the script (only used for testing)
if __name__ == "__main__":
    # Test data
    test = {}
    handler(test, None)
