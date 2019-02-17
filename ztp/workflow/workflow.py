from string import Template
import logging
import os


log = logging.getLogger('workflow')
log.setLevel(logging.DEBUG)
if not len(log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s:%(levelname)s:%(funcName)s:%(lineno)s: %(message)s'))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)
log.debug(os.getcwd())


def pre_register_device():
    log.info("Serial Number not found, will pre-register")
    nbiQuery = '''
mutation {
    network{
        preRegisterDevices(
            input:{
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
            }
        )
        {
        status
        message
        }
    }
}
'''
    try:
        # populated string with values from emc_vars
        s = Template(nbiQuery).substitute(emc_vars)
    except Exception as e:
        log.error(e)
        return False

    log.debug(s)
    results = emc_nbi.query(s)['network']['preRegisterDevices']
    log.debug(results)
    log.debug('{} {}'.format(results.get("status"), results.get("message")))
    if results.get("status") == 'SUCCESS':
        return True
    return False


def db_device_list():
    query = '''{
  network {
    devices {
      deviceData {
        serialNumber
      }
    }
  }
}
'''
    log.debug(query)
    result = emc_nbi.query(query)
    log.debug(result)
    # return the list of device serial numbers
    return result['network']['devices']


def preregistered_device_list():
    nbiQuery = '''
    {
  network {
      discoveredDevices{
        serialNumber
      }
  }
}
'''
    log.debug(nbiQuery)
    result = emc_nbi.query(nbiQuery)
    log.debug(result)
    results = result['network']['discoveredDevices']
    return results


def create_site():
    # format the site location from the XMC environment
    query_tpl = '''
mutation {
  network {
    createSite(input :{
      siteLocation: "$siteLocation"
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
          dnsServer:"$dnsServer"
          ntpServer: "$ntpServer"
          domainName:"$domain"
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
    try:
        # populated string with values from emc_vars
        query = Template(query_tpl).substitute(emc_vars)
    except Exception as e:
        log.error(e)
        return None
    log.debug(query)

    response = emc_nbi.query(query)
    log.debug(response)

    try:
        return response["network"]['create_site']["siteId"]
    except Exception as e:
        # response isn't valid
        log.error(e)
        return None


def get_site_id():
    nbiQuery = '''{
      network {
        siteByLocation(location:"$siteLocation"){
          siteId
          siteName
          location
        }
      }
    }
    '''
    try:
        # populated string with values from emc_vars
        q = Template(nbiQuery).substitute(emc_vars)
    except Exception as e:
        log.error(e)
        return None
    log.debug(q)

    result = emc_nbi.query(q)
    log.debug(result)

    try:
        return result['network']['siteByLocation']['siteId']
    except Exception as e:
        # response isn't valid
        log.error(e)
        return None


def main():
    # for debugging, dump all of emc_vars to see what values are available
    for k in sorted(emc_vars.keys()):
        log.debug('{}:{}'.format(k, emc_vars[k]))
    # publish the siteLocation to the workflow environment
    try:
        siteLocation = Template('$zone/$siteName').substitute(emc_vars)
        log.debug(siteLocation)
        # update our current environment
        emc_vars['siteLocation'] = siteLocation
        # also put this in results for any following scripts
        emc_results.put('siteLocation', siteLocation)
    except Exception as e:
        log.error(e)
        emc_results.setStatus(emc_results.Status.ERROR)
        return

    # does site exist?
    for retry in [0, 1]:
        site_id = get_site_id()
        # is site_id valid?
        if site_id:
            break
        # site does not exist, create it
        site_id = create_site()
        log.info('created site id {}'.format(site_id))
    else:
        # something went wrong, tell XMC
        emc_results.setStatus(emc_results.Status.ERROR)
        return

    # publish the site to the environment
    log.debug('publish site id {}'.format(site_id))
    emc_results.put("siteId", str(site_id))

    # does the serial number already exist or is it pre-registered
    if emc_vars.get('serialNumber') in db_device_list():
        log.info("Serial Number {} already exists, no need to create".format(
            emc_vars.get('serialNumber')))
        emc_results.setStatus(emc_results.Status.SKIPPED)
    elif emc_vars.get('serialNumber') in preregistered_device_list():
        log.info("Serial Number {} already discovered, no need to create".format(
            emc_vars.get('serialNumber')))
        emc_results.setStatus(emc_results.Status.SKIPPED)
    else:
        # device wasn't found, pre register it
        if pre_register_device() is True:
            emc_results.setStatus(emc_results.Status.SUCCESS)
        else:
            emc_results.setStatus(emc_results.Status.ERROR)


main()
