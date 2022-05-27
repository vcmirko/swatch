# how it works

## ServiceNow -> Python
ServiceNow will trigger the logic.py script.  
It will also need to cover rest-api credentials.  
In my python code, as a demo, I have bas64 encoded them.

```
logic.py --template --protocol --application --suffix --volsize
```

## Python -> AWX
Python script does following steps :

* Parse arguments
* Convert functional data into technical data
  * Get aggregate/cluster/svm (search and filter)
  * Get volume name (search and auto increment)
  * Assemble extravars
* Get AWX template
* Launch template
* Print output

**Note** : A function to get aggregates from AIQUM is included, but not used

## AWX -> Ansible
In AWX you must :

* Create ontap credential type and credentials (will be passed to playbook)
* Get AWX Token (using api) (to use in python script)
* Create sourcecontrol credentials (for git repo)
* Create project (source = git) to this repo, using sourcecontrol creds
* Create template (source = project), choose its_cifs.yml
  * use dummy inventory (we target localhost and inventory is mandatory)
  * prompt for extravars
  * add ontap credentials (used in playbook)

## Ansible
`its_cifs.yml` will call `create_source_volume.yml` and optionally (enable_mirror flag in python) `create_destination_volume.yml`
