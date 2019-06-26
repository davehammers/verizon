from sys import exit
import argparse
import requests
import json
from time import sleep
import socket
from subprocess import check_call
from string import Template
import logging
from logging.handlers import RotatingFileHandler
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


site_change_list = []
profile_dict = {}

VERIZON_HOME = '/usr/verizon'
LOG_DIR = '{}/logs'.format(VERIZON_HOME)
QUERY = 'query'
MUTATION = 'mutation'
AUX_IP_FIELD = 'userData1'
DEVICE_IP = 'ipAddress'
DEV_DATA = 'deviceData'


LOG_FORMAT = '%(asctime)s:%(levelname)s:%(funcName)s:%(lineno)s: %(message)s'
log = logging.getLogger('devicescanner')
log.setLevel(logging.DEBUG)
if not len(log.handlers):
    std_handler = logging.StreamHandler()
    std_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    std_handler.setLevel(logging.WARNING)
    log.addHandler(std_handler)


def add_ip_log_handler(ipaddress):
    try:
        os.makedirs(LOG_DIR)
    except Exception:
        pass
    ipaddress_log_file = '{}/{}.txt'.format(LOG_DIR, ipaddress)
    handler = RotatingFileHandler(ipaddress_log_file, maxBytes=100 * 1024, backupCount=1)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)


def send_http_post(args, query):
    url = 'https://{}:8443/nbi/graphql'.format(args.ipaddress)
    try:
        resp = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={'query': query},
            verify=False,
            auth=(args.username, args.password),
            timeout=30
            )
        log.debug(resp)
        log.debug(resp.text)
        return resp
    except Exception:
        return None


def get_profile_list(args):
    profile_query = '''
{
    administration{
        profiles {
            profileId
            profileName
        }
    }
}
'''
    profile_dict.clear()
    resp = send_http_post(args, profile_query)
    if resp is None:
        return None

    try:
        rslt = resp.json()
    except ValueError as e:
        log.error(e)
        return None

    log.debug(json.dumps(rslt, indent=2))
    try:
        profile_list = rslt["data"]["administration"]["profiles"]
    except Exception:
        return None
    for row in profile_list:
        profileId = row.get("profileId")
        profileName = row.get("profileName")
        profile_dict[profileName] = profileId


def get_xmc_device_list(args):
    query = '''
{
    network{
        devices{
            nickName
            sitePath
            ip
            deviceData{
                ipAddress
                userData1
                serialNumber
                profileName
            }
        }
    }
}
    '''
    resp = send_http_post(args, query)
    if resp is None:
        return None

    try:
        rslt = resp.json()
    except ValueError as e:
        log.error(e)
        return None
    log.debug(json.dumps(rslt, indent=2))
    try:
        device_data_list = rslt["data"]["network"]["devices"]
    except Exception:
        return None
    rslt_list = []
    for row in device_data_list:
        entry = row.get(DEV_DATA)
        # does the device entry have a serial number
        if entry.get('serialNumber') is None:
            continue
        # does the user entry contain a valid IP address
        aux_ip = entry.get(AUX_IP_FIELD)
        if not aux_ip:
            continue
        try:
            socket.inet_pton(socket.AF_INET, aux_ip)
        except socket.error as e:
            log.error(e)
            continue
        # check if it matches the ip address
        ip = entry.get(DEVICE_IP)
        if ip and aux_ip == ip:
            continue
        # getting here means the device has an alternamte IP address
        # in aux_ip and it is different than the devices current ipAddress

        rslt_list.append(row)
    return rslt_list


def delete_device(args, row):
    delete_mutation = '''
mutation {
  network {
    deleteDevices(
        input:{
            removeData: true
            devices: [
                {
                    ipAddress: "$ipAddress"
                }
            ]
        }
    ){
      status
      message
    }
  }
}
'''
    device_data = row.get(DEV_DATA)
    delete_cmd = Template(delete_mutation).substitute(ipAddress=device_data.get(DEVICE_IP))
    log.debug('delete device {}'.format(delete_cmd))
    send_http_post(args, delete_cmd)


