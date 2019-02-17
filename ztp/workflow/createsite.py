import json
from string import Template
# from xmclib import nbi

def createSite(siteLocation):
    query_tpl ='''mutation {
  network {
    createSite(input :{
      siteLocation: "$location"
      siteConfig: {
        customActionsConfig:{
          mutationType: REPLACE_ALL
          customActionConfig:[{
            vendor: "Extreme"
            family: "Summit Series"
            topology: "Any"
            enabled: true
            task: "Save Config"
          }]
        }
        ztpPlusDefaultsConfig:{
          useDiscoveredIP:true
          dnsServer:"${dnsServer}"
          ntpServer: "${ntpServer}"
          domainName:"${dnsDomain}"
          pollType:SNMP
          lacp:true
          lacpLoggingLevel:ERROR
          lldp:true
          lldpLoggingLevel:ERROR
          poe:true
          poeLoggingLevel:ERROR
        }
      }
    }){
      status
      message
      siteLocation
      siteId
    }
  }
}'''
    query = Template(query_tpl).substitute(
        dict(location=siteLocation,
            dnsServer=emc_vars.get('dnsServer'),
            ntpServer=emc_vars.get('ntpServer'),
            dnsDomain=emc_vars.get('dnsDomain')
            ))
    print query
    response = emc_nbi.query(query);
    print response
    return dict(response["network"]["createSite"])

def main():
    results = createSite(emc_vars["siteLocation"])
    if results.get("status") == "SUCCESS":
        siteId=str(results.get("siteId"))
        emc_results.put("siteId",siteId)
    else:
        errorMessage = results.get("message")
        emc_results.put("errorMessage",errorMessage)
        raise Exception("createSite failed: ",errorMessage)

main()
