# debugserver 
**Web service for viewing Verizon debug files**

This web service runs next to XMC on https://<ip>:8444

debugserver checks with XMC to see if the user is logged in.

If the user is logged in, debugserver enables viewing of the log files create in `/usr/verizon/logs`.

To build the debug server binary, The Go compiler must be installed on your system. 

Enter the following command to build.

```
make
```