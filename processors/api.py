#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pkg_resources import resource_filename
from .processors import *
from .sentiment import SentimentAnalysisAPI
import os
import shlex
import os
import subprocess as sp
import requests
import time
import sys
import logging


class ProcessorsAPI(object):

    PROC_VAR = 'PROCESSORS_SERVER'

    def __init__(self, port, hostname="127.0.0.1", timeout=120, jar_path=None, log_file=None):

        self.hostname = hostname
        self.port = port
        self.make_address(hostname, port)
        self._start_command = "java -cp {} NLPServer {}"
        self.timeout = timeout
        # how long to wait between requests
        self.wait_time = 2
        # processors
        self.default = Processor(self.address)
        self.fastnlp = FastNLPProcessor(self.address)
        self.bionlp = BioNLPProcessor(self.address)
        # sentiment
        self.sentiment = SentimentAnalysisAPI(self.address)
        # use the os module's devnull for compatibility with python 2.7
        #self.DEVNULL = open(os.devnull, 'wb')

        self.logger = logging.getLogger(__name__)
        self.log_file = self.prepare_log_file(log_file)

        # resolve jar path
        self.resolve_jar_path(jar_path)
        # attempt to establish connection with server
        self.establish_connection()

    def prepare_log_file(self, lf):
        """
        Configure logger and return file path for logging
        """
        # log_file
        log_file = os.path.expanduser(os.path.join("~", ".py-processors.log")) if not lf else os.path.expanduser(lf)
        # attach handler
        handler = logging.FileHandler(log_file)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        return log_file

    def annotate(self, text):
        """
        Uses default processor (CoreNLP) to annotate text.  Included for backwards compatibility.
        """
        return self.default.annotate(text)

    def establish_connection(self):
        """
        Attempt to connect to a server (assumes server is running)
        """
        if self.annotate("Blah"):
            print("Connection with server established!")
        else:
            try:
                # Attempt to start the server
                self._start_server()
            except Exception as e:
                if not os.path.exists(self.jar_path):
                    print("processors-server.jar not found.")
                print("Unable to start server. Please start the server manually with .start_server(\"path/to/processors-server.jar\")")
                print("\n{}".format(e))

    def resolve_jar_path(self, jar_path):
        """
        Attempts to preferentially set value of self.jar_path
        """
        # Preference 1: if a .jar is given, check to see if the path is valid
        if jar_path:
            print("Using provided path")
            jp = os.path.expanduser(jar_path)
            # check if path is valid
            if os.path.exists(jp):
                self.jar_path = jp
        else:
            # Preference 2: if a PROCESSORS_SERVER environment variable is defined, check its validity
            if ProcessorsAPI.PROC_VAR in os.environ:
                print("Using path given via $PROCESSORS_SERVER")
                jp = os.path.expanduser(os.environ[ProcessorsAPI.PROC_VAR])
                # check if path is valid
                if os.path.exists(jp):
                    self.jar_path = jp
                else:
                    print("WARNING: {0} path is invalid.  \nPlease verify this entry in your environment:\n\texport {0}=/path/to/processors-server.jar".format(ProcessorsAPI.PROC_VAR))
            # Preference 3: attempt to use the processors-sever.jar downloaded when this package was installed
            else:
                print("Using default")
                self.jar_path = resource_filename(__name__, "processors-server.jar")

    def start_server(self, jar_path=None, timeout=120):
        """
        Starts processors-sever.jar
        """
        self.timeout = int(float(timeout)/2)
        if jar_path:
            self.jar_path = jar_path
        self._start_server()

    def stop_server(self, port=None):
        """
        Sends a poison pill to the server and waits for shutdown response
        """
        port = port or self.port
        address = "http://{}:{}".format(self.hostname, port)
        shutdown_address = "{}/shutdown".format(address)
        # attempt shutdown
        try:
            response = requests.post(shutdown_address)
            if response:
                print(response.content.decode("utf-8"))
            return True
        # will fail if the server is already down
        except Exception as e:
            pass
        return False

    def _start_server(self, port=None):
        """
        "Private" method called by start_server()
        """
        if port:
            self.port = port
        # build the command
        cmd = self._start_command.format(self.jar_path, self.port)
        #print(cmd)
        self._process = sp.Popen(shlex.split(cmd),
                                 shell=False,
                                 stderr=open(self.log_file, 'wb'),
                                 stdout=open(self.log_file, 'wb'),
                                 universal_newlines=True)

        print("Starting processors-server ({}) on port {} ...".format(self.jar_path, self.port))
        print("\nWaiting for server...")

        progressbar_length = int(self.timeout/self.wait_time)
        for i in range(progressbar_length):
            try:
                success = self.annotate("blah")
                if success:
                    print("\n\nConnection with processors-server established ({})".format(self.address))
                    return True
                sys.stdout.write("\r[{:{}}]".format('='*i, progressbar_length))
                time.sleep(self.wait_time)
            except Exception as e:
                raise(e)
                #print(e)

        # if the server still hasn't started, raise an Exception
        raise Exception("Couldn't connect to processors-server. Is the port in use?")

    def make_address(self, hostname, port):
        # update hostname
        self.hostname = hostname
        # update port
        self.port = port
        # update address
        self.address = "http://{}:{}".format(self.hostname, self.port)

    def _get_path(self, p):
        """
        Expand a user-specified path.  Supports "~" shortcut.
        """
        return os.path.abspath(os.path.normpath(os.path.expanduser(p)))

    def __del__(self):
        """
        Stop server
        """
        try:
            self.stop_server()
            # close our file object
            #self.DEVNULL.close()
            print("Successfully shut down processors-server!")
        except Exception as e:
            #print(e)
            print("Couldn't kill processors-server.  Was server started externally?")
