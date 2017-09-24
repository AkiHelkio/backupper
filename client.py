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
        self.ssh = None
        self.sftp = None
    
    def createSSHclient(self):
        # get key
        key = paramiko.RSAKey.from_private_key_file(self.keypath)
        # create client:
        self.ssh = paramiko.SSHClient()
        # for now, force accept
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # make connection
        self.ssh.connect(
            hostname=self.hostname,
            port=self.port,
            pkey=key
        )
        print("Connected to", self.hostname, "as", self.username)
        
    def connect(self):
        try:
            self.createSSHclient()
            print("SSH session opened")
            self.sftp = self.ssh.open_sftp()
            print("SFTP session opened")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
            
    def runRemote(self, cmd):
        try:
            stdin, stdout, sterr = self.ssh.exec_command(cmd)
            for data in stdout.readlines():
                print(data, end="")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
            
    def getAvailableSpace(self, mountpoint):
        try:
            space = None
            stdin, stdout, stderr = self.ssh.exec_command('df')
            for data in stdout.readlines():
                row = [a for a in data.strip().split(" ") if a != '']
                if row[-1] == mountpoint:
                    space = int(row[3])
            if not space:
                print("Unable to find space for mountpoint '",mountpoint,"'")
            return space
        except SSHException as e:
            self.disconnect()
            sys.exit(e.args)
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
        
    def disconnect(self):
        if self.ssh:
            self.ssh.close()
            print('SSH session closed')
        if self.sftp:
            self.sftp.close()
            print('SFTP session closed')
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
                        self.sftp.remove(f['path'])
                        print("Removed",f['path'])
            except SSHException as e:
                self.disconnect()
                sys.exit(e.args)
            except Exception as e:
                self.disconnect()
                sys.exit(e.args)
                
    # - - - generator collection - - -
    # creates an array of dictionaries with time and path:
    # format: [
    # {"time": "2017-01-01 10:00:00", "path": "/location"}
    # ]
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
        print("Cleaning",self.workdir)
        for f in os.listdir(self.workdir):
            temp = os.path.join(self.workdir, f)
            print("Removing", temp)
            os.remove(temp)
    
    def createBackup(self):
        # generate filename from config and timestamp
        self.backupfilename = (
            self.filetag + "_" +
            datetime.now().strftime(self.timeformat) +
            ".tar.gz")
        print("Creating backup",self.backupfilename)
        try:
            tarpath = os.path.join(self.workdir, self.backupfilename)
            with tarfile.open(tarpath, "w:gz") as tar:
                # loop configured folders and add to tarfile:
                for f in self.foldernames:
                    targetpath = os.path.join(self.homedir, f)
                    print("Adding",targetpath)
                    tar.add(targetpath)
                print("Backup created")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
            
    def canUpload(self):
        upload = True
        print("Checking that the server has enough space")
        space = self.getAvailableSpace('/')
        if not space:
            upload = False
        else:
            print("Server has",int(space/1024),"MB available")
            print("Backup size is ", end="")
            fsize = int(os.stat(os.path.join(self.workdir, self.backupfilename)).st_size/1024)
            print(str(int(fsize/1024))+" MB")
            # ensure we have atleast one gigabyte at server :D 
            if space - fsize > (1024*1024):
                upload = True
            else:
                upload = False
        return upload
        
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

