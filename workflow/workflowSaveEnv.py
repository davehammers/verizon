from os import makedirs
from os.path import dirname
import json

ENV_DIR = '/usr/verizon/env/{serial_no}.json'

path_filename = ENV_DIR.format(serial_no=emc_vars.get('serialNumber'))

# create environment directory if it doesn't exist
try:
    makedirs(dirname(path_filename), 0o777)
except Exception:
    pass

with open(path_filename, 'w') as fd:
    print 'Environment captured in', path_filename
    json.dump(emc_vars, fd, indent=2, sort_keys=True)
