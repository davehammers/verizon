all: ../verizon/bin/devicescanner ../verizon/bin/startscanner
../verizon/bin/devicescanner: devicescanner.py
	cp -f $? $@
	chmod +x $@

../verizon/bin/startscanner: startscanner
	cp -f $? $@
	chmod +x $@

