#! -*- coding:utf8 -*-


import os
import sys
import json
import paramiko
from getpass import getpass
from datetime import datetime


class Log:
    def __init__(self):
        self.textformat = "[{time}][{type}] {text}"
        self.eventtype = "info"
        
    def event(self, text, eventtype=None):
        if (eventtype):
            self.eventtype = eventtype
        row = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": self.eventtype,
            "text": text
        }
        print(self.textformat.format(**row))


# basic json to dict to attributes reader
class Configreader:
    def __init__(self, configpath):
        self.configpath = configpath
        self.config = None
        self.load()
        
    def load(self):
        try:
            with open(self.configpath, 'r') as f:
                self.config = json.load(f)
            # convert dict to attributes
            for k,v in self.config.items():
                setattr(self, k, v)
        except FileNotFoundException:
            print("Unable to find", self.configpath)
            sys.exit(1)


# client extends Configreader
class Client(Configreader):
    def __init__(self, configpath):
        super().__init__(configpath)
        # paramiko variables
        self.transport = None
        self.sftp = None

    def connect(self):
        try:
            # get key
            print ("trying to convert ", self.keypath)
            key = paramiko.RSAKey.from_private_key_file(self.keypath)
            # make connection
            self.transport = paramiko.Transport((self.hostname, self.port))
            self.transport.connect(username=self.username, pkey=key)
            print("Connected to", self.hostname, "as", self.username)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            print("Started sftp session")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
            print('Sftp session closed')
        if self.transport:
            self.transport.close()
            print('Transport closed')        
    
    def listdir(self, path):
        if self.sftp:
            for f in self.sftp.listdir():
                print("Found:", f)
        else:
            print("Not connected!")
    
    def backup(self, files):
        pass

    def retrieve(self, backup):
        pass


def main():
    client = Client('config.json')
    client.connect()
    client.listdir('.')
    client.disconnect()


if __name__ == '__main__':
    main()

