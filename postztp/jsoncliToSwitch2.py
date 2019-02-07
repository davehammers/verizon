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
EXOS_WRAPUP_CLI = '{}/exoswrapup.txt'.format(CONFIG_DIR)
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
    handler = RotatingFileHandler(serial_log_file, maxBytes=500 * 1024, backupCount=1)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)


def import_workflow_env(serial_no):
    env_file = '{}/{}.json'.format(ENV_DIR, serial_no)
    with open(env_file, 'r') as fd:
        workflow_env = json.load(fd)
        # variables may be IP address with a CIDR
        # create a <name>Noslash version automatically
        # e.g. mgmtIP = 10.10.10.1/16, mgmtIPNoslash = 10.10.10.1
        for k, v in workflow_env.items():
            if '/' in v:
                lpart, _, rpart = v.rpartition('/')
                workflow_env['{}Noslash'.format(k)] = lpart
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


# check the file for consistency
# each block type must have the same parameters defined
# e.g. if a,b,c is present for one block, a,b,c must be present
# for all blocks.
#    [
#    {
#        "user": {
#            "login": "dave",
#            "password": "extreme",
#            "level": "admin"
#        }
#    },
#    {
#        "user": {
#            "login": "neil",
#            "password": "verizon",
#            "level": "admin"
#            "superPower": "xray vision" <--- this is out of place
#        }
#    }
#    ]
def accounts_file_ok(accounts_env):
    for row in accounts_env:
        for row2 in accounts_env:
            # are the block types the same?
            if set(row.keys()) != set(row2.keys()):
                # no skip this block
                continue
            for v in row.values():
                for v2 in row2.values():
                    if set(v.keys()) == set(v2.keys()):
                        continue
                    # if we are here the keys are not the same in 2 blocks of   the same type
                    log.error("+++ Configuraiton error. Account blocks have different parameters")
                    log.error('\n{}{}'.format(
                        json.dumps(row, indent=2),
                        json.dumps(row2, indent=2)))
                    return False
    return True


def configure_switch_accounts():
    # assume switch accounts are stored somewhere else
    # Here we simulate remote accounts by reading them from a file
    accounts_env = []
    try:
        with open(ACCOUNT_CFG) as fd:
            accounts_env = yaml.load(stream=fd)
    except Exception as e:
        log.error(e)
        return []
    if accounts_file_ok(accounts_env):
        return accounts_env
    raise Exception("++++++ {} file is inconsistent".format(ACCOUNT_CFG))
    return accounts_env


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


def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z


# for each block in the accounts file
# create an output EXOS CLI command
def EXOS_combined_group_cli(cmd, grouptype, workflow_env, accounts_env):
    for row in accounts_env:
        for k, v in row.items():
            if k != grouptype:
                continue
            try:
                xlate_cli = Template(cmd).substitute(merge_two_dicts(workflow_env, v))
                # log.debug("Accounts translated CLI: {}".format(xlate_cli))
                cli_list.append(xlate_cli)
            except Exception as e:
                log.error(e)


# try to combine the workflow environment with the account groups
# to see if a CLI substitution will work
def EXOS_cli_accounts_and_workflow(cmd, workflow_env, accounts_env):
    # try the differnt blocks of information in the accounts file
    for row in accounts_env:
        for k, v in row.items():
            try:
                # test to see if the substitution works with data from the accounts file
                Template(cmd).substitute(merge_two_dicts(workflow_env, v))
            except Exception:
                continue
            # the substitution worked
            # lets do it for each accounts data block
            EXOS_combined_group_cli(cmd, k, workflow_env, accounts_env)
            return True
    return False


# for each block in the accounts file
# create an output EXOS CLI command
def EXOS_account_group_cli(cmd, grouptype, accounts_env):
    for row in accounts_env:
        for k, v in row.items():
            if k != grouptype:
                continue
            try:
                xlate_cli = Template(cmd).substitute(v)
                # log.debug("Accounts translated CLI: {}".format(xlate_cli))
                cli_list.append(xlate_cli)
            except Exception as e:
                log.error(e)


def EXOS_cli_account_test(cmd, accounts_env):
    # try the differnt blocks of information in the accounts file
    for row in accounts_env:
        for k, v in row.items():
            try:
                # test to see if the substitution works with data from the accounts file
                Template(cmd).substitute(v)
            except Exception:
                continue
            # the substitution worked
            # lets do it for each accounts data block
            EXOS_account_group_cli(cmd, k, accounts_env)
            return True
    return False


