#! -*- coding:utf8 -*-


import os
import sys
import json
import tarfile
import paramiko
from getpass import getpass
from datetime import datetime, timedelta


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
                # convert all but foldernames to primary names:
                if type(v) is dict:
                    for subkey,subvalue in v.items():
                        # print("Setting sub:", subkey)
                        setattr(self, subkey, subvalue)
                else:
                    # print("Setting",k)
                    setattr(self, k, v)
                    
        except FileNotFoundException:
            print("Unable to find", self.configpath)
            sys.exit(1)


# client extends Configreader and handles connections
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


# backupper as its own class
class Backupper(Client):
    def __init__(self, configpath):
        super().__init__(configpath)
    
    def removeOldFiles(self):
        cycletime = datetime.now() - timedelta(days=self.daystokeep)
        print("Removing files older than",str(cycletime))
        if self.sftp:
            try:
                for f in self.getRemoteFiles():
                    if f['time'] < cycletime:
                        #self.sftp.remove(f['path'])
                        print("Removed",f['path'])
            except Exception as e:
                self.disconnect()
                sys.exit(e.args)
                
    # - - - generator collection - - -
    def getRemoteFiles(self, directory=None, show=False):
        if not directory:
            directory = self.remotedir
        files = self.listdir(directory)
        times = self.listmtimes(files)
        filelist = self.asDatetime(times)
        for f in sorted(filelist, key=lambda row: row['time']):
            if show:
                print(f['time'],"\t",f['path'])
            else:
                yield f
            
    def listdir(self, path='.'):
        print("Listing remotedir",path)
        if self.sftp:
            for f in self.sftp.listdir(path):
                yield os.path.join(path, f)
        else:
            print("Not connected!")
            
    def listmtimes(self, files):
        if self.sftp:
            for f in files:
                yield { "path": f, "time": self.sftp.stat(f).st_mtime }
    
    def asDatetime(self, mtimes, toString=False):
        for m in mtimes:
            d = datetime.fromtimestamp(m['time'])
            if toString:
                yield { "path": m['path'], "time": d.strftime('%Y-%m-%d %H:%M:%S') }
            else:
                yield { "path": m['path'], "time": d }
    # - - - generator collection end - - -
    
    def cleanWorkdir(self):
        for f in os.listdir(self.workdir):
            temp = os.path.join(self.workdir, f)
            print("removing", temp)
            os.remove(temp)
    
    def createBackup(self):
        # generate filename from config and timestamp
        self.backupfilename = (
            self.filetag + "_" +
            datetime.now().strftime(self.timeformat) +
            ".tar.gz")
        print("Creating backup",self.backupfilename)
        # loop configured folders
        try:
            tarpath = os.path.join(self.workdir, self.backupfilename)
            with tarfile.open(tarpath, "w:gz") as tar:
                for f in self.foldernames:
                    targetpath = os.path.join(self.homedir, f)
                    print("Adding",targetpath)
                    tar.add(targetpath)
                print("Backup created")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
            
    def canUpload(self):
        print("Checking that the server has enough space")
        # testing: functionality not implemented
        return True
        
    def sendtoServer(self):
        localpath = os.path.join(self.workdir, self.backupfilename)
        remotepath = os.path.join(self.remotedir, self.backupfilename)
        if self.sftp:
            try:
                print("Sending",localpath,"...")
                self.sftp.put(localpath, remotepath)
                print("Backup sent to",remotepath) 
            except Exception as e:
                self.disconnect()
                sys.exit(e.args)
                    
    def retrieve(self, backup):
        pass


def main():
    b = Backupper('config.json')
    b.connect()
    b.cleanWorkdir()
    b.getRemoteFiles(show=True)
    b.removeOldFiles()
    b.createBackup()
    if b.canUpload():
        b.sendtoServer()
    b.disconnect()
    

if __name__ == '__main__':
    main()

