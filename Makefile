VERIZON_BASE = verizonXMC
VERIZON_TAR = $(VERIZON_BASE).tar
all:
	@echo
	@echo "make verizon to build a self extracting file for verizon"
	@echo

PHONY: verizon debugserver devicescanner
verizon: $(VERIZON_BASE)

$(VERIZON_BASE): $(VERIZON_TAR)
	@echo Building self extracting file $@
	@echo "#!/bin/bash" > $@
	@echo "set -x" >> $@
	@echo "echo" >> $@
	@echo "echo Installing the Verizon Files" >> $@
	@echo "echo ===================================" >> $@
	@echo "echo" >> $@
	@echo "echo \$$0" >> $@
	@echo "mkdir -p /usr/verizon" >> $@
	@echo "sed -e '1,/^__ARCHIVE_BEGIN__\$$/d' \$$0 | tar -xvf - -C /usr/verizon" >> $@
	@echo "chmod 0777 /usr/verizon" >> $@
	@echo "chmod +x /usr/verizon/bin/*" >> $@
	@echo "kill -9 \`ps -e | grep debugserver | nawk -e '{print \$$1}'\`" >> $@
	@echo "rm -f nohup.out" >> $@
	@echo "nohup /usr/verizon/bin/debugserver 8444&" >> $@
	@echo "cd /usr/verizon/config" >> $@
	@echo "if [ ! -f accounts.yaml ]; then cp template.accounts.yaml accounts.yaml; fi" >> $@
	@echo "if [ ! -f exoscli.txt ]; then cp template.exoscli.txt exoscli.txt; fi" >> $@
	@echo "if [ ! -f zone.yaml ]; then cp template.zone.yaml zone.yaml; fi" >> $@
	@echo "exit 0" >> $@
	@echo "__ARCHIVE_BEGIN__" >> $@
	@cat $? >> $@
	@chmod +x $@

$(VERIZON_TAR): debugserver devicescanner
	tar -cvf verizonXMC.tar -C verizon .

debugserver devicescanner:
	make -C $@

clean:
	rm -f $(VERIZON_TAR) $(VERIZON_BASE)
