export GOOS=linux

all:
	go fmt
	go build
	cp debugserver ../verizon/bin

clean:
	$(RM) $(notdir $(GOPATH))
