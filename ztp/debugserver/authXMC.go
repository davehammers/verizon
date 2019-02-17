package main

// Copyright (c) 2018 by Extreme Networks Inc.

import (
	"net/http"
)

func checkWithXMC(r *http.Request) (w *http.Response, err error) {

	client := &http.Client{}
	req, _ := http.NewRequest("HEAD", "https://extremecontrol:8443/nbi/", nil)

	// check the headers with XMC to see if it likes the auth values
	copyHeader(req.Header, r.Header)
	dumpReq("to XMC", req)

	resp, err := client.Do(req)
	dumpResp("after files", resp)

	return resp, err
}
