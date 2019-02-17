from string import Template
# Graphiql query
# {
#  network{sites{location}}}

import json


def device_in_db():
    query='''{
  network {
    devices {
      deviceData {
        serialNumber
      }
    }
  }
}
'''
    return emc_nbi.query(query)['network']['devices']

def device_pregistered():
    nbiQuery='''
    {
  network {
      discoveredDevices{
        serialNumber
      }
  }
}
'''
    result = emc_nbi.query(nbiQuery)
    results = result['network']['discoveredDevices']
    return results

if emc_vars.get('serialNumber') in device_in_db():
    print "Serial Number ", emc_vars.get('serialNumber'), " already exists, no need to create"
elif emc_vars.get('serialNumber') in device_pregistered():
    print "Serial Number ", emc_vars.get('serialNumber'), " already discovered, no need to create"
else:
    print ("Serial Number not found, will pre-register")
    nbiQuery = '''
    mutation    {
  network{
    preRegisterDevices(input:{
      devices:[
        {
          serialNumber: "$serialNumber"
          gateway: "$gatewayAddress"
          domainName: "$domain"
          siteLocation: "$siteLocation"
          userDiscoveredIP: true
          dnsServer: "$dnsServer"
        }
      ]
    }){
      status
      message

    }
  }
}
    '''
    s = Template(nbiQuery).safe_substitute(
        dict(serialNumber=emc_vars.get('serialNumber'),
             gatewayAddress=emc_vars.get('gatewayAddress'),
             siteLocation=emc_vars.get('siteLocation'),
             domainName=emc_vars.get('domain'),
             dnsServer=emc_vars.get('dnsServer')
            ))
    print s
    results = emc_nbi.query(s)
    print results
    print results.get("status"), results.get("message")
