export GOPATH=$(shell pwd)
export GOBIN=$(shell pwd)/../verizon/bin
export GOOS=linux

all:
	go fmt
	go install

clean:
	$(RM) $(notdir $(GOPATH))
