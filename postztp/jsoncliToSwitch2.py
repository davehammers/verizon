from jsonrpc import JsonRPC
import os
import yaml
import json
from string import Template
from subprocess import call
import socket
import logging
from logging.handlers import RotatingFileHandler


# directories and files
VERIZON_HOME = '/usr/verizon'
VERIZON_LST = 'verizon.lst'
WEB_DIR = '../standalone/deployments/Monitor.war/scripts/'
WEB_LIST = '{}/{}'.format(WEB_DIR, VERIZON_LST)
LST_FILE = '{}/{}'.format(VERIZON_HOME, VERIZON_LST)
DOWNLOAD_DIR = '{}/download'.format(VERIZON_HOME)
CONFIG_DIR = '{}/config'.format(VERIZON_HOME)
EXOS_CLI_CFG = '{}/exoscli.txt'.format(CONFIG_DIR)
ACCOUNT_CFG = '{}/accounts.yaml'.format(CONFIG_DIR)
ZONE_CFG = '{}/zone.yaml'.format(CONFIG_DIR)
SERIAL_ENV_DIR = '{}/env'.format(VERIZON_HOME)
LOG_DIR = '{}/logs'.format(VERIZON_HOME)
ENV_DIR = '{}/env'.format(VERIZON_HOME)

# aggregate all of the command into a list before sending to EXOS
cli_list = []

LOG_FORMAT = '%(asctime)s:%(levelname)s:%(funcName)s:%(lineno)s: %(message)s'
log = logging.getLogger('postztp')
log.setLevel(logging.DEBUG)
if not len(log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)


def dump_debug():
    print os.getcwd()

    for k in sorted(emc_vars.keys()):
        print k, emc_vars.get(k)


def get_switch_serial_no():
    # ask the switch it's serial number
    try:
        rslt = emc_cli.send('show version')
        cli_out = rslt.getOutput()
        for line in cli_out.splitlines():
            if line.startswith('Switch'):
                parts = line.split()
                return parts[3]
    except Exception as e:
        print e
    return None


def add_serial_log_handler(serial_no):
    try:
        os.makedirs(LOG_DIR)
    except Exception:
        pass
    serial_log_file = '{}/{}.txt'.format(LOG_DIR, serial_no)
    handler = RotatingFileHandler(serial_log_file, maxBytes=100 * 1024, backupCount=1)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)


def import_workflow_env(serial_no):
    env_file = '{}/{}.json'.format(ENV_DIR, serial_no)
    with open(env_file, 'r') as fd:
        workflow_env = json.load(fd)
        log.debug('Workflow environment \n{}'.format(json.dumps(workflow_env, indent=2)))
        return workflow_env


def create_JSONRPC_session():
    return JsonRPC(
        ipaddress=emc_vars.get('deviceIP'),
        username=emc_vars.get('deviceLogin'),
        password=emc_vars.get('devicePwd'))


def remote_cli_screen_display(out_list):
    # this function searches for all of the 'CLIoutput' entries and
    # displays them as they would have shown on the EXOS shell output
    #
    # If multiple commands were sent in the request, there will be
    # one CLIoutput entry per command
    if isinstance(out_list, list):
        for cli_out in out_list:
            if isinstance(cli_out, list):
                remote_cli_screen_display(cli_out)
                continue
            if isinstance(cli_out, dict):
                cli_output = cli_out.get('CLIoutput')
                if cli_output is not None:
                    log.debug('Reply: {}'.format(cli_output))


def configure_switch_accounts(workflow_env):
    accounts = None
    # assume switch accounts are stored somewhere else
    # Here we simulate remote accounts by reading them from a file
    try:
        with open(ACCOUNT_CFG) as fd:
            accounts = yaml.load(stream=fd)
    except Exception as e:
        print e
        return

    if accounts is None:
        print "Account file", ACCOUNT_CFG, "notfound"
        return
    user_cnt = 0
    for row in accounts:
        user_row = row.get('user')
        if user_row:
            user_cnt += 1
            workflow_env['login{}'.format(user_cnt)] = user_row.get('login', '')
            workflow_env['password{}'.format(user_cnt)] = user_row.get('password', '')
            workflow_env['level{}'.format(user_cnt)] = user_row.get('level', '')
        snmp_row = row.get('snmp')
        if snmp_row:
            workflow_env['snmpWriteView'] = snmp_row.get('snmpWriteView', '')
            workflow_env['snmpReadWrite'] = snmp_row.get('snmpReadWrite', '')
            workflow_env['snmpReadOnly'] = snmp_row.get('snmpReadOnly', '')




def download_add_ons():
    try:
        os.mkdir(WEB_DIR)
    except Exception:
        pass
    cmd = 'tar -cvf {} -C {} .'.format(LST_FILE, DOWNLOAD_DIR)
    call(cmd, shell=True)
    call('ln {} {}'.format(LST_FILE, WEB_LIST), shell=True)
    try:
        rslt = socket.getaddrinfo('extremecontrol', socket.AF_INET)
        server_ip = rslt[0][4][0]
    except Exception:
        server_ip = emc_vars.get('serverIP')

    cli_list.append('download url https://{}:8443/scripts/{}'.format(
        server_ip, VERIZON_LST))


