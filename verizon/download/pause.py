# Python Scripts provided by Extreme Networks.

# This script is provided free of charge by Extreme.  We hope such scripts are
# helpful when used in conjunction with Extreme products and technology;
# however, scripts are provided simply as an accommodation and are not
# supported nor maintained by Extreme.  ANY SCRIPTS PROVIDED BY EXTREME ARE
# HEREBY PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL EXTREME OR ITS
# THIRD PARTY LICENSORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE USE OR DISTRIBUTION OF SUCH SCRIPTS.

# This script produces a port summary output for selected ports

import argparse
from os.path import (
    basename,
    splitext,
    )
import exsh
import os

'''
    This script provides a combined output of the following EXOS commands

    show ports config port-number no-refresh

    show ports utilization port-number packets

    show port utilization port-number bytes

    show port utilization port-number bandwidth

    show ports txerrors no-refresh port-number

    Show ports 23 statistics no-refresh

    Show ports 23 rxerrors no-refresh

    show port 23 information detail

    show ports 23 wred no-refresh

    show ports 23 flow-control no-refresh

    show ports 23 qosmonitor no-refresh

    show ports 23 qosmonitor congestion no-refresh
'''
_version_ = '1.0.0.1'


class Interface(object):
    def __init__(self):
        self.proc_name = splitext(basename(__file__))[0]

    def get_params(self):
        parser = argparse.ArgumentParser(prog=self.proc_name)
        parser.add_argument(
                'ports',
                help='Ports to display. Default is all ports',
                nargs='?',
                default='')
        parser.add_argument(
                '-v', '--version',
                help='Display version',
                action='store_true',
                default=False)
		parser.add_argument(
				'-p', 'os.system("pause")'
				help='pauses screen output',
				default='')

        self.args = parser.parse_args()
        return self.args

    def __call__(self):
        self.get_params()
        # just display the version and exit
        if self.args.version is True:
            print self.proc_name, "Version:", _version_
            return

        # run these commands in sequence
        cmd_list = [
            ('show ports {} config port-number no-refresh'.format(self.args.ports), False),
            ('show ports {} utilization port-number packets'.format(self.args.ports), False),
            ('show port {} utilization port-number bytes'.format(self.args.ports), False),
            ('show port {} utilization port-number bandwidth'.format(self.args.ports), False),
            ('run script portsum.py {}'.format(self.args.ports), True),  # the script produces its own output
            ('show ports {} information detail'.format(self.args.ports), False),
            ('show ports {} wred no-refresh'.format(self.args.ports), False),
            ('show ports {} flow-control no-refresh'.format(self.args.ports), False),
            ('show ports {} qosmonitor no-refresh'.format(self.args.ports), False),
            ]
        for cmd, no_display in cmd_list:
            print '*' * 80
            print cmd
            if no_display:
                exsh.clicmd(cmd)
            else:
                print exsh.clicmd(cmd, capture=True)


'''
try:
    a = Interface()
    a()
except (KeyboardInterrupt, SystemExit, TypeError):
    pass
'''
a = Interface()
a()
