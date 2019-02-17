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

site_change_list = []

VERIZON_HOME = '/usr/verizon'
LOG_DIR = '{}/logs'.format(VERIZON_HOME)
QUERY = 'query'
MUTATION = 'mutation'
AUX_IP_FIELD = 'userData1'
DEVICE_IP = 'ipAddress'
DEV_DATA = 'deviceData'


LOG_FORMAT = '%(asctime)s:%(levelname)s:%(funcName)s:%(lineno)s: %(message)s'
log = logging.getLogger('postztp')
log.setLevel(logging.DEBUG)
if not len(log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)


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

    rslt = resp.json()
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
        profileName=device_data.get('profileName')
        )
    log.debug('create device {}'.format(add_cmd))
    send_http_post(args, add_cmd)


def rediscover_device(args, row):
    rediscover_device_mutation = '''
mutation {
  network {
    rediscoverDevices(
        input:{
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
    update_cmd = Template(rediscover_device_mutation).substitute(
        ipAddress=device_data.get(AUX_IP_FIELD),
        serialNumber=device_data.get('serialNumber')
        )
    log.debug('rediscover device {}'.format(update_cmd))
    send_http_post(args, update_cmd)


def move_device_site(args, row):
    move_site_mutation = '''
mutation {
  network {
    configureDevice(
        input: {
            deviceConfig: {
                ipAddress: "$ipAddress"
                generalConfig: {
                    defaultSitePath: "$defaultSitePath"
                }
            }
        }
    ){
      status
      message
    }
  }
}
'''
    device_data = row.get(DEV_DATA)
    move_cmd = Template(move_site_mutation).substitute(
        ipAddress=device_data.get(AUX_IP_FIELD),
        defaultSitePath=row.get('sitePath')
        )
    log.debug('move site {}'.format(move_cmd))
    resp = send_http_post(args, move_cmd)
    xmc_resp = resp.json()
    try:
        if str(xmc_resp['data']['network']['configureDevice']['status']) == 'ERROR':
            site_change_list.append((device_data.get(AUX_IP_FIELD), row.get('sitePath')))
            log.debug('appending {} {} to change list'.format(
                device_data.get(AUX_IP_FIELD),
                row.get('sitePath')))
    except Exception as e:
        log.error(e)


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
        add_device(args, row)
        delete_device(args, row)
        move_device_site(args, row)


def get_params():
    # These are the command line options for jsonrpc_client
    parser = argparse.ArgumentParser(prog='devicescanner')
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

    add_ip_log_handler(args.ipaddress)
    return args


def scanner_move_sites(args):
    global site_change_list
    move_list = list(site_change_list)
    site_change_list = []
    for ip, sitePath in move_list:
        row = {"sitePath": sitePath, DEV_DATA: {AUX_IP_FIELD: ip}}
        move_device_site(args, row)


def scanner(args):
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

    # mutation_test(args)
    # move_site_test(args)
    # log.debug("test site_change_list:{}".format(site_change_list))

    while True:
        scanner(args)
        # sleep 5 minutes
        if site_change_list:
            scanner_move_sites(args)
            sleep(15)
        else:
            sleep(5 * 60)


def mutation_test(args):
    test_row = {
          "sitePath": "/World",
          "nickName": "Switch Moscow",
          "deviceData": {
            "profileName": "public_v1_Profile",
            "userData1": "10.68.69.23",
            "ipAddress": "10.68.69.60",
            "serialNumber": "1633N-42851"
          },
          "ip": "10.68.69.60"
        }
    add_device(args, test_row)
    rediscover_device(args, test_row)


def move_site_test(args):
    site_change_list.append(("10.68.69.60", "/World/Switches/Access/Retail/Zone1/test30"))
    return scanner_move_sites(args)


main()