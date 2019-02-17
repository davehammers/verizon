from string import Template


def preRegisterDevice(siteLocation, serialNumber):
    query_tpl = '''
mutation	{
  network{
    preRegisterDevices(input:{
      devices:[
        {
          serialNumber: "${serialNumber}"
          gateway: "${gatewayAddress}"
          domainName: "labtest.homelab.com"
          siteLocation: "${location}"
          userDiscoveredIP: true
          dnsServer: "${dnsServer}"
        }
      ]
    }){
      status
      message

    }
  }
} '''
    query = Template(query_tpl).safe_substitute(emc_vars)
    print query
    response = emc_nbi.query(query)
    return response["network"]["preRegisterDevices"]


# results = preRegisterDevice(emc_vars["siteLocation"], emc_vars["serialNumber"])
results = preRegisterDevice('a', 'b')
print results
if results.get("status") == "SUCCESS":
    print "preRegisterDevice success"
else:
    print "preRegisterDevice failed"
