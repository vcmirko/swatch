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

Note : A function to get aggregates from AIQUM is included, but not used

## AWX -> Ansible
In AWX you must do :

* Create ontap credential type and credentials
* Get AWX Token (using api)
* Create sourcecontrol credentials (for git)
* Create project (source = git) to this repo
* Create template (source = project)
  * use dummy inventory (we target localhost)
  * prompt for extravars
