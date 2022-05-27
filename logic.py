# -*- coding: utf-8 -*-
AWX_OAUTH2_TOKEN = "CjDw4KIEobnXcWMfz40Ozc3ogHJVnR"
AWX_HOST="https://172.16.50.1:80"
AWX_JOB_TEMPLATES_API = "{}/api/v2/job_templates".format(AWX_HOST)
REST_USERNAME = "admin"
REST_PASSWORD = "Netapp12"

import logging   # professional logging (file & console)
import requests  # rest api
import time      # time/date lib
import re        # regex
import json      # json parsing
import argparse  # argument parsing
import base64    # base64 encoding/decoding
import sys       # for console logger
from operator import itemgetter   # filter object-arrays
from requests.packages.urllib3.exceptions import InsecureRequestWarning # ignore certs

def makeCreds(username,password):
    return base64.b64encode("{}:::{}".format(username,password).encode('ascii')).decode('ascii')

def getCreds(creds):
    return base64.b64decode(creds.encode('ascii')).decode('ascii').split(':::')

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

headers = {"Content-Type": "application/json","Authorization": "Bearer {}".format(AWX_OAUTH2_TOKEN)}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("swatch.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger=logging.getLogger('awx')

# define a class to encapsulate Job template info
class JobTemplate():
    def __init__(self,id,name,launch_url):
        self.id=id
        self.name=name
        self.launch_url=launch_url

# get volumes in a cluster
def getVolumes(cluster,creds):
    url = "https://{}/api/storage/volumes?return_records=true&return_timeout=15".format(cluster)
    user,pw = getCreds(creds)
    volumes = []
    response = requests.get(url,auth=(user,pw),verify=False)
    for volume in response.json()['records']:
        volname = volume['name']
        volumes.append(volname)
    return volumes

# get aggregates in a cluster
def getAggregatesByCluster(cluster,creds):
    url = "https://{}/api/storage/aggregates?fields=space.block_storage.available&return_records=true&return_timeout=15".format(cluster)
    user,pw = getCreds(creds)
    aggregates = []
    response = requests.get(url,auth=(user,pw),verify=False)
    for aggregate in response.json()['records']:
        aggr = {}
        aggr["name"] = aggregate['name']
        aggr["space"] = aggregate['space']['block_storage']['available']
        aggregates.append(aggr)
    return aggregates

# get all aggegrates from AIQUM
# the python developers will need to tweak this so that the necessary filtering
# happens and the right aggregate is chosen based on functional data (location, service, tier, ...)
def getAggregates(company,application,suffix,volsize,retention,location,protocol,purpose,service,tier,creds):
    url = "https://{}/api/storage/aggregates?fields=space.block_storage.available&return_records=true&return_timeout=15".format(cluster)
    user,pw = getCreds(creds)
    aggregates = []
    response = requests.get(url,auth=(user,pw),verify=False)
    for aggregate in response.json()['records']:
        aggr = {}
        aggr["name"] = aggregate['name']
        aggr["space"] = aggregate['space']['block_storage']['available']
        aggregates.append(aggr)
    return aggregates

# get aggregate with most space
def getBestAggregate(aggregates):
    if(len(aggregates)>0):
        temp = sorted(aggregates,key=itemgetter('space'),reverse=True)
        return temp[0]["name"]
    else:
        raise Exception('No aggregates found')

# help functions to get auto incremental volume name
def getVolumeByRegex(volumes,regex):
    r = re.compile(regex)
    return list(filter(r.match,volumes))
def getTrailingNumber(s):
    m = re.search("(\d+)$", s)
    number=None
    match = str(m.group(1))
    if(m):
        number=int(match)
    return number
def getNextVolumeName(volumes,base,pad):
    number = 0
    vols = getVolumeByRegex(volumes, "{0}[0-9]{{{1}}}$".format(base,pad))
    for volume in vols:
        numbersuffix = getTrailingNumber(volume)
        if(numbersuffix>number):
            number=numbersuffix
    volname = "{}{}".format(base,str(number+1).rjust(pad,'0'))
    return volname

# the logic to convert function data into technical data
def getTemplateData(company,application,suffix,volsize,retention,location,protocol,purpose,service,tier,rest_creds):
    # write business logic here, based on the above input => select your cluster.
    # aggregate is picked first in WFA based on input.  We can acchieve this to
    # connect to AIQUM rest api and use the same search pattern
    # but it would be wiser to first find the right cluster and then the right
    # aggregate in that cluster.
    # you could read a config file and make the decision this way
    # selection of aggregate would be best by quickly querying cluster api
    location = 'bi' if purpose=='fsssmb1' else ('gr' if purpose=='fssdmz' else location)
    cluster = "r2d2.slash.local"
    svm = "svm_cifs"

    cluster_dr = "c3po.slash.local"
    svm_dr = "svm_cifs_dr"

    aggregate = getBestAggregate(getAggregatesByCluster(cluster,rest_creds))
    aggregate_dr = getBestAggregate(getAggregatesByCluster(cluster_dr,rest_creds))
    base = "{}_{}_{}{}".format(company,protocol,application,('_'+suffix) if (suffix!='') else '')
    volume = getNextVolumeName(getVolumes(cluster,rest_creds),base,3)

    data = {}
    data["extra_vars"] = {}
    data["extra_vars"]["source"] = {}
    data["extra_vars"]["source"]["cluster"] = cluster
    data["extra_vars"]["source"]["svm"] = svm
    data["extra_vars"]["source"]["volname"] = volume
    data["extra_vars"]["source"]["aggregate"] = aggregate
    data["extra_vars"]["source"]["volsize"] = volsize # in mb
    data["extra_vars"]["destination"] = {}
    data["extra_vars"]["destination"]["cluster"] = cluster_dr
    data["extra_vars"]["destination"]["svm"] = svm_dr
    data["extra_vars"]["destination"]["volname"] = volume
    data["extra_vars"]["destination"]["aggregate"] = aggregate_dr
    data["extra_vars"]["enable_mirror"]=True  # set this is you want snapmirror


    logger.info("Data = {}".format(data))
    return json.dumps(data, indent = 4)

# find awx template
def getJobTemplate(template):
    logger.info("Locating job template {}".format(template))
    response = requests.get(AWX_JOB_TEMPLATES_API,headers=headers,verify=False)
    for job in response.json()['results']:
        job_template = JobTemplate(job['id'], job['name'], AWX_HOST + job['related']['launch'])

        if(job_template.name == template):
            logger.info("Job template {} located.".format(job_template.name))
            return job_template

# lauch awx template
def launchJobTemplate(job_template,company,application,suffix,volsize,retention,location,protocol,purpose,service,tier,rest_creds):

    extravars = getTemplateData(company,application,suffix,volsize,retention,location,protocol,purpose,service,tier,rest_creds)
    logger.info("Launch URL = {}".format(job_template.launch_url))
    response = requests.post(job_template.launch_url, headers=headers, data=extravars,verify=False)

    # Checking the response status code, ensures the launch was ok
    if(response.status_code == 201):

        job_status_url = AWX_HOST + response.json()['url']

        logger.info("Job launched successfully.")
        logger.info("Job URL = {}".format(job_status_url))

        logger.info("Job id = {}".format(response.json()['id']))
        logger.info("Status = {}".format(
            response.json()['status']))
        logger.info("Waiting for job to complete (timeout = 15mins).")
        timeout = time.time() + 60*15

        while(True):
            time.sleep(2)

            job_response = requests.get(job_status_url, headers=headers,verify=False)
            if(job_response.json()['status'] == "new"):
                logger.info("Job status = new.")
            if(job_response.json()['status'] == "pending"):
                logger.info("Job status = pending.")
            if(job_response.json()['status'] == "waiting"):
                logger.info("Job status = waiting.")
            if(job_response.json()['status'] == "running"):
                logger.info("Job status = running.")
            if(job_response.json()['status'] == "successful"):
                logger.info("Job status = successful.")
                break
            if(job_response.json()['status'] == "failed"):
                logger.error("Job status = failed.")
                break
            if(job_response.json()['status'] == "error"):
                logger.error("Job status = error.")
                break
            if(job_response.json()['status'] == "canceled"):
                logger.info("Job status = canceled.")
                break
            if(job_response.json()['status'] == "never updated"):
                logger.info("Job status = never updated.")

            # timeout of 15m break loop
            if time.time() > timeout:
                logger.warning("Timeout after 15mins.")
                break

        logger.info("Fetching Job stdout")
        job_stdout_response = requests.get(
            AWX_HOST + response.json()['related']['stdout'] + "?format=json", headers=headers, verify=False)

        print(job_stdout_response.json()['content'])
    else:
        logger.error("Failed with status : {}".format(response))

# parse command line arguments
def init_argparse() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser()
    parser.add_argument("--template", help="AWX Template")
    parser.add_argument("--company", help="Company")
    parser.add_argument("--application", help="Application")
    parser.add_argument("--suffix", help="Suffix")
    parser.add_argument("--volsize", help="Volume Size")
    parser.add_argument("--retention", help="Retention")
    parser.add_argument("--location", help="Location")
    parser.add_argument("--protocol", help="Protocol")
    parser.add_argument("--purpose", help="Purpose")
    parser.add_argument("--service", help="Service")
    parser.add_argument("--tier", help="Tier")
    return parser

# main code
def main() -> None:

    parser = init_argparse()
    args = parser.parse_args()
    jt = getJobTemplate(args.template)

    # we pass credentials for the rest calls in a base64 format.  It's up to the python developer to get the credentials
    # from somewhere, either from service now, or a file, or a vault...
    # for this poc, I'm encoding and decoding them
    rest_creds = makeCreds(REST_USERNAME,REST_PASSWORD)

    launchJobTemplate(jt,args.company,args.application,args.suffix,args.volsize,args.retention,args.location,args.protocol,args.purpose,args.service,args.tier,rest_creds)



main()
