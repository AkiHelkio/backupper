#! -*- coding:utf8 -*-


import os
import sys
import json
import logging
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
                        # logging.info("Setting sub: "+str(subkey))
                        setattr(self, subkey, subvalue)
                else:
                    # logging.info("Setting "+str(k))
                    setattr(self, k, v)
                    
        except FileNotFoundException:
            logging.info("Unable to find "+str(self.configpath))
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
        logging.info("Connected to "+self.hostname+" as "+self.username)
        
    def connect(self):
        try:
            self.createSSHclient()
            logging.info("SSH session opened")
            self.sftp = self.ssh.open_sftp()
            logging.info("SFTP session opened")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
            
    def runRemote(self, cmd):
        try:
            stdin, stdout, sterr = self.ssh.exec_command(cmd)
            for data in stdout.readlines():
                logging.info(data.replace("\n"))
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
                logging.info("Unable to find space for mountpoint '"+str(mountpoint)+"'")
            return space
        except SSHException as e:
            self.disconnect()
            sys.exit(e.args)
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
        
    def disconnect(self):
        if self.sftp:
            self.sftp.close()
            logging.info('SFTP session closed')
        if self.ssh:
            self.ssh.close()
            logging.info('SSH session closed')
        if self.transport:
            self.transport.close()
            logging.info('Transport closed')


# backupper as its own class
class Backupper(Client):
    def __init__(self, configpath):
        super().__init__(configpath)
    
    def removeOldFiles(self):
        cycletime = datetime.now() - timedelta(days=self.daystokeep)
        logging.info("Removing files older than "+str(cycletime))
        if self.sftp:
            try:
                for f in self.getRemoteFiles():
                    if f['time'] < cycletime:
                        self.sftp.remove(f['path'])
                        logging.info("Removed "+f['path'])
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
                logging.info(str(f['time'])+"\t"+f['path'])
            else:
                yield f
            
    def listdir(self, path='.'):
        logging.info("Listing remotedir "+path)
        if self.sftp:
            for f in self.sftp.listdir(path):
                yield os.path.join(path, f)
        else:
            logging.info("Not connected!")
            
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
        logging.info("Cleaning "+self.workdir)
        for f in os.listdir(self.workdir):
            temp = os.path.join(self.workdir, f)
            logging.info("Removing "+temp)
            os.remove(temp)
    
    def createBackup(self):
        # generate filename from config and timestamp
        self.backupfilename = (
            self.filetag + "_" +
            datetime.now().strftime(self.timeformat) +
            ".tar.gz")
        logging.info("Creating backup "+self.backupfilename)
        try:
            tarpath = os.path.join(self.workdir, self.backupfilename)
            with tarfile.open(tarpath, "w:gz") as tar:
                # loop configured folders and add to tarfile:
                for f in self.foldernames:
                    targetpath = os.path.join(self.homedir, f)
                    logging.info("Adding "+targetpath)
                    tar.add(targetpath)
                logging.info("Backup created")
        except Exception as e:
            self.disconnect()
            sys.exit(e.args)
            
    def canUpload(self):
        upload = True
        logging.info("Checking that the server has enough space")
        space = self.getAvailableSpace('/')
        if not space:
            upload = False
        else:
            logging.info("Server has "+str(int(space/1024))+" MB available")
            fsize = int(os.stat(os.path.join(self.workdir, self.backupfilename)).st_size/1024)
            logging.info("Backup size is "+str(int(fsize/1024))+" MB")
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
                logging.info("Sending " + localpath + "...")
                self.sftp.put(localpath, remotepath)
                logging.info("Backup sent to " + remotepath) 
            except Exception as e:
                self.disconnect()
                sys.exit(e.args)
                
    def retrieve(self, backup):
        pass


def main():
    logging.basicConfig(
        format='[%(asctime)s] %(message)s',
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
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

