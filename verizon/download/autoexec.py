# ******************************************************
#  Copyright (c) Extreme Networks Inc. 2018
#  All rights reserved
# ******************************************************
'''
This autoexec.py script will start diagnostics at startup.
Once diagnostic complete, detect if reboot is returning from
diags and do not start them again
'''
from os import remove
from os.path import isfile, splitext, basename
from sys import stderr
from time import sleep
import subprocess

# Determine our running context by which import is available
try:
    import exsh
    i_am_script = True
except Exception:
    i_am_script = False


# **********************************************************************
# This class is invoked in the expy context via the EXOS CLI: create process
# **********************************************************************
class ExpyAutoexec(object):
    def __call__(self):
        # create an empty file to mark we are starting diags
        p = subprocess.Popen(
                ['/exos/bin/exsh', '-n', '0', '-b'],
                stdin=subprocess.PIPE)

        sleep(2)
        # print >> p.stdin, 'run diagnostics normal'
        # HACK TODO just reboot to simulate diags running in test env
        print >> p.stdin, 'reboot'
        print 'simulating runing diags by just rebooting'

        # Running Diagnostics will disrupt network traffic.
        # Are you sure you want to continue? (y/N) Yes
        # HACK TODO put these back for production
        # sleep(2)
        # print >> p.stdin, 'y'

        # Do you want to save configuration changes to currently selected configuration file (primary.cfg)?
        sleep(2)
        print >> p.stdin, 'n'


# **********************************************************************
# This class is invoked from autoexec.py
# **********************************************************************
class Autoexec(object):
    def __init__(self):
        self.process_name = splitext(basename(__file__))[0]
        self.diag_lock = '/usr/local/cfg/diag.lock'

    def __call__(self):
        # cleanup from previous run
        try:
            exsh.clicmd('delete process {}'.format(self.process_name))
        except Exception:
            pass

        if isfile(self.diag_lock):
            # returning from a diagnostics reboot
            remove(self.diag_lock)
            self.fix_mgmt_port()
            return

        # create an EXOS process that starts diagnostics
        print >> stderr, "\nStarting Diagnostics\n"
        with open(self.diag_lock, 'w'):
            pass
        # create the EXOS expy backend process
        exsh.clicmd('create process {0} python-module {0} start on-demand'.format(self.process_name))

        slot_clause = ''
        exsh.clicmd('start process {0} {1}'.format(self.process_name, slot_clause))
    
    def fix_mgmt_port(self):
        try:
            exsh.clicmd('unconfigure vlan Mgmt ipaddress')
            exsh.clicmd('enable dhcp vlan Mgmt')
        except Exception:
            pass



# **********************************************************************
# Determine the run time context and invoke the proper class
# **********************************************************************
if __name__ == '__main__':
    if i_am_script is True:
        # started from autoexec.py
        autoexec = Autoexec()
        autoexec()
    else:
        # Script was started as EXOS process
        expy_autoexec = ExpyAutoexec()
        expy_autoexec()