def import_EXOS_cli(workflow_env):
    with open(EXOS_CLI_CFG, 'r') as fd:
        for cmd in fd.read().splitlines():
            cmd = cmd.split('#', 1)[0]
            cmd = cmd.strip()
            if cmd:
                xlate_cli = Template(cmd).substitute(workflow_env)
                cli_list.append(xlate_cli)


def zone_parameters(workflow_env):
    log.debug('Processing Zone Parameters')
    pri_sec = ['primary', 'secondary']
    zone_info = None
    try:
        with open('{}/zone.yaml'.format(CONFIG_DIR)) as fd:
            zone_info = yaml.load(stream=fd)
            log.debug(zone_info)
    except Exception as e:
        log.error(e)
        return

    my_zone = workflow_env.get('zone')
    log.debug('My Zone: {}'.format(my_zone))
    if my_zone is None:
        print "No zone found in workflow_env"
        return
    for zone_row in zone_info:
        zone = zone_row.get('zone')
        log.debug('Zone: {}'.format(zone))
        if not my_zone.endswith(zone):
            # log.debug('No Match')
            continue

        # TACACS parameters
        tacacs = zone_row.get('tacacs')
        log.debug('TACACS: {}'.format(tacacs))
        if tacacs:
            for p in pri_sec:
                # configure tacacs [primary | secondary] server [ipaddress | hostname]
                #   {tcp_port} client-ip ipaddress {vr vr_name}
                ip = tacacs.get(p)
                if p:
                    cmd = 'configure tacacs {pri_sec} server {ip} client-ip {client} vr VR-Default'.format(
                        pri_sec=p,
                        ip=ip,
                        client=workflow_env.get('mgmtIP')
                    )
                    cli_list.append(cmd)

        # NTP client params
        ntp = zone_row.get('ntp')
        log.debug('SNTP: {}'.format(ntp))
        if ntp:
            for p in pri_sec:
                ip = ntp.get(p)
                if p:
                    cmd = 'configure sntp-client {pri_sec} {ip} vr VR-Default'.format(
                        pri_sec=p,
                        ip=ip
                    )
                    cli_list.append(cmd)


def store_aux_ip(workflow_env):
    aux_ip_mutation = '''
mutation {
  network {
    configureDevice(
        input:{
            deviceConfig: {
                ipAddress: "$ipAddress"
                deviceAnnotationConfig: {
                  userData1: "$userData1"
                  nickName: "$nickName"
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
    aux_ip = workflow_env.get('mgmtIP')
    if '/' in aux_ip:
        aux_ip = aux_ip.split('/')[0]
    aux_ip_cmd = Template(aux_ip_mutation).substitute(
        ipAddress=emc_vars.get('deviceIP'),
        userData1=aux_ip,
        nickName=workflow_env.get('hostname', "")
        )
    log.debug(aux_ip_cmd)
    resp = emc_nbi.query(aux_ip_cmd)
    log.debug(resp)


def main():
    # ask the switch for its serial number
    serial_no = get_switch_serial_no()

    # add serial number specific log handler
    add_serial_log_handler(serial_no)
    log.debug('*' * 80)
    log.debug('Start {}'.format(serial_no))
    log.debug('*' * 80)

    # dump the runtime environment
    dump_debug()

    # get the runtime environment from the workflow process
    workflow_env = import_workflow_env(serial_no)

    # get accounts from parameter file
    configure_switch_accounts(workflow_env)

    # download switch add ons
    download_add_ons()

    # import EXOS CLI
    import_EXOS_cli(workflow_env)

    # process any zone specific parameters
    zone_parameters(workflow_env)

    # establish a JSONRPC session with the switch
    switch = create_JSONRPC_session()

    log.debug('Sending CLI commands to the switch')
    log.debug('-' * 40)
    log.debug('\n{}'.format('\n'.join(cli_list)))
    log.debug('-' * 40)
    for cmd in cli_list:
        # remove any leading/trailing whitespace and newline
        cmd = cmd.strip()
        log.debug('Send: {}'.format(cmd))
        try:
            json_rslt = switch.cli(cmd)
        except Exception as e:
            log.error(e)
            continue
        # print 'JSON results', json_rslt
        if not json_rslt:
            log.error('Did not get a propper JSONRPC response')
            continue

        if isinstance(json_rslt, dict):
            result = json_rslt.get('result')
            if "error" in result:
                log.error('Command error: {}'.format(result.get('error')))
                continue
        remote_cli_screen_display(result)
        log.debug('')
    log.debug("+" * 40)
    log.debug('Configuration Complete')
    log.debug("+" * 40)

    store_aux_ip(workflow_env)


# call main processing
main()