def add_device(args, row):
    add_mutation = '''
 mutation {
  network {
    createDevices(
        input: {
            devices:[
                {
                    siteLocation:"$sitePath"
                    ipAddress: "$ipAddress"
                    nickName: "$nickName"
                    profileName: "$profileName"
                    profileId: $profileId
                }
            ]
        }
    ){
      status
      message
    }
  }
}
'''
    device_data = row.get(DEV_DATA)
    add_cmd = Template(add_mutation).substitute(
        sitePath=row.get('sitePath'),
        ipAddress=device_data.get(AUX_IP_FIELD),
        nickName=row.get('nickName'),
        profileName=device_data.get('profileName'),
        profileId=profile_dict.get(device_data.get('profileName'))
        )
    log.debug('create device {}'.format(add_cmd))
    resp = send_http_post(args, add_cmd)
    if resp is None:
        return False

    rslt = resp.json()
    log.debug(json.dumps(rslt, indent=2))
    try:
        status = rslt["data"]["network"]["createDevices"]["status"]
    except Exception:
        return False
    if status == "ERROR":
        return False
    return True


def get_site_profile(args, site_path):
    # sample response
    # {
    #   "data" : {
    #     "network" : {
    #       "siteByLocation" : {
    #         "defaultProfile" : "public_v2_Profile",
    #         "location" : "/World/North America/United States/North Carolina/Raleigh"
    #       }
    #     }
    #   }
    # }
    get_site_profile_query = '''
{
    network{
        siteByLocation(location: "$sitePath") {
                deviceData{
                    defaultProfile
                    location
                }
        }
    }
}
'''
    query = Template(get_site_profile_query).substitute(sitePath=site_path)
    resp = send_http_post(args, query)
    if resp is None:
        return None

    rslt = resp.json()
    log.debug(json.dumps(rslt, indent=2))
    try:
        site_dict = rslt["data"]["network"]["siteByLocation"]
    except Exception:
        return None
    return site_dict.get("defaultProfile")


def ping_device(args, device_list):
    for row in device_list:
        device_data = row.get(DEV_DATA)
        aux_ip = device_data.get(AUX_IP_FIELD)
        ping_cmd = 'ping -c 5 -i 3 -w 20 -q {}'.format(aux_ip)
        log.debug(ping_cmd)
        try:
            check_call(ping_cmd, shell=True)
        except Exception as e:
            # ping is not successful
            # don't change the device attributes
            log.error(e)
            continue
        if add_device(args, row):
            # if add was successful, delete the old device
            delete_device(args, row)


def get_params():
    # These are the command line options for jsonrpc_client
    parser = argparse.ArgumentParser(prog='devicescanner')
    parser.add_argument(
        '-d',
        dest='debug',
        help='Enable debug output directly to the terminal',
        action='store_true',
        default=False)
    parser.add_argument(
        '-u',
        dest='username',
        help='Login username for Extreme Management Center')
    parser.add_argument(
        '-p',
        dest='password',
        help='Login password for Extreme Management Center',
        default='')
    parser.add_argument(
        '-i',
        help='Extreme Management Center IP address',
        dest='ipaddress',
        default='extremecontrol')
    args = parser.parse_args()

    try:
        add_ip_log_handler(args.ipaddress)
    except Exception as e:
        log.error(e)
        ipaddress_log_file = '{}/{}.txt'.format(LOG_DIR, args.ipaddress)
        log.error('Cannot open {}'.format(ipaddress_log_file))
        exit(1)

    if args.debug:
        std_handler.setLevel(logging.DEBUG)
    return args


def scanner(args):
    # collect the list of available profile names
    get_profile_list(args)
    # get list of devices from XMC
    # Look for devices with IP addresses in user data
    device_list = get_xmc_device_list(args)
    if device_list is None:
        return
    log.info(json.dumps(device_list, indent=2, sort_keys=True))
    # check if secondary device is reachable
    ping_device(args, device_list)
    log.debug('site_change_list: {}'.format(site_change_list))


def main():
    # get xmc credentials
    args = get_params()

    while True:
        scanner(args)
        # sleep 5 minutes
        sleep(5 * 60)


main()
