package main

import (
	"crypto/tls"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	//	"net/http/httputil"
	"os"
	"strconv"
	"strings"
)

func fileServer(w http.ResponseWriter, req *http.Request) {
	// The incomming request URL is a relative path name of a file or directory
	// The name is relative to the CWD when this program was started
	name := fmt.Sprintf("%s", strings.TrimLeft(req.URL.String(), "/"))
	if len(name) == 0 {
		name = "."
	}

	// stat the file/dir name
	fi, err := os.Stat(name)
	if err != nil {
		return
	}

	// handle the file type of directory or file
	switch mode := fi.Mode(); {
	case mode.IsDir():
		// read the directory into fileList
		fileList, err := ioutil.ReadDir(name)
		if err != nil {
			fmt.Println("Error reading directory")
			return
		}

		// prepart the HTTP response to be constant width
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		// fmt.Fprintf(w, "<pre style=\"font-size: 16px\">\n")
		fmt.Fprintf(w, "<pre style=\"font-size: larger\">\n")

		// Browser headings
		fmt.Fprintf(w, "Directory: %s\n\n", name)

		// list each file/directory with permissions and size
		// for dir names, add ah '/' to the end
		var entryName string
		for _, f := range fileList {
			entryName = f.Name()
			if f.IsDir() {
				entryName = entryName + "/"
			}

			// format the line for the browser
			fmt.Fprintf(w, "%10s %9d  %17s <a href=\"%s\">%s</a>\n",
				f.Mode().String(),
				f.Size(),
				f.ModTime().Format("_2-Jan-2006 15:04"),
				fmt.Sprintf("/%s/%s", name, f.Name()),
				entryName)
		}

		// end of http block
		fmt.Fprintf(w, "</pre>\n")
	case mode.IsRegular():
		// for file names, copy the file to the browser
		from, err := os.Open(name)
		if err != nil {
			log.Fatal(err)
		}
		defer from.Close()
		// prepart the HTTP response to be constant width
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		// fmt.Fprintf(w, "<pre style=\"font-size: 16px\">\n")
		fmt.Fprintf(w, "<pre>\n")
		_, err = io.Copy(w, from)
		// end of http block
		fmt.Fprintf(w, "</pre>\n")

	}

}

func dumpReq(title string, r *http.Request) {
	/*
		dump, err := httputil.DumpRequest(r, true)
		if err != nil {
			log.Println(err)
			return
		}
		log.Println(title)
		log.Println(string(dump))
	*/
}

func dumpResp(title string, resp *http.Response) {
	/*
		dump, err := httputil.DumpResponse(resp, true)
		if err != nil {
			log.Println(err)
			return
		}
		log.Println(title)
		log.Println(string(dump))
	*/
}

func copyHeader(dst, src http.Header) {
	for k, vv := range src {
		for _, v := range vv {
			dst.Add(k, v)
		}
	}
}
func authentication(next http.Handler) http.Handler {

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// authenticate each request before proceeding to the next function
		dumpReq("from broswer", r)

		resp, err := checkWithXMC(r)
		if err != nil {
			// http.NotFound(w, r)
			http.Error(w, "Cannot resolve extremecontrol network domain name", 404)
			return
		}
		if resp.StatusCode == http.StatusUnauthorized {

			// w.Header().Set("WWW-Authenticate", `Basic realm="XMC debug"`)
			w.WriteHeader(401)
			w.Write([]byte(`<font size="+2">Login to Extreme Management Center before using the debugging service.</font>`))
			return
		}
		dumpReq("Before files", r)

		copyHeader(w.Header(), resp.Header)
		next.ServeHTTP(w, r)
	})
}

func main() {
	var err error
	// get the server port number from the command line
	port := 443
	if len(os.Args) == 2 {
		port, err = strconv.Atoi(os.Args[1])
	}
	log.Println("Server started at http://localhost:", port)

	// get certificates for HTTPS
	certificate, privkey, err := certKeys()
	defer os.Remove(certificate) // clean up
	defer os.Remove(privkey)     // clean up
	if err != nil {
		log.Fatal("Cannot locate certificates for HTTPS")
	}

	// register handler for the root URL
	fileServerFunc := http.HandlerFunc(fileServer)
	http.Handle("/", authentication(fileServerFunc))

	// log.Fatal(http.ListenAndServe(port, nil))
	http.DefaultTransport.(*http.Transport).TLSClientConfig = &tls.Config{InsecureSkipVerify: true}
	log.Fatal(http.ListenAndServeTLS(
		fmt.Sprintf(":%d", port),
		certificate, privkey,
		nil))
}
