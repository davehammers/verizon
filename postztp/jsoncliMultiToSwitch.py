from jsonrpc import JsonRPC
import os


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
                    print 'Reply:', cli_output


def main():
    # ask the switch for its serial number
    serial_no = get_switch_serial_no()

    # establish a JSONRPC session with the switch
    switch = create_JSONRPC_session()

    # open the file with the switch CLI commands
    # then send each command to the switch using JSONRPC CLI method
    cmd_file_name = '../standalone/deployments/Monitor.war/scripts/{}.xsf'.format(serial_no)
    with open(cmd_file_name, 'r') as fd:
        cmd = fd.read().splitlines()
        print 'Send:', cmd
        try:
            json_rslt = switch.cli(cmd)
        except Exception as e:
            print e
            return
        # print 'JSON results', json_rslt
        if not json_rslt:
            print 'Did not get a propper JSONRPC response'
            return

        if isinstance(json_rslt, dict):
            result = json_rslt.get('result')
            if "error" in result:
                print 'Command error:', result.get('error')
                return
        remote_cli_screen_display(result)
        print


# dump the runtime environment
dump_debug()
# call main processing
main()
