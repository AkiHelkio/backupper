#! -*- coding:utf8 -*-


import os
import sys
import json
import tarfile
import paramiko
from getpass import getpass
from datetime import datetime
from operator import itemgetter, attrgetter


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
    
    def test(self):
        files = self.listdir('backups')
        times = self.listmtimes(files)
        listing = sorted(self.asDatetime(times), key=lambda row: row['time'])
        for l in listing:
            print(str(l['time'])+"\t"+l['path'])
                
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
        
    def cleanWorkdir(self):
        for f in os.listdir(self.workdir):
            temp = os.path.join(self.workdir, f)
            print("removing", temp)
            os.remove(temp)
    
    def backup(self):
        # generate filename from config and timestamp
        self.backupfilename = (
            self.filetag + "_" +
            datetime.now().strftime(self.timeformat) +
            ".tar.gz")
        # loop configured folders
        try:
            tarpath = os.path.join(self.workdir, self.backupfilename)
            with tarfile.open(tarpath, "w:gz") as tar:
                for f in os.listdir(self.foldernames):
                    tar.add(os.path.join(self.homedir, f))
                print("Backup created")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
    
    def convertMtime(self, mtime, toString=False):
        d = datetime.fromtimestamp(
            self.sftp.lstat(remotepath).st_mtime
        )
        if toString:
            d = d.strftime('%Y-%m-%d %H:%M:%S')
        return d
                
    def checkBackups(self, clean=False):
        # get all backups, sort by st_mtime
        # remotepath = os.path.join(self.remotedir, self.backupfilename)
        if not self.sftp:
            self.disconnect()
            sys.exit(1)
        with self.sftp as s:
            try:
                ajat = sorted([
                    s.stat(path).st_mtime for path in [
                    os.path.join(self.remotedir, f) for f in s.listdir(self.remotedir)
                    ]
                ])
                datet = [convertMtime(a) for a in ajat]
                print("Oldest backup:",datet[-1])
                print("Newest backup:",datet[0])
                    
            except Exception as e:
                self.disconnect()
                sys.exit(e.args)
        return date
        
    def sendtoserver(self):
        localpath = os.path.join(self.workdir, self.backupfilename)
        remotepath = os.path.join(self.remotedir, self.backupfilename)
        if self.sftp:
            try:
                self.sftp.put(localpath, remotepath)
                print("Backup sent") 
            except Exception as e:
                self.disconnect()
                sys.exit(e.args)
                    
    def retrieve(self, backup):
        pass


def main():
    b = Backupper('config.json')
    # b.cleanWorkdir()
    # b.backup()
    b.connect()
    b.test()
    b.disconnect()
    """
    client.checkBackups()
    client.backupfolders()
    client.sendtoserver()
    client.disconnect()
    """
    

if __name__ == '__main__':
    main()

