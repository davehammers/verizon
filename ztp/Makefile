BIN_DIR = bin
BUILD_DIR = _build
BUILD_BIN_DIR = $(BUILD_DIR)/bin
BUILD_DEBUGSERVER = $(BUILD_DIR)/debugserver
BUILD_DEVICESCANNER = $(BUILD_DIR)/devicescanner
VERIZON_BASE = verizonXMC
VERIZON_BIN = $(BIN_DIR)/$(VERIZON_BASE)
VERIZON_TAR = $(BUILD_BIN_DIR)/$(VERIZON_BASE).tar

all: $(VERIZON_BIN)

$(VERIZON_BIN): $(VERIZON_TAR)
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

$(VERIZON_TAR): $(BUILD_DEBUGSERVER) $(BUILD_DEVICESCANNER)
	mkdir -p $(@D)
	mkdir -p $(BUILD_DIR)
	cp -r verizon $(BUILD_DIR)
	cd $(BUILD_DIR);tar -cvf ../$@ -C verizon .

$(BUILD_DEBUGSERVER) $(BUILD_DEVICESCANNER):
	mkdir -p $(@D)
	cp -r $(@F) $@
	make -C $@

clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR)/*

release: $(VERIZON_BIN)
	git tag $(date +"%Y-%m-%d")
	git push --tags
