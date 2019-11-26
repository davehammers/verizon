# Verizon XMC and EXOS customizations

This repo contains customization created for Verizon to enhance the Extreme Management Center and ExtremeXOS switch opererating system.

The directories are organized as:

```
 ── ztp
    ├── debugserver
    ├── devicescanner
    ├── postztp
    ├── verizon
    │   ├── bin
    │   ├── config
    │   └── download
    └── workflow
```
-	[debugserver](https://github.com/davehammers/verizon/tree/master/ztp/debugserver) Server for web debug log viewer
-	[devicescanner](https://github.com/davehammers/verizon/tree/master/ztp/devicescanner) Looks for ZTP devices and moves them to the correct site
-	[postztp](https://github.com/davehammers/verizon/tree/master/ztp/postztp) Use by XMC to process devices after ZTP
-	[verizon](https://github.com/davehammers/verizon/tree/master/ztp/verizon) Verizon working directory contents for XMC
-   [verizon/download](https://github.com/davehammers/verizon/tree/master/ztp/verizon/download) Custom EXOS scripts downloaded to a switch during ZTP
-	[workflow XMC scripts](https://github.com/davehammers/verizon/tree/master/ztp/workflow) Used by XMC workflow to configure ZTP behavior

