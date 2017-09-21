# backupper
A collection of tools to backup linux home directories to a remote centralized location with python and cron

### initial setup
First create a certificate for automated ssh connection on the client 
computer:
```bash
ssh-keygen -t rsa
```

Then add the public certificate to the backup remote host:

Example: public key is named 'example.pub'
```bash
cat /home/testuser/.ssh/example.pub | ssh testuser@backuphost "cat >>  
~/.ssh/authorized_keys"
```

### config
The client.py relies on a json file for configuration parameters. It 
also defines which local folders within the users homefolder will be 
backupped to the tar.gz-file.

configexample.json is provided and contains the current parameters for 
automated backup.