# Read the EXOS CLI command file with embedded variables
# This function will substitute the variables with values
# from the XMC workflow and/or the accounts.yaml file.
#
def import_EXOS_cli(workflow_env, accounts_env):
    with open(EXOS_CLI_CFG, 'r') as fd:
        for cmd in fd.read().splitlines():
            # strip off any comments that begin with #
            cmd = cmd.split('#', 1)[0]
            # remove any leading/trailing whitespace
            cmd = cmd.strip()
            if not cmd:
                continue
            try:
                # first see if the command line substitution works with the worflow env
                xlate_cli = Template(cmd).substitute(workflow_env)
                cli_list.append(xlate_cli)
                continue
            except Exception:
                pass

            if EXOS_cli_account_test(cmd, accounts_env):
                continue
            if EXOS_cli_accounts_and_workflow(cmd, workflow_env, accounts_env):
                continue

            # nothing worked for the entry in the EXOS CLI
            msg = '\n+++ EXOS CLI could not be processed:\n--->{}'.format(cmd)
            log.error(msg)
            raise Exception(msg)


def zone_parameters(workflow_env):
    log.debug('Processing Zone Parameters')
    zone_env = None
    try:
        with open(ZONE_CFG) as fd:
            zone_env = yaml.load(stream=fd)
            log.debug(json.dumps(zone_env, indent=2))
            if not accounts_file_ok(zone_env):
                raise Exception("++++++ {} file is inconsistent".format(ZONE_CFG))
    except Exception as e:
        log.error(e)
        raise
    if zone_env is None:
        log.error('{} is empty or formatted wrong'.format(ZONE_CFG))

    my_zone = workflow_env.get('zone')
    log.debug('My Zone: {}'.format(my_zone))
    if my_zone is None:
        print "No zone found in workflow_env"
        return

    for zone_row in zone_env:
        log.debug(zone_row)
        log.debug(zone_row.items())
        try:
            k, v = zone_row.items()[0]
        except Exception as e:
            log.error(e)
            continue
        zoneName = v.get('name')
        if zoneName is None:
            log.error('zone entry missing name field {}', zone_row)
            continue

        if not my_zone.endswith(zoneName):
            continue

        log.debug('Found zone: {}'.format(json.dumps(zone_row)))

        # update the workflow_env with the zone variables
        workflow_env.update(v)
        return


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


# Function "get_stp_domain" takes the user entered hostname from the workflow
# and gets everything before the dash "-" and uses that as the spanning tree domain
# name per Verizon convention. The dash should always be in the 10th position in the hostname.
# A consideration for later is that for India locations there will not be a dash
# but an "i" (lowercase) but it will also be in the 10th position. The code below
# only looks for the dash.
def get_stp_domain(workflow_env):
    stpd = workflow_env.get('hostname')
    if '-' in stpd:
        stpd = stpd.split('-')[0]
        workflow_env['domain'] = stpd
        log.debug("domain value changed to {}".format(workflow_env.get('domain')))
    else:
        log.debug('{} is not a valid hostname'.format(stpd))
    log.debug(workflow_env['domain'])


def send_commands_to_switch(switch):
    log.debug('Sending CLI commands to the switch')
    log.debug('-' * 40)
    log.debug('\n{}'.format('\n'.join(cli_list)))
    log.debug('-' * 40)
    for cmd in cli_list:
        # remove any leading/trailing whitespace and newline
        cmd = cmd.strip()
        log.debug('Send: {}'.format(cmd))
        try:
            # json_rslt = switch.cli(cmd)
            rslt = emc_cli.send(cmd)
            log.debug("\n{}".format(rslt.getOutput()))
        except Exception as e:
            log.error(e)
            continue
        # print 'JSON results', json_rslt
        '''
        if not json_rslt:
            log.error('Did not get a propper JSONRPC response')
            continue

        if isinstance(json_rslt, dict):
            result = json_rslt.get('result')
            if "error" in result:
                log.error('Command error: {}'.format(result.get('error')))
                continue
        remote_cli_screen_display(result)
        '''
        log.debug('')
    log.debug("+" * 40)
    log.debug('Configuration Complete')
    log.debug("+" * 40)


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

    # Modify the worflow_env
    # Use the hostname before "-" as stpDomain name
    get_stp_domain(workflow_env)

    # get accounts from parameter file
    # these variables are used to repeat commands per each configuration
    # block of data.
    accounts_env = configure_switch_accounts()

    # process any zone specific variables and update the workflow_env
    zone_parameters(workflow_env)

    # download switch add ons
    download_add_ons()

    # import EXOS CLI
    # All of the CLI variables substitutions happen at this point
    # The translatted commands will be downloaded to the switch below
    import_EXOS_cli(workflow_env, accounts_env)

    # establish a JSONRPC session with the switch
    switch = create_JSONRPC_session()

    # All variable substitution is complete. Send all CLI commands
    # to the switch
    send_commands_to_switch(switch)

    # update XMC with the auxillary IP addres in user data1
    store_aux_ip(workflow_env)


# call main processing
main()
