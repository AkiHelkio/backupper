# backupper
A tool for taking full backups of specific folders within a linux homedirectory with
the ability to send backups to centralized remote location.

## Todo
* [x] Create test keys and environment
* [x] Implement client sftp connection
* [x] create tar.gz backup functionality
* [x] Old backup cleanup by config
* [x] workdir cleanup
* [x] Sanity checking before sftp put
* [x] Improve logging
* [ ] Add automatic testing of config.json
* [ ] Create backup statistics history database
* [ ] Implement statistics append to database
* [ ] Create cron scheduling for backupper
* [ ] Implement cron process (create, start, stop, remove)
* [ ] Add install feature to build config.json from template
* [ ] Add GUI for config.json and scheduling cron
* [ ] Implement backup retrieval
* [ ] Implement backup restore process


## Setup

#### key creation
First create a certificate for automated ssh connection on the client 
computer:
```bash
ssh-keygen -t rsa
```

Then add the public certificate to the backup remote host:

Example: public key is named 'example.pub'
```bash
cat /home/testuser/.ssh/example.pub | ssh testuser@backuphost "cat >> ~/.ssh/authorized_keys"
```

#### Additional steps
First fill the fields that are provided with the configtemplate.json.

Then run the backup with:
```bash
python3 client.py config.json
```

